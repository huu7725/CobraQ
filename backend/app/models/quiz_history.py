"""
QuizHistory model — unified quiz history for both map and document quiz types.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from app.db.database import Base


class QuizHistory(Base):
    __tablename__ = "quiz_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quiz_type = Column(String(20), nullable=False)  # "map" or "document"
    quiz_session_id = Column(Integer, nullable=True)

    score = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)
    time_taken_seconds = Column(Integer, nullable=True)

    difficulty_level = Column(Integer, nullable=True)
    tags = Column(String(500), nullable=True)

    completed_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "quiz_type": self.quiz_type,
            "quiz_session_id": self.quiz_session_id,
            "score": self.score,
            "total_questions": self.total_questions,
            "percentage": self.percentage,
            "time_taken_seconds": self.time_taken_seconds,
            "difficulty_level": self.difficulty_level,
            "tags": self.tags,
            "completed_at": str(self.completed_at) if self.completed_at else None,
        }
