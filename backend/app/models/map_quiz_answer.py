"""
MapQuizAnswer model — tracks a user's answer to a specific question in a map quiz.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func, UniqueConstraint
from app.db.database import Base


class MapQuizAnswer(Base):
    __tablename__ = "map_quiz_answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("map_quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("map_quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    selected_choice = Column(String(10), nullable=True)
    is_correct = Column(Boolean, default=False)
    time_spent_seconds = Column(Integer, nullable=True)

    answered_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_session_question"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "question_id": self.question_id,
            "user_id": self.user_id,
            "selected_choice": self.selected_choice,
            "is_correct": self.is_correct,
            "time_spent_seconds": self.time_spent_seconds,
            "answered_at": str(self.answered_at) if self.answered_at else None,
        }
