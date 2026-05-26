from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from orch.daemon.batch_manager import BatchManager, WorktreeSetupError
from orch.daemon.project_registry import ProjectConfig
from orch.db.alembic_guard import GuardStatus
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)


def _ok_guard() -> GuardStatus:
    return GuardStatus(current_rev="abc", head_rev="abc", pending=[], multiple_heads=[], ok=True)


def _make_manager(db_session, tmp_path: Path) -> BatchManager:
    project_root = tmp_path / "repo"
    project_root.mkdir(exist_ok=True)
    (project_root / ".worktrees").mkdir(exist_ok=True)

    project_config = ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root=str(project_root),
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )

    from orch.config import DaemonConfig

    @contextmanager
    def session_factory():
        yield db_session

    daemon_config = DaemonConfig(
        db_host="localhost",
        db_port=5432,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5432/test",
        dashboard_host="127.0.0.1",
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=str(tmp_path / "projects.toml"),
    )

    return BatchManager("test-proj", project_config, session_factory, daemon_config)


def _seed_batch(db_session, batch_id: str, item_ids: list[str]) -> list[BatchItem]:
    db_session.add(
        Batch(project_id="test-proj", id=batch_id, status=BatchStatus.executing, max_parallel=3)
    )
    for item_id in item_ids:
        db_session.add(
            WorkItem(
                project_id="test-proj",
                id=item_id,
                type=WorkItemType.Feature,
                title=f"Item {item_id}",
                status=WorkItemStatus.approved,
                config={},
            )
        )
        db_session.add(
            BatchItem(
                project_id="test-proj",
                batch_id=batch_id,
                work_item_id=item_id,
                execution_group=0,
                status=BatchItemStatus.pending,
            )
        )
    db_session.commit()
    return (
        db_session.query(BatchItem)
        .filter(BatchItem.project_id == "test-proj", BatchItem.batch_id == batch_id)
        .order_by(BatchItem.work_item_id)
        .all()
    )


@pytest.mark.integration
def test_worktree_setup_uv_sync_failure_marks_item_terminal_error(
    db_session, test_project, tmp_path, chaos_daemon
):
    manager = _make_manager(db_session, tmp_path)
    item_a = _seed_batch(db_session, "B-FAIL", ["I-FAIL-A"])[0]

    chaos_daemon.inject_worktree_setup_failure_after_clone()

    with patch("orch.daemon.batch_manager.check_db_at_head", return_value=_ok_guard()):
        manager._launch_item(db_session, item_a)
    db_session.commit()

    db_session.refresh(item_a)
    work_item = db_session.get(WorkItem, ("test-proj", "I-FAIL-A"))
    event = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == "test-proj",
            DaemonEvent.event_type == "item_failed",
            DaemonEvent.entity_id == "I-FAIL-A",
        )
        .order_by(DaemonEvent.id.desc())
        .first()
    )

    assert item_a.status == BatchItemStatus.setup_failed
    assert work_item is not None
    assert work_item.status == WorkItemStatus.failed
    assert item_a.notes is not None
    assert "injected worktree setup failure" in item_a.notes
    assert event is not None
    assert event.event_metadata.get("reason") == "setup_failed"


@pytest.mark.integration
def test_worktree_setup_failure_does_not_leave_zombie_directory(
    db_session, test_project, tmp_path, chaos_daemon
):
    manager = _make_manager(db_session, tmp_path)
    _seed_batch(db_session, "B-ZOMBIE", ["I-ZOMBIE-A"])
    item_a = (
        db_session.query(BatchItem)
        .filter(BatchItem.project_id == "test-proj", BatchItem.work_item_id == "I-ZOMBIE-A")
        .one()
    )

    chaos_daemon.inject_worktree_setup_failure_after_clone()
    with patch("orch.daemon.batch_manager.check_db_at_head", return_value=_ok_guard()):
        manager._launch_item(db_session, item_a)
    db_session.commit()

    worktree_path = (
        Path(manager.project_config.working_dir)
        / manager.project_config.worktree_base
        / "I-ZOMBIE-A"
    )
    if worktree_path.exists():
        assert {p.name for p in worktree_path.iterdir()} <= {"setup_failed.flag"}
    else:
        assert not worktree_path.exists()

    event_count = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == "test-proj",
            DaemonEvent.event_type == "item_failed",
            DaemonEvent.entity_id == "I-ZOMBIE-A",
        )
        .count()
    )
    assert event_count == 1


@pytest.mark.integration
def test_worktree_setup_failure_does_not_poison_batch(
    db_session, test_project, tmp_path, chaos_daemon
):
    manager = _make_manager(db_session, tmp_path)
    _seed_batch(db_session, "B-POISON", ["I-POISON-A", "I-POISON-B", "I-POISON-C"])

    attempts: list[str] = []
    chaos_daemon.inject_worktree_setup_failure_after_clone()

    def _conditional_setup(_self, item_id: str):
        attempts.append(item_id)
        if item_id == "I-POISON-A":
            chaos_daemon.hooks_triggered["worktree_setup_failure_after_clone"] = True
            raise WorktreeSetupError("injected worktree setup failure at stage=after_clone")
        wt_path = (
            Path(manager.project_config.working_dir)
            / manager.project_config.worktree_base
            / item_id
        )
        wt_path.mkdir(parents=True, exist_ok=True)
        return {"path": str(wt_path), "branch": f"agent/{item_id}", "created_at": "now"}

    with (
        patch("orch.daemon.batch_manager.check_db_at_head", return_value=_ok_guard()),
        patch.object(BatchManager, "_setup_worktree", _conditional_setup),
        patch.object(BatchManager, "_launch_next_step", return_value=None),
    ):
        batch = db_session.get(Batch, ("test-proj", "B-POISON"))
        for _ in range(3):
            chaos_daemon.advance_one_cycle()
            manager._process_batch(db_session, batch)
    db_session.commit()

    a = (
        db_session.query(BatchItem)
        .filter_by(project_id="test-proj", work_item_id="I-POISON-A")
        .one()
    )
    b = (
        db_session.query(BatchItem)
        .filter_by(project_id="test-proj", work_item_id="I-POISON-B")
        .one()
    )
    c = (
        db_session.query(BatchItem)
        .filter_by(project_id="test-proj", work_item_id="I-POISON-C")
        .one()
    )

    assert a.status == BatchItemStatus.setup_failed
    assert any(i in attempts for i in ("I-POISON-B", "I-POISON-C"))
    assert b.status in {
        BatchItemStatus.executing,
        BatchItemStatus.completed,
        BatchItemStatus.setup_failed,
    }
    assert c.status in {
        BatchItemStatus.executing,
        BatchItemStatus.completed,
        BatchItemStatus.setup_failed,
    }


@pytest.mark.integration
def test_worktree_setup_failure_before_git_worktree_add(
    db_session, test_project, tmp_path, chaos_daemon
):
    manager = _make_manager(db_session, tmp_path)
    _seed_batch(db_session, "B-BOUNDARY", ["I-BOUND-A", "I-BOUND-B", "I-BOUND-C"])

    attempts: list[str] = []
    chaos_daemon.inject_worktree_setup_failure_after_clone(stage="before_git_worktree_add")

    def _conditional_setup(_self, item_id: str):
        attempts.append(item_id)
        if item_id == "I-BOUND-A":
            chaos_daemon.hooks_triggered["worktree_setup_failure_after_clone"] = True
            raise WorktreeSetupError(
                "injected worktree setup failure at stage=before_git_worktree_add"
            )
        wt_path = (
            Path(manager.project_config.working_dir)
            / manager.project_config.worktree_base
            / item_id
        )
        wt_path.mkdir(parents=True, exist_ok=True)
        return {"path": str(wt_path), "branch": f"agent/{item_id}", "created_at": "now"}

    with (
        patch("orch.daemon.batch_manager.check_db_at_head", return_value=_ok_guard()),
        patch.object(BatchManager, "_setup_worktree", _conditional_setup),
        patch.object(BatchManager, "_launch_next_step", return_value=None),
    ):
        batch = db_session.get(Batch, ("test-proj", "B-BOUNDARY"))
        for _ in range(3):
            manager._process_batch(db_session, batch)
    db_session.commit()

    a = (
        db_session.query(BatchItem)
        .filter_by(project_id="test-proj", work_item_id="I-BOUND-A")
        .one()
    )
    b = (
        db_session.query(BatchItem)
        .filter_by(project_id="test-proj", work_item_id="I-BOUND-B")
        .one()
    )
    c = (
        db_session.query(BatchItem)
        .filter_by(project_id="test-proj", work_item_id="I-BOUND-C")
        .one()
    )

    failed_event = (
        db_session.query(DaemonEvent)
        .filter(DaemonEvent.event_type == "item_failed", DaemonEvent.entity_id == "I-BOUND-A")
        .order_by(DaemonEvent.id.desc())
        .first()
    )
    worktree_a = (
        Path(manager.project_config.working_dir)
        / manager.project_config.worktree_base
        / "I-BOUND-A"
    )

    assert a.status == BatchItemStatus.setup_failed
    assert not worktree_a.exists()
    assert any(i in attempts for i in ("I-BOUND-B", "I-BOUND-C"))
    assert b.status in {
        BatchItemStatus.executing,
        BatchItemStatus.completed,
        BatchItemStatus.setup_failed,
    }
    assert c.status in {
        BatchItemStatus.executing,
        BatchItemStatus.completed,
        BatchItemStatus.setup_failed,
    }
    assert failed_event is not None
    assert "before_git_worktree_add" in failed_event.message
