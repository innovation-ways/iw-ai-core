"""Unit tests for archive_batch in orch.archive.archiver — no DB, no subprocess.

All database interaction is mocked via patching get_session.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from orch.archive.archiver import archive_batch
from orch.db.models import BatchItemStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_batch_item(
    work_item_id: str,
    status: BatchItemStatus = BatchItemStatus.merged,
    project_id: str = "proj",
    batch_id: str = "BATCH-001",
) -> MagicMock:
    bi = MagicMock()
    bi.work_item_id = work_item_id
    bi.status = status
    bi.project_id = project_id
    bi.batch_id = batch_id
    return bi


def _make_project(repo_root: str = "/repos/proj") -> MagicMock:
    p = MagicMock()
    p.repo_root = repo_root
    return p


def _make_db(batch_items: list, project: MagicMock | None = None) -> MagicMock:
    db = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = batch_items
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars
    db.execute.return_value = execute_result
    db.get.return_value = project if project is not None else _make_project()
    return db


@contextmanager
def _mock_session(db: MagicMock):
    yield db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestArchiveBatchCompleted:
    """Happy path: all merged items are archived."""

    def test_archive_batch_completed(self) -> None:
        items = [
            _make_batch_item("F-00001"),
            _make_batch_item("F-00002"),
        ]
        db = _make_db(items)

        with (
            patch("orch.db.session.get_session", return_value=_mock_session(db)),
            patch("orch.archive.archiver.archive_work_item") as mock_archive,
        ):
            result = archive_batch("proj", "BATCH-001")

        assert sorted(result) == ["F-00001", "F-00002"]
        assert mock_archive.call_count == 2
        db.commit.assert_called_once()


class TestArchiveBatchNoItems:
    """Batch with zero merged items — returns empty list."""

    def test_archive_batch_no_items(self) -> None:
        db = _make_db([])

        with (
            patch("orch.db.session.get_session", return_value=_mock_session(db)),
            patch("orch.archive.archiver.archive_work_item") as mock_archive,
        ):
            result = archive_batch("proj", "BATCH-001")

        assert result == []
        assert mock_archive.call_count == 0


class TestArchiveBatchItemArchiveError:
    """One item archive raises — others still archived."""

    def test_archive_batch_item_archive_error(self) -> None:
        items = [
            _make_batch_item("F-00001"),
            _make_batch_item("F-00002"),
        ]
        db = _make_db(items)

        def _side_effect(db, project_id, item_id, archive_dir):
            if item_id == "F-00001":
                raise RuntimeError("disk full")

        with (
            patch("orch.db.session.get_session", return_value=_mock_session(db)),
            patch("orch.archive.archiver.archive_work_item", side_effect=_side_effect),
        ):
            result = archive_batch("proj", "BATCH-001")

        # F-00002 still archived despite F-00001 failing
        assert result == ["F-00002"]
