"""FastAPI dependency injection for the dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.session import SessionLocal

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for a single request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
