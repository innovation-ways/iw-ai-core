"""Integration tests for merge-queue retry-merge command against a real PostgreSQL testcontainer.

These tests require a testcontainer DB (make test-integration) because they
verify semantic DB outcomes (status flips, audit events written) that can
only be observed with a real database session.

For pure unit tests (no DB, CliRunner with mocks), see tests/unit/test_merge_queue_cli.py.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from orch.cli.main import cli as root_cli
from orch.daemon.merge_queue import OPERATOR_RECOVERABLE_MERGE_STATUSES
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _seeded_retry_session(
    session: Any,
    project_id: str,
    item_id: str,
    status: BatchItemStatus,
    worktree_path: Path,
    notes: str | None = None,
) -> Any:
    """Context manager that seeds a BatchItem into an existing session and yields it.

    session must be the test's db_session so that seeded rows are on the same
    connection as cli_get_session (which also yields db_session). This ensures
    the CLI can see the flushed-but-not-yet-committed rows under PostgreSQL
    READ COMMITTED isolation.
    """
    project = session.get(Project, project_id)
    if project is None:
        project = Project(
            id=project_id,
            display_name="Test Project",
            repo_root="/repos/test",
            config={},
        )
        session.add(project)

    work_item = (
        session.execute(
            select(WorkItem).where(WorkItem.project_id == project_id, WorkItem.id == item_id)
        )
        .scalars()
        .first()
    )
    if work_item is None:
        work_item = WorkItem(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Issue,
            title=f"Test item {item_id}",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        session.add(work_item)

    batch_id = f"BATCH-TEST-{item_id}"
    batch = session.get(Batch, (project_id, batch_id))
    if batch is None:
        batch = Batch(
            project_id=project_id,
            id=batch_id,
            status=BatchStatus.executing,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
        )
        session.add(batch)
        session.flush()

    batch_item = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=item_id,
        status=status,
        notes=notes,
        worktree_info={"path": str(worktree_path)},
    )
    session.add(batch_item)
    session.flush()

    yield session


def _invoke_retry_merge(
    runner: CliRunner,
    item_id: str,
    get_session: Callable[..., Any],
) -> Any:
    return runner.invoke(
        root_cli,
        ["--project", "test-proj", "merge-queue", "retry-merge", item_id],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRetryMergeAcceptsRecoverableStatuses:
    """Regression tests for all four operator-recoverable statuses.

    These tests verify that `iw merge-queue retry-merge` accepts each
    status in OPERATOR_RECOVERABLE_MERGE_STATUSES and flips it to
    `completed` with a `merge_retry_requested` audit event.
    """

    @pytest.mark.parametrize(
        "status",
        [
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
            BatchItemStatus.migration_rolled_back,
        ],
    )
    def test_i00072_retry_merge_accepts_recoverable_status(
        self,
        db_session: Any,
        test_project: Any,
        cli_get_session: Callable[..., Any],
        status: BatchItemStatus,
        sample_worktree_path: Path,
    ) -> None:
        """Each recoverable status is accepted, flipped to completed, and audited."""
        project_id = "test-proj"
        item_id = f"F-RETRY-{status.name}"

        with _seeded_retry_session(
            db_session,
            project_id=project_id,
            item_id=item_id,
            status=status,
            worktree_path=sample_worktree_path,
        ) as session:
            runner = CliRunner()
            result = _invoke_retry_merge(runner, item_id, cli_get_session)

            assert result.exit_code == 0, (
                f"[{status.name}] exit {result.exit_code}: {result.output}"
            )

            item = (
                session.execute(select(BatchItem).where(BatchItem.work_item_id == item_id))
                .scalars()
                .first()
            )
            assert item.status == BatchItemStatus.completed, (
                f"[{status.name}] expected completed, got {item.status.name}"
            )

            event = (
                session.execute(
                    select(DaemonEvent).where(
                        DaemonEvent.event_type == "merge_retry_requested",
                        DaemonEvent.entity_id == item_id,
                    )
                )
                .scalars()
                .first()
            )
            assert event is not None, f"[{status.name}] merge_retry_requested event not found"


class TestRetryMergeLegacyBackCompat:
    """Legacy back-compat: pre-CR-00028 items in `failed` status with merge notes.

    Two sub-cases:
    - 3a: notes start with "Merge failed" → accepted
    - 3b: notes do NOT start with "Merge failed" → rejected with non-zero exit
    """

    def test_i00072_retry_merge_accepts_legacy_failed_with_merge_notes(
        self,
        db_session: Any,
        test_project: Any,
        cli_get_session: Callable[..., Any],
        sample_worktree_path: Path,
    ) -> None:
        """Legacy: failed + 'Merge failed: …' notes → accepted."""
        project_id = "test-proj"
        item_id = "F-LEGACY-OK"
        notes = "Merge failed: rebase conflict on orch/db/migrations/versions/abc.py"

        with _seeded_retry_session(
            db_session,
            project_id=project_id,
            item_id=item_id,
            status=BatchItemStatus.failed,
            worktree_path=sample_worktree_path,
            notes=notes,
        ) as session:
            runner = CliRunner()
            result = _invoke_retry_merge(runner, item_id, cli_get_session)

            assert result.exit_code == 0, f"expected 0, got {result.exit_code}: {result.output}"

            item = (
                session.execute(select(BatchItem).where(BatchItem.work_item_id == item_id))
                .scalars()
                .first()
            )
            assert item.status == BatchItemStatus.completed, (
                f"expected completed, got {item.status.name}"
            )

            event = (
                session.execute(
                    select(DaemonEvent).where(
                        DaemonEvent.event_type == "merge_retry_requested",
                        DaemonEvent.entity_id == item_id,
                    )
                )
                .scalars()
                .first()
            )
            assert event is not None, "merge_retry_requested event not found"

    def test_i00072_retry_merge_rejects_legacy_failed_without_merge_notes(
        self,
        db_session: Any,
        test_project: Any,
        cli_get_session: Callable[..., Any],
        sample_worktree_path: Path,
    ) -> None:
        """Legacy: failed + non-merge notes → rejected, status unchanged."""
        project_id = "test-proj"
        item_id = "F-LEGACY-BAD"
        notes = "Setup failed: clone timeout"

        with _seeded_retry_session(
            db_session,
            project_id=project_id,
            item_id=item_id,
            status=BatchItemStatus.failed,
            worktree_path=sample_worktree_path,
            notes=notes,
        ) as session:
            runner = CliRunner()
            result = _invoke_retry_merge(runner, item_id, cli_get_session)

            assert result.exit_code != 0, f"expected non-zero, got {result.exit_code}"

            item = (
                session.execute(select(BatchItem).where(BatchItem.work_item_id == item_id))
                .scalars()
                .first()
            )
            assert item.status == BatchItemStatus.failed, (
                f"expected failed (unchanged), got {item.status.name}"
            )

            assert "item restart" in result.output.lower(), (
                f"error should guide to 'iw item restart', got: {result.output}"
            )


class TestRetryMergeWorktreeMissing:
    """Worktree-missing case — existing behaviour preserved by a regression pin."""

    def test_i00072_retry_merge_rejects_missing_worktree(
        self,
        db_session: Any,
        test_project: Any,
        cli_get_session: Callable[..., Any],
        tmp_path: Path,
    ) -> None:
        """A recoverable-item whose worktree no longer exists is rejected."""
        project_id = "test-proj"
        item_id = "F-WT-GONE"
        missing_path = tmp_path / "this-path-does-not-exist"

        with _seeded_retry_session(
            db_session,
            project_id=project_id,
            item_id=item_id,
            status=BatchItemStatus.merge_failed,
            worktree_path=missing_path,
        ) as session:
            runner = CliRunner()
            result = _invoke_retry_merge(runner, item_id, cli_get_session)

            assert result.exit_code != 0, f"expected non-zero, got {result.exit_code}"
            assert "Worktree not found" in result.output, (
                f"expected 'Worktree not found' error, got: {result.output}"
            )

            item = (
                session.execute(select(BatchItem).where(BatchItem.work_item_id == item_id))
                .scalars()
                .first()
            )
            assert item.status == BatchItemStatus.merge_failed, (
                f"expected merge_failed (unchanged), got {item.status.name}"
            )


class TestRetryMergeParity:
    """CLI/dashboard parity test — requires full integration fixtures."""

    def test_i00072_cli_and_dashboard_share_recoverable_status_set(
        self,
        db_engine: Any,
        db_session: Any,
        test_project: Any,
        cli_get_session: Callable[..., Any],
    ) -> None:
        """The CLI and dashboard must accept the same set of statuses.

        Future drift is prevented by both surfaces importing
        OPERATOR_RECOVERABLE_MERGE_STATUSES from the same module.
        """
        from unittest.mock import patch

        import orch.cli.merge_queue_commands as cli_module  # type: ignore[import-untyped]

        with patch("orch.db.live_db_guard.is_live_db_url", return_value=False):
            import dashboard.routers.actions as dash_module  # type: ignore[import-untyped]

        # Identity check: the modules share the same frozenset object, not a copy.
        assert cli_module.OPERATOR_RECOVERABLE_MERGE_STATUSES is OPERATOR_RECOVERABLE_MERGE_STATUSES
        assert (
            dash_module.OPERATOR_RECOVERABLE_MERGE_STATUSES is OPERATOR_RECOVERABLE_MERGE_STATUSES
        )
