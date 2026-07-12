"""
UserMapProgress model — tracks which historical events a user has viewed.
This is the "learning memory" that powers the Map-based AI Quiz.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func, UniqueConstraint
from app.db.database import Base


class UserMapProgress(Base):
    __tablename__ = "user_map_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("historical_events.id", ondelete="CASCADE"), nullable=False, index=True)

    # Interaction quality
    view_duration_seconds = Column(Integer, default=0)
    scrolled_to_content = Column(Boolean, default=False)
    watched_video = Column(Boolean, default=False)

    # Session grouping
    session_id = Column(String(100), nullable=True, index=True)

    viewed_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "event_id", "session_id", name="uq_user_event_session"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_id": self.event_id,
            "view_duration_seconds": self.view_duration_seconds,
            "scrolled_to_content": self.scrolled_to_content,
            "watched_video": self.watched_video,
            "session_id": self.session_id,
            "viewed_at": str(self.viewed_at) if self.viewed_at else None,
        }
