"""Integration tests for orch.mcp.tools.read_tools — all 8 read tool functions.

Tests call the plain module-level functions (sync) directly after seeding rows
via db_session and test_project fixtures. Covers empty results, filtered results,
ServiceError-to-ToolError propagation, and cross-project isolation.
"""

from __future__ import annotations

from typing import Any

import pytest

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_work_item(
    session: Any,
    project_id: str,
    item_id: str,
    *,
    status: WorkItemStatus = WorkItemStatus.draft,
) -> WorkItem:
    """Insert a minimal WorkItem row for testing.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        item_id: Work-item identifier.
        status: Initial status; defaults to ``draft``.

    Returns:
        The flushed ``WorkItem`` ORM instance.
    """
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title=f"Test item {item_id}",
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    session.add(item)
    session.flush()
    return item


def _make_batch(
    session: Any,
    project_id: str,
    batch_id: str,
    item_id: str,
    *,
    status: BatchStatus = BatchStatus.planning,
) -> Batch:
    """Insert a minimal Batch + one BatchItem row for testing.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        batch_id: Batch identifier.
        item_id: Work-item identifier to include in the batch.
        status: Batch status; defaults to ``planning``.

    Returns:
        The flushed ``Batch`` ORM instance.
    """
    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=status,
        max_parallel=4,
        auto_publish=False,
        auto_merge=True,
    )
    session.add(batch)
    session.flush()
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=item_id,
        execution_group=1,
        status=BatchItemStatus.pending,
    )
    session.add(bi)
    session.flush()
    return batch


# ---------------------------------------------------------------------------
# project_list
# ---------------------------------------------------------------------------


class TestProjectList:
    """Covers project_list tool — listing registered projects."""

    def test_project_list_returns_projects_key(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies project_list returns a projects list containing the seeded project."""
        from orch.mcp.tools.read_tools import project_list

        result = project_list()
        assert len(result["projects"]) >= 1
        ids = [p["id"] for p in result["projects"]]
        assert any(pid == test_project.id for pid in ids)

    def test_project_list_includes_test_project(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that project_list includes the seeded test project by id."""
        from orch.mcp.tools.read_tools import project_list

        result = project_list()
        ids = [p["id"] for p in result["projects"]]
        assert any(pid == test_project.id for pid in ids), (
            f"test_project.id={test_project.id!r} not found in project_list ids={ids!r}"
        )

    def test_project_list_includes_required_fields(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies each project dict has id, display_name, enabled, repo_root."""
        from orch.mcp.tools.read_tools import project_list

        result = project_list()
        projects = result["projects"]
        assert len(projects) >= 1
        proj = next(p for p in projects if p["id"] == test_project.id)
        assert proj["id"] == test_project.id
        assert proj["display_name"] == test_project.display_name
        assert proj["enabled"] == test_project.enabled
        assert proj["repo_root"] == test_project.repo_root


# ---------------------------------------------------------------------------
# work_item_list
# ---------------------------------------------------------------------------


class TestWorkItemList:
    """Covers work_item_list tool — paginated work-item listing."""

    def test_work_item_list_empty_project(self, db_session: Any, test_project: Project) -> None:
        """Verifies that an empty project returns items=[] and total=0."""
        from orch.mcp.tools.read_tools import work_item_list

        result = work_item_list(test_project.id)
        assert result["total"] == 0
        assert result["items"] == []

    def test_work_item_list_returns_seeded_item(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that a seeded item appears in work_item_list results."""
        _make_work_item(db_session, test_project.id, "F-00001")
        from orch.mcp.tools.read_tools import work_item_list

        result = work_item_list(test_project.id)
        assert result["total"] == 1
        assert result["items"][0]["id"] == "F-00001"

    def test_work_item_list_filters_by_status(self, db_session: Any, test_project: Project) -> None:
        """Verifies that the status filter returns only matching items."""
        _make_work_item(db_session, test_project.id, "F-00001", status=WorkItemStatus.draft)
        _make_work_item(db_session, test_project.id, "F-00002", status=WorkItemStatus.approved)
        from orch.mcp.tools.read_tools import work_item_list

        result = work_item_list(test_project.id, status="approved")
        assert result["total"] == 1
        assert result["items"][0]["id"] == "F-00002"

    def test_work_item_list_invalid_project_raises_tool_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that a nonexistent project_id raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.read_tools import work_item_list

        with pytest.raises(ToolError):
            work_item_list("nonexistent-proj")

    def test_work_item_list_cross_project_isolation(
        self, db_session: Any, test_project: Project, second_project: Any
    ) -> None:
        """Verifies that project B's items don't appear when querying project A."""
        from orch.mcp.tools.read_tools import work_item_list

        result_a = work_item_list(test_project.id)
        b_id = second_project.proj_b.id
        b_item_id = second_project.proj_b_ids.work_item_id
        for item in result_a["items"]:
            assert item["id"] != b_item_id, f"Project B's item {b_item_id} leaked into project A"
        # Project B sees its own item
        result_b = work_item_list(b_id)
        b_ids = [it["id"] for it in result_b["items"]]
        assert any(bid == b_item_id for bid in b_ids), (
            f"Project B item {b_item_id!r} not found in work_item_list for project {b_id!r}"
        )


# ---------------------------------------------------------------------------
# work_item_get
# ---------------------------------------------------------------------------


class TestWorkItemGet:
    """Covers work_item_get tool — single item status lookup."""

    def test_work_item_get_returns_expected_shape(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that work_item_get returns the standard item-status shape."""
        _make_work_item(db_session, test_project.id, "F-00001")
        from orch.mcp.tools.read_tools import work_item_get

        result = work_item_get(test_project.id, "F-00001")
        assert result["id"] == "F-00001"
        assert result["project_id"] == test_project.id
        assert result["status"] == "draft"
        assert "steps" in result
        assert "total_steps" in result

    def test_work_item_get_missing_item_raises_tool_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that a missing item raises ToolError, not ServiceError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.read_tools import work_item_get

        with pytest.raises(ToolError):
            work_item_get(test_project.id, "I-99999")

    def test_work_item_get_invalid_project_raises_tool_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that a nonexistent project_id raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.read_tools import work_item_get

        with pytest.raises(ToolError):
            work_item_get("no-such-project", "F-00001")


# ---------------------------------------------------------------------------
# batch_list
# ---------------------------------------------------------------------------


class TestBatchList:
    """Covers batch_list tool — listing batches for a project."""

    def test_batch_list_empty_project(self, db_session: Any, test_project: Project) -> None:
        """Verifies that an empty project returns batches=[]."""
        from orch.mcp.tools.read_tools import batch_list

        result = batch_list(test_project.id)
        assert result["batches"] == []

    def test_batch_list_returns_seeded_batch(self, db_session: Any, test_project: Project) -> None:
        """Verifies that a seeded batch appears in batch_list results."""
        _make_work_item(db_session, test_project.id, "F-00001")
        _make_batch(db_session, test_project.id, "BATCH-00001", "F-00001")
        from orch.mcp.tools.read_tools import batch_list

        result = batch_list(test_project.id)
        assert len(result["batches"]) == 1
        assert result["batches"][0]["batch_id"] == "BATCH-00001"

    def test_batch_list_invalid_project_raises_tool_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that a nonexistent project_id raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.read_tools import batch_list

        with pytest.raises(ToolError):
            batch_list("no-such-proj")


# ---------------------------------------------------------------------------
# batch_status
# ---------------------------------------------------------------------------


class TestBatchStatus:
    """Covers batch_status tool — detailed batch status lookup."""

    def test_batch_status_returns_expected_shape(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that batch_status returns the standard batch-status shape."""
        _make_work_item(db_session, test_project.id, "F-00001")
        _make_batch(db_session, test_project.id, "BATCH-00001", "F-00001")
        from orch.mcp.tools.read_tools import batch_status

        result = batch_status(test_project.id, "BATCH-00001")
        assert result["batch_id"] == "BATCH-00001"
        assert result["project_id"] == test_project.id
        assert result["status"] == "planning"
        assert "items" in result

    def test_batch_status_missing_batch_raises_tool_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that a missing batch raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.read_tools import batch_status

        with pytest.raises(ToolError):
            batch_status(test_project.id, "BATCH-99999")

    def test_batch_status_invalid_project_raises_tool_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that a nonexistent project_id raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.read_tools import batch_status

        with pytest.raises(ToolError):
            batch_status("no-such-proj", "BATCH-00001")


# ---------------------------------------------------------------------------
# job_list
# ---------------------------------------------------------------------------


class TestJobList:
    """Covers job_list tool — unified background-job listing."""

    def test_job_list_returns_expected_shape(self, db_session: Any, test_project: Project) -> None:
        """Verifies that job_list returns jobs, total, page, page_size keys."""
        from orch.mcp.tools.read_tools import job_list

        result = job_list(test_project.id)
        assert result["total"] == 0
        assert result["jobs"] == []
        assert result["page"] == 1
        assert result["page_size"] == 25

    def test_job_list_invalid_project_raises_tool_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that a nonexistent project_id raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.read_tools import job_list

        with pytest.raises(ToolError):
            job_list("no-such-proj")


# ---------------------------------------------------------------------------
# worktree_status
# ---------------------------------------------------------------------------


class TestWorktreeStatus:
    """Covers worktree_status tool — active worktree listing."""

    def test_worktree_status_empty_project(self, db_session: Any, test_project: Project) -> None:
        """Verifies that an empty project returns worktrees=[]."""
        from orch.mcp.tools.read_tools import worktree_status

        result = worktree_status(test_project.id)
        assert result["worktrees"] == []

    def test_worktree_status_invalid_project_raises_tool_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that a nonexistent project_id raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.read_tools import worktree_status

        with pytest.raises(ToolError):
            worktree_status("no-such-proj")


# ---------------------------------------------------------------------------
# daemon_status
# ---------------------------------------------------------------------------


class TestDaemonStatus:
    """Covers daemon_status tool — daemon liveness + DB stats."""

    def test_daemon_status_returns_expected_shape(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that daemon_status returns status, pid, and DB stat keys."""
        from orch.mcp.tools.read_tools import daemon_status

        result = daemon_status()
        # Must contain the basic shape even with no daemon running
        assert result["status"].find("running") != -1 or result["status"].find("stopped") != -1
        assert "pid" in result
        assert "poll_count" in result
        assert "running_steps" in result
        assert "active_batches" in result
        assert "projects" in result

    def test_daemon_status_stopped_when_no_pid_file(
        self, db_session: Any, test_project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that daemon_status reports 'stopped' when the PID file is absent."""
        import tempfile
        from pathlib import Path

        # Point PID file to a nonexistent path so liveness check returns False
        monkeypatch.setenv("IW_CORE_PID_FILE", str(Path(tempfile.mkdtemp()) / "no.pid"))
        from orch.mcp.tools.read_tools import daemon_status

        result = daemon_status()
        assert result["status"] == "stopped"
        assert result["pid"] is None
        assert result["liveness_source"] is None

    def test_daemon_status_running_via_heartbeat_without_pid(
        self, db_session: Any, test_project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fresh DB poll heartbeat reports 'running' even with no resolvable PID file."""
        import tempfile
        from datetime import UTC, datetime
        from pathlib import Path

        from orch.db.models import DaemonEvent

        # No local PID (simulates the MCP server in a different namespace/host).
        monkeypatch.setenv("IW_CORE_PID_FILE", str(Path(tempfile.mkdtemp()) / "no.pid"))
        db_session.add(DaemonEvent(event_type="daemon_poll", created_at=datetime.now(UTC)))
        db_session.flush()

        from orch.mcp.tools.read_tools import daemon_status

        result = daemon_status()
        assert result["status"] == "running"
        assert result["liveness_source"] == "heartbeat"
        assert result["pid"] is None
        assert result["last_poll_age_seconds"] is not None
        assert result["last_poll_age_seconds"] < 180

    def test_daemon_status_stopped_when_heartbeat_stale(
        self, db_session: Any, test_project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stale poll heartbeat (older than the window) with no PID reports 'stopped'."""
        import tempfile
        from datetime import UTC, datetime, timedelta
        from pathlib import Path

        from orch.db.models import DaemonEvent

        monkeypatch.setenv("IW_CORE_PID_FILE", str(Path(tempfile.mkdtemp()) / "no.pid"))
        db_session.add(
            DaemonEvent(
                event_type="daemon_poll",
                created_at=datetime.now(UTC) - timedelta(seconds=100_000),
            )
        )
        db_session.flush()

        from orch.mcp.tools.read_tools import daemon_status

        result = daemon_status()
        assert result["status"] == "stopped"
        assert result["liveness_source"] is None
        assert result["last_poll_age_seconds"] >= 100_000
