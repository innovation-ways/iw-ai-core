"""End-to-end integration test for F-00076 cross-batch scope conflict gate.

Verifies AC1: Two Features in different batches with overlapping impacted_paths.
The first is already executing; the second must be held. Once the first transitions
to merged, the second launches in the next poll cycle.
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


class TestE2EScopeGate:
    """End-to-end cross-batch scope conflict gate."""

    def test_overlapping_features_different_batches_held_then_releases(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """AC1: Two Features in different batches, overlapping paths.

        Batch A (I-100): executing with ["orch/daemon/**"]
        Batch B (I-200): pending with ["orch/daemon/batch_manager.py"]

        → I-200 is held. After I-100 reaches merged, I-200 launches.
        """
        # Batch A: in-flight Feature
        f1_id = _uid("F-00076")
        _wi(db_session, test_project.id, f1_id, WorkItemType.Feature, ["orch/daemon/**"])
        b1 = _batch(db_session, test_project.id, _uid("B"))
        _bi(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )

        # Batch B: candidate Feature with overlapping paths
        f2_id = _uid("F-00076")
        _wi(
            db_session,
            test_project.id,
            f2_id,
            WorkItemType.Feature,
            ["orch/daemon/batch_manager.py"],
        )
        b2 = _batch(db_session, test_project.id, _uid("B"))
        _bi(
            db_session,
            test_project.id,
            b2.id,
            f2_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        # First poll cycle: process batch B → I-200 should be held
        batch2 = db_session.get(Batch, (test_project.id, b2.id))
        batch_manager._process_batch(db_session, batch2)

        bi2_held = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi2_held is not None
        assert bi2_held.status == BatchItemStatus.pending

        # item_held_for_scope event must be emitted
        event = db_session.execute(
            DaemonEvent.__table__.select().where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "item_held_for_scope",
                DaemonEvent.entity_id == f2_id,
            )
        ).fetchone()
        assert event is not None, "item_held_for_scope event not emitted for held item"
        event_meta = event.metadata
        assert event_meta["blocking_item_id"] == f1_id
        assert "orch/daemon/batch_manager.py" in event_meta["conflicting_globs"]

        # Advance I-100 to merged (simulate merge completion)
        db_session.execute(
            BatchItem.__table__.update()
            .where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f1_id,
            )
            .values(status=BatchItemStatus.merged)
        )
        db_session.commit()

        # Second poll cycle: process batch B → I-200 should now launch
        batch_manager._process_batch(db_session, batch2)

        bi2_launched = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi2_launched is not None
        assert bi2_launched.status == BatchItemStatus.executing

    def test_only_one_item_launches_per_project_per_cycle_when_overlap(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """When two different batches have overlapping Features, only one launches per cycle.

        Batch A: I-100 executing with ["src/app/**"]
        Batch B: I-200 pending with ["src/app/main.py"]  (overlaps I-100)
        Batch C: I-300 pending with ["docs/readme.md"]  (does NOT overlap I-100)

        → I-300 launches (docs/readme.md does not conflict with src/app/**)
        → I-200 is held when its batch is processed (conflicts with I-100)
        """
        # Batch A: in-flight Feature
        f1_id = _uid("F-00076")
        _wi(db_session, test_project.id, f1_id, WorkItemType.Feature, ["src/app/**"])
        b1 = _batch(db_session, test_project.id, _uid("B"))
        _bi(
            db_session,
            test_project.id,
            b1.id,
            f1_id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )

        # Batch B: overlapping Feature
        f2_id = _uid("F-00076")
        _wi(db_session, test_project.id, f2_id, WorkItemType.Feature, ["src/app/main.py"])
        b2 = _batch(db_session, test_project.id, _uid("B"))
        _bi(
            db_session,
            test_project.id,
            b2.id,
            f2_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        # Batch C: non-overlapping Feature
        f3_id = _uid("F-00076")
        _wi(db_session, test_project.id, f3_id, WorkItemType.Feature, ["docs/readme.md"])
        b3 = _batch(db_session, test_project.id, _uid("B"))
        _bi(
            db_session,
            test_project.id,
            b3.id,
            f3_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        # Process batch C first (non-overlapping I-300) — should launch
        batch3 = db_session.get(Batch, (test_project.id, b3.id))
        batch_manager._process_batch(db_session, batch3)

        # I-300 should launch (no conflict with I-100's src/app/**)
        bi3_launched = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f3_id,
            )
        ).fetchone()
        assert bi3_launched is not None
        assert bi3_launched.status == BatchItemStatus.executing

        # Process batch B (overlapping I-200) — should be held
        batch2 = db_session.get(Batch, (test_project.id, b2.id))
        batch_manager._process_batch(db_session, batch2)

        # I-200 should be held (conflicts with still-executing I-100)
        bi2_held = db_session.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == test_project.id,
                BatchItem.work_item_id == f2_id,
            )
        ).fetchone()
        assert bi2_held is not None
        assert bi2_held.status == BatchItemStatus.pending
