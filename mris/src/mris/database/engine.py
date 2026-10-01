"""SQLite engine with WAL mode and enforced foreign keys."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from mris.config import get_settings


def _configure_sqlite(dbapi_connection, _record) -> None:  # pragma: no cover - driver hook
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite:///") and not url.endswith(":memory:"):
        from pathlib import Path

        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _configure_sqlite)
    return engine


@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    return build_engine(url or get_settings().database_url)


def make_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    session = make_session_factory(engine)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
