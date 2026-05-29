import json
from pathlib import Path
from typing import Optional


class GroupScores:
    """
    Store quiz results per group.
    file: data/group_scores.json
    Structure: { group_id: { file_id: { student_email: { session_id, score, percent, time_taken, answers, submitted_at } } } }
    """

    _path = Path("D:/CobraQ/backend/data/group_scores.json")

    @classmethod
    def _load(cls) -> dict:
        cls._path.parent.mkdir(parents=True, exist_ok=True)
        if not cls._path.exists():
            return {}
        try:
            with open(cls._path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    @classmethod
    def _save(cls, data: dict):
        cls._path.parent.mkdir(parents=True, exist_ok=True)
        with open(cls._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def save_score(cls, group_id: str, file_id: str, student_email: str, name: str, score_data: dict):
        data = cls._load()
        data.setdefault(group_id, {}).setdefault(file_id, {})[student_email] = {
            "name": name,
            "score": score_data.get("score"),
            "percent": score_data.get("percent"),
            "time_taken": score_data.get("time_taken"),
            "answers": score_data.get("answers", {}),
            "total_questions": score_data.get("total_questions"),
            "submitted_at": str(Path(__file__).resolve().parent.parent.parent.stat().st_ctime)[:10],
        }
        cls._save(data)

    @classmethod
    def get_student_scores(cls, group_id: str, file_id: str, student_email: str) -> dict:
        data = cls._load()
        return data.get(group_id, {}).get(file_id, {}).get(student_email, {})

    @classmethod
    def get_group_scores(cls, group_id: str, file_id: str) -> dict:
        data = cls._load()
        return data.get(group_id, {}).get(file_id, {})

    @classmethod
    def get_teacher_view(cls, group_id: str, file_id: str) -> list:
        raw_scores = cls.get_group_scores(group_id, file_id)
        return [
            {
                "email": email,
                "name": raw.get("name", email.split("@")[0]),
                "score": raw.get("score", 0),
                "percent": raw.get("percent", 0),
                "time_taken": raw.get("time_taken", 0),
                "total_questions": raw.get("total_questions", 0),
                "submitted_at": raw.get("submitted_at", ""),
            }
            for email, raw in raw_scores.items()
        ]


group_scores = GroupScores()
