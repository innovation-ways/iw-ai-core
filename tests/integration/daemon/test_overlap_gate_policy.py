"""Integration tests for the CR-00058 configurable per-project overlap gate.

End-to-end check that ``BatchManager._process_batch`` honours the
``overlap_gate`` policy across batches and emits the expected
``DaemonEvent`` audit rows. Mirrors the real-world CR-00057 vs
I-00087/I-00088 scenario:

  * default policy (synthesized DEFAULT_BLOCK_PATTERNS /
    DEFAULT_ALLOW_PATTERNS) still holds candidates whose impacted source
    paths overlap an in-flight item in a different batch;
  * a permissive policy (e.g. ``allow_on_overlap = ["dashboard/**", ...]``)
    releases the candidate AND emits a single
    ``item_overlap_allowed_by_policy`` event for auditing;
  * the allow filter is per-conflicting-glob (an item with one allowed and
    one non-allowed conflict still gets held — the held event only lists
    the non-allowed globs);
  * the policy never short-circuits the in-batch execution-group
    dependency graph.

Pattern note: ``ProjectConfig`` already exposes ``overlap_block_patterns``
and ``overlap_allow_patterns`` as plain dataclass fields, so each test
constructs the ``BatchManager`` with the desired policy directly instead
of round-tripping through ``Project.config`` + ``_parse_overlap_gate``.
The parser path is covered exhaustively by the S01 unit tests in
``tests/unit/daemon/test_project_registry_overlap_gate.py``.
"""

from __future__ import annotations

import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from orch.config import DaemonConfig
from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.daemon.scope_overlap import DEFAULT_ALLOW_PATTERNS, DEFAULT_BLOCK_PATTERNS
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Row factories — keep tests focused on the gate, not on fixture wiring
# ---------------------------------------------------------------------------


def _uid(prefix: str) -> str:
    """Short unique suffix so each test gets fresh IDs even within one clone."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _create_work_item(
    db: Session,
    project_id: str,
    item_id: str,
    impacted_paths: list[str],
    item_type: WorkItemType = WorkItemType.Feature,
) -> WorkItem:
    wi = WorkItem(
        project_id=project_id,
        id=item_id,
        type=item_type,
        title=f"Test {item_type.value} {item_id}",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        impacted_paths=impacted_paths,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(wi)
    db.flush()
    # An item with at least one workflow step is required so _launch_item has
    # something to schedule when the gate releases it.
    step = WorkflowStep(
        project_id=project_id,
        work_item_id=item_id,
        step_number=1,
        step_id="S01",
        agent_label="Agent_S01",
        step_type=StepType.implementation,
        status=StepStatus.pending,
    )
    db.add(step)
    db.flush()
    return wi


def _create_batch(
    db: Session,
    project_id: str,
    batch_id: str,
    status: BatchStatus = BatchStatus.executing,
    max_parallel: int = 2,
) -> Batch:
    batch = Batch(
        id=batch_id,
        project_id=project_id,
        status=status,
        max_parallel=max_parallel,
    )
    db.add(batch)
    db.flush()
    return batch


def _create_batch_item(
    db: Session,
    project_id: str,
    batch_id: str,
    work_item_id: str,
    *,
    execution_group: int = 0,
    status: BatchItemStatus = BatchItemStatus.pending,
) -> BatchItem:
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=execution_group,
        status=status,
    )
    db.add(bi)
    db.flush()
    return bi


# ---------------------------------------------------------------------------
# BatchManager construction with a custom overlap_gate policy
# ---------------------------------------------------------------------------


def _build_manager(
    db_session: Session,
    test_project: Project,
    work_dir: Path,
    *,
    block_patterns: list[str] | None = None,
    allow_patterns: list[str] | None = None,
) -> BatchManager:
    """Construct a BatchManager whose ProjectConfig pins the requested policy.

    ``None`` for either argument yields the synthesized default (matches the
    case where ``.iw-orch.json`` does not declare an ``overlap_gate`` block).

    ``work_dir`` is used only to materialise the ``projects.toml`` placeholder
    that ``DaemonConfig`` insists on; the test does not exercise daemon
    bootstrap paths that read it. The caller owns the directory's lifetime —
    we deliberately avoid pytest's ``tmp_path`` fixture because the shared
    ``/tmp/pytest-of-<user>`` tree is raced by concurrent pytest sessions
    started by mutmut / parallel agent worktrees on this dev host, which
    deletes the basetemp mid-session and crashes ``tmp_path`` fixture setup.
    """
    project_config = ProjectConfig(
        id=test_project.id,
        display_name=test_project.display_name,
        repo_root="/repos/test",
        enabled=True,
        cli_tool="iw",
        model="minimax",
        worktree_base="/tmp/worktrees",  # noqa: S108 — synthetic, mocked away
        config={},
        overlap_block_patterns=(
            list(block_patterns) if block_patterns is not None else list(DEFAULT_BLOCK_PATTERNS)
        ),
        overlap_allow_patterns=(
            list(allow_patterns) if allow_patterns is not None else list(DEFAULT_ALLOW_PATTERNS)
        ),
    )
    projects_toml = work_dir / "projects.toml"
    projects_toml.write_text("")
    config = DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(work_dir / "daemon.pid"),
        archive_dir=str(work_dir / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(work_dir / "daemon.log"),
        projects_toml=projects_toml,
    )

    @contextmanager
    def session_factory() -> Generator[Session, None, None]:
        yield db_session

    return BatchManager(
        project_id=test_project.id,
        project_config=project_config,
        session_factory=session_factory,
        config=config,
    )


@pytest.fixture
def work_dir() -> Generator[Path, None, None]:
    """A throwaway per-test directory backed by ``tempfile.TemporaryDirectory``.

    Used instead of pytest's built-in ``tmp_path`` to side-step a basetemp
    race condition on this dev host: a long-running mutmut sweep in a sibling
    worktree (CR-00059) re-runs the integration test suite per mutant and
    its cleanup of ``/tmp/pytest-of-<user>`` deletes our session's basetemp
    mid-run, blowing up ``tmp_path`` fixture setup with FileNotFoundError.
    """
    with tempfile.TemporaryDirectory(prefix="cr00058-overlap-gate-") as raw:
        yield Path(raw)


@pytest.fixture
def _launch_isolation() -> Generator[None, None, None]:
    """Stub the worktree/subprocess pieces so ``_launch_item`` is observable.

    Mirrors the autouse fixture in ``test_batch_manager_scope_gate.py``:
    we are exercising the gate decision, not the worktree setup or the
    agent subprocess. Without these patches ``_launch_item`` would fail
    because ``/repos/test`` does not exist and the test would never reach
    the assertions about ``DaemonEvent`` rows.
    """
    from orch.db.alembic_guard import GuardStatus

    ok = GuardStatus(
        current_rev="abc",
        head_rev="abc",
        pending=[],
        multiple_heads=[],
        ok=True,
    )
    fake_worktree = {
        "path": f"/tmp/fake_wt_{uuid.uuid4().hex[:8]}",  # noqa: S108
        "branch": "agent/test",
        "created_at": "now",
    }
    with (
        patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok),
        patch.object(BatchManager, "_setup_worktree", return_value=fake_worktree),
        patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
        patch.object(BatchManager, "_complete_item"),
        patch("pathlib.Path.open", MagicMock()),
        patch("pathlib.Path.mkdir"),
    ):
        mock_popen.return_value = MagicMock(pid=12345)
        yield


# ---------------------------------------------------------------------------
# Small query helpers — express intent at the call site
# ---------------------------------------------------------------------------


def _load_batch(db: Session, project_id: str, batch_id: str) -> Batch:
    """Type-narrowed ``db.get(Batch, ...)`` — fails loudly if the row is missing.

    Keeps mypy happy at every ``_process_batch`` call site without each test
    repeating an ``assert is not None``.
    """
    batch = db.get(Batch, (project_id, batch_id))
    assert batch is not None, f"Batch {batch_id!r} not in DB"
    return batch


def _fetch_batch_item(db: Session, project_id: str, work_item_id: str) -> BatchItem:
    bi = (
        db.query(BatchItem)
        .filter(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == work_item_id,
        )
        .one()
    )
    db.refresh(bi)
    return bi


def _events(
    db: Session, project_id: str, event_type: str, work_item_id: str | None = None
) -> list[DaemonEvent]:
    q = db.query(DaemonEvent).filter(
        DaemonEvent.project_id == project_id,
        DaemonEvent.event_type == event_type,
    )
    if work_item_id is not None:
        q = q.filter(DaemonEvent.entity_id == work_item_id)
    return q.all()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_launch_isolation")
class TestOverlapGatePolicy:
    """End-to-end coverage of the CR-00058 per-project overlap_gate policy."""

    def test_default_policy_holds_source_overlap_across_batches(
        self,
        db_session: Session,
        test_project: Project,
        work_dir: Path,
    ) -> None:
        """With the synthesized default, two batches that touch the same
        source file produce one held candidate and one item_held_for_scope
        event — and zero item_overlap_allowed_by_policy events."""
        manager = _build_manager(db_session, test_project, work_dir)

        a_id = _uid("F-DFLT")
        b_id = _uid("F-DFLT")
        _create_work_item(db_session, test_project.id, a_id, ["dashboard/foo.py"])
        _create_work_item(db_session, test_project.id, b_id, ["dashboard/foo.py"])

        batch1 = _create_batch(db_session, test_project.id, _uid("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            batch1.id,
            a_id,
            status=BatchItemStatus.executing,
        )
        batch2 = _create_batch(db_session, test_project.id, _uid("B"))
        _create_batch_item(db_session, test_project.id, batch2.id, b_id)
        db_session.commit()

        manager._process_batch(db_session, _load_batch(db_session, test_project.id, batch2.id))

        b_item = _fetch_batch_item(db_session, test_project.id, b_id)
        assert b_item.status == BatchItemStatus.pending, (
            "Default policy must hold B when source paths overlap an in-flight item"
        )

        held = _events(db_session, test_project.id, "item_held_for_scope", b_id)
        assert len(held) == 1, f"expected exactly one item_held_for_scope event, got {len(held)}"
        meta = held[0].event_metadata or {}
        assert meta.get("candidate_item_id") == b_id
        assert meta.get("blocking_item_id") == a_id
        assert "dashboard/foo.py" in (meta.get("conflicting_globs") or [])

        allowed = _events(db_session, test_project.id, "item_overlap_allowed_by_policy", b_id)
        assert allowed == [], (
            "Default policy must not emit item_overlap_allowed_by_policy — that event "
            "is reserved for non-default policies that release would-be-blocked items"
        )

    def test_permissive_allow_releases_overlap_and_emits_audit_event(
        self,
        db_session: Session,
        test_project: Project,
        work_dir: Path,
    ) -> None:
        """A permissive ``allow_on_overlap`` releases the candidate AND
        emits exactly one ``item_overlap_allowed_by_policy`` audit row whose
        metadata pins the released globs and the matched allow patterns."""
        permissive_allow = [
            "dashboard/**",
            "tests/**",
            "test/**",
            "__tests__/**",
            "**/*conftest*",
            "**/*.test.*",
            "**/*.spec.*",
        ]
        manager = _build_manager(
            db_session,
            test_project,
            work_dir,
            block_patterns=["**/*"],
            allow_patterns=permissive_allow,
        )

        a_id = _uid("F-PERM")
        b_id = _uid("F-PERM")
        _create_work_item(db_session, test_project.id, a_id, ["dashboard/foo.py"])
        _create_work_item(db_session, test_project.id, b_id, ["dashboard/foo.py"])

        batch1 = _create_batch(db_session, test_project.id, _uid("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            batch1.id,
            a_id,
            status=BatchItemStatus.executing,
        )
        batch2 = _create_batch(db_session, test_project.id, _uid("B"))
        _create_batch_item(db_session, test_project.id, batch2.id, b_id)
        db_session.commit()

        manager._process_batch(db_session, _load_batch(db_session, test_project.id, batch2.id))

        b_item = _fetch_batch_item(db_session, test_project.id, b_id)
        assert b_item.status in {
            BatchItemStatus.setting_up,
            BatchItemStatus.executing,
        }, (
            f"Permissive allow_on_overlap should have released B; observed {b_item.status!r}. "
            "_launch_item is stubbed so the post-launch status depends on the patched flow."
        )

        held = _events(db_session, test_project.id, "item_held_for_scope", b_id)
        assert held == [], "No item_held_for_scope event should be emitted when policy releases"

        allowed = _events(db_session, test_project.id, "item_overlap_allowed_by_policy", b_id)
        assert len(allowed) == 1, (
            f"Expected exactly one item_overlap_allowed_by_policy audit event, got {len(allowed)}"
        )
        meta = allowed[0].event_metadata or {}
        assert meta.get("candidate_item_id") == b_id
        assert meta.get("in_flight_item_ids") == [a_id]
        assert "dashboard/foo.py" in (meta.get("dropped_block_globs") or [])
        matched = meta.get("matched_allow_patterns") or []
        assert "dashboard/**" in matched, (
            f"matched_allow_patterns should record the allow rule that fired, got {matched!r}"
        )

    def test_per_conflicting_glob_precedence(
        self,
        db_session: Session,
        test_project: Project,
        work_dir: Path,
    ) -> None:
        """The allow filter is per-glob: a candidate with one allowed and
        one non-allowed conflict is still held, and the held event lists
        only the unallowed glob."""
        manager = _build_manager(
            db_session,
            test_project,
            work_dir,
            block_patterns=["**/*"],
            allow_patterns=["dashboard/**"],
        )

        a_id = _uid("F-PREC")
        b_id = _uid("F-PREC")
        _create_work_item(
            db_session,
            test_project.id,
            a_id,
            ["dashboard/x.py", "orch/foo.py"],
        )
        _create_work_item(
            db_session,
            test_project.id,
            b_id,
            ["dashboard/y.py", "orch/foo.py"],
        )

        batch1 = _create_batch(db_session, test_project.id, _uid("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            batch1.id,
            a_id,
            status=BatchItemStatus.executing,
        )
        batch2 = _create_batch(db_session, test_project.id, _uid("B"))
        _create_batch_item(db_session, test_project.id, batch2.id, b_id)
        db_session.commit()

        manager._process_batch(db_session, _load_batch(db_session, test_project.id, batch2.id))

        b_item = _fetch_batch_item(db_session, test_project.id, b_id)
        assert b_item.status == BatchItemStatus.pending, (
            "B must still be held — orch/foo.py is not covered by the allow list"
        )

        held = _events(db_session, test_project.id, "item_held_for_scope", b_id)
        assert len(held) == 1
        meta = held[0].event_metadata or {}
        conflicting = meta.get("conflicting_globs") or []
        assert "orch/foo.py" in conflicting, (
            f"orch/foo.py should be reported as the blocking glob, got {conflicting!r}"
        )
        assert "dashboard/y.py" not in conflicting, (
            f"dashboard/y.py was allowlisted and must NOT appear in conflicting_globs; "
            f"got {conflicting!r}"
        )

    def test_dependency_graph_not_affected_by_policy(
        self,
        db_session: Session,
        test_project: Project,
        work_dir: Path,
    ) -> None:
        """An everything-allowed policy must not override the in-batch
        execution-group dependency rule: a later group still waits for
        the earlier group to finish."""
        manager = _build_manager(
            db_session,
            test_project,
            work_dir,
            block_patterns=["**/*"],
            allow_patterns=["**/*"],
        )

        a_id = _uid("F-DEP")
        b_id = _uid("F-DEP")
        _create_work_item(db_session, test_project.id, a_id, ["docs/foo.md"])
        _create_work_item(db_session, test_project.id, b_id, ["docs/foo.md"])

        batch = _create_batch(db_session, test_project.id, _uid("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            a_id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            b_id,
            execution_group=1,
            status=BatchItemStatus.pending,
        )
        db_session.commit()

        manager._process_batch(db_session, _load_batch(db_session, test_project.id, batch.id))

        b_item = _fetch_batch_item(db_session, test_project.id, b_id)
        assert b_item.status == BatchItemStatus.pending, (
            "B is in execution_group=1 and must wait for group 0 (A still executing) — "
            "the overlap policy must not short-circuit the in-batch dependency graph"
        )

        # And we must not have emitted either gate event for B — neither the
        # hold nor the allowance is relevant when the dependency graph is the
        # gating factor.
        assert _events(db_session, test_project.id, "item_held_for_scope", b_id) == []
        assert _events(db_session, test_project.id, "item_overlap_allowed_by_policy", b_id) == []
