"""
Pipeline Service - Orchestrator cho RAG + MRC.
Kết hợp retrieval (RAG) và LLM answering (MRC) thành 1 pipeline hoàn chỉnh.
"""

from typing import List, Dict, Optional, Tuple
import logging

from services.embedding_service import EmbeddingService
from services.vector_store import VectorStore
from services.rag_service import RAGService
from services.mrc_service import MRCService

logger = logging.getLogger(__name__)

class AIPipeline:
    """
    Orchestrator pipeline:
    1. RAG: Tìm câu tương tự trong vector DB
    2. Nếu tìm thấy với confidence cao → trả về từ DB
    3. Nếu không → Gọi LLM (MRC) với context từ RAG
    4. Cache kết quả vào vector DB
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        rag_service: RAGService,
        mrc_service: MRCService,
        cache_llm_results: bool = True,
        default_threshold: float = 0.90
    ):
        """
        Khởi tạo AI Pipeline.

        Args:
            embedding_service: Service tạo embeddings
            vector_store: Vector database
            rag_service: Retrieval service
            mrc_service: LLM answering service
            cache_llm_results: Có lưu kết quả LLM vào DB không
            default_threshold: Ngưỡng mặc định để dùng cached/rag result
        """
        self.embedder = embedding_service
        self.vector_store = vector_store
        self.rag = rag_service
        self.mrc = mrc_service
        self.cache_enabled = cache_llm_results
        self.default_threshold = default_threshold

    def process_question(
        self,
        question_data: Dict,
        subject: str = "",
        use_rag: bool = True,
        force_llm: bool = False,
        threshold: Optional[float] = None
    ) -> Dict:
        """
        Xử lý 1 câu hỏi: RAG → LLM (nếu cần) → Cache.

        Args:
            question_data: Dict với keys: question, choices, id, file_id, ...
            subject: Môn học (toán, lý, hóa, ...)
            use_rag: Bật/tắt RAG retrieval
            force_llm: Bắt dùng LLM bất kỳ trường hợp nào
            threshold: Ngưỡng similarity tùy chỉnh

        Returns:
            Dict: {
                "question_id": ...,
                "question": "...",
                "answer": "A",
                "confidence": 0.95,
                "explanation": "...",
                "source": "vector_db" | "llm" | "existing",
                "similar_questions": [...],
                "processing_time_ms": 1234,
                "cached": bool
            }
        """
        import time
        start_time = time.time()

        question = str(question_data.get("question", "")).strip()
        choices = question_data.get("choices", [])
        qid = question_data.get("id", "")
        file_id = question_data.get("file_id", "")

        result = {
            "question_id": qid,
            "question": question,
            "answer": "",
            "confidence": 0.0,
            "explanation": "",
            "source": "",
            "similar_questions": [],
            "processing_time_ms": 0,
            "cached": False
        }

        # Validate input
        if not question or len(choices) < 2:
            result["source"] = "error"
            result["explanation"] = "Câu hỏi hoặc phương án không hợp lệ"
            result["processing_time_ms"] = int((time.time() - start_time) * 1000)
            return result

        # Step 1: Check nếu câu đã có đáp án trong DB (từ user nhập)
        if question_data.get("answer") and not force_llm:
            result.update({
                "answer": question_data["answer"].upper(),
                "confidence": 1.0,
                "explanation": "Đáp án đã có sẵn",
                "source": "existing"
            })
            result["processing_time_ms"] = int((time.time() - start_time) * 1000)
            return result

        # Step 2: RAG retrieval (nếu bật)
        similar_questions = []
        if use_rag and not force_llm:
            similar_questions = self.rag.retrieve_similar(
                question=question,
                choices=choices,
                top_k=5,
                subject=subject
            )
            result["similar_questions"] = similar_questions

            # Step 3: Check nếu có match tốt từ DB
            thresh = threshold if threshold is not None else self.default_threshold
            best_match = None
            for sq in similar_questions:
                if sq["similarity"] >= thresh and sq.get("answer"):
                    best_match = sq
                    break

            if best_match:
                # Dùng kết quả từ vector DB (confidence = similarity)
                result.update({
                    "answer": best_match["answer"].upper(),
                    "confidence": best_match["similarity"],
                    "explanation": best_match.get("explanation", "Lấy từ câu hỏi tương tự"),
                    "source": "vector_db"
                })
                result["processing_time_ms"] = int((time.time() - start_time) * 1000)
                result["cached"] = True
                logger.info(f"Question ID {qid}: Hit vector DB (sim={best_match['similarity']:.3f})")
                return result

        # Step 4: Gọi LLM (MRC)
        logger.info(f"Question ID {qid}: Calling LLM...")
        context = self.rag.build_context_string(similar_questions)

        llm_result = self.mrc.predict(
            question=question,
            choices=choices,
            subject=subject,
            context=context
        )

        result.update(llm_result)
        result["similar_questions"] = similar_questions

        # Step 5: Cache result vào vector DB (nếu enable)
        if self.cache_enabled and not result.get("error") and result.get("answer"):
            self._cache_question_result(question_data, result)

        result["processing_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    def process_batch(
        self,
        questions: List[Dict],
        subject: str = "",
        use_rag: bool = True,
        force_llm: bool = False,
        progress_callback=None
    ) -> Dict[str, any]:
        """
        Xử lý hàng loạt câu hỏi.

        Args:
            questions: List question_data
            subject, use_rag, force_llm: Như process_question
            progress_callback: Callback function(current, total) để update UI

        Returns:
            Dict: {
                "total": int,
                "results": List[Dict],
                "summary": {
                    "from_vector_db": int,
                    "from_llm": int,
                    "errors": int,
                    "avg_confidence": float,
                    "avg_processing_time_ms": float
                }
            }
        """
        results = []
        stats = {
            "from_vector_db": 0,
            "from_llm": 0,
            "existing": 0,
            "errors": 0,
            "total_confidence": 0.0,
            "total_time": 0.0
        }

        total = len(questions)
        for i, q in enumerate(questions, 1):
            # Progress callback
            if progress_callback:
                progress_callback(i, total)

            result = self.process_question(
                question_data=q,
                subject=subject,
                use_rag=use_rag,
                force_llm=force_llm
            )

            results.append(result)

            # Update stats
            source = result.get("source", "")
            if source == "vector_db":
                stats["from_vector_db"] += 1
            elif source == "llm":
                stats["from_llm"] += 1
            elif source == "existing":
                stats["existing"] += 1
            else:
                stats["errors"] += 1

            stats["total_confidence"] += result.get("confidence", 0)
            stats["total_time"] += result.get("processing_time_ms", 0)

        # Calculate averages
        if results:
            stats["avg_confidence"] = round(stats["total_confidence"] / len(results), 4)
            stats["avg_processing_time_ms"] = round(stats["total_time"] / len(results), 2)

        return {
            "total": total,
            "results": results,
            "summary": stats
        }

    def _cache_question_result(
        self,
        question_data: Dict,
        result: Dict,
        batch_size: int = 50
    ):
        """
        Lưu kết quả vào vector DB để cache.

        Args:
            question_data: Dữ liệu câu hỏi gốc
            result: Kết quả từ MRC/RAG
            batch_size: Batch size khi insert (hiện tại dùng single add)
        """
        try:
            # Embed question + choices
            combined = self.embedder.embed_question_with_choices(
                question_data.get("question", ""),
                question_data.get("choices", [])
            )
            embedding = self.embedder.embed_text(combined).tolist()

            # Prepare metadata
            qid = str(question_data.get("id", ""))
            file_id = question_data.get("file_id", "")
            subject = question_data.get("subject", "")

            # Add to vector store
            success = self.vector_store.add_question(
                question_id=f"cache_{qid}_{self._get_hash(combined[:50])}",
                embedding=embedding,
                question_text=question_data.get("question", ""),
                answer=result.get("answer", ""),
                explanation=result.get("explanation", ""),
                file_id=file_id,
                subject=subject,
                metadata={
                    "cached": True,
                    "source": result.get("source", "llm"),
                    "confidence": result.get("confidence", 0.0),
                    "model": result.get("model", "unknown")
                }
            )

            if success:
                logger.debug(f"Cached question ID {qid} into vector DB")
        except Exception as e:
            logger.error(f"Lỗi khi cache question result: {e}")

    def _get_hash(self, text: str) -> str:
        """Tạo hash ngắn từ text (cho question_id cache)."""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()[:8]

    def clear_cache_by_file(self, file_id: str) -> int:
        """Xóa cache của 1 file (khi file bị xóa)."""
        return self.vector_store.delete_by_file(file_id)

    def clear_cache_by_subject(self, subject: str) -> int:
        """Xóa cache của 1 môn học."""
        return self.vector_store.delete_by_subject(subject)

    def get_cache_stats(self) -> Dict:
        """Lấy thống kê cache."""
        return self.vector_store.get_stats()
