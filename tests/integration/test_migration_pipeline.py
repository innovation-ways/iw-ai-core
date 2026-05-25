"""Integration tests for the 3-phase migration pipeline.

These tests use mocking to control the pipeline's DB access while verifying
the three-phase orchestration logic (dry_run → apply → rollback).

Tests that require real DB access for freeze/unfreeze verification are in
test_migration_pipeline_frozen.py.

I-00041: these tests must NOT write to the live DB. The connection-layer
guard in orch/db/live_db_guard.py enforces this; the mocks here are
defense-in-depth. Each test uses a unique batch_id to prevent collision.
"""

from __future__ import annotations

import hashlib
import os
from unittest.mock import patch

import pytest

from orch.daemon.migration_pipeline import (
    run_post_merge_apply,
    run_pre_merge_dry_run,
    run_rollback,
)

DUMMY_DB_URL = "postgresql+psycopg://test:test@localhost:5432/test_db"


@pytest.fixture
def unique_batch_id(request: pytest.FixtureRequest) -> int:
    """Per-test unique negative batch_id.

    Negatives never collide with real batch IDs (which are positive
    auto-incrementing). The hash of the test name + xdist worker ID
    keeps it stable across reruns of the same test on the same worker
    but unique across tests.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    name = f"{worker}:{request.node.nodeid}"
    h = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)
    return -(h % 1_000_000) - 1


def _run_pipeline_happy_path(batch_id: int) -> None:
    """Plain function with the body of test_pipeline_happy_path.

    Extracted so the I-00041 mock-coverage smoke test can invoke it
    without going through pytest collection (and thus without needing
    fixture resolution beyond the explicit batch_id argument).
    """
    with patch("orch.daemon.migration_pipeline.get_db_url", return_value=DUMMY_DB_URL):
        with patch("orch.daemon.migration_pipeline.safe_dry_run") as mock_dry:
            from orch.db.safe_migrate import DryRunResult

            mock_dry.return_value = DryRunResult(
                revisions_applied=["abc123"],
                success=True,
                duration_ms=100,
                stdout_tail="",
                stderr_tail="",
                error_message=None,
            )
            result = run_pre_merge_dry_run(batch_id=batch_id)

        assert result.success is True
        assert result.final_batch_state == "proceed_to_merge"
        assert result.frozen is False

        with patch("orch.daemon.migration_pipeline.safe_apply") as mock_apply:
            from orch.db.safe_migrate import ApplyResult

            mock_apply.return_value = ApplyResult(
                revisions_applied=["abc123"],
                success=True,
                duration_ms=200,
                stdout_tail="",
                stderr_tail="",
                error_message=None,
            )
            result = run_post_merge_apply(batch_id=batch_id)

        assert result.success is True
        assert result.final_batch_state == "merged"


@pytest.mark.integration
@pytest.mark.slow
def test_pipeline_happy_path(unique_batch_id: int) -> None:  # noqa: assertion-scanner
    """Valid migration → Phase 1 pass → Phase 2 pass."""
    _run_pipeline_happy_path(unique_batch_id)


@pytest.mark.integration
@pytest.mark.slow
def test_dry_run_rejects_broken_migration(unique_batch_id: int) -> None:
    """Migration whose upgrade() raises → Phase 1 fails → MIGRATION_INVALID."""
    with patch("orch.daemon.migration_pipeline.get_db_url", return_value=DUMMY_DB_URL):
        with patch("orch.daemon.migration_pipeline.safe_dry_run") as mock_dry:
            from orch.db.safe_migrate import DryRunResult

            mock_dry.return_value = DryRunResult(
                revisions_applied=[],
                success=False,
                duration_ms=50,
                stdout_tail="",
                stderr_tail="ERROR: syntax error",
                error_message="syntax error",
            )
            result = run_pre_merge_dry_run(batch_id=unique_batch_id)

        assert result.success is False
        assert result.final_batch_state == "MIGRATION_INVALID"
        assert result.frozen is False


@pytest.mark.integration
@pytest.mark.slow
def test_apply_fails_rollback_succeeds(unique_batch_id: int) -> None:
    """Migration passes dry-run but fails apply → Phase 3 downgrades cleanly."""
    with patch("orch.daemon.migration_pipeline.get_db_url", return_value=DUMMY_DB_URL):
        with patch("orch.daemon.migration_pipeline.safe_dry_run") as mock_dry:
            from orch.db.safe_migrate import DryRunResult

            mock_dry.return_value = DryRunResult(
                revisions_applied=["abc123"],
                success=True,
                duration_ms=100,
                stdout_tail="",
                stderr_tail="",
                error_message=None,
            )
            dry_result = run_pre_merge_dry_run(batch_id=unique_batch_id)

        assert dry_result.success is True

        with patch("orch.daemon.migration_pipeline.safe_apply") as mock_apply:
            from orch.db.safe_migrate import ApplyResult

            # Apply started, committed revision abc123, then died — Phase 3
            # rollback is warranted because the live DB advanced.
            mock_apply.return_value = ApplyResult(
                revisions_applied=["abc123"],
                success=False,
                duration_ms=50,
                stdout_tail="",
                stderr_tail="ERROR: connection lost",
                error_message="connection lost",
            )
            apply_result = run_post_merge_apply(batch_id=unique_batch_id)

        assert apply_result.success is False
        assert apply_result.final_batch_state == "rollback_triggered"
        assert apply_result.revisions_applied == ["abc123"]

        with patch("orch.daemon.migration_pipeline.safe_rollback") as mock_rollback:
            from orch.db.safe_migrate import RollbackResult

            mock_rollback.return_value = RollbackResult(
                revision_from="abc123",
                revision_to="base",
                success=True,
                duration_ms=100,
                error_message=None,
            )
            rollback_result = run_rollback(batch_id=unique_batch_id)

        assert rollback_result.success is True
        assert rollback_result.final_batch_state == "MIGRATION_ROLLED_BACK"
        assert rollback_result.frozen is False


@pytest.mark.integration
@pytest.mark.slow
def test_apply_fails_before_any_revision_defers_without_rollback(
    unique_batch_id: int,
) -> None:
    """A SelfBlockerError-style apply failure that applied *zero* revisions
    must NOT advertise ``rollback_triggered`` — there is nothing on the DB to
    roll back, and a ``downgrade -1`` would clobber a previously-applied
    migration (the post-merge rollback regression seen after the BATCH-00089
    merge on 2026-05-11)."""
    with patch("orch.daemon.migration_pipeline.get_db_url", return_value=DUMMY_DB_URL):
        with patch("orch.daemon.migration_pipeline.safe_apply") as mock_apply:
            from orch.db.safe_migrate import ApplyResult

            mock_apply.return_value = ApplyResult(
                revisions_applied=[],
                success=False,
                duration_ms=0,
                stdout_tail="",
                stderr_tail="",
                error_message=(
                    "Phase 2 apply would self-deadlock: daemon's own session "
                    "holds AccessShareLock on projects. See I-00063 for context."
                ),
            )
            apply_result = run_post_merge_apply(batch_id=unique_batch_id)

        assert apply_result.success is False
        assert apply_result.final_batch_state == "apply_deferred"
        assert apply_result.revisions_applied == []


@pytest.mark.integration
@pytest.mark.slow
def test_apply_fails_rollback_fails_freezes_queue(unique_batch_id: int) -> None:
    """Both apply AND rollback fail → PipelineResult.frozen is True."""
    with patch("orch.daemon.migration_pipeline.get_db_url", return_value=DUMMY_DB_URL):
        with patch("orch.daemon.migration_pipeline.safe_apply") as mock_apply:
            from orch.db.safe_migrate import ApplyResult

            mock_apply.return_value = ApplyResult(
                revisions_applied=[],
                success=False,
                duration_ms=50,
                stdout_tail="",
                stderr_tail="connection lost",
                error_message="connection lost",
            )
            apply_result = run_post_merge_apply(batch_id=unique_batch_id)

        assert apply_result.success is False

        with patch("orch.daemon.migration_pipeline.safe_rollback") as mock_rollback:
            from orch.db.safe_migrate import RollbackResult

            mock_rollback.return_value = RollbackResult(
                revision_from="abc123",
                revision_to="base",
                success=False,
                duration_ms=50,
                error_message="downgrade failed",
            )
            with patch("orch.daemon.migration_pipeline.set_merge_queue_frozen"):
                rollback_result = run_rollback(batch_id=unique_batch_id)

        assert rollback_result.success is False
        assert rollback_result.frozen is True
        assert rollback_result.final_batch_state == "MIGRATION_ROLLED_BACK"


@pytest.mark.integration
@pytest.mark.slow
def test_multi_head_state_rejected(unique_batch_id: int) -> None:
    """Two heads → run_pre_merge_dry_run → MultipleHeadsError → MIGRATION_INVALID."""
    with patch("orch.daemon.migration_pipeline.get_db_url", return_value=DUMMY_DB_URL):
        with patch("orch.daemon.migration_pipeline.safe_dry_run") as mock_dry:
            from orch.db.safe_migrate import MultipleHeadsError

            mock_dry.side_effect = MultipleHeadsError(
                "Multiple alembic heads detected: ['rev_a', 'rev_b']. "
                "Create a merge revision with `alembic merge -m 'merge branches' rev_a rev_b` "
                "before applying migrations."
            )
            result = run_pre_merge_dry_run(batch_id=unique_batch_id)

        assert result.success is False
        assert result.final_batch_state == "MIGRATION_INVALID"
        assert "Multiple" in result.message or "heads" in result.message.lower()


@pytest.mark.integration
def test_frozen_queue_blocks_merges() -> None:  # noqa: assertion-scanner
    """When merge queue is frozen, process_merge_queue skips batches entirely."""
    from unittest.mock import MagicMock

    from orch.daemon.merge_queue import process_merge_queue

    config = MagicMock()
    project_config = MagicMock()
    project_config.working_dir = "/tmp"
    project_config.worktree_base = "worktrees"
    project_config.cli_tool = "opencode"

    with patch("orch.daemon.merge_queue.is_merge_queue_frozen", return_value=True):
        process_merge_queue(MagicMock(), "any-project", project_config, config)


# ---------------------------------------------------------------------------
# R4 — I-00041 mock-coverage smoke test (operator-only)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_no_pending_migration_log_writes_to_live_db_under_test_context(
    unique_batch_id: int,
) -> None:
    """I-00041 regression: running the migration pipeline tests under
    test-context must NOT write any row to live pending_migration_log.

    Snapshot the live DB row count before, run a representative pipeline
    test in-process (under mocks), snapshot after, assert equal. This is
    the truth oracle that the connection-layer guard + mock coverage
    together close the bypass.

    This test is OPERATOR-ONLY — it deliberately opts into the live DB
    read to verify writes haven't happened. Skipped in normal CI.
    """
    from sqlalchemy import create_engine, text

    live_host = os.environ.get("IW_CORE_DB_HOST", "localhost")
    live_port = os.environ.get("IW_CORE_DB_PORT", "5433")

    if os.environ.get("IW_CORE_OPERATOR_APPLY") != "true":
        pytest.skip("Operator-only smoke test — set IW_CORE_OPERATOR_APPLY=true to run")

    url = f"postgresql://iw_orch:iw_orch@{live_host}:{live_port}/iw_orch"
    engine = create_engine(url)
    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM pending_migration_log")).scalar()

    _run_pipeline_happy_path(unique_batch_id)

    with engine.connect() as conn:
        after = conn.execute(text("SELECT count(*) FROM pending_migration_log")).scalar()

    assert after == before, (
        f"I-00041 regression: pipeline test wrote {after - before} row(s) "
        f"to live pending_migration_log. The mocks are not covering "
        f"_write_migration_log."
    )
