"""Strict output contract and deterministic checks for generated questions."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


QuestionType = Literal["multiple_choice", "short_essay"]
BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate"]


class Choice(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1, max_length=500)


class CitationRef(BaseModel):
    chunk_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=800)


class GeneratedQuestion(BaseModel):
    question_id: Optional[str] = None
    question_type: QuestionType
    stem: str = Field(min_length=10, max_length=1500)
    choices: list[Choice] = Field(default_factory=list)
    correct_answer: str = Field(min_length=1, max_length=2000)
    explanation: str = Field(min_length=10, max_length=2500)
    difficulty: int = Field(ge=1, le=3)
    bloom_level: BloomLevel
    lesson_id: str = Field(min_length=1)
    citations: list[CitationRef] = Field(default_factory=list)
    generation_condition: Literal["C0", "C1", "C2", "C3"]

    @model_validator(mode="after")
    def validate_question_contract(self):
        if self.question_type == "multiple_choice":
            if len(self.choices) != 4:
                raise ValueError("Multiple-choice questions must have exactly four choices")
            labels = [choice.label for choice in self.choices]
            if len(set(labels)) != 4:
                raise ValueError("Choice labels must be unique")
            if self.correct_answer not in labels:
                raise ValueError("correct_answer must be one of A/B/C/D")
            normalized = [" ".join(choice.text.lower().split()) for choice in self.choices]
            if len(set(normalized)) != 4:
                raise ValueError("Choice texts must be unique")
        elif self.choices:
            raise ValueError("Short-essay questions must not contain choices")
        if self.generation_condition in {"C1", "C3"} and not self.citations:
            raise ValueError("RAG conditions must cite at least one retrieved chunk")
        return self


class GenerationEnvelope(BaseModel):
    questions: list[GeneratedQuestion] = Field(min_length=1)
    model_id: str = Field(min_length=1)
    adapter_id: Optional[str] = None
    retrieval_mode: Literal["none", "dense", "keyword", "hybrid"]
    latency_ms: int = Field(ge=0)


def build_json_schema_instruction() -> str:
    schema = GenerationEnvelope.model_json_schema()
    import json

    return json.dumps(schema, ensure_ascii=False, indent=2)
