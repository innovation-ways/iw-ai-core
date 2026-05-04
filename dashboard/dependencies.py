"""FastAPI dependency injection for the dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import Request

from orch.db.session import SessionLocal

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    """Yield a synchronous database session for a single request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_id(request: Request) -> str:
    """Read the session_id from request.state set by the session cookie middleware.

    Raises RuntimeError if middleware hasn't set it (should never happen
    if the middleware is registered).
    """
    session_id = getattr(request.state, "session_id", None)
    if session_id is None:
        raise RuntimeError(
            "session_id not found on request.state. "
            "Ensure SessionCookieMiddleware is registered in app.py."
        )
    return cast("str", session_id)


async def _build_async_engine() -> async_sessionmaker[AsyncSession]:
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        async_sessionmaker,
        create_async_engine,
    )

    from orch.config import get_db_url

    async_engine: AsyncEngine = create_async_engine(
        get_db_url().replace("postgresql+psycopg://", "postgresql+asyncpg://"),
        pool_pre_ping=True,
    )
    return async_sessionmaker(bind=async_engine, expire_on_commit=False)


_async_session_maker: async_sessionmaker[AsyncSession] | None = None


async def get_db_async() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for a single request (for use in async endpoints)."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = await _build_async_engine()
    session: AsyncSession = _async_session_maker()
    try:
        yield session
    finally:
        await session.close()
