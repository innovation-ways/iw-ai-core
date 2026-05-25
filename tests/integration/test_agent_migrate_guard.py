"""Integration tests for IW_CORE_AGENT_CONTEXT guard propagation.

Tests:
- Agent env propagates to subprocess (batch_manager spawn)
- Agent cannot apply migration via CLI with IW_CORE_AGENT_CONTEXT=true
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
    Project,
)


@pytest.fixture
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture
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


@pytest.fixture
def test_project(db_session):  # noqa: assertion-scanner
    project = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.mark.integration
def test_agent_env_propagates_to_subprocess(
    monkeypatch,
    db_session,
    test_project,
) -> None:
    """batch_manager spawn echoes $IW_CORE_AGENT_CONTEXT — value must be 'true' in subprocess."""
    from orch.daemon.batch_manager import _build_agent_env

    monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")

    env = _build_agent_env(
        cli_tool="opencode",
        item_id="CR-99901",
        worktree_path="/tmp/worktrees/CR-99901",
    )

    assert env.get("IW_CORE_AGENT_CONTEXT") == "true"


@pytest.mark.integration
def test_agent_cannot_apply_migration(
    monkeypatch,
    db_session,
    test_project,
) -> None:
    """Run CLI with IW_CORE_AGENT_CONTEXT=true; assert exit 2 (agent blocked)."""
    monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")

    project_root = Path(__file__).parent.parent.parent.resolve()
    result = subprocess.run(
        [
            "uv",
            "run",
            "iw",
            "migrations",
            "apply",
            "--i-am-operator",
        ],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert "agent" in combined.lower()
