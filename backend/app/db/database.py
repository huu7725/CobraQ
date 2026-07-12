"""
SQLAlchemy database engine and session factory.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from typing import Generator

# Resolve path relative to this file. database.py lives at <repo>/backend/app/db/database.py
# so going up 3 dirs lands us in <repo>/, and we want <repo>/backend/data/cobraq.db.
import os
_THIS = os.path.abspath(__file__)
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS)))
DB_PATH = os.path.join(_BACKEND_ROOT, "data", "cobraq.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH.replace(chr(92), '/')}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

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
