"""Evidence-grounded Auto-Exam pipeline used by CobraQ conditions C0-C3."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import get_settings
from .experiment_config import get_condition, load_experiment_config
from .model_provider import create_backend
from .question_schema import GeneratedQuestion
from .trust_layer import Chunk, TrustLayer
from .vector_service import VectorService


class AutoExamRequest(BaseModel):
    condition_id: Literal["C0", "C1", "C2", "C3"] = "C3"
    lesson_id: str = Field(pattern=r"^lesson_(?:0[1-9]|1[0-7])$")
    question_type: Literal["multiple_choice", "short_essay"] = "multiple_choice"
    difficulty: int = Field(default=2, ge=1, le=3)
    bloom_level: Literal["remember", "understand", "apply", "analyze", "evaluate"] = "understand"
    num_questions: int = Field(default=1, ge=1, le=5)
    learning_objective: str = Field(default="", max_length=1000)
    model_backend: Optional[Literal["local", "api"]] = None


class AutoExamPipeline:
    def __init__(self):
        settings = get_settings()
        config = load_experiment_config()
        shared = config["shared"]
        corpus_dir = Path(settings.cobraq_corpus_dir)
        project_root = Path(__file__).resolve().parents[3]
        if not corpus_dir.is_absolute():
            corpus_dir = project_root / corpus_dir
        self.settings = settings
        self.shared = shared
        self.vector = VectorService(
            persist_dir=str(corpus_dir / "chroma_db"),
            collection_name=settings.cobraq_collection,
            embedding_model=settings.cobraq_embedding_model,
        )
        self.trust = TrustLayer(min_confidence=0.45, min_chunks=1)
        self._backends: dict[tuple[str, str, str], Any] = {}

    def _retrieve(self, request: AutoExamRequest) -> list[Chunk]:
        query = (
            f"Nội dung trọng tâm {request.lesson_id}. {request.learning_objective} "
            f"Câu hỏi mức độ {request.bloom_level}."
        ).strip()
        return self.vector.search(
            query,
            doc_id=self.shared["corpus_id"],
            top_k=int(self.shared["retrieval_top_k"]),
            mode=self.shared["retrieval_mode"],
            filters={"lesson_id": request.lesson_id},
        )

    @staticmethod
    def _context(chunks: list[Chunk]) -> str:
        return "\n\n".join(
            f"[{chunk.id} | trang {chunk.page}]\n{chunk.text}" for chunk in chunks
        )

    def _prompt(self, request: AutoExamRequest, chunks: list[Chunk], use_rag: bool) -> str:
        context = self._context(chunks) if use_rag else "Không cung cấp ngữ liệu truy xuất."
        citation_rule = (
            "Mỗi câu phải có citations chứa chunk_id, page và một quote nguyên văn từ ngữ liệu."
            if use_rag
            else "Để citations là danh sách rỗng."
        )
        return f"""NHIỆM VỤ
Sinh đúng {request.num_questions} câu hỏi {request.question_type} cho {request.lesson_id}.
Độ khó: {request.difficulty}/3. Bậc nhận thức: {request.bloom_level}.
Mục tiêu bổ sung: {request.learning_objective or 'Không có'}.

QUY TẮC
- Không bịa đặt ngày tháng, nhân vật, địa điểm hoặc quan hệ nguyên nhân-kết quả.
- Trắc nghiệm phải có đúng bốn lựa chọn A/B/C/D và một đáp án đúng duy nhất.
- Phương án nhiễu phải hợp lý nhưng không được vô tình đúng.
- {citation_rule}
- Chỉ trả về JSON, không dùng Markdown.

NGỮ LIỆU
{context}

JSON OUTPUT
{{"questions":[{{"question_type":"{request.question_type}","stem":"...","choices":[],"correct_answer":"A","explanation":"...","difficulty":{request.difficulty},"bloom_level":"{request.bloom_level}","lesson_id":"{request.lesson_id}","citations":[],"generation_condition":"{request.condition_id}"}}]}}
"""

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            return json.loads(cleaned[start:end + 1])

    @staticmethod
    def _claim_text(question: GeneratedQuestion) -> str:
        answer_text = question.correct_answer
        if question.question_type == "multiple_choice":
            answer_text = next(
                (choice.text for choice in question.choices if choice.label == question.correct_answer),
                question.correct_answer,
            )
        return "\n".join((question.stem, answer_text, question.explanation))

    @staticmethod
    def _citation_is_valid(question: GeneratedQuestion, chunks: list[Chunk], use_rag: bool) -> bool:
        if not use_rag:
            return not question.citations
        chunk_map = {chunk.id: chunk for chunk in chunks}
        for citation in question.citations:
            chunk = chunk_map.get(citation.chunk_id)
            if not chunk or citation.page != chunk.page:
                return False
            quote = " ".join(citation.quote.lower().split())
            evidence = " ".join(chunk.text.lower().split())
            if not quote or quote not in evidence:
                return False
        return bool(question.citations)

    def generate(self, request: AutoExamRequest) -> dict[str, Any]:
        condition = get_condition(request.condition_id)
        verification_chunks = self._retrieve(request)
        exposed_chunks = verification_chunks if condition.use_rag else []
        backend_name = request.model_backend or self.settings.cobraq_model_backend
        adapter = condition.adapter_path if condition.use_lora else ""
        if adapter and not Path(adapter).is_absolute():
            adapter = str(Path(__file__).resolve().parents[3] / adapter)
        backend_key = (backend_name, self.settings.cobraq_base_model, adapter)
        if backend_key not in self._backends:
            self._backends[backend_key] = create_backend(
                backend_name,
                model_id=self.settings.cobraq_base_model,
                adapter_path=adapter,
            )
        backend = self._backends[backend_key]
        decoding = self.shared["decoding"]
        output = backend.generate(
            self._prompt(request, exposed_chunks, condition.use_rag),
            max_new_tokens=int(decoding["max_new_tokens"]),
            temperature=float(decoding["temperature"]),
            top_p=float(decoding["top_p"]),
        )
        payload = self._extract_json(output.text)
        raw_questions = payload.get("questions") or []
        if len(raw_questions) != request.num_questions:
            raise ValueError(
                f"Model returned {len(raw_questions)} questions; expected {request.num_questions}"
            )
        validated = []
        for raw in raw_questions:
            raw["lesson_id"] = request.lesson_id
            raw["generation_condition"] = request.condition_id
            question = GeneratedQuestion.model_validate(raw)
            trust = self.trust.evaluate(self._claim_text(question), verification_chunks)
            cited_ids = {citation.chunk_id for citation in question.citations}
            citation_valid = self._citation_is_valid(question, exposed_chunks, condition.use_rag)
            evidence_chunks = [chunk for chunk in verification_chunks if not cited_ids or chunk.id in cited_ids]
            evidence_reviewed = bool(evidence_chunks) and all(
                not chunk.metadata.get("review_required", False) for chunk in evidence_chunks
            )
            auto_status = (
                "auto_verified"
                if not trust["hallucination_detected"] and citation_valid and evidence_reviewed
                else "needs_teacher_review"
            )
            validated.append(
                {
                    **question.model_dump(),
                    "auto_evaluation": {
                        **trust,
                        "citation_valid": citation_valid,
                        "evidence_ocr_reviewed": evidence_reviewed,
                        "status": auto_status,
                    },
                }
            )
        return {
            "condition": condition.id,
            "use_rag": condition.use_rag,
            "use_lora": condition.use_lora,
            "model_backend": backend_name,
            "model_id": output.model_id,
            "adapter_id": output.adapter_id,
            "latency_ms": output.latency_ms,
            "prompt_tokens": output.prompt_tokens,
            "completion_tokens": output.completion_tokens,
            "retrieved_chunks": [
                {
                    "chunk_id": chunk.id,
                    "page": chunk.page,
                    "score": round(chunk.score, 4),
                    "lesson_id": chunk.metadata.get("lesson_id", ""),
                    "text": chunk.text,
                    "exposed_to_model": condition.use_rag,
                }
                for chunk in verification_chunks
            ],
            "questions": validated,
        }
