"""
Embedding Service - Tạo vector embeddings cho câu hỏi trắc nghiệm.
Sử dụng SentenceTransformer multilingual model hỗ trợ tiếng Việt.
"""

import os, threading, logging
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Global singleton + pre-warm state
_embedding_service_instance = None
_embedding_init_lock = threading.Lock()
_embedding_init_done = threading.Event()


def _best_device() -> str:
    """Chọn device tối ưu: CUDA > MPS > CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


class EmbeddingService:
    """
    Dịch vụ tạo embeddings cho văn bản sử dụng SentenceTransformer.
    Hỗ trợ nhiều ngôn ngữ, bao gồm tiếng Việt.
    """

    DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None,
        cache_folder: Optional[str] = None
    ):
        """
        Khởi tạo EmbeddingService.

        Args:
            model_name: Tên model SentenceTransformer
            device: 'cpu'/'cuda'/'mps' (auto-detect nếu None)
            cache_folder: Thư mục cache model
        """
        resolved_device = device or _best_device()
        if resolved_device not in ("cpu", "cuda", "mps"):
            resolved_device = "cpu"

        logger.info(f"Đang tải embedding model: {model_name} (device={resolved_device})")
        try:
            # Cache folder mặc định: dùng cache có sẵn để tránh download lại
            resolved_cache = cache_folder or os.path.expanduser("~/.cache/torch/sentence_transformers")
            self.model = SentenceTransformer(
                model_name,
                device=resolved_device,
                cache_folder=resolved_cache
            )
            logger.info(f"Embedding model loaded successfully. Dimension: {self.model.get_sentence_embedding_dimension()}, device: {resolved_device}")
        except Exception as e:
            logger.error(f"Lỗi tải embedding model: {e}")
            raise

    def embed_text(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        Tạo embedding cho 1 đoạn văn bản.

        Args:
            text: Văn bản cần embedding
            normalize: L2 normalize vector (mặc định True)

        Returns:
            np.ndarray: Vector embedding (shape: [dimension])
        """
        if not text or not text.strip():
            # Trả về vector zeros nếu text rỗng
            return np.zeros(self.model.get_sentence_embedding_dimension())

        try:
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=normalize,
                show_progress_bar=False
            )
            return embedding
        except Exception as e:
            logger.error(f"Lỗi khi tạo embedding: {e}")
            return np.zeros(self.model.get_sentence_embedding_dimension())

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Tạo embeddings cho nhiều văn bản (batch).

        Args:
            texts: List các văn bản
            batch_size: Số lượng mẫu mỗi batch
            normalize: L2 normalize
            show_progress: Hiển thị progress bar

        Returns:
            np.ndarray: Matrix embeddings (shape: [n_samples, dimension])
        """
        if not texts:
            return np.array([])

        # Filter out empty texts
        valid_texts = [t if t and t.strip() else " " for t in texts]

        try:
            embeddings = self.model.encode(
                valid_texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=normalize,
                show_progress_bar=show_progress
            )
            return embeddings
        except Exception as e:
            logger.error(f"Lỗi khi tạo batch embeddings: {e}")
            return np.zeros((len(texts), self.model.get_sentence_embedding_dimension()))

    def embed_question_with_choices(
        self,
        question: str,
        choices: List[dict],
        include_labels: bool = True,
        separator: str = " | "
    ) -> str:
        """
        Kết hợp question + choices thành 1 text để embedding.

        Args:
            question: Nội dung câu hỏi
            choices: List dict [{"label": "A", "text": "..."}, ...]
            include_labels: Có thêm label (A., B., ...) vào text không
            separator: Dấu phân cách giữa các phần

        Returns:
            str: Văn bản kết hợp đã được normalize
        """
        if not question:
            return ""

        # Normalize question
        q_text = question.strip()

        # Build choices text
        choices_texts = []
        for c in choices:
            label = (c.get("label") or "").strip().upper()
            text = (c.get("text") or "").strip()
            if text:
                if include_labels and label:
                    choices_texts.append(f"{label}. {text}")
                else:
                    choices_texts.append(text)

        # Combine
        combined = q_text
        if choices_texts:
            combined += separator + separator.join(choices_texts)

        # Clean extra spaces
        combined = " ".join(combined.split())

        return combined

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Tính cosine similarity giữa 2 embeddings.

        Args:
            embedding1: Vector 1
            embedding2: Vector 2

        Returns:
            float: Cosine similarity (0-1)
        """
        if embedding1.ndim == 1:
            embedding1 = embedding1.reshape(1, -1)
        if embedding2.ndim == 1:
            embedding2 = embedding2.reshape(1, -1)

        # Dot product (vì đã normalize nên dot = cosine)
        similarity = np.dot(embedding1, embedding2.T)[0][0]
        return float(similarity)

    def compute_similarities_batch(
        self,
        query_embedding: np.ndarray,
        corpus_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Tính similarity giữa 1 query và nhiều corpus embeddings.

        Args:
            query_embedding: Vector query (1D hoặc 2D)
            corpus_embeddings: Ma trận corpus (N x dim)

        Returns:
            np.ndarray: Array similarities (N,)
        """
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        if corpus_embeddings.ndim == 1:
            corpus_embeddings = corpus_embeddings.reshape(1, -1)

        # Cosine similarity
        similarities = np.dot(corpus_embeddings, query_embedding.T).flatten()
        return similarities

    def get_dimension(self) -> int:
        """Trả về dimension của embedding."""
        return self.model.get_sentence_embedding_dimension()

    def save_to_file(self, embeddings: np.ndarray, filepath: str):
        """Lưu embeddings vào file numpy."""
        np.save(filepath, embeddings)

    def load_from_file(self, filepath: str) -> np.ndarray:
        """Load embeddings từ file numpy."""
        return np.load(filepath)
