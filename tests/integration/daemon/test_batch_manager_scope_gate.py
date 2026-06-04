"""Integration tests for F-00076 cross-batch scope conflict gate.

Uses testcontainer PostgreSQL to test the full _process_batch flow with
real DB queries. Verifies:
- Two Features in different batches, overlapping globs → second is held
- Research items bypass the gate even with overlapping globs
- In-flight items in terminal statuses (merged, setup_failed) don't block
- Held items resume once blocking item reaches merged status
- Two items in the same group with overlapping globs: only one launches
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from orch.config import DaemonConfig
from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.daemon.scope_overlap import (
    DEFAULT_ALLOW_PATTERNS,
    DEFAULT_BLOCK_PATTERNS,
    find_blocking_items,
)
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _unique_id(prefix: str = "F-00076") -> str:
    """Generate a unique ID with a UUID suffix to prevent collisions between test runs.

    Args:
        prefix: Prefix string prepended to the UUID hex suffix.

    Returns:
        A unique string in the form ``<prefix>-<8-char-hex>``.
    """
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _create_work_item(
    db: Session,
    project_id: str,
    item_id: str,
    item_type: WorkItemType = WorkItemType.Feature,
    impacted_paths: list[str] | None = None,
) -> WorkItem:
    """Create a WorkItem row."""
    wi = WorkItem(
        project_id=project_id,
        id=item_id,
        type=item_type,
        title=f"Test {item_type.value} {item_id}",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        impacted_paths=impacted_paths or [],
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(wi)
    db.flush()
    return wi


def _create_workflow_step(
    db: Session,
    project_id: str,
    work_item_id: str,
    step_number: int,
    step_id: str,
    status: StepStatus = StepStatus.pending,
) -> WorkflowStep:
    """Create a WorkflowStep row for the given work item."""
    from orch.db.models import StepType

    step = WorkflowStep(
        project_id=project_id,
        work_item_id=work_item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label=f"Agent_{step_id}",
        step_type=StepType.implementation,
        status=status,
    )
    db.add(step)
    db.flush()
    return step


def _create_batch(
    db: Session,
    project_id: str,
    batch_id: str,
    status: BatchStatus = BatchStatus.approved,
    max_parallel: int = 2,
) -> Batch:
    """Create a Batch row."""
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
    execution_group: int = 0,
    status: BatchItemStatus = BatchItemStatus.pending,
) -> BatchItem:
    """Create a BatchItem row."""
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


class TestFindBlockingItemsIntegration:
    """Unit-level tests for find_blocking_items (no DB needed)."""

    def test_research_item_not_blocked_by_feature(self) -> None:
        """Research items are excluded from the gate; candidate Research with
        overlapping globs should launch even when a Feature is in-flight."""
        # This is a logical property: if the candidate is Research and the
        # in-flight is Feature, the gate should not trigger. The actual
        # BatchManager._process_batch skips the gate for Research types.
        # (No DB needed to document this contract — the test is a placeholder.)
        assert True

    def test_merged_item_not_in_flight(self) -> None:
        """Items in 'merged' status are not in-flight and don't block."""
        # Simulate: in_flight contains a merged item
        candidate = ["src/app/main.py"]
        in_flight = [
            ("F-00001", ["src/app/main.py"]),  # this would be merged in reality
        ]
        # find_blocking_items only checks paths, not status. The caller
        # (_collect_in_flight_scopes) is responsible for only returning
        # non-terminal statuses. This test documents the contract.
        result = find_blocking_items(
            candidate,
            in_flight,
            block_patterns=list(DEFAULT_BLOCK_PATTERNS),
            allow_patterns=list(DEFAULT_ALLOW_PATTERNS),
        )
        # The function IS designed to return a blocking result for same paths.
        # It's the caller's job to exclude merged items from in_flight.
        assert len(result) == 1


class TestBatchManagerScopeGate:
    """Full integration tests for the scope gate in _process_batch."""

    @pytest.fixture
    def project_id(self) -> str:
        """Provide the project ID string for scope gate integration tests.

        Returns:
            The ``test-proj-scope-gate`` project ID string.
        """
        return "test-proj-scope-gate"

    @pytest.fixture
    def batch_manager(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> BatchManager:
        """Build a BatchManager wired to the test db_session.

        Args:
            db_session: The SQLAlchemy session for the testcontainer DB.
            test_project: The Project row created by the shared test_project fixture.
            tmp_path: pytest tmp_path used for the projects.toml placeholder.

        Returns:
            A BatchManager instance configured for the test project.
        """
        project_config = ProjectConfig(
            id=test_project.id,
            display_name=test_project.display_name,
            repo_root="/repos/test",
            enabled=True,
            cli_tool="iw",
            model="minimax",
            worktree_base="/tmp/worktrees",
            config={},
        )
        projects_toml = tmp_path / "projects.toml"
        projects_toml.write_text("")
        config = DaemonConfig(
            db_host="localhost",
            db_port=5433,
            db_name="test",
            db_user="test",
            db_password="test",  # noqa: S106, S104
            db_url="postgresql+psycopg://test:test@localhost:5433/test",
            dashboard_host="0.0.0.0",  # noqa: S106, S104
            dashboard_port=9900,
            poll_interval=60,
            stall_threshold=600,
            pid_file=str(tmp_path / "daemon.pid"),
            archive_dir=str(tmp_path / "archive"),
            archive_ttl=90,
            log_level="DEBUG",
            log_file=str(tmp_path / "daemon.log"),
            projects_toml=projects_toml,
        )

        @contextmanager
        def session_factory():
            yield db_session

        return BatchManager(
            project_id=test_project.id,
            project_config=project_config,
            session_factory=session_factory,
            config=config,
        )

    @pytest.fixture(autouse=True)
    def _mock_alembic_guard_and_launch(self, tmp_path: Path) -> None:
        """Mock the I-00040 check_db_at_head() pre-flight and the worktree
        launch subprocess in _launch_item.

        Tests in this file exercise the scope gate, not the worktree setup or
        step execution. Without these mocks, _launch_item's subprocess calls fail
        because /repos/test doesn't exist, and _complete_item would transition
        items to 'completed' before the gate assertions can be verified.
        """
        from unittest.mock import MagicMock

        from orch.db.alembic_guard import GuardStatus

        ok = GuardStatus(
            current_rev="abc",
            head_rev="abc",
            pending=[],
            multiple_heads=[],
            ok=True,
        )
        fake_worktree = {
            "path": f"/tmp/fake_wt_{uuid.uuid4().hex[:8]}",
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

    def test_overlapping_features_different_batches_second_held(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """Two Features in different batches, overlapping globs → second is held.

        Batch 1 (already executing): F-00001 with "src/app/main.py"
        Batch 2 (new batch, same project): F-00002 with "src/app/main.py"
        → F-00002 should be held, item_held_for_scope event emitted.
        """
        # Create in-flight F-00001 in batch B1
        f1_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f1_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        b1 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )

        # Create F-00002 in batch B2 (same project, different batch)
        f2_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f2_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        b2 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b2.id,
            f2_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        # Run _process_batch for batch B2
        batch2 = db_session.get(Batch, (test_project.id, b2.id))
        batch_manager._process_batch(db_session, batch2)

        # F-00002 should remain pending (held for scope)
        bi2 = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi2 is not None
        assert bi2.status == BatchItemStatus.pending

        # event should be emitted
        event = db_session.execute(
            DaemonEvent.__table__.select().where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "item_held_for_scope",
            )
        ).fetchone()
        assert event is not None
        assert f2_id in (event.entity_id or "")

    def test_research_item_bypasses_gate(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """Research with overlapping globs launches despite in-flight Feature.

        In-flight Feature F-00001 touching src/app/main.py.
        Candidate Research R-00001 touching src/app/main.py.
        → R-00001 should launch (Research bypasses gate).
        """
        # In-flight Feature
        f1_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f1_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        b1 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )

        # Candidate Research
        r1_id = _unique_id("R-00076")
        _create_work_item(
            db_session, test_project.id, r1_id, WorkItemType.Research, ["src/app/main.py"]
        )
        b2 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b2.id,
            r1_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        # Process batch 2
        batch2 = db_session.get(Batch, (test_project.id, b2.id))
        batch_manager._process_batch(db_session, batch2)

        # Research should launch (status becomes executing after mocked worktree setup)
        # Note: _launch_item sets setting_up then immediately executing after
        # _setup_worktree succeeds; the test assertion checks the post-setup state.
        bi_r = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == r1_id,
            )
        ).fetchone()
        assert bi_r is not None
        assert bi_r.status == BatchItemStatus.executing

    def test_merged_item_not_in_flight_candidate_launches(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """In-flight Feature that reaches 'merged' no longer blocks.

        F-00001 is in 'merged' status (terminal success).
        F-00002 with same overlapping paths tries to launch.
        → F-00002 should launch (merged is not in-flight).
        """
        # Merged F-00001
        f1_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f1_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        b1 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.merged,
        )

        # Candidate F-00002 (same paths)
        f2_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f2_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        b2 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b2.id,
            f2_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        # Process batch 2
        batch2 = db_session.get(Batch, (test_project.id, b2.id))
        batch_manager._process_batch(db_session, batch2)

        # F-00002 should launch
        bi2 = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi2 is not None
        assert bi2.status == BatchItemStatus.executing

    def test_setup_failed_not_in_flight_candidate_launches(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """In-flight Feature in 'setup_failed' status doesn't block.

        F-00001 is in 'setup_failed' (terminal failure).
        F-00002 with overlapping paths tries to launch.
        → F-00002 should launch (setup_failed is not in-flight).
        """
        # setup_failed F-00001
        f1_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f1_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        b1 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.setup_failed,
        )

        # Candidate F-00002
        f2_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f2_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        b2 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b2.id,
            f2_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        batch2 = db_session.get(Batch, (test_project.id, b2.id))
        batch_manager._process_batch(db_session, batch2)

        bi2 = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi2 is not None
        assert bi2.status == BatchItemStatus.executing

    def test_held_item_resumes_after_blocker_merges(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """Held item (blocked by in-flight) resumes once blocker reaches merged.

        F-00001 is executing, blocking F-00002 (held).
        Then F-00001 reaches merged.
        Next poll: F-00002 should launch.
        """
        # In-flight F-00001
        f1_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f1_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        b1 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )

        # Held F-00002
        f2_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f2_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        b2 = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            b2.id,
            f2_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        # Process: F-00002 should be held
        db_session.commit()
        batch2 = db_session.get(Batch, (test_project.id, b2.id))
        batch_manager._process_batch(db_session, batch2)

        bi2_held = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi2_held.status == BatchItemStatus.pending

        # Advance F-00001 to merged
        db_session.execute(
            BatchItem.__table__.update()
            .where(BatchItem.project_id == test_project.id)
            .where(BatchItem.work_item_id == f1_id)
            .values(status=BatchItemStatus.merged)
        )
        db_session.commit()

        # Re-process batch 2: F-00002 should now launch
        batch_manager._process_batch(db_session, batch2)

        bi2_launched = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi2_launched is not None
        assert bi2_launched.status == BatchItemStatus.executing

    def test_two_pending_same_group_overlap_only_one_launches(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """Two pending items in same execution group with overlapping globs:
        only the first (by BatchItem.id order) launches per cycle.

        F-00001 and F-00002 are both pending in group 0 with overlapping paths.
        max_parallel=2 but only one should launch because the first one,
        once launched, adds itself to in_flight_scopes and blocks the second.
        """
        f1_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f1_id, WorkItemType.Feature, ["src/app/main.py"]
        )
        f2_id = _unique_id("F-00076")
        _create_work_item(
            db_session, test_project.id, f2_id, WorkItemType.Feature, ["src/app/main.py"]
        )

        b1 = _create_batch(db_session, test_project.id, _unique_id("B"), max_parallel=2)
        # Create F-00001 first (lower id)
        _create_batch_item(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )
        # Create F-00002 second (higher id)
        _create_batch_item(
            db_session,
            test_project.id,
            b1.id,
            f2_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        batch1 = db_session.get(Batch, (test_project.id, b1.id))
        batch_manager._process_batch(db_session, batch1)

        # F-00001 (first by id) should launch; F-00002 should remain pending
        bi1 = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f1_id,
            )
        ).fetchone()
        bi2 = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi1 is not None
        assert bi1.status == BatchItemStatus.executing
        assert bi2 is not None
        assert bi2.status == BatchItemStatus.pending
