"""Integration tests for SSE stream endpoint in code_ui router.

Uses testcontainers to run a real PostgreSQL instance.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    CodeIndexJob,
    Project,
)
from orch.rag.job import JOB_REGISTRY


@pytest.fixture(scope="session")
def pg_container():
    """Start a PostgreSQL 15 container for the entire test session."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_engine(pg_container):
    """Create a SQLAlchemy engine connected to the test container."""
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    engine = create_engine(url, pool_pre_ping=True)

    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(text(FTS_FUNCTION_SQL))
        conn.execute(text(FTS_TRIGGER_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_FUNCTION_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_TRIGGER_SQL))
        conn.commit()

    return engine


@pytest.fixture
def db_session(db_engine):
    """Provide a transactional DB session that rolls back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


class TestCodeSSEStream:
    """Tests for GET /project/{project_id}/api/code/index/stream."""

    def test_sse_returns_idle_when_no_running_job(self, db_session):
        """SSE stream sends done/idle when no job is in JOB_REGISTRY."""
        from fastapi.testclient import TestClient

        from dashboard.app import create_app
        from dashboard.dependencies import get_db

        app = create_app()
        app.dependency_overrides[get_db] = lambda: db_session

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(
            "/project/test-proj/api/code/index/stream",
            timeout=5,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        chunks = b"".join(response.iter_bytes(chunk_size=64))
        assert b'"event": "done"' in chunks
        assert b'"status": "idle"' in chunks

    @pytest.mark.asyncio
    async def test_sse_sends_progress_and_done_events(self, db_engine, db_session):
        """SSE stream sends progress events then terminal done event when runner is in registry."""
        from httpx import ASGITransport, AsyncClient

        from dashboard.app import create_app
        from dashboard.dependencies import get_db

        project = Project(
            id="test-proj",
            display_name="Test Project",
            repo_root="/repos/test",
            config={"code_understanding": {"index_tier": "balanced"}},
        )
        db_session.add(project)
        db_session.flush()

        job = CodeIndexJob(
            id="job-123",
            project_id="test-proj",
            status="running",
            llm_model="gemma4:26b",
            embed_model="qwen3-embedding:8b",
        )
        db_session.add(job)
        db_session.commit()

        fake_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        class FakeRunner:
            job_id = "job-123"
            project_id = "test-proj"

            def __init__(self) -> None:
                self.progress_queue = fake_queue

            def request_cancel(self) -> None:
                pass

        runner = FakeRunner()
        JOB_REGISTRY["test-proj"] = runner

        app = create_app()
        session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        def get_session_override():
            session = session_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_session_override

        async def inject_events() -> None:
            await asyncio.sleep(0.1)
            await fake_queue.put(
                {
                    "event": "progress",
                    "phase": "indexing",
                    "files_indexed": 10,
                    "files_total": 100,
                    "chunks_created": 500,
                    "elapsed_seconds": 5,
                    "message": "Indexing file 10/100",
                }
            )
            await asyncio.sleep(0.1)
            await fake_queue.put({"event": "progress", "phase": "done"})

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                inject_task = asyncio.create_task(inject_events())
                try:
                    response = await asyncio.wait_for(
                        client.get(
                            "/project/test-proj/api/code/index/stream",
                            timeout=5,
                        ),
                        timeout=10,
                    )
                    assert response.status_code == 200
                    chunks = b"".join(response.iter_bytes(chunk_size=256))
                    assert b'"event": "progress"' in chunks
                    assert b'"phase": "indexing"' in chunks
                    assert b'"event": "done"' in chunks
                    assert b'"status": "completed"' in chunks
                finally:
                    inject_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await inject_task
        finally:
            JOB_REGISTRY.pop("test-proj", None)
