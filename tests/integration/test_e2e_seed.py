"""Integration test: scripts/e2e_seed.seed() runs cleanly against a fresh schema.

Guards against the regression class where a per-item fixture's parent/child
inserts emit in FK-violating order. F-00076's fixture shipped with this bug
because no test ever exercised the seed end-to-end against a real schema —
``tests/unit/test_e2e_seed_discovery.py`` only covers the discovery mechanism.

A failure here means the next ``qv-browser`` step on this project would fail
with ``ForeignKeyViolation`` while bringing up the E2E stack.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    FUNCTIONAL_DOC_FTS_FUNCTION_SQL,
    FUNCTIONAL_DOC_FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    BatchItem,
    Project,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy import Engine


@pytest.fixture
def fresh_seed_engine() -> Generator[Engine, None, None]:
    """Dedicated PostgresContainer for the seed test.

    Uses its own container (rather than the session-scoped ``pg_container``)
    because ``seed()`` calls ``db.commit()`` and would pollute every other
    integration test relying on the shared transactional rollback fixture.
    """
    with PostgresContainer("postgres:15-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(text(FTS_FUNCTION_SQL))
            conn.execute(text(FTS_TRIGGER_SQL))
            conn.execute(text(PROJECT_DOCS_FTS_FUNCTION_SQL))
            conn.execute(text(PROJECT_DOCS_FTS_TRIGGER_SQL))
            conn.execute(text(FUNCTIONAL_DOC_FTS_FUNCTION_SQL))
            conn.execute(text(FUNCTIONAL_DOC_FTS_TRIGGER_SQL))
            conn.commit()
        yield engine


def test_e2e_seed_runs_against_fresh_db(
    fresh_seed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The full e2e_seed pipeline must complete against a clean schema.

    Discovers and runs every per-item fixture under
    ``ai-dev/{active,archive}/*/e2e_fixtures/*.py``. A FK violation, schema
    drift, or any other fixture regression surfaces here instead of at the
    next browser verification.
    """
    engine = fresh_seed_engine
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    @contextmanager
    def _test_get_session() -> Generator[Session, None, None]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr("scripts.e2e_seed.get_session", _test_get_session)
    # The script's production guardrail aborts when IW_CORE_EXPECTED_INSTANCE_ID
    # is set; the test session sets that via tests/conftest.py for every test.
    monkeypatch.setattr("scripts.e2e_seed._check_production_guardrail", lambda: None)

    from scripts.e2e_seed import seed

    # The regression class this test guards against is a fixture that emits
    # parent/child INSERTs in FK-violating order — ``seed()`` would raise
    # ``ForeignKeyViolation`` mid-run. Simply completing without raising is
    # the success criterion.
    seed()

    with session_factory() as s:
        proj = s.get(Project, "iw-ai-core")
        assert proj is not None, "seed() must create the iw-ai-core project"

        # At least one fixture must have produced StepRun rows — the only
        # way to exercise the FK ordering path is to actually run a fixture
        # that inserts child rows (StepRun -> WorkflowStep -> WorkItem).
        from orch.db.models import StepRun, WorkflowStep

        step_run_count = s.execute(
            select(StepRun).where(StepRun.step_id.in_(
                select(WorkflowStep.id).where(WorkflowStep.project_id == "iw-ai-core")
            ))
        ).all()
        assert step_run_count, (
            "no StepRun rows after seed() — either every fixture has been "
            "archived (this regression net is then defunct) or fixtures are "
            "silently skipping their inserts"
        )
