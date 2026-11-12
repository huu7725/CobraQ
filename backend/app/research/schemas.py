from __future__ import annotations

from datetime import date
from difflib import SequenceMatcher
import hashlib
import json
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceChunk(StrictModel):
    id: str
    text: str = Field(min_length=40)
    source: str
    source_sha256: str
    book_page: int = Field(ge=1)
    pdf_page: int = Field(ge=1)
    lesson_id: int = Field(ge=1, le=17)
    lesson_title: str
    topic_id: int = Field(ge=1, le=6)
    provenance: Literal["review_pdf_extract", "tesseract_ocr"]
    review_status: Literal["review_required", "teacher_approved", "rejected"] = "review_required"
    reviewer_id: str = ""
    reviewed_at: str = ""
    years: list[str] = Field(default_factory=list)
    ocr_confidence: float | None = None

    @model_validator(mode="after")
    def approval_metadata(self):
        if self.review_status == "teacher_approved":
            if not self.reviewer_id:
                raise ValueError("Teacher approval requires a reviewer identity")
            date.fromisoformat(self.reviewed_at)
        return self


class Question(StrictModel):
    question_type: Literal["multiple_choice", "short_answer"]
    stem: str = Field(min_length=12, max_length=4000)
    choices: dict[str, str] = Field(default_factory=dict)
    correct_answer: str = Field(min_length=1, max_length=5000)
    explanation: str = Field(min_length=10, max_length=6000)

    @model_validator(mode="after")
    def check_choices(self):
        if self.question_type == "multiple_choice":
            if set(self.choices) != set("ABCD") or self.correct_answer not in self.choices:
                raise ValueError("MCQ requires exactly A/B/C/D and one matching answer key")
            values = [normalize(v) for v in self.choices.values()]
            if any(not v for v in values):
                raise ValueError("Empty answer choice")
            for i, a in enumerate(values):
                for b in values[i + 1:]:
                    if a == b or (min(len(a), len(b)) > 15 and SequenceMatcher(None, a, b).ratio() >= .92):
                        raise ValueError("Duplicate or near-duplicate answer choices")
        elif self.choices:
            raise ValueError("Short-answer questions cannot contain answer choices")
        return self


class ExamRequest(StrictModel):
    query: str = Field(min_length=5, max_length=1000)
    lesson_id: int = Field(ge=1, le=17)
    question_type: Literal["multiple_choice", "short_answer"] = "multiple_choice"
    difficulty: int = Field(default=1, ge=1, le=3)
    configuration: Literal["C0", "C1", "C2", "C3"] = "C3"
    seed: int = Field(default=42, ge=0, le=2147483647)
    max_new_tokens: int = Field(default=512, ge=64, le=1024)


class Citation(StrictModel):
    chunk_id: str
    source: str
    book_page: int
    pdf_page: int
    quote: str


def parse_question(raw: str, expected_type: str) -> Question:
    # Strict JSON only: never repair malformed outputs or silently change type.
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    question = Question.model_validate(json.loads(raw, object_pairs_hook=unique_keys))
    if question.question_type != expected_type:
        raise ValueError("Generated question type differs from the request")
    return question
