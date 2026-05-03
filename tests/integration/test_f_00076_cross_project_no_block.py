"""Integration tests for F-00076 — cross-project items do NOT block each other.

Verifies Invariant 4: The cross-batch gate NEVER compares items from different
project_id. Two items with identical impacted_paths in different projects must
both launch.
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


def _uid(prefix: str = "F-00076") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _create_project(db: Session, project_id: str, display_name: str) -> Project:
    project = Project(
        id=project_id,
        display_name=display_name,
        repo_root=f"/repos/{project_id}",
        config={},
    )
    db.add(project)
    db.flush()
    return project


@pytest.fixture
def proj_a(db_session: Session) -> Project:
    return _create_project(db_session, "proj-a", "Project A")


@pytest.fixture
def proj_b(db_session: Session) -> Project:
    return _create_project(db_session, "proj-b", "Project B")


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
def batch_manager_proj_a(
    db_session: Session,
    proj_a: Project,
    tmp_path: Path,
) -> BatchManager:
    project_config = ProjectConfig(
        id=proj_a.id,
        display_name=proj_a.display_name,
        repo_root="/repos/proj-a",
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
        project_id=proj_a.id,
        project_config=project_config,
        session_factory=session_factory,
        config=config,
    )


@pytest.fixture
def batch_manager_proj_b(
    db_session: Session,
    proj_b: Project,
    tmp_path: Path,
) -> BatchManager:
    project_config = ProjectConfig(
        id=proj_b.id,
        display_name=proj_b.display_name,
        repo_root="/repos/proj-b",
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
        project_id=proj_b.id,
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


class TestCrossProjectNoBlock:
    """Invariant 4: cross-project items never block each other."""

    def test_identical_paths_in_different_projects_both_launch(
        self,
        db_session: Session,
        proj_a: Project,
        proj_b: Project,
        batch_manager_proj_a: BatchManager,
        batch_manager_proj_b: BatchManager,
    ) -> None:
        """Items with identical paths in different projects both launch.

        Project A: F-00001 executing with ["orch/daemon/**"]
        Project B: F-00002 pending with ["orch/daemon/**"]

        → F-00002 launches (project filter prevents comparison).
        """
        # Project A: in-flight Feature
        f1_id = _uid("F-00076")
        _wi(
            db_session,
            proj_a.id,
            f1_id,
            WorkItemType.Feature,
            ["orch/daemon/**"],
        )
        b1 = _batch(db_session, proj_a.id, _uid("B"))
        _bi(
            db_session,
            proj_a.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )

        # Project B: candidate Feature with identical paths
        f2_id = _uid("F-00076")
        _wi(
            db_session,
            proj_b.id,
            f2_id,
            WorkItemType.Feature,
            ["orch/daemon/**"],
        )
        b2 = _batch(db_session, proj_b.id, _uid("B"))
        _bi(
            db_session,
            proj_b.id,
            b2.id,
            f2_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        # Process project B's batch
        batch_b = db_session.get(Batch, (proj_b.id, b2.id))
        batch_manager_proj_b._process_batch(db_session, batch_b)

        # F-00002 in project B should launch (cross-project filter applies)
        bi2 = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == proj_b.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi2 is not None
        assert bi2.status == BatchItemStatus.executing

        # No hold event emitted for project B item
        held_events = db_session.execute(
            DaemonEvent.__table__.select().where(
                DaemonEvent.project_id == proj_b.id,
                DaemonEvent.event_type == "item_held_for_scope",
                DaemonEvent.entity_id == f2_id,
            )
        ).fetchall()
        assert len(held_events) == 0
