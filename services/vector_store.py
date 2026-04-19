"""
Vector Store Service - Sử dụng ChromaDB để lưu trữ và tìm kiếm vector embeddings.
Lưu trữ câu hỏi + embedding + metadata (answer, explanation, file_id, subject).
"""

import os
import json
import uuid
from typing import List, Dict, Optional, Any
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.errors import IDAlreadyExistsError

import logging

logger = logging.getLogger(__name__)

class VectorStore:
    """
    Vector Database sử dụng ChromaDB (local, không cần server).
    Lưu trữ và tìm kiếm câu hỏi dựa trên embedding.
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "questions",
        distance_metric: str = "cosine"
    ):
        """
        Khởi tạo VectorStore với ChromaDB.

        Args:
            persist_directory: Thư mục lưu DB (persistent)
            collection_name: Tên collection
            distance_metric: 'cosine', 'l2', 'ip' (inner product)
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"Khởi tạo ChromaDB tại: {persist_directory}")

        # Khởi tạo ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Tạo hoặc lấy collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            logger.info(f"Đã nạp collection '{collection_name}' với {self.collection.count()} items")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": distance_metric}
            )
            logger.info(f"Đã tạo collection mới '{collection_name}'")

    def add_question(
        self,
        question_id: str,
        embedding: List[float],
        question_text: str,
        answer: str = "",
        explanation: str = "",
        file_id: str = "",
        subject: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Thêm 1 câu hỏi vào vector DB.

        Args:
            question_id: ID duy nhất (có thể là string)
            embedding: Vector embedding (list of floats)
            question_text: Nội dung câu hỏi
            answer: Đáp án (A/B/C/D)
            explanation: Giải thích (có thể rỗng)
            file_id: ID của file gốc
            subject: Môn học (toán, lý, hóa, ...)
            metadata: Metadata bổ sung

        Returns:
            bool: True nếu thành công
        """
        try:
            meta = {
                "answer": str(answer).strip().upper(),
                "explanation": str(explanation).strip(),
                "file_id": str(file_id).strip(),
                "subject": str(subject).strip(),
                "created_at": self._get_timestamp()
            }
            if metadata:
                meta.update(metadata)

            self.collection.add(
                ids=[str(question_id)],
                embeddings=[embedding],
                documents=[str(question_text).strip()],
                metadatas=[meta]
            )
            logger.debug(f"Đã thêm câu hỏi ID={question_id}")
            return True
        except IDAlreadyExistsError:
            logger.warning(f"Question ID {question_id} đã tồn tại, bỏ qua")
            return False
        except Exception as e:
            logger.error(f"Lỗi khi thêm question vào vector DB: {e}")
            return False

    def add_batch(
        self,
        questions: List[Dict],
        embeddings: List[List[float]],
        batch_size: int = 100
    ) -> int:
        """
        Thêm nhiều câu hỏi cùng lúc (batch insert).

        Args:
            questions: List các dict question data
            embeddings: List các embedding tương ứng
            batch_size: Số lượng mỗi batch (tránh quá tải)

        Returns:
            int: Số câu đã thêm thành công
        """
        if len(questions) != len(embeddings):
            raise ValueError("Số lượng questions và embeddings phải bằng nhau")

        total_added = 0
        for i in range(0, len(questions), batch_size):
            batch_q = questions[i:i+batch_size]
            batch_e = embeddings[i:i+batch_size]

            ids = []
            docs = []
            metas = []

            for q, emb in zip(batch_q, batch_e):
                qid = q.get("id", str(uuid.uuid4()))
                if not isinstance(qid, str):
                    qid = str(qid)

                ids.append(f"q_{qid}")
                docs.append(str(q.get("question", "")))

                meta = {
                    "answer": str(q.get("answer", "")).upper().strip(),
                    "explanation": str(q.get("explanation", "")).strip(),
                    "file_id": str(q.get("file_id", "")).strip(),
                    "subject": str(q.get("subject", "")).strip(),
                    "cached": True,
                    "created_at": self._get_timestamp()
                }
                metas.append(meta)

            try:
                self.collection.add(
                    ids=ids,
                    embeddings=batch_e,
                    documents=docs,
                    metadatas=metas
                )
                total_added += len(batch_q)
            except Exception as e:
                logger.error(f"Lỗi khi add batch: {e}")

        logger.info(f"Đã add {total_added}/{len(questions)} câu hỏi vào vector DB")
        return total_added

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        include: List[str] = ["documents", "distances", "metadatas"]
    ) -> Dict[str, Any]:
        """
        Tìm kiếm câu hỏi tương tự.

        Args:
            query_embedding: Embedding của câu query
            top_k: Số kết quả trả về
            where: Filter theo metadata (VD: {"subject": "toán"})
            where_document: Filter theo nội dung document
            include: Các field cần trả về

        Returns:
            Dict: Kết quả từ ChromaDB
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                where_document=where_document,
                include=include
            )
            return results
        except Exception as e:
            logger.error(f"Lỗi khi search similar: {e}")
            return {
                "ids": [[]],
                "distances": [[]],
                "documents": [[]],
                "metadatas": [[]]
            }

    def get_by_id(self, question_id: str) -> Optional[Dict]:
        """
        Lấy 1 câu hỏi theo ID.

        Returns:
            Dict với keys: id, document, metadata, embedding (nếu có)
        """
        try:
            result = self.collection.get(
                ids=[question_id],
                include=["documents", "metadatas", "embeddings"]
            )
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "question": result["documents"][0],
                    "metadata": result["metadatas"][0],
                    "embedding": result["embeddings"][0] if result["embeddings"] else None
                }
            return None
        except Exception as e:
            logger.error(f"Lỗi khi get_by_id: {e}")
            return None

    def get_by_file(self, file_id: str) -> List[Dict]:
        """
        Lấy tất cả câu hỏi thuộc về 1 file.

        Args:
            file_id: File ID

        Returns:
            List các dict: {id, question, metadata}
        """
        try:
            results = self.collection.get(
                where={"file_id": file_id},
                include=["documents", "metadatas"]
            )

            items = []
            for i, qid in enumerate(results["ids"]):
                items.append({
                    "id": qid,
                    "question": results["documents"][i],
                    "metadata": results["metadatas"][i]
                })
            return items
        except Exception as e:
            logger.error(f"Lỗi khi get_by_file: {e}")
            return []

    def delete_by_id(self, question_id: str) -> bool:
        """Xóa 1 câu hỏi theo ID."""
        try:
            self.collection.delete(ids=[question_id])
            return True
        except Exception as e:
            logger.error(f"Lỗi khi delete_by_id: {e}")
            return False

    def delete_by_file(self, file_id: str) -> int:
        """
        Xóa tất cả câu hỏi của 1 file.
        Returns: Số câu đã xóa
        """
        try:
            # Lấy tất cả IDs của file
            results = self.collection.get(
                where={"file_id": file_id},
                include=[]
            )
            ids_to_delete = results["ids"]

            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                logger.info(f"Đã xóa {len(ids_to_delete)} câu từ file {file_id}")
                return len(ids_to_delete)
            return 0
        except Exception as e:
            logger.error(f"Lỗi khi delete_by_file: {e}")
            return 0

    def delete_by_subject(self, subject: str) -> int:
        """Xóa tất cả câu hỏi của 1 môn học."""
        try:
            results = self.collection.get(
                where={"subject": subject},
                include=[]
            )
            ids_to_delete = results["ids"]

            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                logger.info(f"Đã xóa {len(ids_to_delete)} câu của môn {subject}")
                return len(ids_to_delete)
            return 0
        except Exception as e:
            logger.error(f"Lỗi khi delete_by_subject: {e}")
            return 0

    def count(self) -> int:
        """Đếm tổng số câu hỏi trong DB."""
        return self.collection.count()

    def get_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê tổng quan về vector DB.

        Returns:
            Dict: {total, by_subject, by_file}
        """
        try:
            total = self.collection.count()

            # Lấy tất cả metadata
            results = self.collection.get(include=["metadatas"])

            by_subject = {}
            by_file = {}

            for meta in results["metadatas"]:
                subj = meta.get("subject", "unknown")
                by_subject[subj] = by_subject.get(subj, 0) + 1

                fid = meta.get("file_id", "unknown")
                by_file[fid] = by_file.get(fid, 0) + 1

            return {
                "total": total,
                "by_subject": by_subject,
                "by_file": by_file,
                "collection_name": self.collection.name
            }
        except Exception as e:
            logger.error(f"Lỗi khi get_stats: {e}")
            return {"total": 0, "by_subject": {}, "by_file": {}}

    def list_all(self, limit: int = 100) -> List[Dict]:
        """
        Liệt kê tất cả câu hỏi (hữu ích cho debugging).

        Args:
            limit: Số lượng tối đa trả về

        Returns:
            List các dict
        """
        try:
            results = self.collection.get(
                limit=limit,
                include=["documents", "metadatas"]
            )

            items = []
            for i, qid in enumerate(results["ids"]):
                items.append({
                    "id": qid,
                    "question": results["documents"][i],
                    "answer": results["metadatas"][i].get("answer", ""),
                    "subject": results["metadatas"][i].get("subject", ""),
                    "file_id": results["metadatas"][i].get("file_id", ""),
                    "has_explanation": bool(results["metadatas"][i].get("explanation"))
                })
            return items
        except Exception as e:
            logger.error(f"Lỗi khi list_all: {e}")
            return []

    def reset(self):
        """Xóa toàn bộ collection (cẩn thận!)."""
        try:
            self.client.delete_collection(name=self.collection.name)
            self.collection = self.client.create_collection(
                name=self.collection.name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.warning("Đã reset vector DB")
        except Exception as e:
            logger.error(f"Lỗi khi reset: {e}")

    def _get_timestamp(self) -> str:
        """Lấy timestamp hiện tại dạng string."""
        from datetime import datetime
        return datetime.now().isoformat()

    def close(self):
        """Đóng client (nếu cần)."""
        # ChromaDB không có close, nhưng giữ lại để tương lai
        pass
