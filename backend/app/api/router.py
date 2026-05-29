from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.security import HTTPBearer
import json, re
from pathlib import Path

from pathlib import Path
import os

# Absolute path — avoid Path.resolve() case issues on Windows
_DATA_ROOT = Path("D:/CobraQ/backend/data")
USERS_DIR = _DATA_ROOT / "users"
from .auth import router as auth_router
from .quiz import router as quiz_router
from .files import router as files_router
from .config import router as config_router
from .tutoring import router as tutoring_router
from .evaluation import router as evaluation_router
from .users import router as users_router
from .admin import router as admin_router
from .groups import router as groups_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(quiz_router)
api_router.include_router(files_router)
api_router.include_router(config_router)
api_router.include_router(tutoring_router)
api_router.include_router(evaluation_router)
api_router.include_router(users_router)
api_router.include_router(admin_router)
api_router.include_router(groups_router)


# ── Stats endpoint (ghép từ main_updated.py) ──
def user_dir(uid):
    d = USERS_DIR / re.sub(r"[^\w]", "_", uid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_json(path, default):
    try:
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def files_index_path(uid): return user_dir(uid) / "files_index.json"
def history_path(uid):     return user_dir(uid) / "history.json"


@api_router.get("/stats")
def get_stats(x_user_id: str = Header(default="guest"),
              authorization: str = Header(default="")):
    if authorization:
        try:
            from ..core.security import decode_token
            token_data = decode_token(authorization.replace("Bearer ", ""))
            uid = token_data.get("sub") or x_user_id
        except Exception:
            uid = x_user_id
    else:
        uid = x_user_id
    try:
        index = load_json(files_index_path(uid), {})
        return {
            "total_questions": sum(f.get("count", 0) for f in index.values()),
            "with_answer": sum(f.get("with_answer", 0) for f in index.values()),
            "total_sessions": 0,
            "avg_score": 0,
            "best_score": 0,
            "ai_available": True,
            "ai_enabled": True,
            "files": [
                {"id": fid, "name": f.get("name", ""), "count": f.get("count", 0),
                 "with_answer": f.get("with_answer", 0), "uploaded_at": f.get("uploaded_at", ""),
                 "parse_method": f.get("parse_method", "normal")}
                for fid, f in index.items()
            ]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))


@api_router.get("/history")
def get_history(x_user_id: str = Header(default="guest"),
                 authorization: str = Header(default="")):
    if authorization:
        try:
            from ..core.security import decode_token
            token_data = decode_token(authorization.replace("Bearer ", ""))
            uid = token_data.get("sub") or x_user_id
        except Exception:
            uid = x_user_id
    else:
        uid = x_user_id
    return load_json(history_path(uid), [])


@api_router.delete("/history/clear")
def clear_history(x_user_id: str = Header(default="guest"),
                   authorization: str = Header(default="")):
    if authorization:
        try:
            from ..core.security import decode_token
            token_data = decode_token(authorization.replace("Bearer ", ""))
            uid = token_data.get("sub") or x_user_id
        except Exception:
            uid = x_user_id
    else:
        uid = x_user_id
    hp = history_path(uid)
    hp.write_text("[]", encoding="utf-8")
    return {"message": "Đã xóa lịch sử"}
