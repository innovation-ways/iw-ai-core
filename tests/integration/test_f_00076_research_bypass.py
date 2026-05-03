"""Integration tests for F-00076 — Research items bypass the scope gate.

Verifies AC2: Given a Feature in-flight with overlapping impacted_paths,
a Research candidate with overlapping paths MUST still launch.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from orch.config import DaemonConfig
from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _uid(prefix: str = "R-00076") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _wi(
    db: Session,
    project_id: str,
    item_id: str,
    item_type: WorkItemType = WorkItemType.Feature,
    impacted_paths: list[str] | None = None,
) -> WorkItem:
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


def _batch(
    db: Session,
    project_id: str,
    batch_id: str,
    status: BatchStatus = BatchStatus.approved,
    max_parallel: int = 2,
) -> Batch:
    b = Batch(
        id=batch_id,
        project_id=project_id,
        status=status,
        max_parallel=max_parallel,
    )
    db.add(b)
    db.flush()
    return b


def _bi(
    db: Session,
    project_id: str,
    batch_id: str,
    work_item_id: str,
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


@pytest.fixture
def batch_manager(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
) -> BatchManager:
    project_config = ProjectConfig(
        id=test_project.id,
        display_name=test_project.display_name,
        repo_root="/repos/test",
        enabled=True,
        cli_tool="iw",
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
def _mock_alembic_guard_and_launch(tmp_path: Path) -> None:
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


class TestResearchBypass:
    """AC2: Research items bypass the cross-batch scope gate."""

    def test_research_item_bypasses_gate_with_overlapping_globs(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """Feature in-flight + Research candidate with overlapping paths → Research launches.

        In-flight Feature F-00001 touching "docs/**", "orch/foo.py".
        Research candidate RES-00001 touching "docs/architecture.md".
        → RES-00001 launches even though F-00001 is executing.
        """
        # In-flight Feature
        f1_id = _uid("F-00076")
        _wi(
            db_session,
            test_project.id,
            f1_id,
            WorkItemType.Feature,
            ["docs/**", "orch/foo.py"],
        )
        b1 = _batch(db_session, test_project.id, _uid("B"))
        _bi(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )

        # Research candidate with overlapping docs path
        r1_id = _uid("R-00076")
        _wi(
            db_session,
            test_project.id,
            r1_id,
            WorkItemType.Research,
            ["docs/architecture.md"],
        )
        b2 = _batch(db_session, test_project.id, _uid("B"))
        _bi(
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

        # Research should launch (no hold event, status becomes executing)
        bi_r = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == r1_id,
            )
        ).fetchone()
        assert bi_r is not None
        assert bi_r.status == BatchItemStatus.executing

        # No item_held_for_scope event for the Research item
        held_events = db_session.execute(
            DaemonEvent.__table__.select().where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "item_held_for_scope",
                DaemonEvent.entity_id == r1_id,
            )
        ).fetchall()
        assert len(held_events) == 0

    def test_research_with_identical_paths_as_feature_still_bypasses(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """Research with EXACT same impacted_paths as in-flight Feature → still bypasses.

        This is the strongest form of AC2: even complete path overlap
        between Research and Feature must not block Research.
        """
        f1_id = _uid("F-00076")
        _wi(
            db_session,
            test_project.id,
            f1_id,
            WorkItemType.Feature,
            ["orch/daemon/**", "orch/batch_planner.py"],
        )
        b1 = _batch(db_session, test_project.id, _uid("B"))
        _bi(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )

        # Research with identical paths
        r1_id = _uid("R-00076")
        _wi(
            db_session,
            test_project.id,
            r1_id,
            WorkItemType.Research,
            ["orch/daemon/**", "orch/batch_planner.py"],
        )
        b2 = _batch(db_session, test_project.id, _uid("B"))
        _bi(
            db_session,
            test_project.id,
            b2.id,
            r1_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        batch2 = db_session.get(Batch, (test_project.id, b2.id))
        batch_manager._process_batch(db_session, batch2)

        bi_r = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == r1_id,
            )
        ).fetchone()
        assert bi_r is not None
        assert bi_r.status == BatchItemStatus.executing
