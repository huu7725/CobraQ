"""
SQLAlchemy database engine and session factory.

Supports both:
- SQLite (default, for local dev — file at backend/data/cobraq.db)
- Postgres (for production, e.g. Render + Neon)

Switch by setting DATABASE_URL:
- unset or empty       → SQLite at backend/data/cobraq.db
- postgresql://...     → Postgres (Neon, Supabase, Render Postgres, ...)

When DATA_DIR is set we still use the resolved directory for SQLite,
but on Render free tier with Postgres we don't need a persistent disk
for the DB anymore.
"""
import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


def _resolve_database_url() -> str:
    """Return DATABASE_URL from env, or default to SQLite in <repo>/backend/data/."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Render sometimes injects a postgres:// URL; SQLAlchemy 1.4+ expects
        # postgresql://. Render also adds ?sslmode=... which we keep.
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url

    # Fallback: SQLite relative to this file.
    backend_root = Path(__file__).resolve().parents[2]  # .../backend
    data_dir = os.environ.get("DATA_DIR")
    if data_dir:
        # DATA_DIR may be a persistent mount path; honour it.
        db_path = Path(data_dir) / "cobraq.db"
    else:
        db_path = backend_root / "data" / "cobraq.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + db_path.as_posix()


DATABASE_URL = _resolve_database_url()
IS_POSTGRES = DATABASE_URL.startswith(("postgresql://", "postgres://"))


def _make_engine(url: str):
    if url.startswith("sqlite"):
        # SQLite needs check_same_thread=False when used by FastAPI's threadpool.
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
            pool_pre_ping=True,
        )
    # Postgres / Neon: pool_pre_ping survives Neon autosuspend drops.
    return create_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


engine = _make_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    """FastAPI dependency — yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Call once on startup."""
    Base.metadata.create_all(bind=engine)
