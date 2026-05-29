import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum

from ..core.config import get_settings

settings = get_settings()


class EventType(str, Enum):
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed_login"
    AUTH_REGISTER = "auth.register"
    QUIZ_START = "quiz.start"
    QUIZ_SUBMIT = "quiz.submit"
    FILE_UPLOAD = "file.upload"
    FILE_DELETE = "file.delete"
    QUESTION_CREATE = "question.create"
    QUESTION_UPDATE = "question.update"
    QUESTION_DELETE = "question.delete"
    TUTORING_QUERY = "tutoring.query"
    CONFIG_UPDATE = "config.update"


class AuditLogger:
    _log_path = Path("data/audit_log.jsonl")

    @classmethod
    def _ensure_dir(cls):
        cls._log_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def log(
        cls,
        event_type: str,
        user_id: str = "anonymous",
        role: str = "guest",
        resource: str = "",
        action: str = "",
        ip_address: str = "0.0.0.0",
        details: Optional[dict] = None,
    ):
        cls._ensure_dir()
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "user_id": user_id,
            "role": role,
            "resource": resource,
            "action": action,
            "ip_address": ip_address,
            "details": details or {},
        }
        with open(cls._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @classmethod
    def get_logs(cls, limit: int = 100, user_id: Optional[str] = None) -> list:
        cls._ensure_dir()
        if not cls._log_path.exists():
            return []
        logs = []
        with open(cls._log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    logs.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        if user_id:
            logs = [l for l in logs if l.get("user_id") == user_id]
        return logs[-limit:]


audit_log = AuditLogger()
