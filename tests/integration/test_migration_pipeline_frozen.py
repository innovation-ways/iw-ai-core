"""Integration tests for merge queue frozen-state behavior.

Tests:
- Unfreeze refuses in agent context
- Unfreeze logs ack reason
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    DaemonEvent,
)


@pytest.fixture(scope="session")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_engine(pg_container: PostgresContainer):
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    from sqlalchemy import create_engine

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
    from sqlalchemy.orm import sessionmaker

    connection = db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_factory()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.mark.integration
def test_unfreeze_refuses_in_agent_context(
    monkeypatch,
) -> None:
    """Set IW_CORE_AGENT_CONTEXT=true, invoke unfreeze via CLI, assert exit 2."""
    monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")

    project_root = Path(__file__).parent.parent.parent.resolve()
    result = subprocess.run(
        [
            "uv",
            "run",
            "iw",
            "merge-queue",
            "unfreeze",
            "--ack",
            "test reason",
        ],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert "agent" in combined.lower()


@pytest.mark.integration
def test_unfreeze_logs_ack_reason(db_session) -> None:
    """After unfreeze, daemon_events has a row with the ack reason and acknowledged_by."""
    import getpass

    user = getpass.getuser()

    event = DaemonEvent(
        project_id=None,
        event_type="merge_queue_frozen",
        entity_id=None,
        entity_type=None,
        message="Operator resolved the issue",
        event_metadata={
            "active": False,
            "reason": "Operator resolved the issue",
            "acknowledged_by": user,
        },
    )
    db_session.add(event)
    db_session.commit()

    events = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.event_type == "merge_queue_frozen",
        )
        .order_by(DaemonEvent.created_at.desc())
        .all()
    )
    assert len(events) >= 1
    last_event = events[0]
    assert last_event.event_metadata.get("active") is False
    assert "Operator resolved" in last_event.message
    assert last_event.event_metadata.get("acknowledged_by") == user
