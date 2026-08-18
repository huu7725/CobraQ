"""Strict output contract and deterministic checks for generated questions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


QuestionType = Literal["multiple_choice", "short_essay"]
BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate"]


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1, max_length=500)


class CitationRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=800)


class QuestionContent(BaseModel):
    """Only the five content fields that the language model may generate."""

    model_config = ConfigDict(extra="forbid")

    question_type: QuestionType
    stem: str = Field(min_length=10, max_length=1500)
    choices: list[Choice]
    correct_answer: str = Field(min_length=1, max_length=2000)
    explanation: str = Field(min_length=10, max_length=2500)

    @model_validator(mode="after")
    def validate_content_contract(self):
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
            for index, left in enumerate(normalized):
                for right in normalized[index + 1 :]:
                    shorter, longer = sorted((left, right), key=len)
                    if len(shorter) >= 20 and shorter in longer:
                        raise ValueError("Choice texts must not be near-duplicates")
        elif self.choices:
            raise ValueError("Short-essay questions must not contain choices")
        return self


class ModelGenerationEnvelope(BaseModel):
    """Compact JSON envelope accepted from the language model."""

    model_config = ConfigDict(extra="forbid")

    questions: list[QuestionContent] = Field(min_length=1)


class GeneratedQuestion(QuestionContent):
    """Strict server-owned question contract returned by the pipeline."""

    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)
    difficulty: int = Field(ge=1, le=3)
    bloom_level: BloomLevel
    lesson_id: str = Field(min_length=1)
    citations: list[CitationRef] = Field(default_factory=list)
    generation_condition: Literal["C0", "C1", "C2", "C3"]

    @model_validator(mode="after")
    def validate_question_contract(self):
        if self.generation_condition in {"C1", "C3"} and not self.citations:
            raise ValueError("RAG conditions must cite at least one retrieved chunk")
        return self


def build_json_schema_instruction() -> str:
    schema = ModelGenerationEnvelope.model_json_schema()
    import json

    return json.dumps(schema, ensure_ascii=False, indent=2)
