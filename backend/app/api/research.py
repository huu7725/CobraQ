"""History 12 research and approved practice, isolated from user-uploaded quizzes."""
from __future__ import annotations

import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import Field

from ..core.security import get_current_user
from ..research.schemas import StrictModel, Question, digest, ExamRequest
from ..research.store import CorpusStore
from ..research.retrieval import search

router = APIRouter(prefix="/research", tags=["history12-research"])


def get_store():
    return CorpusStore()


def teacher(user: dict = Depends(get_current_user)):
    if user.get("role") not in {"teacher", "admin"}:
        raise HTTPException(403, "Cần quyền giáo viên hoặc quản trị viên")
    return user


@router.get("/status")
def status(user: dict = Depends(get_current_user), store: CorpusStore = Depends(get_store)):
    return store.status()


@router.get("/lessons")
def lessons(user: dict = Depends(get_current_user), store: CorpusStore = Depends(get_store)):
    import json
    return json.loads((store.root / "corpus/lessons.json").read_text(encoding="utf-8"))


@router.get("/search")
def retrieve(query: str = Query(min_length=3, max_length=1000), lesson_id: int | None = Query(None, ge=1, le=17),
             mode: Literal["keyword", "dense", "hybrid"] = "keyword", top_k: int = Query(5, ge=1, le=10),
             include_drafts: bool = False, user: dict = Depends(get_current_user),
             store: CorpusStore = Depends(get_store)):
    if include_drafts and user.get("role") not in {"teacher", "admin"}:
        raise HTTPException(403, "Chỉ giáo viên được xem ngữ liệu chưa duyệt")
    try:
        return {"results": search(store.chunks, query, lesson_id=lesson_id, mode=mode,
                                  top_k=top_k, approved_only=not include_drafts),
                "semantic_support": "not_assessed"}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/source-pages/{book_page}")
def source_page(book_page: int, user: dict = Depends(get_current_user), store: CorpusStore = Depends(get_store)):
    import fitz
    chunks = [c for c in store.chunks if c.book_page == book_page]
    if user.get("role") not in {"teacher", "admin"}:
        chunks = [c for c in chunks if c.review_status == "teacher_approved"]
    if not chunks:
        raise HTTPException(404, "Không có trang nguồn đã duyệt")
    path = store.root / "sources/history12_kntt_2023_sample.pdf"
    if not path.exists():
        raise HTTPException(503, "Chưa có PDF nguồn")
    if hashlib.sha256(path.read_bytes()).hexdigest() != chunks[0].source_sha256:
        raise HTTPException(409, "PDF nguồn không khớp manifest")
    with fitz.open(path) as pdf:
        index = chunks[0].pdf_page - 1
        if index < 0 or index >= len(pdf):
            raise HTTPException(404, "Trang PDF không hợp lệ")
        png = pdf[index].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png")
    return Response(png, media_type="image/png")


@router.get("/reviews/{kind}")
def review_queue(kind: Literal["chunks", "questions", "gold"], user: dict = Depends(teacher),
                 store: CorpusStore = Depends(get_store)):
    return {"rows": [{**r, "revision_hash": digest(r)} for r in store.rows(kind)]}


class ReviewBody(StrictModel):
    expected_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["teacher_approved", "rejected", "review_required"]
    question: Question | None = None
    source_text: str | None = Field(default=None, min_length=40, max_length=20000)
    relevant_chunk_ids: list[str] | None = None
    notes: str = Field(default="", max_length=5000)


@router.post("/reviews/{kind}/{row_id}")
def review(kind: Literal["chunks", "questions", "gold"], row_id: str, body: ReviewBody,
           user: dict = Depends(teacher), store: CorpusStore = Depends(get_store)):
    try:
        row = store.review(kind, row_id, expected_hash=body.expected_hash, decision=body.decision,
                           reviewer=user["sub"], question=body.question.model_dump() if body.question else None,
                           relevant_chunk_ids=body.relevant_chunk_ids, notes=body.notes, source_text=body.source_text)
        return {**row, "revision_hash": digest(row)}
    except KeyError:
        raise HTTPException(404, "Không có mục cần duyệt")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/practice")
def practice(lesson_id: int | None = Query(None, ge=1, le=17), user: dict = Depends(get_current_user),
             store: CorpusStore = Depends(get_store)):
    rows = [r for r in store.questions(True) if lesson_id is None or r["lesson_id"] == lesson_id]
    return {"questions": [{"id": r["id"], "lesson_id": r["lesson_id"],
                           "question_type": r["question"]["question_type"], "stem": r["question"]["stem"],
                           "choices": r["question"]["choices"]} for r in rows],
            "notice": "Chỉ hiển thị câu hỏi và nguồn đã được giáo viên duyệt."}


class AnswerBody(StrictModel):
    answer: str = Field(min_length=1, max_length=6000)


@router.post("/practice/{question_id}/answer")
def answer(question_id: str, body: AnswerBody, user: dict = Depends(get_current_user),
           store: CorpusStore = Depends(get_store)):
    row = next((r for r in store.questions(True) if r["id"] == question_id), None)
    if row is None:
        raise HTTPException(404, "Câu hỏi chưa được duyệt hoặc đã thay đổi")
    q = Question.model_validate(row["question"])
    if q.choices and body.answer.upper() not in q.choices:
        raise HTTPException(422, "Chọn một đáp án A/B/C/D")
    return {"correct": body.answer.upper() == q.correct_answer if q.choices else None,
            "grading": "automatic" if q.choices else "teacher_required",
            "correct_answer": q.correct_answer, "explanation": q.explanation,
            "book_page": row["book_page"], "quote": row["quote"]}


@router.post("/auto-exam")
def auto_exam(body: ExamRequest, user: dict = Depends(teacher), store: CorpusStore = Depends(get_store)):
    from ..research.generation import generate
    try:
        return generate(body, store)
    except (RuntimeError, ImportError, OSError) as exc:
        raise HTTPException(503, str(exc)) from exc
