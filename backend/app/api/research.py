"""Research-only endpoints for corpus inspection and C0-C3 generation."""

from __future__ import annotations

from functools import lru_cache
from fastapi import APIRouter, HTTPException
import json
from pathlib import Path
from pydantic import BaseModel, Field
import random
from typing import Literal
from uuid import uuid4

from ..services.auto_exam_pipeline import AutoExamPipeline, AutoExamRequest
from ..services.experiment_config import load_experiment_config
from ..services.model_provider import ModelBackendError


router = APIRouter(prefix="/research", tags=["research"])
ROOT = Path(__file__).resolve().parents[3]
APPROVED_TEST = ROOT / "data" / "research" / "aqg_v2" / "approved" / "test.jsonl"
PRACTICE_SESSIONS: dict[str, list[dict]] = {}


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    lesson_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    mode: str = Field(default="hybrid", pattern="^(dense|keyword|hybrid)$")


class PracticeStartRequest(BaseModel):
    lesson_id: str | None = Field(default=None, pattern=r"^lesson_(?:0[1-9]|1[0-7])$")
    question_type: Literal["multiple_choice", "short_essay"] = "multiple_choice"
    num_questions: int = Field(default=5, ge=1, le=10)


class PracticeSubmitRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    answers: dict[str, str]
    time_taken_seconds: int = Field(default=0, ge=0, le=7200)


@lru_cache(maxsize=1)
def pipeline() -> AutoExamPipeline:
    return AutoExamPipeline()


@lru_cache(maxsize=1)
def approved_practice_records() -> list[dict]:
    if not APPROVED_TEST.is_file():
        return []
    records = []
    with APPROVED_TEST.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            questions = (record.get("response") or {}).get("questions") or []
            if record.get("review_status") == "teacher_approved" and len(questions) == 1:
                records.append(record)
    return records


@router.get("/practice/catalog")
def practice_catalog():
    records = approved_practice_records()
    lessons: dict[str, dict] = {}
    for record in records:
        provenance = record.get("provenance") or {}
        lesson_id = str(provenance.get("lesson_id") or "")
        question = record["response"]["questions"][0]
        if not lesson_id:
            continue
        lesson = lessons.setdefault(lesson_id, {
            "lesson_id": lesson_id,
            "lesson_number": provenance.get("lesson_number"),
            "lesson_title": provenance.get("lesson_title") or lesson_id,
            "topic_id": provenance.get("topic_id") or "",
            "multiple_choice": 0,
            "short_essay": 0,
            "total": 0,
        })
        question_type = question.get("question_type")
        if question_type in {"multiple_choice", "short_essay"}:
            lesson[question_type] += 1
            lesson["total"] += 1
    return {
        "source": "teacher_approved_held_out",
        "total_questions": len(records),
        "lessons": sorted(
            lessons.values(), key=lambda item: int(item.get("lesson_number") or 0)
        ),
    }


@router.post("/practice/start")
def start_practice(body: PracticeStartRequest):
    candidates = []
    for record in approved_practice_records():
        provenance = record.get("provenance") or {}
        question = record["response"]["questions"][0]
        if body.lesson_id and provenance.get("lesson_id") != body.lesson_id:
            continue
        if question.get("question_type") != body.question_type:
            continue
        candidates.append(record)
    if not candidates:
        raise HTTPException(404, "Không có câu hỏi đã duyệt phù hợp")

    selected = random.SystemRandom().sample(
        candidates, min(body.num_questions, len(candidates))
    )
    session_id = f"practice-{uuid4().hex}"
    session_questions = []
    public_questions = []
    for index, record in enumerate(selected, start=1):
        question = record["response"]["questions"][0]
        provenance = record.get("provenance") or {}
        public = {
            "id": str(index),
            "question_type": question["question_type"],
            "stem": question["stem"],
            "choices": question["choices"],
            "lesson_id": provenance.get("lesson_id"),
            "lesson_title": provenance.get("lesson_title"),
            "difficulty": provenance.get("difficulty"),
            "bloom_level": provenance.get("bloom_level"),
        }
        public_questions.append(public)
        session_questions.append({
            **public,
            "correct_answer": question["correct_answer"],
            "explanation": question["explanation"],
            "citations": provenance.get("source_citations") or [],
        })
    PRACTICE_SESSIONS[session_id] = session_questions
    return {
        "session_id": session_id,
        "source": "teacher_approved_held_out",
        "total": len(public_questions),
        "questions": public_questions,
    }


@router.post("/practice/submit")
def submit_practice(body: PracticeSubmitRequest):
    questions = PRACTICE_SESSIONS.pop(body.session_id, None)
    if not questions:
        raise HTTPException(404, "Phiên luyện tập không tồn tại hoặc đã được nộp")

    details = []
    gradable = 0
    correct_count = 0
    for question in questions:
        answer = str(body.answers.get(question["id"], "")).strip()
        is_mcq = question["question_type"] == "multiple_choice"
        is_correct = answer == question["correct_answer"] if is_mcq else None
        if is_mcq:
            gradable += 1
            correct_count += int(bool(is_correct))
        details.append({
            **question,
            "user_answer": answer,
            "is_correct": is_correct,
            "review_status": "auto_scored" if is_mcq else "self_review",
        })
    percentage = round(correct_count / gradable * 100) if gradable else None
    return {
        "score": correct_count,
        "gradable_total": gradable,
        "percentage": percentage,
        "time_taken_seconds": body.time_taken_seconds,
        "details": details,
    }


@router.get("/config")
def experiment_config():
    return load_experiment_config()


@router.get("/corpus/stats")
def corpus_stats():
    return pipeline().vector.get_stats()


@router.post("/search")
def search(body: SearchRequest):
    service = pipeline().vector
    chunks = service.search(
        body.query,
        top_k=body.top_k,
        mode=body.mode,
        filters={"lesson_id": body.lesson_id} if body.lesson_id else None,
    )
    return {
        "query": body.query,
        "results": [
            {
                "chunk_id": chunk.id,
                "text": chunk.text,
                "source": chunk.source,
                "page": chunk.page,
                "score": chunk.score,
                "metadata": chunk.metadata,
            }
            for chunk in chunks
        ],
    }


@router.post("/generate")
def generate(body: AutoExamRequest):
    try:
        return pipeline().generate(body)
    except ModelBackendError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
