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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orch.config import get_db_url

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Engine — created lazily at import time (config must be loaded first).
# Tests MUST NOT import this module; they create their own engine from
# the testcontainer URL.
# ---------------------------------------------------------------------------

engine = create_engine(get_db_url(), pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a database session; commit on success, rollback on exception."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
