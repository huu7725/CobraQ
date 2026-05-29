"""
Admin dashboard endpoints — admin only.
System-wide statistics across all users.
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pathlib import Path
import json

from ..core.security import get_current_user, Role
from ..core.audit import audit_log, EventType
from ..db.user_store import user_store

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_admin(current_user: dict):
    if current_user.get("role") != Role.ADMIN.value:
        raise HTTPException(403, "Chỉ quản trị viên mới có quyền truy cập")


def load_json(path, default):
    try:
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def user_dir(uid):
    return Path("data/users") / uid.replace("[^\w]", "_")


def files_index_path(uid): return user_dir(uid) / "files_index.json"
def history_path(uid):     return user_dir(uid) / "history.json"


@router.get("/stats")
def admin_stats(
    current_user: dict = Depends(get_current_user),
):
    """
    System-wide statistics across all users.
    """
    _check_admin(current_user)

    all_users = user_store.get_all_users()
    role_counts = user_store.count_by_role()

    total_users = len(all_users)
    total_files = 0
    total_questions = 0
    total_sessions = 0
    total_correct = 0
    total_answered = 0

    user_stats = []

    for u in all_users:
        email = u["email"]
        index = load_json(files_index_path(email), {})
        history = load_json(history_path(email), [])

        u_files = len(index)
        u_questions = sum(f["count"] for f in index.values())
        u_sessions = len(history)
        u_correct = sum(h["score"] for h in history)
        u_total = sum(h["total"] for h in history)

        total_files += u_files
        total_questions += u_questions
        total_sessions += u_sessions
        total_correct += u_correct
        total_answered += u_total

        user_stats.append({
            "email": email,
            "name": u["name"],
            "role": u["role"],
            "files": u_files,
            "questions": u_questions,
            "sessions": u_sessions,
            "avg_score": round(u_correct / u_total * 100) if u_total > 0 else 0,
        })

    # Sort by sessions desc
    user_stats.sort(key=lambda x: x["sessions"], reverse=True)

    audit_log.log(
        EventType.CONFIG_UPDATE,
        user_id=current_user.get("sub"),
        role=current_user.get("role"),
        details={"action": "view_admin_stats"},
    )

    return {
        "total_users": total_users,
        "role_counts": role_counts,
        "total_files": total_files,
        "total_questions": total_questions,
        "total_sessions": total_sessions,
        "overall_accuracy": round(total_correct / total_answered * 100) if total_answered > 0 else 0,
        "user_stats": user_stats,
    }


@router.get("/audit")
def admin_audit_logs(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """View audit logs — admin only."""
    _check_admin(current_user)

    audit_path = Path("data/audit_log.jsonl")
    if not audit_path.exists():
        return {"logs": [], "total": 0}

    entries = []
    with open(audit_path, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

    entries = entries[-limit:]
    return {"logs": entries, "total": len(entries)}


@router.get("/activity")
def admin_activity_summary(
    days: int = 7,
    current_user: dict = Depends(get_current_user),
):
    """
    Daily activity summary for the last N days.
    """
    _check_admin(current_user)

    all_users = user_store.get_all_users()
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=days)
    daily_data = {}

    for u in all_users:
        history = load_json(history_path(u["email"]), [])
        for h in history:
            try:
                date_str = h.get("date", "")
                if "/" in date_str:
                    d = datetime.strptime(date_str, "%d/%m/%Y %H:%M")
                elif "-" in date_str:
                    d = datetime.strptime(date_str[:10], "%Y-%m-%d")
                else:
                    continue
                if d >= cutoff:
                    key = d.strftime("%Y-%m-%d")
                    if key not in daily_data:
                        daily_data[key] = {"sessions": 0, "correct": 0, "total": 0}
                    daily_data[key]["sessions"] += 1
                    daily_data[key]["correct"] += h.get("score", 0)
                    daily_data[key]["total"] += h.get("total", 0)
            except Exception:
                continue

    sorted_days = sorted(daily_data.keys())
    return {
        "days": sorted_days,
        "data": [daily_data[d] for d in sorted_days],
        "period_days": days,
    }
