"""
Retrieval quality metrics cho CobraQ evaluation pipeline.

Measures:
- MRR (Mean Reciprocal Rank): average 1/rank of first relevant result
- HitRate@k: % queries with at least one relevant result in top-k
- Precision@k: fraction of retrieved results that are relevant
- NDCG@k: normalized discounted cumulative gain (ideal ranking quality)
"""

from __future__ import annotations
import json
import math
from pathlib import Path
from typing import Optional


def _load_eval_logs(path: Path, limit: int = 500, user_id: Optional[str] = None) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    if user_id:
        entries = [e for e in entries if e.get("user_id") == user_id]
    return entries[-limit:]


def compute_mrr(retrieval_results: list[tuple[int, float]]) -> float:
    """
    Compute Mean Reciprocal Rank.

    Args:
        retrieval_results: list of (rank, score) tuples, sorted by rank.
                          rank starts at 1. Empty list = 0.

    Returns:
        MRR score (0.0 to 1.0)
    """
    if not retrieval_results:
        return 0.0
    ranks = [r for r, _ in retrieval_results if r > 0]
    if not ranks:
        return 0.0
    reciprocal_ranks = [1.0 / r for r in ranks]
    return round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4)


def compute_hit_rate_k(retrieval_results: list[tuple[int, float]], k: int = 5) -> float:
    """
    Compute HitRate@k: % queries where relevant item appears in top-k.

    Args:
        retrieval_results: list of (rank, score) tuples
        k: cutoff rank

    Returns:
        Hit rate (0.0 to 1.0)
    """
    if not retrieval_results:
        return 0.0
    hits = sum(1 for rank, _ in retrieval_results if 0 < rank <= k)
    return round(hits / len(retrieval_results), 4)


def compute_precision_k(retrieval_results: list[tuple[int, float]], k: int = 5) -> float:
    """
    Compute Precision@k: fraction of top-k results that are relevant.

    Args:
        retrieval_results: list of (rank, score) tuples
        k: cutoff rank

    Returns:
        Precision@k (0.0 to 1.0)
    """
    top_k = [(r, s) for r, s in retrieval_results if 0 < r <= k]
    if not top_k:
        return 0.0
    relevant = sum(1 for rank, _ in top_k if rank > 0)
    return round(relevant / k, 4)


def compute_ndcg_k(retrieval_results: list[tuple[int, float]], k: int = 5) -> float:
    """
    Compute NDCG@k (Normalized Discounted Cumulative Gain).

    Args:
        retrieval_results: list of (rank, score) tuples, sorted by rank.
                          relevance = 1 if rank > 0, else 0.

    Returns:
        NDCG@k (0.0 to 1.0)
    """
    def dcg(gains: list[float]) -> float:
        return sum(g / math.log2(i + 2) for i, g in enumerate(gains))

    gains = [1.0 if 0 < r <= k else 0.0 for r, _ in retrieval_results[:k]]
    ideal_gains = sorted([1.0 if 0 < r <= k else 0.0 for r, _ in retrieval_results], reverse=True)[:k]

    dcg_val = dcg(gains)
    idcg_val = dcg(ideal_gains)

    if idcg_val == 0:
        return 0.0
    return round(dcg_val / idcg_val, 4)


def rank_chunks_by_keyword(query: str, chunks: list[str]) -> list[tuple[int, float]]:
    """
    Rank chunks by keyword overlap score (BM25-lite approximation).
    Returns list of (rank, score) where rank is position in sorted list (1-indexed).
    """
    query_terms = set(query.lower().split())
    if not query_terms:
        return []

    scored = []
    for i, chunk in enumerate(chunks):
        chunk_terms = set(chunk.lower().split())
        if not chunk_terms:
            scored.append((0, 0.0))
            continue
        overlap = len(query_terms & chunk_terms)
        score = overlap / max(len(query_terms), 1)
        scored.append((i + 1, round(score, 4)))

    # Sort by score descending, assign rank
    sorted_scores = sorted(scored, key=lambda x: x[1], reverse=True)
    return [(i + 1, s) for i, (_, s) in enumerate(sorted_scores)]


def compute_retrieval_metrics_for_entry(
    query: str,
    retrieved_chunk_ids: list[str],
    all_chunk_ids: list[str],
    ground_truth_relevant: set[str],
) -> dict:
    """
    Compute all retrieval metrics for a single query.

    Args:
        query: the user query string
        retrieved_chunk_ids: ordered list of chunk IDs returned by retrieval
        all_chunk_ids: all chunk IDs in the corpus
        ground_truth_relevant: set of chunk IDs that are actually relevant

    Returns:
        dict with mrr, hit_rate_1/3/5, precision_1/3/5, ndcg_5
    """
    # Build rank map for retrieved chunks
    rank_map = {}
    for i, cid in enumerate(retrieved_chunk_ids):
        rank_map[cid] = i + 1

    # Build result list: (rank, score=1 if relevant)
    results = []
    for cid in retrieved_chunk_ids:
        rank = rank_map.get(cid, 0)
        score = 1.0 if cid in ground_truth_relevant else 0.0
        results.append((rank, score))

    # Add non-retrieved relevant chunks with rank = len(retrieved) + 1 (not retrieved)
    for cid in ground_truth_relevant:
        if cid not in rank_map:
            results.append((0, 1.0))

    mrr = compute_mrr(results)
    hit_1 = compute_hit_rate_k(results, 1)
    hit_3 = compute_hit_rate_k(results, 3)
    hit_5 = compute_hit_rate_k(results, 5)
    p_1 = compute_precision_k(results, 1)
    p_3 = compute_precision_k(results, 3)
    p_5 = compute_precision_k(results, 5)
    ndcg_5 = compute_ndcg_k(results, 5)

    return {
        "mrr": mrr,
        "hit_rate_1": hit_1,
        "hit_rate_3": hit_3,
        "hit_rate_5": hit_5,
        "precision_1": p_1,
        "precision_3": p_3,
        "precision_5": p_5,
        "ndcg_5": ndcg_5,
        "num_retrieved": len(retrieved_chunk_ids),
        "num_relevant": len(ground_truth_relevant),
        "recall": round(len(retrieved_chunk_ids & ground_truth_relevant) / max(len(ground_truth_relevant), 1), 4),
    }


def aggregate_retrieval_metrics(per_query_metrics: list[dict]) -> dict:
    """Aggregate per-query retrieval metrics into dataset-level summary."""
    if not per_query_metrics:
        return {
            "mrr": 0.0, "hit_rate_1": 0.0, "hit_rate_3": 0.0, "hit_rate_5": 0.0,
            "precision_1": 0.0, "precision_3": 0.0, "precision_5": 0.0, "ndcg_5": 0.0,
            "recall": 0.0, "total_queries": 0,
        }

    def avg(key):
        vals = [m[key] for m in per_query_metrics if key in m]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    return {
        "mrr": avg("mrr"),
        "hit_rate_1": avg("hit_rate_1"),
        "hit_rate_3": avg("hit_rate_3"),
        "hit_rate_5": avg("hit_rate_5"),
        "precision_1": avg("precision_1"),
        "precision_3": avg("precision_3"),
        "precision_5": avg("precision_5"),
        "ndcg_5": avg("ndcg_5"),
        "recall": avg("recall"),
        "total_queries": len(per_query_metrics),
    }


def generate_retrieval_report(log_path: Path, limit: int = 500, user_id: Optional[str] = None) -> dict:
    """
    Generate retrieval metrics report from evaluation logs.

    Since ground_truth_relevant isn't stored in logs, we approximate:
    - Relevant = chunks retrieved at rank > 0 AND citation_present == True
    - Non-relevant = retrieved chunks where response was blocked (hallucination_detected == True)
    """
    entries = _load_eval_logs(log_path, limit, user_id)
    tutoring = [e for e in entries if e.get("event_type") == "tutoring_query"]

    per_query = []
    for entry in tutoring:
        retrieved_ids = entry.get("retrieval_chunks", [])
        if not retrieved_ids:
            continue
        # Approximate: if citation_present=True and not blocked, treat as relevant
        is_relevant = entry.get("citation_present", False) and not entry.get("hallucination_detected", False)
        results = [(i + 1, 1.0 if is_relevant else 0.0) for i in range(len(retrieved_ids))]
        mrr = compute_mrr(results)
        hit_5 = compute_hit_rate_k(results, 5)
        per_query.append({"mrr": mrr, "hit_rate_5": hit_5, "retrieved": retrieved_ids})

    agg = aggregate_retrieval_metrics(per_query)

    return {
        **agg,
        "per_query_sample": per_query[:20],
        "total_tutoring_queries": len(tutoring),
    }
