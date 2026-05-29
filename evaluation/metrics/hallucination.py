"""
Hallucination detection metrics cho CobraQ evaluation pipeline.

Measures:
- Hallucination Rate: % words in response not grounded in retrieved chunks
- Citation Rate: % responses that include at least one citation
- Block Rate: % queries blocked by trust layer
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


# Stop-words to exclude from hallucination detection
_STOP_WORDS = {
    "tôi", "bạn", "của", "và", "là", "có", "được", "trong", "này",
    "để", "với", "cho", "không", "thì", "các", "những", "về", "ra",
    "vào", "từ", "đã", "một", "theo", "cũng", "hay", "như", "hơn",
    "hoặc", "nên", "khi", "đó", "nếu", "rằng", "còn", "đều", "qua",
    "chỉ", "sẽ", "lại", "biết", "nào", "họ", "năm", "bởi", "đến",
    "vì", "sao", "đâu", "gì", "ai", "ấy", "ở", "trên", "dưới",
    "trước", "sau", "bây", "giờ", "chưa", "rồi", "muốn", "cần",
    "có thể", "phải", "nữa", "mà", "vẫn", "đang", "rất", "quá",
    "theo", "như", "nhưng", "vậy", "thế", "kia", "lúc", "đây",
}


def _load_eval_logs(path: Path, limit: int = 500, user_id: Optional[str] = None) -> list[dict]:
    """Load evaluation logs from JSONL file."""
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


def _content_words(text: str) -> set[str]:
    """Extract meaningful words from text (exclude stop-words, short words)."""
    words = set()
    for w in text.lower().split():
        w = w.strip(".,!?;:\"'()[]{}-–—")
        if len(w) > 2 and w not in _STOP_WORDS:
            words.add(w)
    return words


def compute_hallucination_rate(response: str, chunks: list[str]) -> float:
    """
    Compute hallucination rate: fraction of response words not in any chunk.

    Args:
        response: AI-generated response text
        chunks: list of source chunk texts

    Returns:
        Float between 0.0 (no hallucination) and 1.0 (fully hallucinated)
    """
    if not response or not response.strip():
        return 1.0

    response_words = _content_words(response)
    if not response_words:
        return 0.0

    grounded_words = set()
    for chunk in chunks:
        grounded_words |= _content_words(chunk)

    hallucinated = response_words - grounded_words
    return round(len(hallucinated) / len(response_words), 4)


def compute_citation_rate(entries: list[dict]) -> float:
    """
    Compute citation rate: % entries with at least one citation.

    Args:
        entries: list of evaluation log entries

    Returns:
        Float between 0.0 and 1.0
    """
    if not entries:
        return 0.0
    cited = sum(1 for e in entries if e.get("citation_present", False))
    return round(cited / len(entries), 4)


def compute_block_rate(entries: list[dict]) -> float:
    """
    Compute block rate: % queries blocked by trust layer.

    Args:
        entries: list of evaluation log entries (event_type == "tutoring_query")

    Returns:
        Float between 0.0 and 1.0
    """
    tutoring = [e for e in entries if e.get("event_type") == "tutoring_query"]
    if not tutoring:
        return 0.0
    blocked = sum(1 for e in tutoring if e.get("hallucination_detected", False))
    return round(blocked / len(tutoring), 4)


def compute_avg_hallucination(entries: list[dict]) -> float:
    """
    Compute average hallucination rate across tutoring entries.
    Falls back to per-entry hallucination_rate field if chunks unavailable.
    """
    tutoring = [e for e in entries if e.get("event_type") == "tutoring_query"]
    if not tutoring:
        return 0.0
    rates = [e.get("hallucination_rate", 0.0) for e in tutoring]
    return round(sum(rates) / len(rates), 4)


def compute_citation_diversity(entries: list[dict], max_cite: int = 10) -> dict:
    """
    Compute citation diversity: distribution of how many citations per response.

    Returns:
        Dict with count distribution and stats
    """
    tutoring = [e for e in entries if e.get("event_type") == "tutoring_query"]
    if not tutoring:
        return {"avg": 0.0, "min": 0, "max": 0, "distribution": {}}

    counts = [len(e.get("retrieval_chunks", [])) for e in tutoring]
    dist = {}
    for c in counts:
        key = str(min(c, max_cite))
        dist[key] = dist.get(key, 0) + 1

    return {
        "avg": round(sum(counts) / len(counts), 2),
        "min": min(counts),
        "max": max(counts),
        "distribution": dist,
    }


def get_all_metrics(entries: list[dict]) -> dict:
    """
    Compute all hallucination-related metrics from evaluation entries.

    Returns:
        Dict with hallucination_rate, citation_rate, block_rate,
        citation_diversity, and per-event-type breakdowns.
    """
    tutoring = [e for e in entries if e.get("event_type") == "tutoring_query"]
    all_events = entries

    return {
        "hallucination_rate": compute_avg_hallucination(all_events),
        "citation_rate": compute_citation_rate(all_events),
        "block_rate": compute_block_rate(all_events),
        "citation_diversity": compute_citation_diversity(all_events),
        "tutoring_query_count": len(tutoring),
        "total_entries": len(all_events),
    }


def generate_hallucination_report(log_path: Path, limit: int = 500, user_id: Optional[str] = None) -> dict:
    """
    Full hallucination report from evaluation logs file.

    Args:
        log_path: path to data/evaluation_logs.jsonl
        limit: max number of entries to read
        user_id: filter by user (None = all users)

    Returns:
        Report dict with all metrics and high-hallucination entries
    """
    entries = _load_eval_logs(log_path, limit, user_id)
    metrics = get_all_metrics(entries)

    # Flag high-hallucination entries
    tutoring = [e for e in entries if e.get("event_type") == "tutoring_query"]
    high_hall = sorted(
        [e for e in tutoring if e.get("hallucination_rate", 0) > 0.3],
        key=lambda x: x.get("hallucination_rate", 0),
        reverse=True,
    )[:20]

    metrics["high_hallucination_entries"] = [
        {
            "session_id": e.get("session_id", ""),
            "query": (e.get("query") or "")[:100],
            "hallucination_rate": e.get("hallucination_rate", 0),
            "citation_present": e.get("citation_present", False),
        }
        for e in high_hall
    ]

    return metrics
