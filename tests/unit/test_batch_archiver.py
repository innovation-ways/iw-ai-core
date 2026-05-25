"""Unit tests for orch.archive.batch_archiver — no DB, no subprocess.

All DB interaction and subprocess calls are mocked.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from orch.archive.batch_archiver import archive_batch
from orch.db.models import BatchItemStatus, BatchStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GET_SESSION = "orch.db.session.get_session"
_ARCHIVE_ITEM = "orch.archive.batch_archiver.archive_work_item"
_SUBPROCESS_RUN = "orch.archive.batch_archiver.subprocess.run"


def _make_batch_item(
    work_item_id: str, project_id: str = "proj", batch_id: str = "BATCH-001"
) -> MagicMock:
    bi = MagicMock()
    bi.work_item_id = work_item_id
    bi.project_id = project_id
    bi.batch_id = batch_id
    bi.status = BatchItemStatus.merged
    return bi


def _make_project(repo_root: str = "/repos/proj", config: dict | None = None) -> MagicMock:
    p = MagicMock()
    p.repo_root = repo_root
    p.config = config or {}
    return p


def _make_batch(status: BatchStatus = BatchStatus.completed) -> MagicMock:
    b = MagicMock()
    b.status = status
    b.archived_at = None
    return b


def _make_db(
    batch: MagicMock | None = None,
    batch_items: list | None = None,
    project: MagicMock | None = None,
) -> MagicMock:
    db = MagicMock()

    work_items: dict[tuple[str, str], MagicMock] = {}

    if batch_items:
        for bi in batch_items:
            wi = MagicMock()
            wi.id = bi.work_item_id
            wi.project_id = bi.project_id
            wi.archived_at = None
            wi.design_doc_content = None
            wi.summary = None
            work_items[(bi.project_id, bi.work_item_id)] = wi

    def _get(model_cls, pk):  # noqa: ANN001
        from orch.db.models import Batch, Project, WorkItem  # noqa: PLC0415

        if model_cls is Batch:
            return batch if batch is not None else _make_batch()
        if model_cls is Project:
            return project if project is not None else _make_project()
        if model_cls is WorkItem:
            return work_items.get(pk)
        return None

    db.get.side_effect = _get

    scalars = MagicMock()
    scalars.all.return_value = batch_items if batch_items is not None else []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars
    db.execute.return_value = execute_result
    return db


@contextmanager
def _mock_session(db: MagicMock):
    yield db


def _session_factory(db: MagicMock):
    """Return a callable that yields `db` each time — safe for multiple calls."""
    return lambda: _mock_session(db)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def _good_run(*args, **kwargs):  # noqa: ANN001
    return MagicMock(returncode=0, stdout="", stderr="")


class TestArchiveBatchSuccess:
    def test_returns_archived_item_ids(self) -> None:
        items = [_make_batch_item("F-00001"), _make_batch_item("F-00002")]
        db = _make_db(batch_items=items)

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM) as mock_archive,
            patch(_SUBPROCESS_RUN, side_effect=_good_run),
        ):
            result = archive_batch("proj", "BATCH-001")

        assert sorted(result) == ["F-00001", "F-00002"]
        assert mock_archive.call_count == 2

    def test_sets_batch_status_to_archived(self) -> None:
        batch = _make_batch()
        db = _make_db(batch=batch, batch_items=[_make_batch_item("F-00001")])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(_SUBPROCESS_RUN, side_effect=_good_run),
        ):
            archive_batch("proj", "BATCH-001")

        assert batch.status == BatchStatus.archived

    def test_sets_batch_archived_at(self) -> None:
        batch = _make_batch()
        db = _make_db(batch=batch, batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(_SUBPROCESS_RUN, side_effect=_good_run),
        ):
            archive_batch("proj", "BATCH-001")

        assert batch.archived_at is not None

    def test_emits_batch_archived_event(self) -> None:
        db = _make_db(batch_items=[_make_batch_item("F-00001")])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(_SUBPROCESS_RUN, side_effect=_good_run),
        ):
            archive_batch("proj", "BATCH-001")

        added = [c.args[0] for c in db.add.call_args_list]
        event_types = [e.event_type for e in added if hasattr(e, "event_type")]
        assert "batch_archived" in event_types

    def test_commits_once(self) -> None:
        db = _make_db(batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(_SUBPROCESS_RUN, side_effect=_good_run),
        ):
            archive_batch("proj", "BATCH-001")

        db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# No items
# ---------------------------------------------------------------------------


class TestArchiveBatchNoItems:
    def test_returns_empty_list(self) -> None:
        db = _make_db(batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM) as mock_archive,
        ):
            result = archive_batch("proj", "BATCH-001")

        assert result == []
        mock_archive.assert_not_called()

    def test_still_sets_batch_archived(self) -> None:
        batch = _make_batch()
        db = _make_db(batch=batch, batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
        ):
            archive_batch("proj", "BATCH-001")

        assert batch.status == BatchStatus.archived


# ---------------------------------------------------------------------------
# Per-item error handling
# ---------------------------------------------------------------------------


class TestArchiveBatchItemErrors:
    def test_one_item_failure_does_not_stop_others(self) -> None:
        items = [_make_batch_item("F-00001"), _make_batch_item("F-00002")]
        db = _make_db(batch_items=items)

        def _side_effect(*args, **kwargs):  # noqa: ANN001
            item_id = args[2] if len(args) > 2 else kwargs.get("item_id")
            if item_id == "F-00001":
                raise RuntimeError("disk full")

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM, side_effect=_side_effect),
            patch(_SUBPROCESS_RUN, side_effect=_good_run),
        ):
            result = archive_batch("proj", "BATCH-001")

        assert result == ["F-00002"]

    def test_item_errors_emit_batch_archive_failed(self) -> None:
        items = [_make_batch_item("F-00001")]
        db = _make_db(batch_items=items)

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM, side_effect=RuntimeError("oops")),
            patch(_SUBPROCESS_RUN, side_effect=_good_run),
        ):
            archive_batch("proj", "BATCH-001")

        added = [c.args[0] for c in db.add.call_args_list]
        event_types = [e.event_type for e in added if hasattr(e, "event_type")]
        assert "batch_archive_failed" in event_types

    def test_item_errors_still_set_batch_archived(self) -> None:
        """Batch is marked archived even when individual items fail."""
        batch = _make_batch()
        db = _make_db(batch=batch, batch_items=[_make_batch_item("F-00001")])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM, side_effect=RuntimeError("oops")),
            patch(_SUBPROCESS_RUN, side_effect=_good_run),
        ):
            archive_batch("proj", "BATCH-001")

        assert batch.status == BatchStatus.archived


# ---------------------------------------------------------------------------
# Post-archive commands
# ---------------------------------------------------------------------------


class TestPostArchiveCommands:
    def test_commands_are_run_in_repo_root(self) -> None:
        project = _make_project(
            repo_root="/repos/proj",
            config={"post_archive_commands": ["alembic upgrade head"]},
        )
        db = _make_db(project=project, batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(_SUBPROCESS_RUN) as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            archive_batch("proj", "BATCH-001")

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == "/repos/proj"

    def test_multiple_commands_all_run(self) -> None:
        project = _make_project(
            config={"post_archive_commands": ["cmd1", "cmd2", "cmd3"]},
        )
        db = _make_db(project=project, batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(_SUBPROCESS_RUN) as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            archive_batch("proj", "BATCH-001")

        assert mock_run.call_count == 3

    def test_no_commands_configured_skips_subprocess(self) -> None:  # noqa: assertion-scanner
        db = _make_db(batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(_SUBPROCESS_RUN) as mock_run,
        ):
            archive_batch("proj", "BATCH-001")

        mock_run.assert_not_called()

    def test_failed_command_does_not_prevent_archiving(self) -> None:
        """A non-zero command exit must not stop the archive."""
        project = _make_project(config={"post_archive_commands": ["alembic upgrade head"]})
        batch = _make_batch()
        db = _make_db(batch=batch, project=project, batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(_SUBPROCESS_RUN) as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="migration failed")
            archive_batch("proj", "BATCH-001")

        assert batch.status == BatchStatus.archived

    def test_failed_command_emits_batch_archive_failed(self) -> None:
        project = _make_project(config={"post_archive_commands": ["bad-cmd"]})
        db = _make_db(project=project, batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(_SUBPROCESS_RUN) as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            archive_batch("proj", "BATCH-001")

        added = [c.args[0] for c in db.add.call_args_list]
        event_types = [e.event_type for e in added if hasattr(e, "event_type")]
        assert "batch_archive_failed" in event_types

    def test_timed_out_command_does_not_prevent_archiving(self) -> None:
        import subprocess  # noqa: PLC0415

        project = _make_project(config={"post_archive_commands": ["slow-cmd"]})
        batch = _make_batch()
        db = _make_db(batch=batch, project=project, batch_items=[])

        with (
            patch(_GET_SESSION, side_effect=_session_factory(db)),
            patch(_ARCHIVE_ITEM),
            patch(
                _SUBPROCESS_RUN,
                side_effect=subprocess.TimeoutExpired("slow-cmd", 300),
            ),
        ):
            archive_batch("proj", "BATCH-001")

        assert batch.status == BatchStatus.archived


# ---------------------------------------------------------------------------
# _archive_paths_for_item — git staging paths
# ---------------------------------------------------------------------------


class TestArchivePathsForItem:
    def test_includes_work_folder(self) -> None:
        """ai-dev/work/<id>/ is staged for deletion alongside the active folder."""
        from pathlib import Path  # noqa: PLC0415

        from orch.archive.batch_archiver import _archive_paths_for_item  # noqa: PLC0415
        from orch.db.models import WorkItem  # noqa: PLC0415

        project = _make_project(repo_root="/repos/proj")
        db = _make_db(project=project, batch_items=[_make_batch_item("F-00001")])
        wi = db.get(WorkItem, ("proj", "F-00001"))
        wi.design_doc_path = "ai-dev/active/F-00001/F-00001_design.md"
        wi.archive_path = "proj/F-00001.tar.zst"

        paths = _archive_paths_for_item(db, "proj", "F-00001", Path("/archives"))

        assert paths == [
            Path("/repos/proj/ai-dev/active/F-00001"),
            Path("/repos/proj/ai-dev/work/F-00001"),
            Path("/archives/proj/F-00001.tar.zst"),
        ]


# ---------------------------------------------------------------------------
# Fatal errors (missing batch/project)
# ---------------------------------------------------------------------------


class TestArchiveBatchFatalErrors:
    def test_missing_batch_returns_empty_list(self) -> None:
        # db.get always returns None → batch not found → ValueError → fatal path
        db = MagicMock()
        db.get.return_value = None

        with patch(_GET_SESSION, side_effect=_session_factory(db)):
            result = archive_batch("proj", "NONEXISTENT")

        assert result == []

    def test_missing_batch_emits_batch_archive_failed(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with patch(_GET_SESSION, side_effect=_session_factory(db)):
            archive_batch("proj", "NONEXISTENT")

        added = [c.args[0] for c in db.add.call_args_list]
        event_types = [e.event_type for e in added if hasattr(e, "event_type")]
        assert "batch_archive_failed" in event_types
