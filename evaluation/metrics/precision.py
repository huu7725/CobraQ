"""
Quiz and answer precision metrics cho CobraQ evaluation pipeline.

Measures:
- Quiz Accuracy: % correct answers across all quiz sessions
- Answer Coverage: % questions that have an answer defined
- Per-session accuracy, score distribution, time-based trends
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from collections import defaultdict


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


def _load_audit_logs(path: Path, limit: int = 500, user_id: Optional[str] = None) -> list[dict]:
    """Load audit logs for quiz session data."""
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


def compute_quiz_accuracy(entries: list[dict]) -> float:
    """
    Compute overall quiz accuracy: % correct answers.

    Uses quiz_submit events from evaluation logs.
    """
    quiz_submits = [
        e for e in entries
        if e.get("event_type") in ("quiz_submit", "quiz_answer")
        and e.get("is_correct") is not None
    ]
    if not quiz_submits:
        return 0.0
    correct = sum(1 for e in quiz_submits if e.get("is_correct", False))
    return round(correct / len(quiz_submits), 4)


def compute_answer_coverage(entries: list[dict]) -> float:
    """
    Compute answer coverage: % questions that have an answer defined.
    Derived from quiz entries with known correct_answer.
    """
    answered = [
        e for e in entries
        if e.get("event_type") in ("quiz_submit", "quiz_answer")
        and e.get("correct_answer")
    ]
    total = [
        e for e in entries
        if e.get("event_type") in ("quiz_submit", "quiz_answer")
    ]
    if not total:
        return 0.0
    return round(len(answered) / len(total), 4)


def compute_session_accuracies(entries: list[dict]) -> list[dict]:
    """
    Compute per-session accuracy stats.
    Groups entries by session_id.
    """
    sessions: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        sid = e.get("session_id", "unknown")
        if e.get("event_type") in ("quiz_submit", "quiz_answer"):
            sessions[sid].append(e)

    result = []
    for sid, session_entries in sessions.items():
        correct = sum(1 for e in session_entries if e.get("is_correct", False))
        total = len(session_entries)
        time_taken = max((e.get("time_taken_ms", 0) for e in session_entries), default=0)
        result.append({
            "session_id": sid,
            "accuracy": round(correct / total, 4) if total > 0 else 0.0,
            "correct": correct,
            "total": total,
            "time_taken_ms": time_taken,
            "ai_used": any(e.get("ai_used", False) for e in session_entries),
        })

    return sorted(result, key=lambda x: x["session_id"], reverse=True)


def compute_score_distribution(entries: list[dict]) -> dict:
    """
    Compute score distribution buckets (0-20%, 20-40%, 40-60%, 60-80%, 80-100%).

    Groups quiz sessions by percentage score.
    """
    sessions = compute_session_accuracies(entries)
    if not sessions:
        return {"buckets": {}, "avg_score": 0.0, "median_score": 0.0}

    scores = [s["accuracy"] * 100 for s in sessions]
    buckets = {"0-20%": 0, "20-40%": 0, "40-60%": 0, "60-80%": 0, "80-100%": 0}
    for score in scores:
        if score < 20:
            buckets["0-20%"] += 1
        elif score < 40:
            buckets["20-40%"] += 1
        elif score < 60:
            buckets["40-60%"] += 1
        elif score < 80:
            buckets["60-80%"] += 1
        else:
            buckets["80-100%"] += 1

    sorted_scores = sorted(scores)
    mid = len(sorted_scores) // 2
    median = sorted_scores[mid] if sorted_scores else 0.0

    return {
        "buckets": buckets,
        "avg_score": round(sum(scores) / len(scores), 2),
        "median_score": round(median, 2),
        "best_score": round(max(scores), 2) if scores else 0.0,
        "worst_score": round(min(scores), 2) if scores else 0.0,
        "total_sessions": len(sessions),
    }


def compute_role_performance(entries: list[dict]) -> dict:
    """
    Break down quiz accuracy by user role.
    """
    role_stats: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})

    for e in entries:
        if e.get("event_type") in ("quiz_submit", "quiz_answer") and e.get("is_correct") is not None:
            role = e.get("role", "unknown")
            role_stats[role]["total"] += 1
            if e.get("is_correct", False):
                role_stats[role]["correct"] += 1

    result = {}
    for role, stats in role_stats.items():
        total = stats["total"]
        result[role] = {
            "accuracy": round(stats["correct"] / total, 4) if total > 0 else 0.0,
            "correct": stats["correct"],
            "total": total,
        }
    return result


def compute_improvement_trend(entries: list[dict]) -> dict:
    """
    Compute improvement trend: compare first-half vs second-half session accuracies.
    """
    sessions = compute_session_accuracies(entries)
    if len(sessions) < 4:
        return {"trend": "insufficient_data", "sessions_needed": 4}

    half = len(sessions) // 2
    first_half = sessions[:half]
    second_half = sessions[half:]

    first_avg = sum(s["accuracy"] for s in first_half) / len(first_half)
    second_avg = sum(s["accuracy"] for s in second_half) / len(second_half)
    diff = second_avg - first_avg

    return {
        "first_half_avg": round(first_avg, 4),
        "second_half_avg": round(second_avg, 4),
        "improvement": round(diff, 4),
        "trend": "improving" if diff > 0.05 else ("declining" if diff < -0.05 else "stable"),
    }


def get_all_quiz_metrics(entries: list[dict]) -> dict:
    """Compute all quiz precision metrics."""
    return {
        "quiz_accuracy": compute_quiz_accuracy(entries),
        "answer_coverage": compute_answer_coverage(entries),
        "score_distribution": compute_score_distribution(entries),
        "role_performance": compute_role_performance(entries),
        "improvement_trend": compute_improvement_trend(entries),
    }


def generate_quiz_report(
    eval_log_path: Path,
    audit_log_path: Path,
    limit: int = 500,
    user_id: Optional[str] = None,
) -> dict:
    """Full quiz precision report from evaluation and audit logs."""
    eval_entries = _load_eval_logs(eval_log_path, limit, user_id)
    audit_entries = _load_audit_logs(audit_log_path, limit, user_id)

    metrics = get_all_quiz_metrics(eval_entries)

    # Merge audit log quiz events
    audit_quiz = [
        e for e in audit_entries
        if e.get("event_type") in ("quiz.start", "quiz.submit")
    ]

    return {
        **metrics,
        "audit_events": len(audit_quiz),
        "total_eval_entries": len(eval_entries),
        "total_audit_entries": len(audit_entries),
    }
