"""
MapQuizSession model — tracks an AI-generated quiz session derived from map events.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func
from app.db.database import Base


class MapQuizSession(Base):
    __tablename__ = "map_quiz_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    session_token = Column(String(100), unique=True, nullable=False, index=True)

    # Configuration
    source_type = Column(String(20), default="map_events")
    source_scope = Column(String(500), nullable=True)  # JSON: region/period filter

    # Quiz params
    num_questions_requested = Column(Integer, nullable=False)
    num_questions_generated = Column(Integer, default=0)
    time_limit_minutes = Column(Integer, nullable=True)
    difficulty_level = Column(Integer, default=2)

    # The events user has viewed (JSON array of event IDs)
    context_event_ids = Column(String(1000), nullable=False)

    # AI metadata
    ai_model_used = Column(String(100), nullable=True)
    ai_prompt_tokens = Column(Integer, nullable=True)
    ai_completion_tokens = Column(Integer, nullable=True)
    generation_time_ms = Column(Integer, nullable=True)

    # Timing
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)

    # Result
    score = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    percentage = Column(Float, default=0.0)

    is_completed = Column(Boolean, default=False)
    is_submitted = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "session_token": self.session_token,
            "source_type": self.source_type,
            "num_questions_requested": self.num_questions_requested,
            "num_questions_generated": self.num_questions_generated,
            "time_limit_minutes": self.time_limit_minutes,
            "difficulty_level": self.difficulty_level,
            "score": self.score,
            "total_questions": self.total_questions,
            "percentage": self.percentage,
            "is_completed": self.is_completed,
            "is_submitted": self.is_submitted,
            "started_at": str(self.started_at) if self.started_at else None,
            "completed_at": str(self.completed_at) if self.completed_at else None,
        }
