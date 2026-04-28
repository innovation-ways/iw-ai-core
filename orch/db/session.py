"""SQLAlchemy engine and session factory for IW AI Core.

Usage (application code):
    from orch.db.session import get_session

    with get_session() as session:
        project = session.get(Project, "myproject")

Usage (Alembic env.py / scripts that need a one-off engine):
    from orch.db.session import engine
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, sessionmaker

from orch.config import get_db_max_overflow, get_db_pool_size, get_db_url, get_orch_db_url
from orch.db.live_db_guard import safe_create_engine

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.engine import Engine

    engine: Engine
    SessionLocal: sessionmaker[Session]

__all__ = [
    "get_orch_session",
    "get_session",
    "safe_create_engine",
]

_engine: Engine | None = None
_session_local: sessionmaker[Session] | None = None

_orch_engine: Engine | None = None
_orch_session_local: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = safe_create_engine(
            get_db_url(),
            pool_pre_ping=True,
            pool_size=get_db_pool_size(),
            max_overflow=get_db_max_overflow(),
            pool_recycle=1800,
            pool_timeout=10,
        )
    return _engine


def _get_session_local() -> sessionmaker[Session]:
    global _session_local
    if _session_local is None:
        _session_local = sessionmaker(
            bind=_get_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _session_local


def _get_orch_engine() -> Engine:
    global _orch_engine
    if _orch_engine is None:
        _orch_engine = safe_create_engine(
            get_orch_db_url(),
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=0,
            pool_recycle=1800,
            pool_timeout=10,
        )
    return _orch_engine


def _get_orch_session_local() -> sessionmaker[Session]:
    global _orch_session_local
    if _orch_session_local is None:
        _orch_session_local = sessionmaker(
            bind=_get_orch_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _orch_session_local


def __getattr__(name: str) -> object:
    if name == "engine":
        return _get_engine()
    if name == "SessionLocal":
        return _get_session_local()
    raise AttributeError(f"module 'orch.db.session' has no attribute {name!r}")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a database session; commit on success, rollback on exception."""
    session: Session = _get_session_local()()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_orch_session() -> Generator[Session, None, None]:
    """Yield a session to the orchestration DB.

    Prefers IW_CORE_ORCH_DB_* over IW_CORE_DB_* so that iw step-done/fail/start
    always reach the real orch DB even when IW_CORE_DB_* has been overridden to
    an isolated E2E container by browser_env._build_env.
    """
    session: Session = _get_orch_session_local()()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
