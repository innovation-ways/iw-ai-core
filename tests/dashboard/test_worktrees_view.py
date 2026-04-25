"""Tests for F-00062 S09 — Per-worktree container isolation frontend.

Verifies:
1. The worktree table includes container status columns.
2. Orphan containers (no matching BatchItem) appear with the orphan CSS class.
3. Force teardown endpoint invokes worktree_compose.down with correct args.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.worktrees import WorktreeRow
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Session, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture
def project_with_batch(db_session: Session) -> tuple[Project, BatchItem]:
    project = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root="/tmp/test-repo",
        enabled=True,
        config={},
    )
    db_session.add(project)
    db_session.flush()

    work_item = WorkItem(
        project_id=project.id,
        id="WI-001",
        type=WorkItemType.Feature,
        title="Test Work Item",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.work,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)
    db_session.flush()

    batch = Batch(
        id="B-001",
        project_id=project.id,
        status=BatchStatus.executing,
    )
    db_session.add(batch)
    db_session.flush()

    batch_item = BatchItem(
        project_id=project.id,
        batch_id=batch.id,
        work_item_id=work_item.id,
        status=BatchItemStatus.executing,
        worktree_info={"path": "/tmp/test-repo/.worktrees/agent-wi-001", "branch": "agent/WI-001"},
    )
    db_session.add(batch_item)
    db_session.flush()

    return project, batch_item


class TestWorktreeTableIncludesContainerStatusColumns:
    """Verify the worktrees page template includes the new container status columns."""

    def test_worktrees_table_fragment_has_container_column_headers(self, client: TestClient):
        """The worktrees table fragment includes container-status columns when worktrees present."""
        now = datetime.now(UTC)
        worktree_row = WorktreeRow(
            project_id="test-proj",
            item_id="WI-001",
            batch_id="B-001",
            branch="agent/WI-001",
            batch_status="executing",
            path="/tmp/test-repo/.worktrees/agent-wi-001",
            git_label="clean",
            modified=0,
            untracked=0,
            ahead=0,
            is_orphan=False,
            checked_at=now,
            container_status="running",
            classification="active",
            batch_item_pk=1,
        )

        with patch(
            "dashboard.routers.worktrees._collect_worktrees",
            return_value=[worktree_row],
        ):
            response = client.get("/system/worktrees/table")
            assert response.status_code == 200
            html = response.text

            assert "Container" in html, "Table must have a 'Container' column header"
            assert "DB" in html, "Table must have a 'DB :Port' column header"
            assert "App" in html, "Table must have an 'App :Port' column header"
            assert "Class" in html, "Table must have a 'Class' column header"
            assert "Actions" in html, "Table must have an 'Actions' column header"

    def test_worktrees_table_fragment_has_running_badge(self, client: TestClient):
        """The worktrees table fragment renders a 'running' badge for container_status."""
        now = datetime.now(UTC)
        worktree_row = WorktreeRow(
            project_id="test-proj",
            item_id="WI-001",
            batch_id="B-001",
            branch="agent/WI-001",
            batch_status="executing",
            path="/tmp/test-repo/.worktrees/agent-wi-001",
            git_label="clean",
            modified=0,
            untracked=0,
            ahead=0,
            is_orphan=False,
            checked_at=now,
            container_status="running",
            classification="active",
            batch_item_pk=1,
        )

        with patch(
            "dashboard.routers.worktrees._collect_worktrees",
            return_value=[worktree_row],
        ):
            response = client.get("/system/worktrees/table")
            assert response.status_code == 200
            html = response.text

            assert "running" in html, "Table should display running container status"


class TestOrphanContainerAppearsInTable:
    """Orphan containers (labelled but no matching BatchItem) appear with the orphan CSS class."""

    def test_orphan_row_has_orphan_css_class(self, client: TestClient, db_session: Session):
        """A row representing an orphan container carries the 'row-orphan' CSS class."""
        now = datetime.now(UTC)
        orphan_row = WorktreeRow(
            project_id="test-proj",
            item_id="—",
            batch_id="—",
            branch="—",
            batch_status="container-orphan",
            path="—",
            git_label="n/a",
            modified=0,
            untracked=0,
            ahead=-1,
            is_orphan=True,
            checked_at=now,
            container_status="stopped",
            classification="orphan",
            batch_item_pk=None,
        )

        with patch(
            "dashboard.routers.worktrees._collect_worktrees",
            return_value=[orphan_row],
        ):
            response = client.get("/system/worktrees")
            assert response.status_code == 200
            html = response.text

            assert "row-orphan" in html, (
                "Orphan container row must carry the 'row-orphan' CSS class"
            )
            assert "orphan" in html, "Orphan classification must be displayed"


class TestForceTeardownInvokesComposeDown:
    """POST /worktrees/{batch_item_id}/teardown calls worktree_compose.down."""

    def test_teardown_calls_compose_down_with_correct_args(
        self,
        client: TestClient,
        db_session: Session,
        project_with_batch: tuple[Project, BatchItem],
    ):
        """The teardown endpoint calls worktree_compose.down with correct args."""
        project, batch_item = project_with_batch

        with patch("dashboard.routers.worktrees.worktree_compose") as mock_compose:
            mock_compose.down.return_value = True

            response = client.post(f"/system/worktrees/{batch_item.id}/teardown")

            assert response.status_code == 200, (
                f"Teardown endpoint should return 200, got {response.status_code}: {response.text}"
            )
            mock_compose.down.assert_called_once()
            call_args = mock_compose.down.call_args
            assert call_args[0][0] == str(batch_item.id), (
                "First positional arg to down() must be the batch_item_id string"
            )


class TestWorktreeRowDataclass:
    """Verify WorktreeRow dataclass has all required container fields."""

    def test_worktree_row_has_container_fields(self):
        """WorktreeRow includes container_status, db_port, app_port, classification."""
        now = datetime.now(UTC)
        row = WorktreeRow(
            project_id="p",
            item_id="i",
            batch_id="b",
            branch="br",
            batch_status="executing",
            path="/tmp/wt",
            git_label="clean",
            modified=0,
            untracked=0,
            ahead=0,
            is_orphan=False,
            checked_at=now,
            container_status="running",
            db_port=5432,
            app_port=9900,
            classification="active",
            batch_item_pk=123,
        )

        assert row.container_status == "running"
        assert row.db_port == 5432
        assert row.app_port == 9900
        assert row.classification == "active"
        assert row.batch_item_pk == 123

    def test_worktree_row_defaults(self):
        """WorktreeRow defaults container fields to n/a when not provided."""
        now = datetime.now(UTC)
        row = WorktreeRow(
            project_id="p",
            item_id="i",
            batch_id="b",
            branch="br",
            batch_status="main",
            path="/tmp/wt",
            git_label="clean",
            modified=0,
            untracked=0,
            ahead=-1,
            is_orphan=False,
            checked_at=now,
        )

        assert row.container_status == "n/a"
        assert row.db_port is None
        assert row.app_port is None
        assert row.classification == "n/a"
        assert row.batch_item_pk is None


class TestLegacyWorktreeRow:
    """Verify legacy worktree rows (no compose stack) render correctly."""

    def test_legacy_worktree_row_renders_with_na_classification(self, client: TestClient) -> None:
        """A worktree without a compose stack shows 'n/a' classification."""
        now = datetime.now(UTC)
        legacy_row = WorktreeRow(
            project_id="test-proj",
            item_id="WI-001",
            batch_id="B-001",
            branch="agent/WI-001",
            batch_status="executing",
            path="/tmp/test-repo/.worktrees/agent-wi-001",
            git_label="clean",
            modified=0,
            untracked=0,
            ahead=0,
            is_orphan=False,
            checked_at=now,
            container_status="n/a",
            classification="n/a",
            batch_item_pk=1,
        )

        with patch(
            "dashboard.routers.worktrees._collect_worktrees",
            return_value=[legacy_row],
        ):
            response = client.get("/system/worktrees/table")
            assert response.status_code == 200
            html = response.text

            assert "n/a" in html, "Legacy worktree should show 'n/a' for classification"


class TestLogsStreamEndpoint:
    """Verify logs streaming endpoint behavior."""
