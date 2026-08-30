"""SQLAlchemy engine and session management."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()


def _build_engine() -> Engine:
    url = _settings.database_url
    kwargs: dict = {"echo": _settings.db_echo, "future": True}

    if url.startswith("sqlite"):
        # Used by the test suite only.
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # pool_pre_ping avoids handing out connections that the database has
        # already closed (common when Postgres restarts during development).
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20

    return create_engine(url, **kwargs)


engine: Engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
