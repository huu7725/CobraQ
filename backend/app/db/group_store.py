import json
from pathlib import Path
from typing import Optional
import secrets


class GroupStore:
    """
    Store for quiz groups (lớp học).
    Teachers create groups, get share codes, students join via codes.
    """

    _path = Path("D:/CobraQ/backend/data/groups.json")

    @classmethod
    def _ensure_dir(cls):
        cls._path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _load(cls) -> list:
        cls._ensure_dir()
        if not cls._path.exists():
            return []
        try:
            with open(cls._path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    @classmethod
    def _save(cls, data: list):
        cls._ensure_dir()
        with open(cls._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def _gen_code(cls) -> str:
        return secrets.token_hex(4).upper()

    @classmethod
    def create_group(cls, name: str, teacher_email: str, teacher_name: str) -> dict:
        groups = cls._load()
        code = cls._gen_code()
        while any(g["code"] == code for g in groups):
            code = cls._gen_code()
        group = {
            "id": code,
            "code": code,
            "name": name,
            "teacher_email": teacher_email,
            "teacher_name": teacher_name,
            "created_at": str(Path(__file__).resolve().parent.parent.parent.stat().st_ctime)[:10],
            "members": [],
            "files": [],
        }
        groups.append(group)
        cls._save(groups)
        return group

    @classmethod
    def get_group(cls, code: str) -> Optional[dict]:
        groups = cls._load()
        for g in groups:
            if g["code"] == code.upper():
                return g
        return None

    @classmethod
    def get_group_by_id(cls, group_id: str) -> Optional[dict]:
        groups = cls._load()
        for g in groups:
            if g["id"] == group_id:
                return g
        return None

    @classmethod
    def get_teacher_groups(cls, teacher_email: str) -> list:
        groups = cls._load()
        return [g for g in groups if g["teacher_email"] == teacher_email]

    @classmethod
    def get_student_groups(cls, student_email: str) -> list:
        groups = cls._load()
        return [g for g in groups if any(m["email"] == student_email for m in g.get("members", []))]

    @classmethod
    def add_member(cls, code: str, student_email: str, student_name: str) -> bool:
        groups = cls._load()
        for g in groups:
            if g["code"] == code.upper():
                if any(m["email"] == student_email for m in g["members"]):
                    return True
                g["members"].append({
                    "email": student_email,
                    "name": student_name,
                    "joined_at": str(Path(__file__).resolve().parent.parent.parent.stat().st_ctime)[:10],
                })
                cls._save(groups)
                return True
        return False

    @classmethod
    def remove_member(cls, code: str, student_email: str) -> bool:
        groups = cls._load()
        for g in groups:
            if g["code"] == code.upper():
                g["members"] = [m for m in g["members"] if m["email"] != student_email]
                cls._save(groups)
                return True
        return False

    @classmethod
    def add_file(cls, group_id: str, file_id: str, file_name: str, num_questions: int = 10, time_limit: int = 0) -> bool:
        groups = cls._load()
        for g in groups:
            if g["id"] == group_id:
                existing = next((f for f in g.get("files", []) if f["file_id"] == file_id), None)
                if existing:
                    existing["name"] = file_name
                    existing["num_questions"] = num_questions
                    existing["time_limit"] = time_limit
                else:
                    g.setdefault("files", []).append({
                        "file_id": file_id,
                        "name": file_name,
                        "added_at": str(Path(__file__).resolve().parent.parent.parent.stat().st_ctime)[:10],
                        "num_questions": num_questions,
                        "time_limit": time_limit,
                    })
                cls._save(groups)
                return True
        return False

    @classmethod
    def remove_file(cls, group_id: str, file_id: str) -> bool:
        groups = cls._load()
        for g in groups:
            if g["id"] == group_id:
                g["files"] = [f for f in g.get("files", []) if f["file_id"] != file_id]
                cls._save(groups)
                return True
        return False

    @classmethod
    def delete_group(cls, code: str, teacher_email: str) -> bool:
        groups = cls._load()
        for i, g in enumerate(groups):
            if g["code"] == code.upper() and g["teacher_email"] == teacher_email:
                groups.pop(i)
                cls._save(groups)
                return True
        return False

    @classmethod
    def update_group(cls, code: str, teacher_email: str, updates: dict) -> Optional[dict]:
        groups = cls._load()
        for g in groups:
            if g["code"] == code.upper() and g["teacher_email"] == teacher_email:
                g.update(updates)
                cls._save(groups)
                return g
        return None


group_store = GroupStore()
