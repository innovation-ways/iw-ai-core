"""Integration tests for the 3-phase migration pipeline.

These tests use mocking to control the pipeline's DB access while verifying
the three-phase orchestration logic (dry_run → apply → rollback).

Tests that require real DB access for freeze/unfreeze verification are in
test_migration_pipeline_frozen.py.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from orch.daemon.migration_pipeline import (
    run_post_merge_apply,
    run_pre_merge_dry_run,
    run_rollback,
)

DUMMY_DB_URL = "postgresql+psycopg://test:test@localhost:5432/test_db"


@pytest.mark.integration
@pytest.mark.slow
def test_pipeline_happy_path() -> None:
    """Valid migration → Phase 1 pass → Phase 2 pass."""
    batch_id = 42

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
def test_dry_run_rejects_broken_migration() -> None:
    """Migration whose upgrade() raises → Phase 1 fails → MIGRATION_INVALID."""
    batch_id = 42

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
            result = run_pre_merge_dry_run(batch_id=batch_id)

        assert result.success is False
        assert result.final_batch_state == "MIGRATION_INVALID"
        assert result.frozen is False


@pytest.mark.integration
@pytest.mark.slow
def test_apply_fails_rollback_succeeds() -> None:
    """Migration passes dry-run but fails apply → Phase 3 downgrades cleanly."""
    batch_id = 42

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
            dry_result = run_pre_merge_dry_run(batch_id=batch_id)

        assert dry_result.success is True

        with patch("orch.daemon.migration_pipeline.safe_apply") as mock_apply:
            from orch.db.safe_migrate import ApplyResult

            mock_apply.return_value = ApplyResult(
                revisions_applied=[],
                success=False,
                duration_ms=50,
                stdout_tail="",
                stderr_tail="ERROR: connection lost",
                error_message="connection lost",
            )
            apply_result = run_post_merge_apply(batch_id=batch_id)

        assert apply_result.success is False
        assert apply_result.final_batch_state == "rollback_triggered"

        with patch("orch.daemon.migration_pipeline.safe_rollback") as mock_rollback:
            from orch.db.safe_migrate import RollbackResult

            mock_rollback.return_value = RollbackResult(
                revision_from="abc123",
                revision_to="base",
                success=True,
                duration_ms=100,
                error_message=None,
            )
            rollback_result = run_rollback(batch_id=batch_id)

        assert rollback_result.success is True
        assert rollback_result.final_batch_state == "MIGRATION_ROLLED_BACK"
        assert rollback_result.frozen is False


@pytest.mark.integration
@pytest.mark.slow
def test_apply_fails_rollback_fails_freezes_queue() -> None:
    """Both apply AND rollback fail → PipelineResult.frozen is True."""
    batch_id = 42

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
            apply_result = run_post_merge_apply(batch_id=batch_id)

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
                rollback_result = run_rollback(batch_id=batch_id)

        assert rollback_result.success is False
        assert rollback_result.frozen is True
        assert rollback_result.final_batch_state == "MIGRATION_ROLLED_BACK"


@pytest.mark.integration
@pytest.mark.slow
def test_multi_head_state_rejected() -> None:
    """Two heads → run_pre_merge_dry_run → MultipleHeadsError → MIGRATION_INVALID."""
    batch_id = 42

    with patch("orch.daemon.migration_pipeline.get_db_url", return_value=DUMMY_DB_URL):
        with patch("orch.daemon.migration_pipeline.safe_dry_run") as mock_dry:
            from orch.db.safe_migrate import MultipleHeadsError

            mock_dry.side_effect = MultipleHeadsError(
                "Multiple alembic heads detected: ['rev_a', 'rev_b']. "
                "Create a merge revision with `alembic merge -m 'merge branches' rev_a rev_b` "
                "before applying migrations."
            )
            result = run_pre_merge_dry_run(batch_id=batch_id)

        assert result.success is False
        assert result.final_batch_state == "MIGRATION_INVALID"
        assert "Multiple" in result.message or "heads" in result.message.lower()


@pytest.mark.integration
def test_frozen_queue_blocks_merges() -> None:
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
