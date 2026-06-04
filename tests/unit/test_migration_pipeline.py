"""Unit tests for migration_pipeline module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    import pytest


class TestIsMergeQueueFrozen:
    """Tests for is_merge_queue_frozen()."""

    def test_returns_false_when_no_events_row(self) -> None:
        """Verifies that returns false when no events row."""
        from orch.daemon.migration_pipeline import is_merge_queue_frozen

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result

        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)

        with patch("orch.daemon.migration_pipeline.safe_create_engine") as mock_engine:
            mock_engine.return_value.connect.return_value = mock_connection
            mock_engine.return_value.dispose = MagicMock()
            with patch("orch.daemon.migration_pipeline.sessionmaker") as mock_sm:
                mock_sm.return_value.return_value = mock_session

                result = is_merge_queue_frozen()

        assert result is False

    def test_returns_true_when_active_is_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that returns true when active is true."""
        from orch.daemon.migration_pipeline import is_merge_queue_frozen

        # is_merge_queue_frozen short-circuits to False under IW_CORE_TEST_CONTEXT
        # to keep tests from making out-of-band live-DB connections. This test
        # exercises the real query path with mocks, so opt out of that guard.
        monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)

        mock_result = MagicMock()
        mock_result.fetchone.return_value = ({"active": True},)

        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result

        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)

        with patch("orch.daemon.migration_pipeline.safe_create_engine") as mock_engine:
            mock_engine.return_value.connect.return_value = mock_connection
            mock_engine.return_value.dispose = MagicMock()
            with patch("orch.daemon.migration_pipeline.sessionmaker") as mock_sm:
                mock_sm.return_value.return_value = mock_session

                result = is_merge_queue_frozen()

        assert result is True

    def test_returns_false_when_active_is_false(self) -> None:
        """Verifies that returns false when active is false."""
        from orch.daemon.migration_pipeline import is_merge_queue_frozen

        mock_result = MagicMock()
        mock_result.fetchone.return_value = ({"active": False},)

        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result

        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)

        with patch("orch.daemon.migration_pipeline.safe_create_engine") as mock_engine:
            mock_engine.return_value.connect.return_value = mock_connection
            mock_engine.return_value.dispose = MagicMock()
            with patch("orch.daemon.migration_pipeline.sessionmaker") as mock_sm:
                mock_sm.return_value.return_value = mock_session

                result = is_merge_queue_frozen()

        assert result is False


class TestSetMergeQueueFrozen:
    """Tests for set_merge_queue_frozen()."""

    def test_writes_expected_daemon_events_row(self) -> None:
        """Verifies that writes expected daemon events row."""
        mock_session = MagicMock()
        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)

        with patch("orch.daemon.migration_pipeline.safe_create_engine") as mock_engine:
            mock_engine.return_value.connect.return_value = mock_connection
            mock_engine.return_value.dispose = MagicMock()
            with patch("orch.daemon.migration_pipeline.sessionmaker") as mock_sm:
                mock_sm.return_value.return_value = mock_session
                from orch.daemon.migration_pipeline import set_merge_queue_frozen

                set_merge_queue_frozen(
                    active=True,
                    reason="Rollback failed",
                    acknowledged_by="operator1",
                )

                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()
                # Verify DaemonEvent row was created with correct frozen-state content
                added_event = mock_session.add.call_args[0][0]
                assert added_event.event_type == "merge_queue_frozen"


class TestRunPreMergeDryRun:
    """Tests for run_pre_merge_dry_run()."""

    def test_dispatches_to_safe_dry_run_success(self) -> None:
        """Verifies that dispatches to safe dry run success."""
        from orch.daemon.migration_pipeline import run_pre_merge_dry_run
        from orch.db.safe_migrate import DryRunResult

        mock_result = DryRunResult(
            revisions_applied=["abc123"],
            success=True,
            duration_ms=500,
            stdout_tail="",
            stderr_tail="",
            error_message=None,
        )

        with (
            patch("orch.daemon.migration_pipeline.safe_dry_run", return_value=mock_result),
            patch("testcontainers.postgres.PostgresContainer") as mock_pg_class,
        ):
            mock_container = MagicMock()
            mock_container.get_connection_url.return_value = (
                "postgresql+psycopg://user:pass@host:5432/db"
            )
            mock_container.start = MagicMock()
            mock_container.stop = MagicMock()
            mock_pg_class.return_value = mock_container

            result = run_pre_merge_dry_run(batch_id=42)

            assert result.success is True
            assert result.final_batch_state == "proceed_to_merge"

    def test_returns_migration_invalid_on_dry_run_failure(self) -> None:
        """Verifies that returns migration invalid on dry run failure."""
        from orch.daemon.migration_pipeline import run_pre_merge_dry_run
        from orch.db.safe_migrate import DryRunResult

        mock_result = DryRunResult(
            revisions_applied=[],
            success=False,
            duration_ms=100,
            stdout_tail="",
            stderr_tail="ERROR: syntax error",
            error_message="syntax error",
        )

        with (
            patch("orch.daemon.migration_pipeline.safe_dry_run", return_value=mock_result),
            patch("testcontainers.postgres.PostgresContainer") as mock_pg_class,
        ):
            mock_container = MagicMock()
            mock_container.get_connection_url.return_value = (
                "postgresql+psycopg://user:pass@host:5432/db"
            )
            mock_container.start = MagicMock()
            mock_container.stop = MagicMock()
            mock_pg_class.return_value = mock_container

            result = run_pre_merge_dry_run(batch_id=42)

            assert result.success is False
            assert result.final_batch_state == "MIGRATION_INVALID"

    def test_run_pre_merge_dry_run_threads_worktree_path(self) -> None:
        """Verifies that run pre merge dry run threads worktree path."""
        from orch.daemon.migration_pipeline import run_pre_merge_dry_run
        from orch.db.safe_migrate import DryRunResult

        mock_result = DryRunResult(
            revisions_applied=["abc123"],
            success=True,
            duration_ms=500,
            stdout_tail="",
            stderr_tail="",
            error_message=None,
        )

        with (
            patch(
                "orch.daemon.migration_pipeline.safe_dry_run", return_value=mock_result
            ) as mock_dry,
            patch("testcontainers.postgres.PostgresContainer") as mock_pg_class,
        ):
            mock_container = MagicMock()
            mock_container.get_connection_url.return_value = (
                "postgresql+psycopg://user:pass@host:5432/db"
            )
            mock_container.start = MagicMock()
            mock_container.stop = MagicMock()
            mock_pg_class.return_value = mock_container

            result = run_pre_merge_dry_run(batch_id=42, worktree_path="/wt")

            assert result.success is True
            mock_dry.assert_called_once()
            call_kwargs = mock_dry.call_args[1]
            assert call_kwargs["script_location"] == "/wt/orch/db/migrations"

    def test_run_pre_merge_dry_run_backward_compat(self) -> None:
        """Verifies that run pre merge dry run backward compat."""
        from orch.daemon.migration_pipeline import run_pre_merge_dry_run
        from orch.db.safe_migrate import DryRunResult

        mock_result = DryRunResult(
            revisions_applied=["abc123"],
            success=True,
            duration_ms=500,
            stdout_tail="",
            stderr_tail="",
            error_message=None,
        )

        with (
            patch(
                "orch.daemon.migration_pipeline.safe_dry_run", return_value=mock_result
            ) as mock_dry,
            patch("testcontainers.postgres.PostgresContainer") as mock_pg_class,
        ):
            mock_container = MagicMock()
            mock_container.get_connection_url.return_value = (
                "postgresql+psycopg://user:pass@host:5432/db"
            )
            mock_container.start = MagicMock()
            mock_container.stop = MagicMock()
            mock_pg_class.return_value = mock_container

            result = run_pre_merge_dry_run(batch_id=42)

            assert result.success is True
            mock_dry.assert_called_once()
            call_kwargs = mock_dry.call_args[1]
            assert call_kwargs["script_location"] is None


class TestRunRollback:
    """Tests for run_rollback()."""

    def test_on_rollback_fail_sets_frozen_true(self) -> None:
        """Verifies that on rollback fail sets frozen true."""
        from orch.daemon.migration_pipeline import run_rollback
        from orch.db.safe_migrate import RollbackResult

        mock_result = RollbackResult(
            revision_from="abc123",
            revision_to="base",
            success=False,
            duration_ms=100,
            error_message="Downgrade failed",
        )

        with (
            patch("orch.daemon.migration_pipeline.safe_rollback", return_value=mock_result),
            patch("orch.daemon.migration_pipeline.set_merge_queue_frozen") as mock_freeze,
        ):
            result = run_rollback(batch_id=42)

            assert result.success is False
            assert result.frozen is True
            assert result.final_batch_state == "MIGRATION_ROLLED_BACK"
            mock_freeze.assert_called_once()
            call_kwargs = mock_freeze.call_args[1]
            assert call_kwargs["active"] is True
            assert "Downgrade failed" in call_kwargs["reason"]

    def test_on_rollback_success_returns_rolled_back_state(self) -> None:
        """Verifies that on rollback success returns rolled back state."""
        from orch.daemon.migration_pipeline import run_rollback
        from orch.db.safe_migrate import RollbackResult

        mock_result = RollbackResult(
            revision_from="abc123",
            revision_to="base",
            success=True,
            duration_ms=100,
            error_message=None,
        )

        with (
            patch("orch.daemon.migration_pipeline.safe_rollback", return_value=mock_result),
            patch("orch.daemon.migration_pipeline.set_merge_queue_frozen") as mock_freeze,
        ):
            result = run_rollback(batch_id=42)

            assert result.success is True
            assert result.frozen is False
            assert result.final_batch_state == "MIGRATION_ROLLED_BACK"
            mock_freeze.assert_not_called()
