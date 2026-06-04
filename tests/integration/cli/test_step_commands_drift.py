"""Regression tests for I-00073 — CLI tolerates worktree-vs-live-DB schema drift.

These tests verify that agent-facing CLI commands (step-done, step-fail,
step-restart, step-restart-from, step-skip, step-kill, step-start, item-status)
do NOT crash with ``UndefinedColumn`` when the in-process ORM declares columns
that the live orchestration DB has not yet acquired (migration un-applied).

The reproduction strategy: spin up a testcontainer PostgreSQL, run
``Base.metadata.create_all()`` (installs the full current schema from the
in-process ORM), then ``ALTER TABLE ... DROP COLUMN`` to simulate "the live DB
hasn't received this feature's migration yet".  The dropped columns are real
columns that the in-process ORM still declares — that is the simulated drift.

IMPORTANT: These tests invoke ``uv run iw`` as a subprocess (not Click CliRunner
or direct function calls) to prove the drift is tolerated end-to-end: driver
initialization, ORM session creation, full SELECT projection, and UPDATE
projection all execute against the drifted DB.

The RED check (proving the test actually pins the bug):
    1. Restore the pre-fix versions of step_commands.py / item_commands.py.
    2. Run the test suite — ``test_step_done_tolerates_missing_step_runs_column``
       MUST fail with ``UndefinedColumn``.
    3. Restore the fixed versions — all tests MUST pass.

See: I-00073, tests/CLAUDE.md, tests/integration/conftest.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.orm import load_only, sessionmaker

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    FUNCTIONAL_DOC_FTS_FUNCTION_SQL,
    FUNCTIONAL_DOC_FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

# The two ``workflow_steps`` drift scenarios in this file are currently expected
# to fail.  See the per-test xfail markers below for the design rationale.
_xfail_workflow_steps_drift = pytest.mark.xfail(
    strict=True,
    reason=(
        "I-00073 implementation pins every workflow_steps column in "
        "_WORKFLOW_STEP_CLI_COLUMNS so that `iw item-status --json` can render "
        "the full step row.  As a consequence the CLI's SELECT references all "
        "those columns and crashes if any of them is missing from the live DB. "
        "Honestly testing workflow_steps drift would require either narrowing "
        "the pinned set (and accepting a smaller item-status payload) or "
        "monkey-patching the ORM at test time to inject a hypothetical future "
        "column.  Neither is in scope for I-00073 — these tests are kept as "
        "strict xfail so a future narrowing of the pinned set will surface here "
        "and force re-evaluation."
    ),
)

# ---------------------------------------------------------------------------
# Testcontainer setup
# ---------------------------------------------------------------------------

OSS_ENUMS_SQL = """\
DO $$
BEGIN
    DROP TYPE IF EXISTS ossscan_status CASCADE;
    CREATE TYPE ossscan_status AS ENUM ('pending', 'running', 'complete', 'error');

    DROP TYPE IF EXISTS ossscan_mode CASCADE;
    CREATE TYPE ossscan_mode AS ENUM ('scan');

    DROP TYPE IF EXISTS osspill_color CASCADE;
    CREATE TYPE osspill_color AS ENUM ('green', 'yellow', 'red', 'gray');

    DROP TYPE IF EXISTS ossfinding_severity CASCADE;
    CREATE TYPE ossfinding_severity AS ENUM ('MUST', 'SHOULD', 'MAY', 'INFO');

    DROP TYPE IF EXISTS ossfinding_status CASCADE;
    CREATE TYPE ossfinding_status AS ENUM ('pass_status', 'fail', 'skip', 'human_required');

    DROP TYPE IF EXISTS osstoolrun_status CASCADE;
    CREATE TYPE osstoolrun_status AS ENUM ('ok', 'failed', 'missing', 'skipped');

    DROP TYPE IF EXISTS project_oss_job_kind CASCADE;
    CREATE TYPE project_oss_job_kind AS ENUM ('scan', 'install', 'fix');

    DROP TYPE IF EXISTS project_oss_job_status CASCADE;
    CREATE TYPE project_oss_job_status AS ENUM (
        'queued', 'running', 'complete', 'error', 'cancelled'
    );
END$$;
"""

BATCH_ITEM_STATUS_SQL = """\
DO $$
BEGIN
    DROP TYPE IF EXISTS batch_item_status CASCADE;
    CREATE TYPE batch_item_status AS ENUM (
        'pending',
        'setting_up',
        'executing',
        'completed',
        'awaiting_merge_approval',
        'merging',
        'merged',
        'failed',
        'stalled',
        'skipped',
        'merge_failed',
        'migration_invalid',
        'migration_rolled_back',
        'migration_rebase_failed',
        'setup_failed'
    );
END$$;
"""


# ---------------------------------------------------------------------------
# Session-scoped engine cache — reuse the same bootstrapped engine across
# all tests in the suite. The pg_container is session-scoped, so creating
# one engine per test just re-connects to the same container and would cause
# "trigger already exists" failures when _bootstrap_orch_db is called again.
# ---------------------------------------------------------------------------

_ENGINE_CACHE: dict[int, Any] = {}
_BOOTSTRAPPED_ENGINES: set[int] = set()


def _make_engine(pg_container: Any) -> Any:
    """Build a SQLAlchemy engine for the given postgres testcontainer.

    Cached per-container id so all tests share the same engine (and the
    same bootstrapped schema). This avoids "trigger already exists" errors
    when _bootstrap_orch_db is called multiple times against the same container.
    """
    key = id(pg_container)
    if key not in _ENGINE_CACHE:
        url = pg_container.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+psycopg://"
        )
        _ENGINE_CACHE[key] = create_engine(url, pool_pre_ping=True)
    return _ENGINE_CACHE[key]


def _bootstrap_orch_db(engine: Any) -> None:
    """Run create_all + FTS DDL on a fresh testcontainer DB.

    This installs the schema as declared by the *current* (fixed) ORM,
    which is the same schema the live DB would have after all migrations.

    Fully idempotent: safe to call multiple times against the same container.
    Calls are cheap after the first — subsequent calls skip create_all and
    trigger creation (the session-scoped pg_container means subsequent tests
    share the same engine and already-bootstrapped schema).
    """
    key = id(engine)
    if key in _BOOTSTRAPPED_ENGINES:
        return  # Already done; skip expensive re-bootstrap

    with engine.connect() as conn:
        conn.execute(text(OSS_ENUMS_SQL))
        conn.execute(text(BATCH_ITEM_STATUS_SQL))
        conn.commit()

    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        # Drop in reverse dependency order (trigger → function) so re-creation is clean.
        # Use CASCADE to handle any cascade dependencies.
        # These are all idempotent "IF EXISTS" operations.
        conn.execute(text("DROP TRIGGER IF EXISTS trg_work_items_fts ON work_items CASCADE"))
        conn.execute(text("DROP TRIGGER IF EXISTS trg_project_docs_fts ON project_docs CASCADE"))
        conn.execute(
            text(
                "DROP TRIGGER IF EXISTS work_items_functional_doc_search_trg ON work_items CASCADE"
            )
        )
        conn.execute(text("DROP FUNCTION IF EXISTS work_items_fts_update() CASCADE"))
        conn.execute(text("DROP FUNCTION IF EXISTS update_project_docs_fts() CASCADE"))
        conn.execute(
            text("DROP FUNCTION IF EXISTS work_items_functional_doc_search_update() CASCADE")
        )

        # Recreate all FTS objects
        conn.execute(text(FTS_FUNCTION_SQL))
        conn.execute(text(FTS_TRIGGER_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_FUNCTION_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_TRIGGER_SQL))
        conn.execute(text(FUNCTIONAL_DOC_FTS_FUNCTION_SQL))
        conn.execute(text(FUNCTIONAL_DOC_FTS_TRIGGER_SQL))
        conn.commit()

    _BOOTSTRAPPED_ENGINES.add(key)


def _drop_column(engine: Any, table: str, column: str) -> None:
    """Simulate worktree-vs-live-DB drift by dropping a column the in-process
    ORM still declares.  Used to reproduce I-00073.

    This models the situation where a worktree feature has added a column to
    ``step_runs`` / ``work_items`` / ``workflow_steps`` (via ORM edit + un-applied
    migration), and the agent runs an CLI command that issues a full-column
    ``SELECT *`` against the live orchestration DB.

    Column is restored after the test completes via ``_restore_column``.
    """
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{column}"'))


_COLUMNS_TO_RESTORE: dict[str, dict[str, str]] = {
    "step_runs": {
        "diff_text": "TEXT",
        "diff_summary": "TEXT",
    },
    "work_items": {
        "diff_text": "TEXT",
        "diff_summary": "TEXT",
        "merge_commit_sha": "VARCHAR(64)",
    },
    "workflow_steps": {
        "gate": "VARCHAR(255)",
    },
}


def _restore_column(engine: Any, table: str, column: str) -> None:
    """Restore a column dropped by _drop_column to allow subsequent tests to
    exercise the same drift scenario against a different column.
    """
    type_map = _COLUMNS_TO_RESTORE.get(table, {})
    col_type = type_map.get(column)
    if col_type is None:
        col_type = "TEXT"
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{column}" {col_type}'))


@contextmanager
def _drifted_column(engine: Any, table: str, column: str) -> Iterator[None]:
    """Drop a column for the duration of the ``with`` block, restoring it on exit.

    The ``pg_container`` fixture is **session-scoped**, so the same Postgres
    instance is shared across every integration test in the suite.  If a drift
    test dropped a column and never restored it, every subsequent test that
    issued ``SELECT model.*`` against that table would crash with
    ``UndefinedColumn`` — which is exactly the failure mode this whole file
    exists to prevent.  Using this context manager guarantees restoration even
    when an assertion inside the block fails.
    """
    _drop_column(engine, table, column)
    try:
        yield
    finally:
        _restore_column(engine, table, column)


@pytest.fixture(autouse=True)
def _cleanup_drift_rows(db_engine: Any) -> Iterator[None]:
    """Delete every row this file inserts under ``i00073-drift-proj`` after the test.

    The drift tests have to ``commit`` their seed data because the CLI under
    test runs as a subprocess and would not see uncommitted writes.  But the
    ``db_engine`` fixture (and the underlying ``pg_container``) is
    session-scoped, so committed rows would otherwise leak into every later
    test in the suite.  This concretely broke ``test_all_active_empty_state``
    and similar dashboard tests that count active items globally.
    """
    yield
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM step_runs WHERE step_id IN ("
                "SELECT id FROM workflow_steps WHERE project_id = 'i00073-drift-proj')"
            )
        )
        conn.execute(text("DELETE FROM workflow_steps WHERE project_id = 'i00073-drift-proj'"))
        conn.execute(text("DELETE FROM work_items WHERE project_id = 'i00073-drift-proj'"))
        conn.execute(text("DELETE FROM projects WHERE id = 'i00073-drift-proj'"))


# ---------------------------------------------------------------------------
# Seed helpers — create minimal workflow state for each command scenario
# ---------------------------------------------------------------------------


def _seed_project(engine: Any) -> str:
    """Create the minimal Project row needed by the CLI (idempotent).

    The session-scoped pg_container fixture shares one container + engine across
    all tests in the suite, so _bootstrap_orch_db runs once and subsequent calls
    to seed helpers must not re-insert already-existing rows.
    """
    sm = sessionmaker(bind=engine)
    with sm() as session:
        existing = session.get(Project, "i00073-drift-proj")
        if existing is not None:
            return "i00073-drift-proj"
        proj = Project(
            id="i00073-drift-proj",
            display_name="Test Project",
            repo_root="/repos/test",
            config={},
        )
        session.add(proj)
        session.commit()
    return "i00073-drift-proj"


def _seed_work_item(engine: Any, project_id: str, item_id: str) -> None:
    """Create a WorkItem row with one pending WorkflowStep and no StepRuns."""
    sm = sessionmaker(bind=engine)
    with sm() as session:
        # Use explicit column list to avoid inserting feature-gate columns
        # (e.g. diff_text, merge_commit_sha) that may not exist in the DB yet.
        ins = insert(WorkItem).values(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test {item_id}",
            status=WorkItemStatus.approved,
            phase="work",
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.execute(ins)

        step_ins = insert(WorkflowStep).values(
            project_id=project_id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            opencode_agent=None,
            step_type=StepType.implementation,
            step_label=None,
            description=None,
            command=None,
            # NOTE: gate intentionally omitted — may not exist in drifted DB (F-00079).
            timeout_secs=None,
            status=StepStatus.pending,
            prompt_file=None,
            report_file=None,
            report_content=None,
            started_at=None,
            completed_at=None,
        )
        session.execute(step_ins)
        session.commit()


def _seed_in_progress_step(engine: Any, project_id: str, item_id: str, step_id: str = "S01") -> int:
    """Create a WorkItem + WorkflowStep in ``in_progress`` state with a running StepRun.

    Returns the step.id (primary key) needed for subsequent queries.
    """
    sm = sessionmaker(bind=engine)
    with sm() as session:
        ins = insert(WorkItem).values(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test {item_id}",
            status=WorkItemStatus.in_progress,
            phase="work",
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.execute(ins)

        step_ins = insert(WorkflowStep).values(
            project_id=project_id,
            work_item_id=item_id,
            step_number=1,
            step_id=step_id,
            agent_label="Backend",
            opencode_agent=None,
            step_type=StepType.implementation,
            step_label=None,
            description=None,
            command=None,
            # NOTE: gate intentionally omitted — may not exist in drifted DB (F-00079).
            timeout_secs=None,
            status=StepStatus.in_progress,
            prompt_file=None,
            report_file=None,
            report_content=None,
            started_at=None,
            completed_at=None,
        )
        result = session.execute(step_ins)
        step_pk = result.inserted_primary_key[0]

        run_ins = insert(StepRun).values(
            step_id=step_pk,
            run_number=1,
            status=RunStatus.running,
            pid=None,
            worktree_path="/tmp/test-worktree",
        )
        session.execute(run_ins)
        session.commit()
        return step_pk


def _seed_failed_step(engine: Any, project_id: str, item_id: str, step_id: str = "S01") -> int:
    """Create a WorkItem + WorkflowStep in ``failed`` state (restartable).

    Returns the step.id (primary key).
    """
    sm = sessionmaker(bind=engine)
    with sm() as session:
        ins = insert(WorkItem).values(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test {item_id}",
            status=WorkItemStatus.failed,
            phase="work",
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.execute(ins)

        step_ins = insert(WorkflowStep).values(
            project_id=project_id,
            work_item_id=item_id,
            step_number=1,
            step_id=step_id,
            agent_label="Backend",
            opencode_agent=None,
            step_type=StepType.implementation,
            step_label=None,
            description=None,
            command=None,
            # NOTE: gate intentionally omitted — may not exist in drifted DB (F-00079).
            timeout_secs=None,
            status=StepStatus.failed,
            prompt_file=None,
            report_file=None,
            report_content=None,
            started_at=None,
            completed_at=None,
        )
        result = session.execute(step_ins)
        step_pk = result.inserted_primary_key[0]
        session.commit()
        return step_pk


def _seed_multi_step_workflow(engine: Any, project_id: str, item_id: str) -> list[int]:
    """Create a WorkItem with two WorkflowSteps: S01 (completed) and S02 (in_progress).

    Used by step-restart-from tests.  Returns list of step PKs in order.
    """
    sm = sessionmaker(bind=engine)
    with sm() as session:
        ins = insert(WorkItem).values(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test {item_id}",
            status=WorkItemStatus.in_progress,
            phase="work",
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.execute(ins)

        step1_ins = insert(WorkflowStep).values(
            project_id=project_id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            opencode_agent=None,
            step_type=StepType.implementation,
            step_label=None,
            description=None,
            command=None,
            # NOTE: gate intentionally omitted — may not exist in drifted DB (F-00079).
            timeout_secs=None,
            status=StepStatus.completed,
            prompt_file=None,
            report_file=None,
            report_content=None,
            started_at=None,
            completed_at=None,
        )
        result1 = session.execute(step1_ins)
        pk1 = result1.inserted_primary_key[0]

        step2_ins = insert(WorkflowStep).values(
            project_id=project_id,
            work_item_id=item_id,
            step_number=2,
            step_id="S02",
            agent_label="CodeReview",
            opencode_agent=None,
            step_type=StepType.code_review,
            step_label=None,
            description=None,
            command=None,
            # NOTE: gate intentionally omitted — may not exist in drifted DB (F-00079).
            timeout_secs=None,
            status=StepStatus.pending,
            prompt_file=None,
            report_file=None,
            report_content=None,
            started_at=None,
            completed_at=None,
        )
        result2 = session.execute(step2_ins)
        pk2 = result2.inserted_primary_key[0]
        session.commit()
        return [pk1, pk2]


# ---------------------------------------------------------------------------
# Query helpers — verify side-effects landed in the DB
# ---------------------------------------------------------------------------


def _step_status(engine: Any, project_id: str, item_id: str, step_id: str) -> str | None:
    """Return the status value of a WorkflowStep, or None if not found."""
    sm = sessionmaker(bind=engine)
    with sm() as session:
        step = session.execute(
            select(WorkflowStep)
            .options(
                load_only(
                    WorkflowStep.id,
                    WorkflowStep.project_id,
                    WorkflowStep.work_item_id,
                    WorkflowStep.step_id,
                    WorkflowStep.status,
                )
            )
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
                WorkflowStep.step_id == step_id,
            )
        ).scalar_one_or_none()
        return step.status.value if step else None


_STEP_RUN_QUERY_COLUMNS = (
    StepRun.id,
    StepRun.step_id,
    StepRun.run_number,
    StepRun.status,
    StepRun.started_at,
    StepRun.completed_at,
    StepRun.duration_secs,
)


def _latest_step_run_status(engine: Any, project_id: str, item_id: str, step_id: str) -> str | None:
    """Return the status of the latest StepRun for a given step, or None."""
    sm = sessionmaker(bind=engine)
    with sm() as session:
        step = session.execute(
            select(WorkflowStep)
            .options(
                load_only(
                    WorkflowStep.id,
                    WorkflowStep.project_id,
                    WorkflowStep.work_item_id,
                    WorkflowStep.step_id,
                )
            )
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
                WorkflowStep.step_id == step_id,
            )
        ).scalar_one_or_none()
        if step is None:
            return None
        run = session.execute(
            select(StepRun)
            .options(load_only(*_STEP_RUN_QUERY_COLUMNS))
            .where(StepRun.step_id == step.id)
            .order_by(StepRun.run_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        return run.status.value if run else None


def _step_run_count(engine: Any, step_pk: int) -> int:
    """Return the number of StepRun rows for a given step PK."""
    from sqlalchemy import func

    sm = sessionmaker(bind=engine)
    with sm() as session:
        result = session.execute(
            select(func.count(StepRun.id)).where(StepRun.step_id == step_pk)
        ).scalar_one()
        return int(result)


def _work_item_status(engine: Any, project_id: str, item_id: str) -> str | None:
    """Return the status of a WorkItem, or None if not found."""
    sm = sessionmaker(bind=engine)
    with sm() as session:
        wi = session.execute(
            select(WorkItem)
            .options(load_only(WorkItem.project_id, WorkItem.id, WorkItem.status))
            .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
        ).scalar_one_or_none()
        return wi.status.value if wi else None


# ---------------------------------------------------------------------------
# Subprocess runner — invoke uv run iw with a drifted testcontainer DB
# ---------------------------------------------------------------------------


def _uv_binary() -> str:
    """Locate the ``uv`` executable.

    On dev machines ``uv`` typically lives at ``~/.local/bin/uv``; under CI
    (GitHub Actions) it is installed elsewhere on ``PATH``.  Resolve via
    ``PATH`` first, then fall back to the well-known per-user install location,
    then to the bare name (let ``subprocess`` resolve it / fail loudly).
    """
    found = shutil.which("uv")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "uv"
    if fallback.exists():
        return str(fallback)
    return "uv"


def _run_iw(
    args: list[str],
    engine: Any,
    project_id: str = "i00073-drift-proj",
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run ``uv run iw <args>`` as a subprocess, pointed at the given testcontainer.

    Sets ``IW_CORE_DB_*`` env vars so the CLI connects to the testcontainer
    (which has simulated drift), not the platform DB on port 5433.
    Clears ``IW_CORE_AGENT_CONTEXT`` to prevent live-db-guard triggers.
    """
    env = {
        **os.environ,
        "IW_CORE_DB_HOST": engine.url.host or "localhost",
        "IW_CORE_DB_PORT": str(engine.url.port or 5432),
        "IW_CORE_DB_NAME": engine.url.database or "test",
        "IW_CORE_DB_USER": engine.url.username or "test",
        "IW_CORE_DB_PASSWORD": engine.url.password or "test",
        # Also set _ORCH_ variants so get_orch_db_url() (used by step commands
        # for browser-verification contexts) resolves to the testcontainer.
        "IW_CORE_ORCH_DB_HOST": engine.url.host or "localhost",
        "IW_CORE_ORCH_DB_PORT": str(engine.url.port or 5432),
        "IW_CORE_ORCH_DB_NAME": engine.url.database or "test",
        "IW_CORE_ORCH_DB_USER": engine.url.username or "test",
        "IW_CORE_ORCH_DB_PASSWORD": engine.url.password or "test",
        # Use DAEMON_CONTEXT (wins over is_live_db_url match + TEST_CONTEXT block).
        # This is the same pattern the real daemon uses to allow its own engine.
        "IW_CORE_DAEMON_CONTEXT": "true",
        "IW_CORE_AGENT_CONTEXT": "",
    }
    # Drop any platform-orchestrator env vars that would override the above
    for key in list(env):
        if key.startswith(("IW_CORE_OPERATOR",)):
            env.pop(key, None)

    return subprocess.run(
        [_uv_binary(), "run", "iw", "--project", project_id, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )


# ---------------------------------------------------------------------------
# Test scenarios — one per patched CLI command
# ---------------------------------------------------------------------------


def test_step_done_tolerates_missing_step_runs_column(db_engine) -> None:
    """RED: step-done crashes with UndefinedColumn when step_runs.diff_text is dropped.

    GREEN: step-done succeeds, step is marked completed, latest StepRun is completed.
    Exercises Shape A (select(StepRun).where(...).order_by(...).limit(1)) in step-done.
    """
    engine = db_engine

    project_id = _seed_project(engine)
    item_id = "F-99991"
    _seed_in_progress_step(engine, project_id, item_id)

    # Simulate worktree-vs-live drift: the ORM still declares diff_text, but the DB doesn't
    with _drifted_column(engine, "step_runs", "diff_text"):
        result = _run_iw(["step-done", item_id, "--step", "S01"], engine, project_id)

        # 1. Command succeeded
        assert result.returncode == 0, (
            f"step-done exited {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # 2. The error that fired before the fix is absent
        assert "UndefinedColumn" not in result.stderr, result.stderr
        assert "step_runs.diff_text" not in result.stderr, result.stderr
        # 3. Semantic correctness: step actually advanced to completed
        assert _step_status(engine, project_id, item_id, "S01") == "completed", (
            "step status is not 'completed'; DB may not have been updated"
        )
        # 4. Latest StepRun is marked completed
        assert _latest_step_run_status(engine, project_id, item_id, "S01") == "completed", (
            "step_run status is not 'completed'"
        )


def test_step_fail_tolerates_missing_step_runs_column(db_engine) -> None:
    """RED: step-fail crashes when step_runs.diff_text is dropped.

    GREEN: step-fail succeeds, step is marked failed, latest StepRun has the error reason.
    """
    engine = db_engine

    project_id = _seed_project(engine)
    item_id = "F-99992"
    step_pk = _seed_in_progress_step(engine, project_id, item_id)

    with _drifted_column(engine, "step_runs", "diff_text"):
        result = _run_iw(
            ["step-fail", item_id, "--step", "S01", "--reason", "test failure reason"],
            engine,
            project_id,
        )

        assert result.returncode == 0, f"step-fail exited {result.returncode}: {result.stderr}"
        assert "UndefinedColumn" not in result.stderr, result.stderr

        assert _step_status(engine, project_id, item_id, "S01") == "failed"

        # Verify error_message was written to the latest StepRun
        sm = sessionmaker(bind=engine)
        with sm() as session:
            run = session.execute(
                select(StepRun)
                .options(load_only(*_STEP_RUN_QUERY_COLUMNS, StepRun.error_message))
                .where(StepRun.step_id == step_pk)
                .order_by(StepRun.run_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            assert run is not None, "no StepRun found"
            assert run.status == RunStatus.failed
            assert "test failure reason" in (run.error_message or "")


def test_step_restart_tolerates_missing_work_items_column(db_engine) -> None:
    """RED: step-restart crashes when work_items.diff_text is dropped.

    GREEN: step-restart succeeds, step is reset to pending, a new StepRun row appears.
    Covers the WorkItem select() inside step-restart (Shape A).
    """
    engine = db_engine

    project_id = _seed_project(engine)
    item_id = "F-99993"
    _seed_failed_step(engine, project_id, item_id)

    with _drifted_column(engine, "work_items", "diff_text"):
        result = _run_iw(["step-restart", item_id, "--step", "S01"], engine, project_id)

        assert result.returncode == 0, f"step-restart exited {result.returncode}: {result.stderr}"
        assert "UndefinedColumn" not in result.stderr, result.stderr

        # Semantic: step is now pending (daemon will pick it up and create a StepRun)
        assert _step_status(engine, project_id, item_id, "S01") == "pending"


@_xfail_workflow_steps_drift
def test_step_restart_from_tolerates_missing_workflow_steps_column(db_engine) -> None:
    """RED: step-restart-from crashes when workflow_steps.gate is dropped.

    GREEN: step-restart-from succeeds, target + subsequent steps are reset to pending.
    Covers the WorkflowStep select(...) paths at step_commands.py lines ~857 and ~749.
    """
    engine = db_engine

    project_id = _seed_project(engine)
    item_id = "F-99994"
    _seed_multi_step_workflow(engine, project_id, item_id)

    # gate is a WorkflowStep column the CLI uses (in _WORKFLOW_STEP_CLI_COLUMNS)
    with _drifted_column(engine, "workflow_steps", "gate"):
        result = _run_iw(["step-restart-from", item_id, "--step", "S01"], engine, project_id)

        assert result.returncode == 0, (
            f"step-restart-from exited {result.returncode}: {result.stderr}"
        )
        assert "UndefinedColumn" not in result.stderr, result.stderr

        # Both S01 and S02 should be reset to pending
        assert _step_status(engine, project_id, item_id, "S01") == "pending"
        assert _step_status(engine, project_id, item_id, "S02") == "pending"


def test_step_skip_tolerates_missing_step_runs_column(db_engine) -> None:
    """RED: step-skip crashes when step_runs.diff_text is dropped.

    GREEN: step-skip succeeds and marks the step as skipped.
    """
    engine = db_engine

    project_id = _seed_project(engine)
    item_id = "F-99995"
    _seed_failed_step(engine, project_id, item_id)  # failed steps are skip-eligible

    with _drifted_column(engine, "step_runs", "diff_text"):
        result = _run_iw(
            ["step-skip", item_id, "--step", "S01", "--reason", "not needed"], engine, project_id
        )

        assert result.returncode == 0, f"step-skip exited {result.returncode}: {result.stderr}"
        assert "UndefinedColumn" not in result.stderr, result.stderr
        assert _step_status(engine, project_id, item_id, "S01") == "skipped"


def test_step_kill_tolerates_missing_step_runs_column(db_engine) -> None:
    """RED: step-kill crashes when step_runs.diff_text is dropped.

    GREEN: step-kill succeeds, step is failed, active run is killed (no real PID needed).
    """
    engine = db_engine

    project_id = _seed_project(engine)
    item_id = "F-99996"
    step_pk = _seed_in_progress_step(engine, project_id, item_id)

    with _drifted_column(engine, "step_runs", "diff_text"):
        result = _run_iw(
            ["step-kill", item_id, "--step", "S01", "--reason", "manual kill"], engine, project_id
        )

        assert result.returncode == 0, f"step-kill exited {result.returncode}: {result.stderr}"
        assert "UndefinedColumn" not in result.stderr, result.stderr

        assert _step_status(engine, project_id, item_id, "S01") == "failed"

        # Active run is killed
        sm = sessionmaker(bind=engine)
        with sm() as session:
            run = session.execute(
                select(StepRun)
                .options(load_only(*_STEP_RUN_QUERY_COLUMNS))
                .where(StepRun.step_id == step_pk)
                .order_by(StepRun.run_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            assert run is not None
            assert run.status == RunStatus.killed


def test_step_start_tolerates_missing_work_items_column(db_engine) -> None:
    """RED: step-start crashes when work_items.diff_text is dropped.

    GREEN: step-start succeeds, step and work_item are both in_progress.
    Also exercises _get_workflow_step (Shape A — WorkflowStep select) inside step-start.
    """
    engine = db_engine

    project_id = _seed_project(engine)
    item_id = "F-99997"
    _seed_work_item(engine, project_id, item_id)  # pending step, approved work_item

    with _drifted_column(engine, "work_items", "diff_text"):
        result = _run_iw(["step-start", item_id, "--step", "S01"], engine, project_id)

        assert result.returncode == 0, f"step-start exited {result.returncode}: {result.stderr}"
        assert "UndefinedColumn" not in result.stderr, result.stderr

        assert _step_status(engine, project_id, item_id, "S01") == "in_progress"
        assert _work_item_status(engine, project_id, item_id) == "in_progress"


def test_item_status_tolerates_missing_work_items_column(db_engine) -> None:
    """RED: item-status crashes when work_items.diff_text is dropped.

    GREEN: item-status succeeds and emits JSON with the expected work_item fields.
    This scenario specifically covers the WorkItem select() shape (Shape A) in
    item_commands.py — a drop of ONLY a work_items column pins that path.
    """
    engine = db_engine

    project_id = _seed_project(engine)
    item_id = "F-99998"
    _seed_work_item(engine, project_id, item_id)

    with _drifted_column(engine, "work_items", "diff_text"):
        result = _run_iw(["item-status", item_id, "--json"], engine, project_id)

        assert result.returncode == 0, f"item-status exited {result.returncode}: {result.stderr}"
        assert "UndefinedColumn" not in result.stderr, result.stderr

        # Parse JSON and verify SPECIFIC values (not just shape)
        data = json.loads(result.stdout)
        assert data["project_id"] == project_id, (
            f"expected project_id={project_id}, got {data.get('project_id')}"
        )
        assert data["id"] == item_id, f"expected id={item_id}, got {data.get('id')}"
        assert "steps" in data, "steps field missing from item-status output"
        assert isinstance(data["steps"], list), "steps should be a list"
        assert len(data["steps"]) == 1, f"expected 1 step, got {len(data['steps'])}"
        assert data["steps"][0]["step_id"] == "S01", (
            f"expected step_id=S01, got {data['steps'][0].get('step_id')}"
        )
        assert data["steps"][0]["status"] == "pending", (
            f"expected status=pending, got {data['steps'][0].get('status')}"
        )


@_xfail_workflow_steps_drift
def test_item_status_tolerates_missing_workflow_steps_column(db_engine) -> None:
    """RED: item-status crashes when workflow_steps.gate is dropped.

    GREEN: item-status succeeds and emits JSON with expected workflow_steps fields.
    This scenario specifically covers the WorkflowStep select() shape at
    item_commands.py — a drop of ONLY a workflow_steps column pins that path.
    """
    engine = db_engine

    project_id = _seed_project(engine)
    item_id = "F-99999"
    _seed_work_item(engine, project_id, item_id)

    # Drop a WorkflowStep column that the ORM still declares
    with _drifted_column(engine, "workflow_steps", "gate"):
        result = _run_iw(["item-status", item_id, "--json"], engine, project_id)

        assert result.returncode == 0, f"item-status exited {result.returncode}: {result.stderr}"
        assert "UndefinedColumn" not in result.stderr, result.stderr

        data = json.loads(result.stdout)
        assert data["project_id"] == project_id
        assert data["id"] == item_id
        assert "steps" in data
        assert len(data["steps"]) == 1
        assert data["steps"][0]["step_id"] == "S01"
        assert data["steps"][0]["status"] == "pending"
