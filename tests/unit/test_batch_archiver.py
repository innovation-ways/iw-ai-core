"""Unit tests for batch_archiver — no DB, no subprocess.

All database interaction and subprocess calls are mocked.
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from orch.archive.batch_archiver import archive_batch
from orch.db.models import BatchItemStatus, BatchStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_batch(
    status: BatchStatus = BatchStatus.completed, config: dict | None = None
) -> MagicMock:
    b = MagicMock()
    b.status = status
    b.config = config if config is not None else {}
    b.updated_at = None
    return b


def _make_project(repo_root: str = "/repos/proj", config: dict | None = None) -> MagicMock:
    p = MagicMock()
    p.repo_root = repo_root
    p.config = config if config is not None else {}
    return p


def _make_batch_item(
    work_item_id: str, status: BatchItemStatus = BatchItemStatus.merged
) -> MagicMock:
    bi = MagicMock()
    bi.work_item_id = work_item_id
    bi.status = status
    return bi


def _make_db(batch: MagicMock, project: MagicMock, batch_items: list) -> MagicMock:
    db = MagicMock()

    def _get(model: type, key: object) -> MagicMock | None:
        # Batch has composite key (project_id, batch_id)
        if hasattr(model, "__tablename__") and model.__tablename__ == "batches":
            return batch
        # Project has single key
        if hasattr(model, "__tablename__") and model.__tablename__ == "projects":
            return project
        return None

    db.get.side_effect = _get

    scalars = MagicMock()
    scalars.all.return_value = batch_items
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars
    db.execute.return_value = execute_result

    return db


@contextmanager
def _mock_session(db: MagicMock):
    """Simulate SessionLocal() context manager."""
    yield db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestArchiveBatchCompleted:
    """Happy path: batch completed, all items merged, commands succeed."""

    def test_archive_batch_completed(self) -> None:
        batch = _make_batch(BatchStatus.completed)
        project = _make_project(config={"post_archive_commands": ["echo done"]})
        items = [
            _make_batch_item("F-00001", BatchItemStatus.merged),
            _make_batch_item("F-00002", BatchItemStatus.merged),
        ]
        db = _make_db(batch, project, items)

        proc_result = MagicMock()
        proc_result.returncode = 0
        proc_result.stdout = "done\n"
        proc_result.stderr = ""

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            patch("subprocess.run", return_value=proc_result),
            patch("orch.archive.batch_archiver.archive_work_item") as mock_archive,
        ):
            result = archive_batch("proj", "BATCH-001")

        assert result.success is True
        assert result.batch_id == "BATCH-001"
        assert sorted(result.items_archived) == ["F-00001", "F-00002"]
        assert result.items_skipped == []
        assert result.error is None
        assert len(result.commands_run) == 1
        assert result.commands_run[0].returncode == 0
        assert mock_archive.call_count == 2


class TestArchiveBatchCompletedWithErrors:
    """Mixed merged/failed items — only merged items are archived."""

    def test_archive_batch_completed_with_errors(self) -> None:
        batch = _make_batch(BatchStatus.completed_with_errors)
        project = _make_project()
        items = [
            _make_batch_item("F-00001", BatchItemStatus.merged),
            _make_batch_item("F-00002", BatchItemStatus.failed),
            _make_batch_item("F-00003", BatchItemStatus.merged),
        ]
        db = _make_db(batch, project, items)

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            patch("orch.archive.batch_archiver.archive_work_item") as mock_archive,
        ):
            result = archive_batch("proj", "BATCH-001")

        assert result.success is True
        assert sorted(result.items_archived) == ["F-00001", "F-00003"]
        assert result.items_skipped == ["F-00002"]
        assert mock_archive.call_count == 2


class TestArchiveBatchInvalidStatus:
    """Batch in wrong status → ValueError raised."""

    def test_archive_batch_invalid_status(self) -> None:
        batch = _make_batch(BatchStatus.executing)
        project = _make_project()
        db = _make_db(batch, project, [])

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            pytest.raises(ValueError, match="executing"),
        ):
            archive_batch("proj", "BATCH-001")


class TestArchiveBatchNoPostCommands:
    """No post_archive_commands in project config — no subprocess calls."""

    def test_archive_batch_no_post_commands(self) -> None:
        batch = _make_batch(BatchStatus.completed)
        project = _make_project(config={})
        items = [_make_batch_item("F-00001", BatchItemStatus.merged)]
        db = _make_db(batch, project, items)

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            patch("subprocess.run") as mock_run,
            patch("orch.archive.batch_archiver.archive_work_item"),
        ):
            result = archive_batch("proj", "BATCH-001")

        mock_run.assert_not_called()
        assert result.commands_run == []
        assert result.success is True


class TestArchiveBatchCommandFailure:
    """Command returns non-zero — archive still completes successfully."""

    def test_archive_batch_command_failure(self) -> None:
        batch = _make_batch(BatchStatus.completed, config={"post_archive_commands": ["false"]})
        project = _make_project(config={"post_archive_commands": ["false"]})
        items = [_make_batch_item("F-00001", BatchItemStatus.merged)]
        db = _make_db(batch, project, items)

        proc_result = MagicMock()
        proc_result.returncode = 1
        proc_result.stdout = ""
        proc_result.stderr = "error output"

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            patch("subprocess.run", return_value=proc_result),
            patch("orch.archive.batch_archiver.archive_work_item"),
        ):
            result = archive_batch("proj", "BATCH-001")

        assert result.success is True
        assert result.commands_run[0].returncode == 1


class TestArchiveBatchCommandTimeout:
    """Command times out — archive still completes successfully."""

    def test_archive_batch_command_timeout(self) -> None:
        batch = _make_batch(BatchStatus.completed, config={"post_archive_commands": ["sleep 999"]})
        project = _make_project(config={"post_archive_commands": ["sleep 999"]})
        items = [_make_batch_item("F-00001", BatchItemStatus.merged)]
        db = _make_db(batch, project, items)

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("sleep", 300)),
            patch("orch.archive.batch_archiver.archive_work_item"),
        ):
            result = archive_batch("proj", "BATCH-001")

        assert result.success is True
        # Timed-out command is recorded with returncode -1
        assert len(result.commands_run) == 1
        assert result.commands_run[0].returncode == -1


class TestArchiveBatchItemArchiveError:
    """One item archive raises — others still archived."""

    def test_archive_batch_item_archive_error(self) -> None:
        batch = _make_batch(BatchStatus.completed)
        project = _make_project()
        items = [
            _make_batch_item("F-00001", BatchItemStatus.merged),
            _make_batch_item("F-00002", BatchItemStatus.merged),
        ]
        db = _make_db(batch, project, items)

        call_count = 0

        def _side_effect(db: object, project_id: str, item_id: str, archive_dir: object) -> None:
            nonlocal call_count
            call_count += 1
            if item_id == "F-00001":
                raise RuntimeError("disk full")

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            patch("orch.archive.batch_archiver.archive_work_item", side_effect=_side_effect),
        ):
            result = archive_batch("proj", "BATCH-001")

        # F-00002 still archived despite F-00001 failing
        assert "F-00002" in result.items_archived
        assert result.success is True


class TestArchiveBatchNoItems:
    """Batch with zero items — should still transition to archived."""

    def test_archive_batch_no_items(self) -> None:
        batch = _make_batch(BatchStatus.completed)
        project = _make_project()
        db = _make_db(batch, project, [])

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            patch("subprocess.run"),
            patch("orch.archive.batch_archiver.archive_work_item") as mock_archive,
        ):
            result = archive_batch("proj", "BATCH-001")

        assert result.success is True
        assert result.items_archived == []
        assert result.items_skipped == []
        assert mock_archive.call_count == 0
        # Batch status should still be updated
        assert batch.status == BatchStatus.archived


class TestArchiveBatchProjectNotFound:
    """Project not in DB → ValueError raised."""

    def test_archive_batch_project_not_found(self) -> None:
        batch = _make_batch(BatchStatus.completed)

        # Return None for project lookup
        def _get(model: type, key: object) -> MagicMock | None:
            if hasattr(model, "__tablename__") and model.__tablename__ == "batches":
                return batch
            if hasattr(model, "__tablename__") and model.__tablename__ == "projects":
                return None
            return None

        db = MagicMock()
        db.get.side_effect = _get

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            pytest.raises(ValueError, match="Project.*not found"),
        ):
            archive_batch("proj", "BATCH-001")


class TestArchiveBatchConcurrentAttempt:
    """Second archive call when batch is already archived → handled gracefully."""

    def test_archive_batch_already_archived(self) -> None:
        # First call transitions to archived
        batch = _make_batch(BatchStatus.completed)
        project = _make_project()
        db = _make_db(batch, project, [])

        def _get(model: type, key: object) -> MagicMock | None:
            if hasattr(model, "__tablename__") and model.__tablename__ == "batches":
                return batch
            if hasattr(model, "__tablename__") and model.__tablename__ == "projects":
                return project
            return None

        db.get.side_effect = _get

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            patch("subprocess.run"),
            patch("orch.archive.batch_archiver.archive_work_item"),
        ):
            # First call succeeds
            result1 = archive_batch("proj", "BATCH-001")
            assert result1.success is True

            # Second call on already-archived batch — status is no longer valid
            with pytest.raises(ValueError, match="executing|completed_with_errors|archived"):
                archive_batch("proj", "BATCH-001")


class TestArchiveBatchEmitsEvent:
    """DaemonEvent with event_type='batch_archived' is created after success."""

    def test_archive_batch_emits_event(self) -> None:
        batch = _make_batch(BatchStatus.completed)
        project = _make_project()
        items = [_make_batch_item("F-00001", BatchItemStatus.merged)]
        db = _make_db(batch, project, items)

        added_objects: list[object] = []
        db.add.side_effect = added_objects.append

        with (
            patch("orch.archive.batch_archiver.SessionLocal", return_value=db),
            patch("orch.archive.batch_archiver.archive_work_item"),
        ):
            result = archive_batch("proj", "BATCH-001")

        assert result.success is True
        # Find the DaemonEvent in added objects
        from orch.db.models import DaemonEvent

        events = [o for o in added_objects if isinstance(o, DaemonEvent)]
        assert len(events) == 1
        assert events[0].event_type == "batch_archived"
        assert events[0].project_id == "proj"
