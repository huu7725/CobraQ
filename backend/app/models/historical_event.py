"""
Historical Event model — events displayed as markers on the interactive Vietnam map.
"""
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey, func, UniqueConstraint
from app.db.database import Base


class HistoricalEvent(Base):
    __tablename__ = "historical_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    short_description = Column(Text, nullable=False)
    full_content = Column(Text, nullable=False)

    # Time
    event_date = Column(Date, nullable=True)
    year_range = Column(String(50), nullable=True)
    period = Column(String(100), nullable=True)  # e.g. "Nhà Trần", "Pháp thuộc"

    # Geography
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    region = Column(String(100), nullable=True)  # e.g. "Miền Bắc", "Miền Trung"

    # Classification
    event_type = Column(String(50), default="battle")
    difficulty_level = Column(Integer, default=1)

    # Media
    image_url = Column(Text, nullable=True)
    image_caption = Column(Text, nullable=True)
    video_url = Column(Text, nullable=True)

    # Relationships & metadata
    tags = Column(Text, nullable=True)           # JSON array stored as text
    related_event_ids = Column(Text, nullable=True)  # JSON array
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_marker_dict(self):
        """Lightweight dict for map marker rendering."""
        import json as _json
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "short_description": self.short_description,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "event_type": self.event_type,
            "period": self.period,
            "year_range": self.year_range,
            "image_url": self.image_url,
            "video_url": self.video_url,
            "difficulty_level": self.difficulty_level,
            "is_featured": self.is_featured,
            "region": self.region,
        }

    def to_detail_dict(self):
        """Full dict for modal detail view."""
        import json as _json
        return {
            **self.to_marker_dict(),
            "full_content": self.full_content,
            "event_date": str(self.event_date) if self.event_date else None,
            "image_caption": self.image_caption,
            "video_url": self.video_url,
            "tags": _json.loads(self.tags) if self.tags else [],
            "related_event_ids": _json.loads(self.related_event_ids) if self.related_event_ids else [],
            "is_featured": self.is_featured,
            "is_active": self.is_active,
        }
