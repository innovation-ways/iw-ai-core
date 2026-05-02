"""CR-00028 AC6 end-to-end: abandon-merge triggers cascade to dependents.

AC6:
1. Item in recoverable status (merge_failed) → abandon-merge → becomes failed
2. Run batch_manager.process_batches() → dependents in later groups cascade-fail
3. batch.status → completed_with_errors
4. merge_abandoned daemon_event emitted

Integration test using real PostgreSQL via testcontainers.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_config() -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="opencode",
        worktree_base=".worktrees",
        config={},
    )


@pytest.fixture
def daemon_config(tmp_path: Path) -> Any:
    from orch.config import DaemonConfig

    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    return DaemonConfig(
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
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )


@pytest.fixture
def manager(
    db_session: Session, test_project: Project, project_config: ProjectConfig, daemon_config: Any
) -> BatchManager:
    @contextmanager
    def session_factory() -> Any:
        yield db_session

    return BatchManager(
        project_id="test-proj",
        project_config=project_config,
        session_factory=session_factory,
        config=daemon_config,
    )


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """TestClient backed by the integration test db_session.

    create_app() calls check_db_at_head() at construction time, which hits
    the engine URL from orch.db.session (live DB guard).  We must mock the
    guard so the app can boot using the testcontainer engine.
    """
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        # Mock check_db_at_head so create_app() doesn't call the live DB guard
        guard_ok = MagicMock()
        guard_ok.ok = True
        guard_ok.current_rev = "head"
        guard_ok.head_rev = "head"
        guard_ok.pending = []
        guard_ok.multiple_heads = []

        def override_get_db() -> Session:
            return db_session

        with patch("dashboard.app.check_db_at_head", return_value=guard_ok):
            app = create_app()

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def make_work_item(db: Session, item_id: str) -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Feature,
        title=f"Test {item_id}",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


def make_batch(db: Session, batch_id: str, status: BatchStatus = BatchStatus.executing) -> Batch:
    batch = Batch(
        project_id="test-proj",
        id=batch_id,
        status=status,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()
    return batch


def make_batch_item(
    db: Session,
    batch_id: str,
    work_item_id: str,
    execution_group: int = 0,
    status: BatchItemStatus = BatchItemStatus.pending,
    worktree_info: dict[str, Any] | None = None,
) -> BatchItem:
    item = BatchItem(
        project_id="test-proj",
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=execution_group,
        status=status,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    if worktree_info:
        item.worktree_info = worktree_info
    db.add(item)
    db.flush()
    return item


# ---------------------------------------------------------------------------
# AC6: abandon-merge triggers cascade
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAbandonMergeTriggersCascade:
    """AC6 end-to-end: abandon-merge → cascade-fail for dependents."""

    @pytest.fixture(autouse=True)
    def _alembic_guard(self) -> None:
        """Skip alembic guard checks in these tests."""
        from orch.db.alembic_guard import GuardStatus

        ok = GuardStatus(
            current_rev="abc",
            head_rev="abc",
            pending=[],
            multiple_heads=[],
            ok=True,
        )
        with patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok):
            yield

    @pytest.mark.parametrize(
        "recoverable_status",
        [
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        ],
    )
    def test_abandon_merge_flips_to_failed_then_cascade_fires(
        self,
        db_session: Session,
        manager: BatchManager,
        client: TestClient,
        recoverable_status: BatchItemStatus,
        test_project: Project,
    ) -> None:
        """AC6: abandon-merge → item becomes failed → dependents cascade-fail."""
        # Setup: 2-item batch
        make_work_item(db_session, "F-00001")
        make_work_item(db_session, "F-00002")
        batch = make_batch(db_session, "B001", status=BatchStatus.executing)

        make_batch_item(
            db_session,
            "B001",
            "F-00001",
            execution_group=0,
            status=recoverable_status,
            worktree_info={"path": "/wt/F-00001"},
        )
        make_batch_item(
            db_session,
            "B001",
            "F-00002",
            execution_group=1,
            status=BatchItemStatus.pending,
        )
        db_session.flush()

        # Step 1: abandon-merge via HTTP endpoint
        response = client.post(
            "/project/test-proj/api/item/F-00001/abandon-merge",
            json={},
        )

        # The endpoint must succeed (item is in recoverable status)
        # _action_response() returns empty Response (204 No Content)
        body = response.text
        assert response.status_code in (200, 204), (
            f"Expected 200 or 204, got {response.status_code}: {body[:200]}"
        )

        # Verify I1 is now failed
        db_session.expire_all()
        i1_db: BatchItem | None = db_session.scalar(
            select(BatchItem).where(
                BatchItem.project_id == "test-proj",
                BatchItem.work_item_id == "F-00001",
            )
        )
        assert i1_db is not None
        assert i1_db.status == BatchItemStatus.failed, (
            f"Expected failed after abandon, got {i1_db.status.value}"
        )
        assert "[operator abandoned via abandon-merge]" in (i1_db.notes or "")

        # Step 2: run batch_manager — cascade must fire
        db_session.expire_all()
        manager.process_batches()

        # Refresh items — only i2_after is needed for assertions
        _i1_after: BatchItem | None = db_session.scalar(
            select(BatchItem).where(
                BatchItem.project_id == "test-proj",
                BatchItem.work_item_id == "F-00001",
            )
        )
        i2_after: BatchItem | None = db_session.scalar(
            select(BatchItem).where(
                BatchItem.project_id == "test-proj",
                BatchItem.work_item_id == "F-00002",
            )
        )
        db_session.refresh(batch)

        assert i2_after is not None
        assert i2_after.status == BatchItemStatus.failed, (
            f"Expected cascade-fail for dependent, got {i2_after.status.value}"
        )
        assert "Skipped" in (i2_after.notes or ""), "Cascade note should mention dependency"

        # AC6: batch transitions to completed_with_errors
        # Note: batch stays 'executing' until _check_batch_completion is called
        # (batch_manager._process_batch returns early after cascade without calling it).
        # We call process_batches again to ensure completion check runs.
        db_session.expire_all()
        manager.process_batches()
        db_session.refresh(batch)
        assert batch.status == BatchStatus.completed_with_errors, (
            f"Expected batch completed_with_errors, got {batch.status.value}"
        )

    def test_abandon_merge_emits_merge_abandoned_daemon_event(
        self,
        db_session: Session,
        client: TestClient,
        test_project: Project,
    ) -> None:
        """AC6: abandon-merge emits merge_abandoned daemon_event."""
        make_work_item(db_session, "F-00001")
        make_batch(db_session, "B001", status=BatchStatus.executing)

        make_batch_item(
            db_session,
            "B001",
            "F-00001",
            execution_group=0,
            status=BatchItemStatus.merge_failed,
            worktree_info={"path": "/wt/F-00001"},
        )
        db_session.flush()

        response = client.post(
            "/project/test-proj/api/item/F-00001/abandon-merge",
            json={},
        )

        assert response.status_code in (200, 204), (
            f"Expected 200 or 204, got {response.status_code}: {response.text}"
        )

        # Check event was emitted
        events = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.project_id == "test-proj",
                DaemonEvent.event_type == "merge_abandoned",
            )
            .all()
        )
        assert len(events) >= 1, "merge_abandoned event must be emitted"
        assert events[0].entity_id == "F-00001"
        assert events[0].entity_type == "work_item"
