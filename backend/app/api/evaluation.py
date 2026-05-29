import sys as _sys
from pathlib import Path as _Path
_proj_root = _Path(__file__).resolve().parents[2]
if str(_proj_root) not in _sys.path:
    _sys.path.insert(0, str(_proj_root))

from fastapi import APIRouter, Header, Depends
from pathlib import Path
from typing import Optional

from ..core.security import get_current_user_optional
from ..services.evaluation import evaluation_logger

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/metrics")
def get_metrics(
    limit: int = 100,
    x_user_id: str = Header(default="guest"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = (current_user.get("sub") if current_user else None) or x_user_id
    entries = evaluation_logger.get_entries(limit=limit, user_id=uid)
    metrics = evaluation_logger.compute_metrics(entries)

    from collections import defaultdict
    sessions: dict = defaultdict(lambda: {"correct": 0, "total": 0, "time_taken_ms": 0, "ai_used": False})
    for e in entries:
        sid = e.get("session_id", "unknown")
        if e.get("event_type") in ("quiz_submit", "quiz_answer"):
            sessions[sid]["total"] += 1
            sessions[sid]["time_taken_ms"] = max(sessions[sid]["time_taken_ms"], e.get("time_taken_ms", 0))
            if e.get("is_correct"):
                sessions[sid]["correct"] += 1
            if e.get("ai_used"):
                sessions[sid]["ai_used"] = True

    session_list = []
    for sid, s in sessions.items():
        acc = s["correct"] / s["total"] if s["total"] > 0 else 0
        session_list.append({
            "session_id": sid, "accuracy": acc,
            "correct": s["correct"], "total": s["total"],
            "time_taken_ms": s["time_taken_ms"], "ai_used": s["ai_used"],
        })
    session_list.sort(key=lambda x: x["session_id"], reverse=True)

    return {
        "metrics": metrics,
        "sessions": session_list,
        "total_entries": len(entries),
    }


@router.get("/logs")
def get_eval_logs(
    limit: int = 100,
    x_user_id: str = Header(default="guest"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = (current_user.get("sub") if current_user else None) or x_user_id
    return {"logs": evaluation_logger.get_entries(limit=limit, user_id=uid)}


@router.get("/hallucination")
def get_hallucination_metrics(
    limit: int = 500,
    x_user_id: str = Header(default="guest"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = (current_user.get("sub") if current_user else None) or x_user_id
    log_path = Path("data/evaluation_logs.jsonl")
    try:
        from evaluation.metrics.hallucination import generate_hallucination_report
        return generate_hallucination_report(log_path, limit=limit, user_id=uid if uid != "guest" else None)
    except ImportError:
        return {"status": "unavailable", "message": "evaluation module not installed", "entries": []}


@router.get("/retrieval")
def get_retrieval_metrics(
    limit: int = 500,
    x_user_id: str = Header(default="guest"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = (current_user.get("sub") if current_user else None) or x_user_id
    log_path = Path("data/evaluation_logs.jsonl")
    try:
        from evaluation.metrics.retrieval import generate_retrieval_report
        return generate_retrieval_report(log_path, limit=limit, user_id=uid if uid != "guest" else None)
    except ImportError:
        return {"status": "unavailable", "message": "evaluation module not installed", "entries": []}
