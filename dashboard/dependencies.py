"""FastAPI dependency injection for the dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.session import SessionLocal

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session
    from sqlalchemy.ext.asyncio import async_sessionmaker


def get_db() -> Generator[Session, None, None]:
    """Yield a synchronous database session for a single request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
