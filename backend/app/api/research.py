"""Research-only endpoints for corpus inspection and C0-C3 generation."""

from __future__ import annotations

from functools import lru_cache
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.auto_exam_pipeline import AutoExamPipeline, AutoExamRequest
from ..services.experiment_config import load_experiment_config
from ..services.model_provider import ModelBackendError


router = APIRouter(prefix="/research", tags=["research"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    lesson_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    mode: str = Field(default="hybrid", pattern="^(dense|keyword|hybrid)$")


@lru_cache(maxsize=1)
def pipeline() -> AutoExamPipeline:
    return AutoExamPipeline()


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
