import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class EvaluationEntry:
    session_id: str
    timestamp: str
    user_id: str
    role: str
    event_type: str
    question_id: Optional[str] = None
    query: Optional[str] = None
    response: Optional[str] = None
    student_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    time_taken_ms: int = 0
    ai_used: bool = False
    retrieval_chunks: list[str] = field(default_factory=list)
    hallucination_detected: bool = False
    citation_present: bool = False
    hallucination_rate: float = 0.0
    retrieval_score: float = 0.0
    details: dict = field(default_factory=dict)


class EvaluationLogger:
    """
    Logger cho evaluation pipeline.
    Ghi log structured events để tính metrics.
    """

    _log_path = Path("data/evaluation_logs.jsonl")

    @classmethod
    def _ensure_dir(cls):
        cls._log_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def log(cls, entry: EvaluationEntry):
        cls._ensure_dir()
        with open(cls._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    @classmethod
    def get_entries(cls, limit: int = 500, user_id: Optional[str] = None) -> list:
        cls._ensure_dir()
        if not cls._log_path.exists():
            return []
        entries = []
        with open(cls._log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        if user_id:
            entries = [e for e in entries if e.get("user_id") == user_id]
        return entries[-limit:]

    @classmethod
    def compute_metrics(cls, entries: list) -> dict:
        """
        Tính metrics từ evaluation entries.
        """
        if not entries:
            return {
                "total_events": 0,
                "hallucination_rate": 0.0,
                "citation_rate": 0.0,
                "quiz_accuracy": 0.0,
                "total_sessions": 0,
            }

        total = len(entries)
        hall_entries = [e for e in entries if isinstance(e, dict)]
        hall_rate = sum(1 for e in hall_entries if e.get("hallucination_detected")) / max(total, 1)
        citation_rate = sum(1 for e in hall_entries if e.get("citation_present")) / max(total, 1)

        quiz_entries = [e for e in hall_entries if e.get("event_type") in ("quiz_submit", "quiz_answer")]
        correct = sum(1 for e in quiz_entries if e.get("is_correct"))
        quiz_acc = correct / max(len(quiz_entries), 1)

        tutoring_entries = [e for e in hall_entries if e.get("event_type") == "tutoring_query"]
        avg_hall = sum(e.get("hallucination_rate", 0) for e in tutoring_entries) / max(len(tutoring_entries), 1)

        unique_sessions = set(e.get("session_id") for e in hall_entries if e.get("session_id"))

        return {
            "total_events": total,
            "hallucination_rate": round(avg_hall, 4),
            "citation_rate": round(citation_rate, 4),
            "quiz_accuracy": round(quiz_acc, 4),
            "total_sessions": len(unique_sessions),
            "quiz_count": len(quiz_entries),
            "tutoring_count": len(tutoring_entries),
        }


evaluation_logger = EvaluationLogger()
