"""
MapQuizQuestion model — individual question within a map quiz session.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, func
from app.db.database import Base


class MapQuizQuestion(Base):
    __tablename__ = "map_quiz_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("map_quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), default="multiple_choice")
    difficulty = Column(Integer, default=2)

    # JSON: [{"label": "A", "text": "..."}, ...]
    choices = Column(Text, nullable=False)
    correct_answer = Column(String(10), nullable=False)
    explanation = Column(Text, nullable=True)

    source_event_id = Column(Integer, ForeignKey("historical_events.id"), nullable=True)
    question_order = Column(Integer, nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        import json as _json
        return {
            "id": self.id,
            "session_id": self.session_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "difficulty": self.difficulty,
            "choices": _json.loads(self.choices) if self.choices else [],
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "source_event_id": self.source_event_id,
            "question_order": self.question_order,
        }
