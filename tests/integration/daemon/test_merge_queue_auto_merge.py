"""Integration tests for F-00084 auto-merge integration in merge_queue._merge_item.

Covers the uncovered lines (474-477, 484-486, 489-490, 492, 498-499, 516,
521-524, 526, 539-540, 546-547) by calling _merge_item with mocked subprocess
output containing AUTO_RESOLVE_SKIPPED and AUTO_RESOLVE_REQUESTED markers.

Pattern: same as test_merge_info_conflict_files.py — mock subprocess.run and
the migration helpers, call _merge_item directly, assert on DB state.
"""

from __future__ import annotations

import json
import uuid
from contextlib import ExitStack
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from orch.daemon.auto_merge import (
    EVENT_AUTO_MERGE_CONFIG_INVALID,
    EVENT_AUTO_RESOLUTION_FAILED,
    EVENT_AUTO_RESOLUTION_SKIPPED,
    PHASE_DRY_RUN,
    AutoMergeConfig,
    ClassificationResult,
)
from orch.daemon.merge_queue import _merge_item
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _unique_id(prefix: str = "F-00084-mq") -> str:
    """Generate a unique ID with a UUID suffix for test isolation.

    Args:
        prefix: Prefix to prepend to the UUID hex suffix.

    Returns:
        A unique string in the form ``<prefix>-<8-char-hex>``.
    """
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _make_mock_result(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 1,
) -> MagicMock:
    """Build a mock subprocess.CompletedProcess with controlled stdout, stderr, and returncode.

    Args:
        stdout: Simulated standard output text.
        stderr: Simulated standard error text.
        returncode: Process exit code; defaults to 1 (failure).

    Returns:
        A MagicMock with ``stdout``, ``stderr``, and ``returncode`` attributes set.
    """
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


def _make_project_config(project_id: str, repo_root: str = "/repos/test"):
    """Build a ProjectConfig for auto-merge merge_queue tests.

    Args:
        project_id: ID of the project.
        repo_root: Filesystem path used as the repository root.

    Returns:
        A ProjectConfig instance configured for the claude CLI tool.
    """
    from orch.daemon.project_registry import ProjectConfig

    return ProjectConfig(
        id=project_id,
        display_name="Test Project",
        repo_root=repo_root,
        enabled=True,
        cli_tool="claude",
        model="claude-sonnet-4-6",
        worktree_base="/tmp/worktrees",
        config={},
    )


def _make_batch_item(
    db_session: Session,
    project_id: str,
    item_id: str,
    worktree_path: str,
) -> BatchItem:
    """Insert WorkItem, Batch, and BatchItem rows; return BatchItem."""
    wi = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title=f"Auto-merge test {item_id}",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        design_doc_content="Test feature for auto-merge merge_queue coverage.",
    )
    db_session.add(wi)

    batch_id = _unique_id("B")
    batch = Batch(
        id=batch_id,
        project_id=project_id,
        status=BatchStatus.executing,
        max_parallel=1,
        auto_merge=True,
    )
    db_session.add(batch)
    db_session.flush()

    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=item_id,
        execution_group=0,
        status=BatchItemStatus.merging,
        worktree_info={"path": worktree_path, "branch": f"agent/{item_id}"},
    )
    db_session.add(bi)
    db_session.flush()
    return bi


def _events_of_type(db: Session, project_id: str, event_type: str) -> list[DaemonEvent]:
    """Query all DaemonEvent rows matching the given project and event type.

    Args:
        db: The SQLAlchemy session for the testcontainer DB.
        project_id: Project ID to filter by.
        event_type: Event type string to match.

    Returns:
        List of DaemonEvent ORM instances in insertion order.
    """
    return list(
        db.scalars(
            select(DaemonEvent).where(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type == event_type,
            )
        ).all()
    )


def _standard_patch_specs() -> list:
    """Return patch specs (not yet entered) for the migration helpers."""
    return [
        ("orch.daemon.merge_queue.run_pre_merge_rebase", MagicMock(success=True)),
        ("orch.daemon.merge_queue.run_pre_merge_dry_run", MagicMock(success=True)),
        ("orch.daemon.merge_queue.worktree_compose", None),
        ("orch.daemon.merge_queue.run_post_merge_apply", MagicMock(success=True)),
        (
            "orch.daemon.merge_queue.run_rollback",
            MagicMock(success=True, frozen=False, message="ok"),
        ),
        ("orch.daemon.batch_merge_hooks.trigger_doc_regeneration_on_merge", None),
    ]


def _enter_standard_patches(stack: ExitStack) -> None:
    """Enter the standard migration-helper patches into stack."""
    for target, return_value in _standard_patch_specs():
        if return_value is None:
            stack.enter_context(patch(target))
        else:
            stack.enter_context(patch(target, return_value=return_value))


def _phase0_config() -> AutoMergeConfig:
    """Return an AutoMergeConfig with Phase 0 (disabled/observation) defaults.

    Returns:
        An AutoMergeConfig built from ``AutoMergeConfig.defaults()``.
    """
    return AutoMergeConfig.defaults()


def _phase1_config(runtime_option_id: int | None = None) -> AutoMergeConfig:
    """Build an AutoMergeConfig for Phase 1 (dry-run) with a test allowlist.

    Args:
        runtime_option_id: Optional runtime option ID to embed in the config.

    Returns:
        An AutoMergeConfig in PHASE_DRY_RUN with ``tests/**/*.py`` and ``docs/**/*.md`` allowed.
    """
    d = AutoMergeConfig.defaults()
    return AutoMergeConfig(
        phase=PHASE_DRY_RUN,
        runtime_option_id=runtime_option_id,
        allowlist_patterns=("tests/**/*.py", "docs/**/*.md"),
        refuselist_patterns=d.refuselist_patterns,
        max_conflict_hunk_lines=80,
        max_conflicted_files_per_merge=5,
        max_file_size_bytes=256_000,
        max_event_metadata_bytes=262_144,
        llm_call_timeout_seconds=120,
    )


# ---------------------------------------------------------------------------
# Lines 473-477: AUTO_RESOLVE_SKIPPED marker path
# ---------------------------------------------------------------------------


class TestAutoSkipMarkerPath:
    """Tests for the AUTO_RESOLVE_SKIPPED=<json> branch (lines 473-477)."""

    @pytest.fixture(autouse=True)
    def _mock_branch_resolver(self):
        """Return is_on_default=True so I-00126 guard never fires in tests."""
        from orch.utils.branch_resolver import BranchInfo

        with patch(
            "orch.daemon.merge_queue.resolve_branch_for_project",
            return_value=BranchInfo(
                current_branch="main", default_branch="main", is_on_default=True
            ),
        ):
            yield

    def test_auto_skip_marker_fires_skipped_event(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """AUTO_RESOLVE_SKIPPED marker in stdout → merge_auto_resolution_skipped event.

        Exercises lines 473-475 (the if _auto_skip is not None: branch and
        emit_skipped_event call).
        """
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        skip_payload = json.dumps(
            {
                "reason": "refuse_list",
                "eligible_files": [],
                "refuse_files": ["orch/db/migrations/versions/abc123_test.py"],
            }
        )
        mock_stdout = (
            "[worktree_commit] INFO: rebase conflict detected\n"
            f"AUTO_RESOLVE_SKIPPED={skip_payload}\n"
            "[worktree_commit] ERROR: abort\n"
        )
        mock_result = _make_mock_result(stdout=mock_stdout, stderr="exit 1", returncode=1)
        project_config = _make_project_config(project_id)

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        skipped = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_SKIPPED)
        assert len(skipped) == 1
        meta = skipped[0].event_metadata
        assert meta["reason"] == "refuse_list"
        assert "orch/db/migrations/versions/abc123_test.py" in meta["refuse_files"]

    def test_auto_skip_marker_emit_exception_logged(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """Exception in emit_skipped_event is caught — merge still reaches merge_failed.

        Exercises lines 474-482 (the try/except around emit_skipped_event).
        """
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        skip_payload = json.dumps({"reason": "refuse_list", "eligible_files": []})
        mock_stdout = (
            f"[worktree_commit] ERROR: rebase conflict\nAUTO_RESOLVE_SKIPPED={skip_payload}\n"
        )
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch("orch.daemon.auto_merge.emit_skipped_event", side_effect=RuntimeError("boom"))
            )
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        db_session.refresh(bi)
        assert bi.status == BatchItemStatus.merge_failed


# ---------------------------------------------------------------------------
# Lines 484-486, 489-490: AUTO_RESOLVE_REQUESTED — config loading + parse error
# ---------------------------------------------------------------------------


class TestAutoResolveConfigPath:
    """Tests for config loading inside the AUTO_RESOLVE_REQUESTED branch."""

    @pytest.fixture(autouse=True)
    def _mock_branch_resolver(self):
        """Return is_on_default=True so I-00126 guard never fires in tests."""
        from orch.utils.branch_resolver import BranchInfo

        with patch(
            "orch.daemon.merge_queue.resolve_branch_for_project",
            return_value=BranchInfo(
                current_branch="main", default_branch="main", is_on_default=True
            ),
        ):
            yield

    def test_config_parse_error_fires_config_invalid_event(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """auto_merge.toml parse error → merge_auto_merge_config_invalid event (lines 489-490).

        AutoMergeConfig.load is mocked to return a parse error string.
        """
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        resolve_payload = json.dumps(
            {
                "eligible_files": ["tests/unit/test_foo.py"],
                "branch": f"agent/{item_id}",
                "main_sha": "abc123",
            }
        )
        mock_stdout = (
            f"[worktree_commit] ERROR: conflict\nAUTO_RESOLVE_REQUESTED={resolve_payload}\n"
        )
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        bad_config = AutoMergeConfig.defaults()
        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.AutoMergeConfig.load",
                    return_value=(bad_config, "TOML parse error: unexpected token on line 5"),
                )
            )
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.classify_conflicts",
                    return_value=ClassificationResult(
                        eligible_files=(),
                        refuse_files=(),
                        oversized_files=(),
                        oversized_hunks=(),
                        binary_files=(),
                        skipped_reason="not_allowlisted",
                    ),
                )
            )
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        config_events = _events_of_type(db_session, project_id, EVENT_AUTO_MERGE_CONFIG_INVALID)
        assert len(config_events) == 1
        assert "TOML parse error" in config_events[0].event_metadata["error"]

        db_session.refresh(bi)
        assert bi.status == BatchItemStatus.merge_failed

    def test_auto_resolve_config_loads_and_classify_called(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """AUTO_RESOLVE_REQUESTED → AutoMergeConfig.load called (lines 484-486, 492).

        Verifies the config-loading and classify_conflicts call path runs.
        Uses a mocked classify_conflicts to avoid filesystem access for conflict files.
        """
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        resolve_payload = json.dumps(
            {
                "eligible_files": ["tests/unit/test_config_load.py"],
                "branch": f"agent/{item_id}",
                "main_sha": "deadbeef",
            }
        )
        mock_stdout = f"AUTO_RESOLVE_REQUESTED={resolve_payload}\n[error]\n"
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        classify_calls: list[dict] = []

        def fake_classify(worktree_path, conflict_files, config):  # noqa: ARG001
            classify_calls.append({"conflict_files": conflict_files})
            return ClassificationResult(
                eligible_files=(),
                refuse_files=(),
                oversized_files=(),
                oversized_hunks=(),
                binary_files=(),
                skipped_reason="not_allowlisted",
            )

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch("orch.daemon.auto_merge.classify_conflicts", side_effect=fake_classify)
            )
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        assert len(classify_calls) == 1
        assert "tests/unit/test_config_load.py" in classify_calls[0]["conflict_files"]


# ---------------------------------------------------------------------------
# Lines 498-499: classification skip → emit_skipped_event via classify path
# ---------------------------------------------------------------------------


class TestAutoResolveClassificationSkip:
    """Classification returns skipped_reason → emit_skipped_event (lines 498-513)."""

    @pytest.fixture(autouse=True)
    def _mock_branch_resolver(self):
        """Return is_on_default=True so I-00126 guard never fires in tests."""
        from orch.utils.branch_resolver import BranchInfo

        with patch(
            "orch.daemon.merge_queue.resolve_branch_for_project",
            return_value=BranchInfo(
                current_branch="main", default_branch="main", is_on_default=True
            ),
        ):
            yield

    def test_classification_skipped_fires_skipped_event(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """classify_conflicts returns skipped_reason → merge_auto_resolution_skipped event."""
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        resolve_payload = json.dumps(
            {
                "eligible_files": ["tests/unit/test_skipped.py"],
                "branch": f"agent/{item_id}",
                "main_sha": "cafe0000",
            }
        )
        mock_stdout = f"AUTO_RESOLVE_REQUESTED={resolve_payload}\n[error]\n"
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.AutoMergeConfig.load",
                    return_value=(_phase0_config(), None),
                )
            )
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.classify_conflicts",
                    return_value=ClassificationResult(
                        eligible_files=(),
                        refuse_files=("tests/unit/test_skipped.py",),
                        oversized_files=(),
                        oversized_hunks=(),
                        binary_files=(),
                        skipped_reason="refuse_list",
                    ),
                )
            )
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        skipped = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_SKIPPED)
        assert len(skipped) == 1
        meta = skipped[0].event_metadata
        assert meta["reason"] == "refuse_list"
        assert "tests/unit/test_skipped.py" in meta["refuse_files"]

        db_session.refresh(bi)
        assert bi.status == BatchItemStatus.merge_failed

    @pytest.mark.parametrize(
        (
            "skipped_reason",
            "refuse_files",
            "binary_files",
            "oversized_files",
            "oversized_hunks",
        ),
        [
            ("refuse_list", ("executor/worktree_commit.sh",), (), (), ()),
            ("binary", (), ("dashboard/logo.png",), (), ()),
            ("not_allowlisted", (), (), (), ()),
        ],
    )
    def test_various_skip_reasons_emit_event(
        self,
        skipped_reason: str,
        refuse_files: tuple,
        binary_files: tuple,
        oversized_files: tuple,
        oversized_hunks: tuple,
        db_session: Session,
        test_project,
    ) -> None:
        """Various classification skip reasons produce a skipped event with the right reason."""
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        resolve_payload = json.dumps(
            {
                "eligible_files": list(refuse_files or binary_files or ["orch/something.py"]),
                "branch": f"agent/{item_id}",
                "main_sha": "deadbeef",
            }
        )
        mock_stdout = f"AUTO_RESOLVE_REQUESTED={resolve_payload}\n[error]\n"
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.AutoMergeConfig.load",
                    return_value=(_phase0_config(), None),
                )
            )
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.classify_conflicts",
                    return_value=ClassificationResult(
                        eligible_files=(),
                        refuse_files=refuse_files,
                        oversized_files=oversized_files,
                        oversized_hunks=oversized_hunks,
                        binary_files=binary_files,
                        skipped_reason=skipped_reason,
                    ),
                )
            )
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        skipped = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_SKIPPED)
        assert len(skipped) == 1
        assert skipped[0].event_metadata["reason"] == skipped_reason


# ---------------------------------------------------------------------------
# Lines 516, 521-524, 526: attempt_resolution call path
# ---------------------------------------------------------------------------


class TestAutoResolveAttemptResolutionPath:
    """classify_conflicts returns eligible_files → attempt_resolution called (lines 514-537)."""

    @pytest.fixture(autouse=True)
    def _mock_branch_resolver(self):
        """Return is_on_default=True so I-00126 guard never fires in tests."""
        from orch.utils.branch_resolver import BranchInfo

        with patch(
            "orch.daemon.merge_queue.resolve_branch_for_project",
            return_value=BranchInfo(
                current_branch="main", default_branch="main", is_on_default=True
            ),
        ):
            yield

    def test_attempt_resolution_called_with_work_item_context(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """All eligible files → attempt_resolution invoked with WI title/desc (lines 516-526).

        Verifies that _merge_item queries WorkItem and passes title + description
        to attempt_resolution.
        """
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        resolve_payload = json.dumps(
            {
                "eligible_files": ["tests/unit/test_eligible.py"],
                "branch": f"agent/{item_id}",
                "main_sha": "feedface",
            }
        )
        mock_stdout = f"AUTO_RESOLVE_REQUESTED={resolve_payload}\n[error]\n"
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        attempt_calls: list[dict] = []

        def fake_attempt(**kwargs):
            attempt_calls.append(kwargs)
            result = MagicMock()
            result.success = False
            result.phase = PHASE_DRY_RUN
            return result

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.AutoMergeConfig.load",
                    return_value=(_phase1_config(), None),
                )
            )
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.classify_conflicts",
                    return_value=ClassificationResult(
                        eligible_files=("tests/unit/test_eligible.py",),
                        refuse_files=(),
                        oversized_files=(),
                        oversized_hunks=(),
                        binary_files=(),
                        skipped_reason=None,
                    ),
                )
            )
            stack.enter_context(
                patch("orch.daemon.auto_merge.attempt_resolution", side_effect=fake_attempt)
            )
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        assert len(attempt_calls) == 1
        call = attempt_calls[0]

        wi = db_session.query(WorkItem).filter_by(project_id=project_id, id=item_id).one()
        assert call["item_title"] == wi.title
        assert call["item_description"] == (wi.design_doc_content or "")
        assert call["branch_name"] == f"agent/{item_id}"
        assert call["main_sha"] == "feedface"
        assert "tests/unit/test_eligible.py" in call["eligible_files"]

        db_session.refresh(bi)
        assert bi.status == BatchItemStatus.merge_failed

    def test_attempt_resolution_with_null_title_desc(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """Lines 521-522: WorkItem with None title/desc → empty strings (or "" fallback)."""
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        # Create a WorkItem with empty title and null design_doc_content to exercise the
        # `or ""` fallback on lines 521-522. title="" exercises `"" or ""` = ""; and
        # design_doc_content=None exercises `None or ""` = "".
        wi = WorkItem(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title="",
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            design_doc_content=None,
        )
        db_session.add(wi)
        batch_id = _unique_id("B")
        batch = Batch(
            id=batch_id,
            project_id=project_id,
            status=BatchStatus.executing,
            max_parallel=1,
            auto_merge=True,
        )
        db_session.add(batch)
        db_session.flush()
        bi = BatchItem(
            project_id=project_id,
            batch_id=batch_id,
            work_item_id=item_id,
            execution_group=0,
            status=BatchItemStatus.merging,
            worktree_info={"path": worktree_path, "branch": f"agent/{item_id}"},
        )
        db_session.add(bi)
        db_session.flush()

        resolve_payload = json.dumps(
            {
                "eligible_files": ["tests/unit/test_no_wi.py"],
                "branch": f"agent/{item_id}",
                "main_sha": "baadf00d",
            }
        )
        mock_stdout = f"AUTO_RESOLVE_REQUESTED={resolve_payload}\n[error]\n"
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        attempt_calls: list[dict] = []

        def fake_attempt(**kwargs):
            attempt_calls.append(kwargs)
            result = MagicMock()
            result.success = False
            return result

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.AutoMergeConfig.load",
                    return_value=(_phase1_config(), None),
                )
            )
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.classify_conflicts",
                    return_value=ClassificationResult(
                        eligible_files=("tests/unit/test_no_wi.py",),
                        refuse_files=(),
                        oversized_files=(),
                        oversized_hunks=(),
                        binary_files=(),
                        skipped_reason=None,
                    ),
                )
            )
            stack.enter_context(
                patch("orch.daemon.auto_merge.attempt_resolution", side_effect=fake_attempt)
            )
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        # None title/desc → "" via the `or ""` fallback (lines 521-522)
        assert len(attempt_calls) == 1
        assert attempt_calls[0]["item_title"] == ""
        assert attempt_calls[0]["item_description"] == ""


# ---------------------------------------------------------------------------
# Lines 539-540, 546-547: exception path in the elif block
# ---------------------------------------------------------------------------


class TestAutoResolveExceptionPath:
    """Exception inside the AUTO_RESOLVE_REQUESTED try block (lines 539-547)."""

    @pytest.fixture(autouse=True)
    def _mock_branch_resolver(self):
        """Return is_on_default=True so I-00126 guard never fires in tests."""
        from orch.utils.branch_resolver import BranchInfo

        with patch(
            "orch.daemon.merge_queue.resolve_branch_for_project",
            return_value=BranchInfo(
                current_branch="main", default_branch="main", is_on_default=True
            ),
        ):
            yield

    def test_exception_in_attempt_resolution_emits_failed_event(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """Exception raised by attempt_resolution → merge_auto_resolution_failed event.

        Exercises lines 539-540 (except block) and 546-547 (emit_event call).
        """
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        resolve_payload = json.dumps(
            {
                "eligible_files": ["tests/unit/test_exc.py"],
                "branch": f"agent/{item_id}",
                "main_sha": "badc0de0",
            }
        )
        mock_stdout = f"AUTO_RESOLVE_REQUESTED={resolve_payload}\n[error]\n"
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.AutoMergeConfig.load",
                    return_value=(_phase1_config(), None),
                )
            )
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.classify_conflicts",
                    return_value=ClassificationResult(
                        eligible_files=("tests/unit/test_exc.py",),
                        refuse_files=(),
                        oversized_files=(),
                        oversized_hunks=(),
                        binary_files=(),
                        skipped_reason=None,
                    ),
                )
            )
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.attempt_resolution",
                    side_effect=RuntimeError("simulated LLM subprocess crash"),
                )
            )
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        failed = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_FAILED)
        assert len(failed) == 1
        meta = failed[0].event_metadata
        assert meta["reason"] == "internal_error"
        assert "simulated LLM subprocess crash" in meta["error"]

        db_session.refresh(bi)
        assert bi.status == BatchItemStatus.merge_failed

    def test_exception_in_classify_emits_failed_event(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """Exception in classify_conflicts → caught by the same except; failed event fired."""
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        resolve_payload = json.dumps(
            {
                "eligible_files": ["tests/unit/test_classify_exc.py"],
                "branch": f"agent/{item_id}",
                "main_sha": "deadc0de",
            }
        )
        mock_stdout = f"AUTO_RESOLVE_REQUESTED={resolve_payload}\n[error]\n"
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.AutoMergeConfig.load",
                    return_value=(_phase1_config(), None),
                )
            )
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.classify_conflicts",
                    side_effect=ValueError("unexpected classification failure"),
                )
            )
            _enter_standard_patches(stack)
            _merge_item(db_session, bi, project_id, project_config)

        failed = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_FAILED)
        assert len(failed) == 1
        assert "unexpected classification failure" in failed[0].event_metadata["error"]

        db_session.refresh(bi)
        assert bi.status == BatchItemStatus.merge_failed

    def test_exception_in_emit_event_suppressed(
        self,
        db_session: Session,
        test_project,
    ) -> None:
        """Lines 546-547: exception in emit_event inside suppress is swallowed.

        Even if emit_event fails inside the suppress(Exception) block, the
        merge still reaches merge_failed status.
        """
        project_id = test_project.id
        item_id = _unique_id()
        worktree_path = f"/tmp/wt_{uuid.uuid4().hex[:8]}"

        bi = _make_batch_item(db_session, project_id, item_id, worktree_path)

        resolve_payload = json.dumps(
            {
                "eligible_files": ["tests/unit/test_emit_exc.py"],
                "branch": f"agent/{item_id}",
                "main_sha": "cafe1234",
            }
        )
        mock_stdout = f"AUTO_RESOLVE_REQUESTED={resolve_payload}\n[error]\n"
        mock_result = _make_mock_result(stdout=mock_stdout, returncode=1)
        project_config = _make_project_config(project_id)

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.run", return_value=mock_result))
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.AutoMergeConfig.load",
                    return_value=(_phase1_config(), None),
                )
            )
            stack.enter_context(
                patch(
                    "orch.daemon.auto_merge.classify_conflicts",
                    side_effect=RuntimeError("classify crashed"),
                )
            )
            stack.enter_context(
                patch("orch.daemon.auto_merge.emit_event", side_effect=RuntimeError("emit crashed"))
            )
            _enter_standard_patches(stack)
            # Must not raise despite both classify and emit_event throwing
            _merge_item(db_session, bi, project_id, project_config)

        db_session.refresh(bi)
        assert bi.status == BatchItemStatus.merge_failed
