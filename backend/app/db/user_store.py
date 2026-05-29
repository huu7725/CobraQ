import json
from pathlib import Path
from typing import Optional


class UserStore:
    """
    User store đơn giản dùng JSON file.
    Thay bằng SQL database khi mở rộng.
    """

    _path = Path("data/users_store.json")

    @classmethod
    def _ensure_dir(cls):
        cls._path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _load(cls) -> dict:
        cls._ensure_dir()
        if not cls._path.exists():
            return {}
        try:
            with open(cls._path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    @classmethod
    def _save(cls, data: dict):
        cls._ensure_dir()
        with open(cls._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_user(cls, email: str) -> Optional[dict]:
        users = cls._load()
        return users.get(email)

    @classmethod
    def create_user(cls, email: str, name: str, password_hash: str, role: str = "student") -> dict:
        users = cls._load()
        if email in users:
            raise ValueError(f"Email {email} đã được đăng ký")
        users[email] = {
            "email": email,
            "name": name,
            "password_hash": password_hash,
            "role": role,
            "created_at": str(Path(__file__).stat().st_ctime)[:10],
        }
        cls._save(users)
        return users[email]

    @classmethod
    def update_user(cls, email: str, updates: dict) -> Optional[dict]:
        users = cls._load()
        if email not in users:
            return None
        users[email].update(updates)
        cls._save(users)
        return users[email]

    @classmethod
    def get_all_users(cls) -> list[dict]:
        users = cls._load()
        return list(users.values())

    @classmethod
    def delete_user(cls, email: str) -> bool:
        users = cls._load()
        if email not in users:
            return False
        del users[email]
        cls._save(users)
        return True

    @classmethod
    def user_exists(cls, email: str) -> bool:
        return email in cls._load()

    @classmethod
    def list_by_role(cls, role: str) -> list[dict]:
        users = cls._load()
        return [u for u in users.values() if u.get("role") == role]

    @classmethod
    def count_by_role(cls) -> dict:
        users = cls._load()
        counts = {}
        for u in users.values():
            r = u.get("role", "unknown")
            counts[r] = counts.get(r, 0) + 1
        return counts


user_store = UserStore()
