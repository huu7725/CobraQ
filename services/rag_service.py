"""
RAG Service - Retrieval-Augmented Generation.
Tìm câu hỏi tương tự trong vector DB, trả về context để LLM tham khảo.
"""

from typing import List, Dict, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from services.embedding_service import EmbeddingService
from services.vector_store import VectorStore

import logging

logger = logging.getLogger(__name__)

class RAGService:
    """
    Retrieval-Augmented Generation service.
    - Retrieval: Tìm câu hỏi tương tự trong vector DB
    - Augmentation: Tạo context từ các câu tìm được để đưa vào LLM prompt
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        similarity_threshold: float = 0.85,
        max_context_questions: int = 3
    ):
        """
        Khởi tạo RAGService.

        Args:
            vector_store: Instance VectorStore
            embedding_service: Instance EmbeddingService
            similarity_threshold: Ngưỡng similarity tối thiểu (0-1) để chấp nhận kết quả
            max_context_questions: Số lượng câu tương tự tối đa đưa vào context
        """
        self.vector_store = vector_store
        self.embedder = embedding_service
        self.threshold = similarity_threshold
        self.max_context = max_context_questions

    def retrieve_similar(
        self,
        question: str,
        choices: List[Dict],
        top_k: int = 5,
        subject: Optional[str] = None,
        file_id: Optional[str] = None,
        min_similarity: Optional[float] = None
    ) -> List[Dict]:
        """
        Tìm câu hỏi tương tự trong vector DB.

        Args:
            question: Câu hỏi cần tìm
            choices: List phương án
            top_k: Số kết quả tối đa trả về
            subject: Lọc theo môn học (nếu có)
            file_id: Lọc theo file (nếu có)
            min_similarity: Ghi đè threshold nếu có

        Returns:
            List các dict: {
                "question": str,
                "answer": str,
                "explanation": str,
                "similarity": float,
                "source_file": str,
                "subject": str
            }
        """
        # Step 1: Embed query
        combined_query = self.embedder.embed_question_with_choices(question, choices)
        query_embedding = self.embedder.embed_text(combined_query).tolist()

        # Step 2: Build where filter
        where = {}
        if subject:
            where["subject"] = subject
        if file_id:
            where["file_id"] = file_id

        # Step 3: Search in vector DB
        results = self.vector_store.search_similar(
            query_embedding=query_embedding,
            top_k=top_k,
            where=where if where else None,
            include=["documents", "distances", "metadatas"]
        )

        # Step 4: Parse và filter theo similarity
        threshold = min_similarity if min_similarity is not None else self.threshold
        similar_questions = []

        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        for i in range(len(ids)):
            # Cosine distance → similarity
            distance = distances[i] if i < len(distances) else 1.0
            similarity = 1.0 - distance

            if similarity >= threshold:
                meta = metadatas[i] if i < len(metadatas) else {}
                similar_questions.append({
                    "id": ids[i],
                    "question": documents[i] if i < len(documents) else "",
                    "answer": meta.get("answer", ""),
                    "explanation": meta.get("explanation", ""),
                    "similarity": round(similarity, 4),
                    "source_file": meta.get("file_id", ""),
                    "subject": meta.get("subject", ""),
                    "source": "vector_db"
                })

        # Sort theo similarity giảm dần
        similar_questions.sort(key=lambda x: x["similarity"], reverse=True)

        logger.debug(f"Tìm được {len(similar_questions)} câu tương tự (threshold={threshold})")
        return similar_questions[:self.max_context]

    def retrieve_with_answers(
        self,
        question: str,
        choices: List[Dict],
        top_k: int = 5,
        subject: Optional[str] = None
    ) -> Tuple[List[Dict], bool]:
        """
        Tìm câu hỏi có đáp án rõ ràng và đủ cao.

        Args:
            question, choices, top_k, subject: Như retrieve_similar

        Returns:
            Tuple[List[Dict], bool]:
                - List câu tương tự (có answer)
                - Có câu nào đạt similarity >= threshold không
        """
        similar = self.retrieve_similar(
            question=question,
            choices=choices,
            top_k=top_k,
            subject=subject
        )

        # Lọc chỉ những câu có đáp án
        with_answers = [s for s in similar if s.get("answer")]

        has_high_confidence = any(
            s["similarity"] >= self.threshold for s in with_answers
        )

        return with_answers[:self.max_context], has_high_confidence

    def build_context_string(
        self,
        similar_questions: List[Dict],
        max_total_chars: int = 2000
    ) -> str:
        """
        Tạo context string từ các câu hỏi tương tự để đưa vào LLM prompt.

        Args:
            similar_questions: List kết quả từ retrieve_similar
            max_total_chars: Giới hạn độ dài context (tránh quá token)

        Returns:
            str: Context đã format
        """
        if not similar_questions:
            return ""

        context_parts = ["**Các câu hỏi tương tự có đáp án đã biết:**\n"]

        total_chars = 0
        for i, sq in enumerate(similar_questions, 1):
            part = (
                f"{i}. Câu: {sq['question']}\n"
                f"   Đáp án: {sq['answer']}\n"
            )
            if sq.get("explanation"):
                exp = sq["explanation"][:200]  # Giới hạn explanation
                part += f"   Giải thích: {exp}...\n"
            part += "\n"

            # Check limit
            if total_chars + len(part) > max_total_chars:
                context_parts.append(f"(và {len(similar_questions) - i + 1} câu khác...)")
                break

            context_parts.append(part)
            total_chars += len(part)

        return "".join(context_parts).strip()

    def find_exact_match(
        self,
        question: str,
        choices: List[Dict],
        similarity_cutoff: float = 0.95
    ) -> Optional[Dict]:
        """
        Tìm câu hỏi giống hệt (hoặc gần giống) trong DB.

        Args:
            question: Câu hỏi
            choices: Phương án
            similarity_cutoff: Ngưỡng rất cao (0.95) để coi là "exact match"

        Returns:
            Dict nếu tìm thấy match, else None
        """
        similar = self.retrieve_similar(
            question=question,
            choices=choices,
            top_k=1,
            min_similarity=similarity_cutoff
        )

        if similar and similar[0]["similarity"] >= similarity_cutoff:
            return similar[0]
        return None

    def index_questions_batch(
        self,
        questions: List[Dict],
        file_id: str,
        subject: str = "",
        batch_size: int = 100
    ) -> int:
        """
        Index hàng loạt câu hỏi vào vector DB (gọi khi upload file mới).

        Args:
            questions: List câu hỏi (đã parse từ file)
            file_id: File ID
            subject: Môn học
            batch_size: Batch size cho add

        Returns:
            int: Số câu đã index thành công
        """
        # Prepare data
        texts = []
        questions_with_meta = []

        for q in questions:
            combined = self.embedder.embed_question_with_choices(
                q.get("question", ""),
                q.get("choices", [])
            )
            texts.append(combined)

            q_meta = {
                "id": q.get("id", ""),
                "question": q.get("question", ""),
                "answer": q.get("answer", ""),
                "explanation": q.get("explanation", ""),
                "file_id": file_id,
                "subject": subject
            }
            questions_with_meta.append(q_meta)

        # Generate embeddings batch
        logger.info(f"Đang tạo embeddings cho {len(texts)} câu hỏi...")
        embeddings = self.embedder.embed_batch(texts, batch_size=32)

        # Add to vector DB
        added = self.vector_store.add_batch(
            questions=questions_with_meta,
            embeddings=embeddings.tolist(),
            batch_size=batch_size
        )

        logger.info(f"Đã index {added} câu hỏi vào vector DB")
        return added
