"""Performance test fixtures and configuration.

This module is loaded automatically when tests/perf/ is collected.
It provides session-scoped testcontainer infrastructure and the perf marker
auto-registration hook.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from orch.db.models import (
    Base,
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Perf marker auto-registration
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001
    items: list[pytest.Item],
) -> None:
    """Auto-apply @pytest.mark.perf to every test in tests/perf/.

    Individual test authors don't need to decorate their tests manually —
    this hook ensures every collected perf test is tagged, so the project's
    `addopts = ... and not perf` exclusion in pyproject.toml correctly
    prevents `make test-unit` / `make test-integration` from collecting them.
    """
    for item in items:
        item.add_marker(pytest.mark.perf)


# ---------------------------------------------------------------------------
# Session-scoped seeded orchestration DB
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def seeded_orch_db() -> tuple[PostgresContainer, Engine]:
    """Start a PostgreSQL 16 testcontainer and seed it with representative state.

    This fixture is session-scoped to amortise the ~2-3s container startup
    across all perf tests in tests/perf/.  The DB clone is not used here —
    we share one DB for all perf tests since they run sequentially (not
    in parallel) and each test resets the relevant poll-state via explicit
    transaction boundaries.

    Seeded state:
      - 1 Project row (id='perf-proj', enabled=True)
      - 3 WorkItem rows in different statuses: draft, active, completed
      - 1 Batch row in 'running' status
      - 1 BatchItem row in 'executing' status (active worktree stub)

    The state is designed to exercise the daemon's batch-poller path inside
    `_poll_cycle()` without needing real git repos or agent processes.
    """
    container = PostgresContainer("postgres:16-alpine")
    container.start()
    raw_url = container.get_connection_url()

    # Replace psycopg2 driver with psycopg (as required by CLAUDE.md)
    parsed = urlparse(raw_url.replace("postgresql+psycopg2://", "postgresql://"))
    sa_url = f"postgresql+psycopg://{parsed.netloc}{parsed.path}"
    # perf tests run rounds of 10 hits sequentially; a small default pool
    # (size=5, overflow=10) exhausts between tests when sessions aren't explicitly
    # closed between hits. NullPool gives each acquire a fresh connection from
    # the testcontainer, no session leak possible, no pool management overhead.
    from sqlalchemy.pool import NullPool

    engine = create_engine(
        sa_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )

    # Apply schema
    Base.metadata.create_all(engine)

    # Run FTS triggers (required post-create_all per CLAUDE.md convention)
    from orch.db.models import (
        FTS_FUNCTION_SQL,
        FTS_TRIGGER_SQL,
        FUNCTIONAL_DOC_FTS_FUNCTION_SQL,
        FUNCTIONAL_DOC_FTS_TRIGGER_SQL,
        PROJECT_DOCS_FTS_FUNCTION_SQL,
        PROJECT_DOCS_FTS_TRIGGER_SQL,
    )

    with engine.connect() as conn:
        for stmt in [
            FTS_FUNCTION_SQL,
            FTS_TRIGGER_SQL,
            PROJECT_DOCS_FTS_FUNCTION_SQL,
            PROJECT_DOCS_FTS_TRIGGER_SQL,
            FUNCTIONAL_DOC_FTS_FUNCTION_SQL,
            FUNCTIONAL_DOC_FTS_TRIGGER_SQL,
        ]:
            conn.execute(text(stmt))
        conn.commit()

    # Seed representative data
    _seed_data(engine)

    # Return container + engine so callers can access the connection URL
    # for session-factory creation (session-scoped, so only one URL is used)
    return container, engine


def _seed_data(engine: Engine) -> None:
    """Insert representative rows for daemon poll-loop measurement."""
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session: Session = session_factory()

    try:
        # Project
        project = Project(
            id="perf-proj",
            display_name="Perf Test Project",
            repo_root="/repos/perf-proj",
            config={},
            enabled=True,
        )
        session.add(project)
        session.flush()  # ensure FK constraint satisfied before child inserts

        # Work items in three different statuses
        work_items = [
            WorkItem(
                project_id="perf-proj",
                id="F-99991",
                type=WorkItemType.Feature,
                title="Perf test item A (draft)",
                status=WorkItemStatus.draft,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            ),
            WorkItem(
                project_id="perf-proj",
                id="F-99992",
                type=WorkItemType.Feature,
                title="Perf test item B (in_progress)",
                status=WorkItemStatus.in_progress,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            ),
            WorkItem(
                project_id="perf-proj",
                id="F-99993",
                type=WorkItemType.Feature,
                title="Perf test item C (completed)",
                status=WorkItemStatus.completed,
                phase=WorkItemPhase.work,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            ),
        ]
        for wi in work_items:
            session.add(wi)

        batch = Batch(
            id="BATCH_PERF_001",
            project_id="perf-proj",
            status=BatchStatus.executing,
            max_parallel=4,
            cli_tool="opencode",
            auto_merge=True,
        )
        session.add(batch)

        # Batch item (executing — active worktree stub)
        batch_item = BatchItem(
            project_id="perf-proj",
            batch_id="BATCH_PERF_001",
            work_item_id="F-99992",
            status=BatchItemStatus.executing,
            worktree_info={"path": "/tmp/perf-worktree-stub"},
        )
        session.add(batch_item)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
