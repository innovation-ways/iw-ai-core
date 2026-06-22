"""Unit tests for the migration-pipeline bug fix in merge_queue.

Before the fix, `_merge_item` had three guards:

    if batch_item.batch_id is not None and isinstance(batch_item.batch_id, int):

Because `BatchItem.batch_id` is always a string like "BATCH-00060", all three
pipeline phases (rebase, dry-run, post-merge apply) were silently skipped for
every real batch.  The fix removed the `isinstance` check, leaving only:

    if batch_item.batch_id is not None:

Tests here:
1. `_to_int_batch_id` helper — parametrised over all documented input shapes.
2. `_merge_item` calls all three pipeline functions for a string batch_id
   (regression test — before the fix, none were called).
3. `_merge_item` skips all three pipeline functions when batch_id is None.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from orch.db.safe_migrate import ORCH_DB_PROJECT_ID, _to_int_batch_id, manages_orch_db

# ---------------------------------------------------------------------------
# 1. _to_int_batch_id helper
# ---------------------------------------------------------------------------


class TestToIntBatchId:
    """_to_int_batch_id converts mixed batch-id types to int or None."""

    def test_none_input_returns_none(self) -> None:
        """Verifies that none input returns none."""
        assert _to_int_batch_id(None) is None

    def test_int_input_returned_unchanged(self) -> None:
        """Verifies that int input returned unchanged."""
        assert _to_int_batch_id(42) == 42

    def test_int_zero_returned_unchanged(self) -> None:
        """Verifies that int zero returned unchanged."""
        assert _to_int_batch_id(0) == 0

    def test_string_batch_id_extracts_trailing_digits(self) -> None:
        """Verifies that string batch id extracts trailing digits."""
        assert _to_int_batch_id("BATCH-00060") == 60

    def test_string_batch_id_single_digit(self) -> None:
        """Verifies that string batch id single digit."""
        assert _to_int_batch_id("BATCH-00001") == 1

    def test_string_without_trailing_digits_returns_none(self) -> None:
        """Verifies that string without trailing digits returns none."""
        assert _to_int_batch_id("no-digits") is None

    def test_empty_string_returns_none(self) -> None:
        """Verifies that empty string returns none."""
        assert _to_int_batch_id("") is None

    @pytest.mark.parametrize(
        ("batch_id", "expected"),
        [
            ("BATCH-00060", 60),
            ("BATCH-00001", 1),
            ("BATCH-00100", 100),
            (42, 42),
            (0, 0),
            (None, None),
            ("no-digits", None),
            ("", None),
        ],
    )
    def test_parametrised_conversions(
        self, batch_id: str | int | None, expected: int | None
    ) -> None:
        """Verifies that parametrised conversions."""
        assert _to_int_batch_id(batch_id) == expected


# ---------------------------------------------------------------------------
# Shared helpers for _merge_item tests
# ---------------------------------------------------------------------------


def _make_project_config(
    project_id: str = ORCH_DB_PROJECT_ID,
    migration_validation: object | None = None,
) -> MagicMock:
    """Return a ProjectConfig for _merge_item tests.

    Defaults to the orch-DB-owning project id so the migration pipeline is
    exercised; pass a non-orch project_id to drive the skip/validation paths.
    """
    from orch.daemon.project_registry import MigrationValidationConfig, ProjectConfig

    assert migration_validation is None or isinstance(
        migration_validation, MigrationValidationConfig
    )
    return ProjectConfig(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
        migration_validation=migration_validation,
        owns_orch_db=manages_orch_db(project_id),
    )


def _make_batch_item(
    batch_id: str | int | None,
    status_value: str = "completed",
    item_id: int = 110,
    work_item_id: str = "F-00060",
    worktree_path: str = "/wt/F-00060",
) -> MagicMock:
    """Build a minimal BatchItem mock with the fields _merge_item accesses."""
    from orch.db.models import BatchItem, BatchItemStatus

    item = MagicMock(spec=BatchItem)
    item.id = item_id
    item.batch_id = batch_id
    item.work_item_id = work_item_id
    item.status = BatchItemStatus.completed
    item.started_at = datetime(2024, 1, 1, tzinfo=UTC)
    item.worktree_info = {"path": worktree_path}
    item.worktree_compose_path = None
    item.merge_info = None
    item.merged_at = None
    item.notes = None
    item.project_id = "test-proj"
    return item


def _make_successful_rebase_result() -> MagicMock:
    """A RebaseResult that indicates no rebase was needed (always passes)."""
    from orch.daemon.migration_rebase import RebaseResult

    return RebaseResult(
        success=True,
        rebased=False,
        rewrites=[],
        worktree_base_sha="abc123",
        current_main_sha="abc123",
        message="No rebase needed",
        error_message=None,
    )


def _make_successful_dry_run_result() -> MagicMock:
    """A PipelineResult returned by run_pre_merge_dry_run on success."""
    from orch.daemon.migration_pipeline import PipelineResult

    return PipelineResult(
        phase="dry_run",
        success=True,
        final_batch_state="proceed_to_merge",
        frozen=False,
        message="Dry-run succeeded (100ms)",
    )


def _make_successful_apply_result() -> MagicMock:
    """A PipelineResult returned by run_post_merge_apply on success."""
    from orch.daemon.migration_pipeline import PipelineResult

    return PipelineResult(
        phase="apply",
        success=True,
        final_batch_state="merged",
        frozen=False,
        message="Applied successfully (50ms)",
    )


# ---------------------------------------------------------------------------
# 2. Regression: string batch_id must invoke all three pipeline phases
# ---------------------------------------------------------------------------


class TestMergeItemStringBatchIdInvokesPipeline:
    """Regression tests for the isinstance(batch_id, int) bug.

    Before the fix, all three pipeline phases were bypassed for string batch IDs
    (e.g. "BATCH-00060").  Each test below asserts that the corrected code calls
    the phase in question when batch_id is a non-None string.
    """

    def _run_merge_item(
        self,
        batch_item: MagicMock,
        *,
        mock_rebase_result: MagicMock | None = None,
        mock_dry_result: MagicMock | None = None,
        mock_apply_result: MagicMock | None = None,
    ) -> dict[str, MagicMock]:
        """Run _merge_item with all external side-effects mocked out.

        Returns a dict of the three pipeline mocks so callers can assert on them.
        """
        from orch.daemon.merge_queue import _merge_item

        rebase_result = mock_rebase_result or _make_successful_rebase_result()
        dry_result = mock_dry_result or _make_successful_dry_run_result()
        apply_result = mock_apply_result or _make_successful_apply_result()

        db = MagicMock()
        project_config = _make_project_config()

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=rebase_result,
            ) as mock_rebase,
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=dry_result,
            ) as mock_dry,
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=apply_result,
            ) as mock_apply,
            # I-00126: also patch resolve_branch_for_project so the test's fake
            # project repo does not trigger the default-branch guard.
            patch(
                "orch.daemon.merge_queue.resolve_branch_for_project",
            ) as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_resolve.return_value = MagicMock(
                current_branch="main",
                default_branch="main",
                is_on_default=True,
            )
            mock_subproc.return_value = MagicMock(returncode=0, stdout="squash ok", stderr="")
            _merge_item(db, batch_item, ORCH_DB_PROJECT_ID, project_config)

        return {
            "rebase": mock_rebase,
            "dry_run": mock_dry,
            "apply": mock_apply,
        }

    def test_rebase_called_for_string_batch_id(self) -> None:
        """run_pre_merge_rebase must be invoked when batch_id is a non-None string."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        mocks["rebase"].assert_called_once()

    def test_dry_run_called_for_string_batch_id(self) -> None:
        """run_pre_merge_dry_run must be invoked when batch_id is a non-None string."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        mocks["dry_run"].assert_called_once()

    def test_post_merge_apply_called_for_string_batch_id(self) -> None:
        """run_post_merge_apply must be invoked when batch_id is a non-None string."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        mocks["apply"].assert_called_once()

    def test_all_three_phases_called_together_for_string_batch_id(self) -> None:
        """All three phases run together for a real string batch ID."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        mocks["rebase"].assert_called_once()
        mocks["dry_run"].assert_called_once()
        mocks["apply"].assert_called_once()

    def test_rebase_called_with_correct_batch_id_and_paths(self) -> None:
        """run_pre_merge_rebase receives the string batch_id, worktree path, and working_dir."""
        item = _make_batch_item(batch_id="BATCH-00060", worktree_path="/wt/F-00060")
        mocks = self._run_merge_item(item)
        call_args = mocks["rebase"].call_args
        assert call_args[0][0] == "BATCH-00060"
        assert call_args[0][1] == "/wt/F-00060"

    def test_dry_run_called_with_correct_worktree_path(self) -> None:
        """run_pre_merge_dry_run receives the worktree_path keyword argument."""
        item = _make_batch_item(batch_id="BATCH-00060", worktree_path="/wt/F-00060")
        mocks = self._run_merge_item(item)
        call_kwargs = mocks["dry_run"].call_args[1]
        assert call_kwargs["worktree_path"] == "/wt/F-00060"

    def test_post_merge_apply_called_with_string_batch_id(self) -> None:
        """run_post_merge_apply receives the string batch_id."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        call_args = mocks["apply"].call_args
        assert call_args[0][0] == "BATCH-00060"

    def test_zero_padded_batch_id_also_triggers_pipeline(self) -> None:
        """Batch IDs with zero-padded numbers (e.g. "BATCH-00001") also pass the guard."""
        item = _make_batch_item(batch_id="BATCH-00001")
        mocks = self._run_merge_item(item)
        mocks["rebase"].assert_called_once()
        mocks["dry_run"].assert_called_once()
        mocks["apply"].assert_called_once()


# ---------------------------------------------------------------------------
# 3. batch_id=None skips all three pipeline phases
# ---------------------------------------------------------------------------


class TestMergeItemNoneBatchIdSkipsPipeline:
    """When batch_id is None, the pipeline must NOT be invoked.

    This was already the intended behaviour before the fix (the old guard
    `batch_item.batch_id is not None` still gated it for None).  The tests
    here document that the fix preserves this semantics.
    """

    def test_rebase_not_called_when_batch_id_is_none(self) -> None:  # noqa: assertion-scanner
        """Verifies that rebase not called when batch id is none."""
        item = _make_batch_item(batch_id=None)
        db = MagicMock()

        with (
            patch("orch.daemon.merge_queue.run_pre_merge_rebase") as mock_rebase,
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=_make_successful_dry_run_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=_make_successful_apply_result(),
            ),
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_resolve.return_value = MagicMock(
                current_branch="main",
                default_branch="main",
                is_on_default=True,
            )
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            from orch.daemon.merge_queue import _merge_item

            _merge_item(db, item, ORCH_DB_PROJECT_ID, _make_project_config())

        mock_rebase.assert_not_called()

    def test_dry_run_not_called_when_batch_id_is_none(self) -> None:  # noqa: assertion-scanner
        """Verifies that dry run not called when batch id is none."""
        item = _make_batch_item(batch_id=None)
        db = MagicMock()

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=_make_successful_rebase_result(),
            ),
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry,
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=_make_successful_apply_result(),
            ),
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_resolve.return_value = MagicMock(
                current_branch="main",
                default_branch="main",
                is_on_default=True,
            )
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            from orch.daemon.merge_queue import _merge_item

            _merge_item(db, item, ORCH_DB_PROJECT_ID, _make_project_config())

        mock_dry.assert_not_called()

    def test_post_merge_apply_not_called_when_batch_id_is_none(self) -> None:  # noqa: assertion-scanner
        """Verifies that post merge apply not called when batch id is none."""
        item = _make_batch_item(batch_id=None)
        db = MagicMock()

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=_make_successful_rebase_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=_make_successful_dry_run_result(),
            ),
            patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_resolve.return_value = MagicMock(
                current_branch="main",
                default_branch="main",
                is_on_default=True,
            )
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            from orch.daemon.merge_queue import _merge_item

            _merge_item(db, item, ORCH_DB_PROJECT_ID, _make_project_config())

        mock_apply.assert_not_called()

    def test_merge_succeeds_without_pipeline_when_batch_id_is_none(self) -> None:
        """With batch_id=None the merge still completes successfully (no regressions)."""
        from orch.db.models import BatchItemStatus

        item = _make_batch_item(batch_id=None)
        db = MagicMock()

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=_make_successful_rebase_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=_make_successful_dry_run_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=_make_successful_apply_result(),
            ),
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_resolve.return_value = MagicMock(
                current_branch="main",
                default_branch="main",
                is_on_default=True,
            )
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            from orch.daemon.merge_queue import _merge_item

            _merge_item(db, item, ORCH_DB_PROJECT_ID, _make_project_config())

        assert item.status == BatchItemStatus.merged


# ---------------------------------------------------------------------------
# 4. Phase 3 rollback only when Phase 2 actually applied a revision
# ---------------------------------------------------------------------------


def _make_failed_apply_result(*, revisions_applied: list[str]) -> MagicMock:
    """A PipelineResult for a Phase-2 apply that failed.

    revisions_applied non-empty → apply advanced the DB and then died
    (rollback warranted). Empty → apply tripped a pre-flight check
    (SelfBlockerError / lock timeout) before touching the DB (no rollback).
    """
    from orch.daemon.migration_pipeline import PipelineResult

    if revisions_applied:
        return PipelineResult(
            phase="apply",
            success=False,
            final_batch_state="rollback_triggered",
            frozen=False,
            message="Apply failed after applying revisions",
            revisions_applied=list(revisions_applied),
        )
    return PipelineResult(
        phase="apply",
        success=False,
        final_batch_state="apply_deferred",
        frozen=False,
        message="Phase 2 apply would self-deadlock: ... See I-00063 for context.",
        revisions_applied=[],
    )


def _make_rollback_result() -> MagicMock:
    from orch.daemon.migration_pipeline import PipelineResult

    return PipelineResult(
        phase="rollback",
        success=True,
        final_batch_state="MIGRATION_ROLLED_BACK",
        frozen=False,
        message="Rollback succeeded (10ms)",
    )


class TestMergeItemRollbackGuard:
    """`_merge_item` must only run Phase 3 rollback when Phase 2 advanced the DB.

    Regression: a transient SelfBlockerError pre-flight failure (zero revisions
    applied) used to trigger `alembic downgrade -1`, which rolled back a
    previously-applied migration and left the orch DB behind head with writes
    disabled in the dashboard (observed after the BATCH-00089 merge, 2026-05-11).
    """

    def _run_merge_item(self, apply_result: MagicMock) -> dict[str, MagicMock]:
        """Return run merge item."""
        from orch.daemon.merge_queue import _merge_item

        db = MagicMock()
        item = _make_batch_item(batch_id="BATCH-00089")

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=_make_successful_rebase_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=_make_successful_dry_run_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=apply_result,
            ),
            patch(
                "orch.daemon.merge_queue.run_rollback", return_value=_make_rollback_result()
            ) as mock_rollback,
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_resolve.return_value = MagicMock(
                current_branch="main",
                default_branch="main",
                is_on_default=True,
            )
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            _merge_item(db, item, ORCH_DB_PROJECT_ID, _make_project_config())

        return {"rollback": mock_rollback, "item": item}

    def test_no_rollback_when_apply_failed_with_zero_revisions(self) -> None:
        """Verifies that no rollback when apply failed with zero revisions."""
        result = self._run_merge_item(_make_failed_apply_result(revisions_applied=[]))
        result["rollback"].assert_not_called()
        # The git squash-merge already happened — the item stays merged.
        from orch.db.models import BatchItemStatus

        assert result["item"].status == BatchItemStatus.merged

    def test_rollback_when_apply_failed_after_applying_a_revision(self) -> None:
        """Verifies that rollback when apply failed after applying a revision."""
        result = self._run_merge_item(_make_failed_apply_result(revisions_applied=["abc123"]))
        result["rollback"].assert_called_once()

    def test_no_rollback_on_successful_apply(self) -> None:  # noqa: assertion-scanner
        """Verifies that no rollback on successful apply."""
        result = self._run_merge_item(_make_successful_apply_result())
        result["rollback"].assert_not_called()


# ---------------------------------------------------------------------------
# 5. manages_orch_db gate — which project owns the orch DB migration pipeline
# ---------------------------------------------------------------------------


class TestManagesOrchDb:
    """`manages_orch_db` is True only for the orch-DB-owning project.

    The orch migration pipeline (rebase + apply-to-live) keys on this; every
    other managed project is validation-only. See safe_migrate.ORCH_DB_PROJECT_ID.
    """

    def test_orch_project_owns_orch_db(self) -> None:
        """The iw-ai-core project owns the orch DB."""
        assert manages_orch_db(ORCH_DB_PROJECT_ID) is True

    def test_none_is_false(self) -> None:
        """A None project id never owns the orch DB."""
        assert manages_orch_db(None) is False

    @pytest.mark.parametrize(
        "project_id",
        ["iw-rag", "innoforge", "Podforger", "cv", "IW Website", "", "IW-AI-CORE"],
    )
    def test_non_orch_projects_are_false(self, project_id: str) -> None:
        """Every non-orch project (and case variants) is validation-only."""
        assert manages_orch_db(project_id) is False


# ---------------------------------------------------------------------------
# 6. Non-orch projects: rebase + apply are skipped; dry-run is opt-in (I-00131)
# ---------------------------------------------------------------------------


def _make_migration_validation_config(
    *,
    script_location: str = "alembic",
    db_image: str = "paradedb/paradedb:latest",
    bootstrap_sql: tuple[str, ...] = (),
) -> object:
    """Build a MigrationValidationConfig for the non-orch validation tests."""
    from orch.daemon.project_registry import MigrationValidationConfig

    return MigrationValidationConfig(
        script_location=script_location,
        db_image=db_image,
        bootstrap_sql=bootstrap_sql,
    )


class TestMergeItemNonOrchProjectMigrationPipeline:
    """Non-orch projects must never run the orch rebase or apply-to-live phases.

    Regression for I-00131: the merge queue ran the orch migration pipeline for
    iw-rag (a non-orch project that keeps migrations under ``alembic/``). The
    Phase-1 dry-run was pointed at a hard-coded ``orch/db/migrations`` path that
    does not exist in iw-rag, so the merge was wrongly marked MIGRATION_INVALID.

    After the fix, for a non-orch project:
      * the pre-merge rebase is skipped (it would corrupt the project's chain),
      * the apply-to-live (orch DB) is skipped (the project owns its own DB),
      * the Phase-1 dry-run runs ONLY when the project opts in via
        ``migration_validation``, and then with that project's image + dir.
    """

    def _run_merge_item(
        self,
        *,
        migration_validation: object | None,
        project_id: str = "iw-rag",
        worktree_path: str = "/wt/I-00131",
    ) -> dict[str, MagicMock]:
        """Run _merge_item for a non-orch project, mocking all side-effects."""
        from orch.daemon.merge_queue import _merge_item

        item = _make_batch_item(batch_id="BATCH-00145", worktree_path=worktree_path)
        project_config = _make_project_config(
            project_id=project_id, migration_validation=migration_validation
        )
        db = MagicMock()

        with (
            patch("orch.daemon.merge_queue.run_pre_merge_rebase") as mock_rebase,
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=_make_successful_dry_run_result(),
            ) as mock_dry,
            patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_resolve.return_value = MagicMock(
                current_branch="main",
                default_branch="main",
                is_on_default=True,
            )
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            _merge_item(db, item, project_id, project_config)

        return {"rebase": mock_rebase, "dry_run": mock_dry, "apply": mock_apply, "item": item}

    def test_rebase_skipped_for_non_orch_project(self) -> None:  # noqa: assertion-scanner
        """The orch down_revision-rewriting rebase never runs for a non-orch project."""
        mocks = self._run_merge_item(migration_validation=None)
        mocks["rebase"].assert_not_called()

    def test_apply_skipped_for_non_orch_project(self) -> None:  # noqa: assertion-scanner
        """The apply-to-live-orch-DB phase never runs for a non-orch project."""
        mocks = self._run_merge_item(migration_validation=None)
        mocks["apply"].assert_not_called()

    def test_dry_run_skipped_when_not_opted_in(self) -> None:  # noqa: assertion-scanner
        """Without migration_validation config, the dry-run is skipped (I-00131 fix)."""
        mocks = self._run_merge_item(migration_validation=None)
        mocks["dry_run"].assert_not_called()

    def test_merge_succeeds_for_non_orch_project_without_validation(self) -> None:
        """The I-00131 case: merge completes (status=merged), no MIGRATION_INVALID."""
        from orch.db.models import BatchItemStatus

        mocks = self._run_merge_item(migration_validation=None)
        assert mocks["item"].status == BatchItemStatus.merged

    def test_dry_run_runs_with_project_image_and_dir_when_opted_in(self) -> None:
        """Opted-in projects validate with their own image + migrations dir."""
        cfg = _make_migration_validation_config(
            script_location="alembic",
            db_image="paradedb/paradedb:latest",
            bootstrap_sql=("CREATE EXTENSION IF NOT EXISTS vector",),
        )
        mocks = self._run_merge_item(migration_validation=cfg, worktree_path="/wt/I-00131")
        mocks["dry_run"].assert_called_once()
        kwargs = mocks["dry_run"].call_args.kwargs
        assert kwargs["db_image"] == "paradedb/paradedb:latest"
        assert kwargs["script_location"] == "/wt/I-00131/alembic"
        assert kwargs["bootstrap_sql"] == ("CREATE EXTENSION IF NOT EXISTS vector",)

    def test_rebase_and_apply_still_skipped_when_opted_in(self) -> None:  # noqa: assertion-scanner
        """Opting into validation does NOT enable the orch rebase/apply phases."""
        cfg = _make_migration_validation_config()
        mocks = self._run_merge_item(migration_validation=cfg)
        mocks["rebase"].assert_not_called()
        mocks["apply"].assert_not_called()

    def test_merge_succeeds_when_opted_in_dry_run_passes(self) -> None:
        """A passing project dry-run lets the merge complete normally."""
        from orch.db.models import BatchItemStatus

        cfg = _make_migration_validation_config()
        mocks = self._run_merge_item(migration_validation=cfg)
        assert mocks["item"].status == BatchItemStatus.merged

    def test_failed_project_dry_run_marks_migration_invalid(self) -> None:
        """A failing project dry-run still blocks the merge (validation has teeth)."""
        from orch.daemon.merge_queue import _merge_item
        from orch.daemon.migration_pipeline import PipelineResult
        from orch.db.models import BatchItemStatus

        item = _make_batch_item(batch_id="BATCH-00145", worktree_path="/wt/I-00131")
        cfg = _make_migration_validation_config()
        project_config = _make_project_config(project_id="iw-rag", migration_validation=cfg)
        db = MagicMock()
        failed = PipelineResult(
            phase="dry_run",
            success=False,
            final_batch_state="MIGRATION_INVALID",
            frozen=False,
            message="relation already exists",
        )

        with (
            patch("orch.daemon.merge_queue.run_pre_merge_rebase") as mock_rebase,
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run", return_value=failed),
            patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
            patch("orch.daemon.merge_queue._revert_work_item"),
        ):
            mock_resolve.return_value = MagicMock(
                current_branch="main", default_branch="main", is_on_default=True
            )
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            _merge_item(db, item, "iw-rag", project_config)

        assert item.status == BatchItemStatus.migration_invalid
        # The failing validation must short-circuit BEFORE the squash-merge/apply.
        mock_apply.assert_not_called()
        mock_rebase.assert_not_called()
