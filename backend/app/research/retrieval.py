"""Lesson-filtered BM25 / local multilingual embeddings / reciprocal rank fusion."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import math
import os
import re

from .schemas import SourceChunk, normalize


def evidence_issue(chunk: SourceChunk) -> str:
    text = normalize(chunk.text)
    if re.search(r"(?:sau bài học|học xong bài|mục tiêu bài học|yêu cầu cần đạt|em sẽ|em có thể)", text):
        return "learning_objective"
    title = normalize(chunk.lesson_title)
    if text == title or text == f"bài {chunk.lesson_id} {title}":
        return "heading_only"
    # A short fragment without sentence punctuation cannot support generated claims.
    if len(text.split()) < 12 and not re.search(r"[.!?;]", chunk.text):
        return "short_fragment"
    return ""


@lru_cache(maxsize=1)
def local_encoder():
    from sentence_transformers import SentenceTransformer
    model = os.environ.get("COBRAQ_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    # Loading research features must never silently download a model or substitute hash vectors.
    return SentenceTransformer(model, local_files_only=True)


@lru_cache(maxsize=2)
def dense_vectors(texts: tuple[str, ...]):
    return local_encoder().encode(list(texts), normalize_embeddings=True)


def search(chunks: list[SourceChunk], query: str, *, lesson_id: int | None = None,
           top_k: int = 5, mode: str = "keyword", approved_only: bool = True) -> list[dict]:
    if mode not in {"keyword", "dense", "hybrid"}:
        raise ValueError("Unknown retrieval mode")
    candidates = [c for c in chunks if (lesson_id is None or c.lesson_id == lesson_id)
                  and (not approved_only or c.review_status == "teacher_approved")
                  and c.review_status != "rejected" and not evidence_issue(c)]
    terms = set(normalize(query).split())
    if not candidates or not terms:
        return []
    rankings = []
    if mode in {"keyword", "hybrid"}:
        documents = [Counter(normalize(c.text).split()) for c in candidates]
        average = sum(sum(d.values()) for d in documents) / len(documents)
        df = {t: sum(t in d for d in documents) for t in terms}
        scores = []
        for i, doc in enumerate(documents):
            length = sum(doc.values())
            score = sum(math.log(1 + (len(documents) - df[t] + .5) / (df[t] + .5)) *
                        doc[t] * 2.5 / (doc[t] + 1.5 * (.25 + .75 * length / average))
                        for t in terms if doc[t])
            if score > 0:
                scores.append((i, score))
        rankings.append(sorted(scores, key=lambda item: (-item[1], candidates[item[0]].id)))
    if mode in {"dense", "hybrid"}:
        try:
            vectors = dense_vectors(tuple(c.text for c in candidates))
            query_vector = local_encoder().encode([query], normalize_embeddings=True)[0]
            scores = vectors @ query_vector
        except (ImportError, OSError, RuntimeError) as exc:
            raise RuntimeError("Chưa có embedding đa ngôn ngữ cục bộ. Cấu hình COBRAQ_EMBEDDING_MODEL hoặc chọn keyword.") from exc
        rankings.append(sorted(((i, float(v)) for i, v in enumerate(scores) if v > 0),
                               key=lambda item: (-item[1], candidates[item[0]].id)))
    if mode == "hybrid":
        fused = Counter()
        for ranking in rankings:
            for rank, (i, _) in enumerate(ranking, 1):
                fused[i] += 1 / (60 + rank)
        ranking = sorted(fused.items(), key=lambda item: (-item[1], candidates[item[0]].id))
    else:
        ranking = rankings[0]
    return [{"chunk": candidates[i].model_dump(), "score": score, "mode": mode}
            for i, score in ranking[:top_k]]
