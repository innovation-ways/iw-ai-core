"""Integration tests for orch.mcp.tools.write_tools — full lifecycle and audit logging.

Tier-1 tools (work_item_next_id, work_item_register) are plain sync functions and
are called directly.  Tier-2 tools (work_item_approve, batch_create, batch_approve,
batch_control, item_retry) are now async and policy-gated (default: ask).  Tests
that need execution behaviour set an explicit 'allow' policy via _set_allow_policy()
and call via asyncio.run().
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from orch.db.models import (
    McpAuditLog,
    McpPolicy,
    McpPolicyDecision,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

# ---------------------------------------------------------------------------
# Helper fixtures / utilities
# ---------------------------------------------------------------------------


def _count_audit_rows(session: Any, tool_name: str) -> int:
    """Return the number of McpAuditLog rows for a given tool name.

    Args:
        session: Active SQLAlchemy session.
        tool_name: MCP tool name to filter on.

    Returns:
        Count of matching audit rows.
    """
    from sqlalchemy import func, select

    return session.execute(
        select(func.count()).select_from(McpAuditLog).where(McpAuditLog.tool_name == tool_name)
    ).scalar_one()


def _get_last_audit_row(session: Any, tool_name: str) -> McpAuditLog | None:
    """Fetch the most-recent McpAuditLog row for tool_name, or None.

    Args:
        session: Active SQLAlchemy session.
        tool_name: MCP tool name to query.

    Returns:
        Most recent McpAuditLog row or None if none exist.
    """
    from sqlalchemy import select

    return session.execute(
        select(McpAuditLog)
        .where(McpAuditLog.tool_name == tool_name)
        .order_by(McpAuditLog.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _set_allow_policy(session: Any, project_id: str, tool_name: str) -> None:
    """Insert a McpPolicy row that forces 'allow' for (project_id, tool_name).

    Used by Tier-2 tests that need to verify execution behaviour rather than
    the approval-gating envelope.  The per-test transaction rollback means
    this row is automatically discarded after each test.

    Args:
        session: Active SQLAlchemy session (the test's db_session).
        project_id: Project to apply the override to.
        tool_name: Tool name to override to 'allow'.
    """
    row = McpPolicy(
        project_id=project_id,
        tool_name=tool_name,
        decision=McpPolicyDecision.allow,
        updated_by="test-allow-override",
    )
    session.add(row)
    session.flush()


class TestWorkItemNextId:
    """Covers work_item_next_id tool function."""

    def test_allocates_sequential_id_for_feature(self, db_session: Any, test_project: Project):
        """Verifies that work_item_next_id returns a properly formatted F- ID."""
        from orch.mcp.tools.write_tools import work_item_next_id

        result = work_item_next_id(test_project.id, "feature")
        assert result["item_type"] == "feature"
        assert result["item_id"].find("F-") != -1

    def test_audit_row_written_on_success(self, db_session: Any, test_project: Project):
        """Verifies that a McpAuditLog row with outcome='success' is written after the call."""
        from orch.mcp.tools.write_tools import work_item_next_id

        before = _count_audit_rows(db_session, "work_item_next_id")
        work_item_next_id(test_project.id, "feature")
        after = _count_audit_rows(db_session, "work_item_next_id")
        assert after == before + 1

    def test_unknown_type_raises_tool_error(self, db_session: Any, test_project: Project):
        """Verifies that an unknown item_type raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.write_tools import work_item_next_id

        with pytest.raises(ToolError, match="Unknown item type"):
            work_item_next_id(test_project.id, "bogus_type")

    def test_unknown_type_writes_error_audit_row(self, db_session: Any, test_project: Project):
        """Verifies that a failed call writes an audit row with outcome='error'."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.tools.write_tools import work_item_next_id

        before = _count_audit_rows(db_session, "work_item_next_id")
        with pytest.raises(ToolError):
            work_item_next_id(test_project.id, "bogus_type")
        after = _count_audit_rows(db_session, "work_item_next_id")
        assert after == before + 1
        row = _get_last_audit_row(db_session, "work_item_next_id")
        assert row is not None
        assert row.outcome == "error"


class TestWorkItemRegisterInline:
    """Covers work_item_register with inline content (no disk I/O)."""

    def test_register_with_inline_content_creates_work_item(
        self, db_session: Any, test_project: Project
    ):
        """Verifies that registering with inline content inserts a WorkItem row."""
        from orch.mcp.tools.write_tools import work_item_register

        result = work_item_register(
            test_project.id,
            "F-00001",
            "My Feature",
            "feature",
            design_doc_content="## Summary\n\nSome content.\n",
            manifest_steps=[{"step": "S01", "agent": "backend-impl"}],
        )
        assert result["created"] is True
        assert result["id"] == "F-00001"
        # Verify the row exists in the DB
        from sqlalchemy import select

        row = db_session.execute(
            select(WorkItem).where(WorkItem.project_id == test_project.id, WorkItem.id == "F-00001")
        ).scalar_one_or_none()
        assert row is not None
        assert row.title == "My Feature"
        assert row.status == WorkItemStatus.draft

    def test_register_audit_row_written(self, db_session: Any, test_project: Project):
        """Verifies that work_item_register writes an audit row with outcome='success'."""
        from orch.mcp.tools.write_tools import work_item_register

        before = _count_audit_rows(db_session, "work_item_register")
        work_item_register(
            test_project.id,
            "F-00002",
            "Another Feature",
            "feature",
        )
        after = _count_audit_rows(db_session, "work_item_register")
        assert after == before + 1
        row = _get_last_audit_row(db_session, "work_item_register")
        assert row is not None
        assert row.outcome == "success"

    def test_register_dry_run_does_not_create_work_item(
        self, db_session: Any, test_project: Project
    ):
        """Verifies that dry_run=True returns a preview dict without inserting any row."""
        from sqlalchemy import select

        from orch.mcp.tools.write_tools import work_item_register

        result = work_item_register(
            test_project.id,
            "F-00099",
            "Dry Run Feature",
            "feature",
            manifest_steps=[{"step": "S01", "agent": "backend-impl"}],
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert result["would_register"]["item_id"] == "F-00099"
        # No DB row should exist
        row = db_session.execute(
            select(WorkItem).where(WorkItem.project_id == test_project.id, WorkItem.id == "F-00099")
        ).scalar_one_or_none()
        assert row is None

    def test_register_is_idempotent_on_duplicate(self, db_session: Any, test_project: Project):
        """Verifies that registering the same item_id twice returns created=False on second call."""
        from orch.mcp.tools.write_tools import work_item_register

        work_item_register(test_project.id, "F-00003", "First", "feature")
        result2 = work_item_register(test_project.id, "F-00003", "Second", "feature")
        assert result2["created"] is False
        assert result2["id"] == "F-00003"


class TestWorkItemRegisterFromDisk:
    """Covers work_item_register with file-based design doc and manifest."""

    def test_register_with_design_doc_file(
        self, db_session: Any, test_project: Project, tmp_path: Path
    ):
        """Verifies that registering with a design doc file path reads and stores the content."""
        doc_file = tmp_path / "F-00010_Design.md"
        doc_file.write_text("## Summary\n\nFeature from disk.\n## Impacted Paths\n\n- orch/\n")
        manifest_file = tmp_path / "workflow-manifest.json"
        manifest_file.write_text(json.dumps({"steps": [{"step": "S01", "agent": "backend-impl"}]}))

        from orch.mcp.tools.write_tools import work_item_register

        result = work_item_register(
            test_project.id,
            "F-00010",
            "Disk Feature",
            "feature",
            design_doc_path=str(doc_file),
            manifest_path=str(manifest_file),
        )
        assert result["created"] is True
        assert result["id"] == "F-00010"


class TestWorkItemApprove:
    """Covers work_item_approve tool function (async, Tier-2 gated)."""

    def _make_draft_item(self, session: Any, project_id: str, item_id: str) -> WorkItem:
        """Insert a draft WorkItem row.

        Args:
            session: Active SQLAlchemy session.
            project_id: Project scope.
            item_id: Work-item identifier.

        Returns:
            The flushed WorkItem instance.
        """
        item = WorkItem(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Draft item {item_id}",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.add(item)
        session.flush()
        return item

    def test_approve_transitions_item_to_approved(self, db_session: Any, test_project: Project):
        """Verifies that work_item_approve changes the item status to approved."""
        self._make_draft_item(db_session, test_project.id, "F-00020")
        _set_allow_policy(db_session, test_project.id, "work_item_approve")
        from orch.mcp.tools.write_tools import work_item_approve

        result = asyncio.run(work_item_approve(test_project.id, "F-00020"))
        assert result["status"] == "approved"
        assert result["id"] == "F-00020"

    def test_approve_audit_row_written(self, db_session: Any, test_project: Project):
        """Verifies that work_item_approve writes an audit row with outcome='success'."""
        self._make_draft_item(db_session, test_project.id, "F-00021")
        _set_allow_policy(db_session, test_project.id, "work_item_approve")
        from orch.mcp.tools.write_tools import work_item_approve

        before = _count_audit_rows(db_session, "work_item_approve")
        asyncio.run(work_item_approve(test_project.id, "F-00021"))
        after = _count_audit_rows(db_session, "work_item_approve")
        assert after == before + 1

    def test_approve_nonexistent_raises_tool_error(self, db_session: Any, test_project: Project):
        """Verifies that approving a non-existent item raises ToolError."""
        from fastmcp.exceptions import ToolError

        _set_allow_policy(db_session, test_project.id, "work_item_approve")
        from orch.mcp.tools.write_tools import work_item_approve

        with pytest.raises(ToolError, match="not found"):
            asyncio.run(work_item_approve(test_project.id, "F-99999"))

    def test_approve_nonexistent_writes_error_audit_row(
        self, db_session: Any, test_project: Project
    ):
        """Verifies that a failed approve call writes an audit row with outcome='error'."""
        from fastmcp.exceptions import ToolError

        _set_allow_policy(db_session, test_project.id, "work_item_approve")
        from orch.mcp.tools.write_tools import work_item_approve

        before = _count_audit_rows(db_session, "work_item_approve")
        with pytest.raises(ToolError):
            asyncio.run(work_item_approve(test_project.id, "F-99999"))
        after = _count_audit_rows(db_session, "work_item_approve")
        assert after == before + 1
        row = _get_last_audit_row(db_session, "work_item_approve")
        assert row is not None
        assert row.outcome == "error"
        # decision is 'allow' because we inserted an allow policy row
        assert row.decision == "allow"


class TestBatchCreateAndApprove:
    """Covers the batch_create and batch_approve tool functions (async, Tier-2 gated)."""

    def _make_approved_item(self, session: Any, project_id: str, item_id: str) -> WorkItem:
        """Insert an approved WorkItem row.

        Args:
            session: Active SQLAlchemy session.
            project_id: Project scope.
            item_id: Work-item identifier.

        Returns:
            The flushed WorkItem instance in approved status.
        """
        item = WorkItem(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Approved item {item_id}",
            status=WorkItemStatus.approved,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.add(item)
        session.flush()
        return item

    def test_batch_create_returns_batch_id(self, db_session: Any, test_project: Project):
        """Verifies that batch_create returns a dict with a batch_id key."""
        self._make_approved_item(db_session, test_project.id, "F-00030")
        _set_allow_policy(db_session, test_project.id, "batch_create")
        from orch.mcp.tools.write_tools import batch_create

        result = asyncio.run(batch_create(test_project.id, ["F-00030"]))
        assert "batch_id" in result
        assert result["batch_id"].find("BATCH-") != -1
        assert result["status"] == "planning"
        assert result["item_count"] == 1

    def test_batch_create_audit_row_written(self, db_session: Any, test_project: Project):
        """Verifies that batch_create writes an audit row with outcome='success'."""
        self._make_approved_item(db_session, test_project.id, "F-00031")
        _set_allow_policy(db_session, test_project.id, "batch_create")
        from orch.mcp.tools.write_tools import batch_create

        before = _count_audit_rows(db_session, "batch_create")
        asyncio.run(batch_create(test_project.id, ["F-00031"]))
        after = _count_audit_rows(db_session, "batch_create")
        assert after == before + 1

    def test_batch_create_dry_run_returns_preview_without_persisting(
        self, db_session: Any, test_project: Project
    ):
        """Verifies that dry_run=True returns a preview dict and writes no Batch row."""
        from sqlalchemy import func, select

        from orch.db.models import Batch
        from orch.mcp.tools.write_tools import batch_create

        self._make_approved_item(db_session, test_project.id, "F-00032")
        # dry_run bypasses gating — no allow policy needed
        before_count = db_session.execute(
            select(func.count()).select_from(Batch).where(Batch.project_id == test_project.id)
        ).scalar_one()

        result = asyncio.run(batch_create(test_project.id, ["F-00032"], dry_run=True))
        assert result["dry_run"] is True
        assert result["item_ids"] == ["F-00032"]

        after_count = db_session.execute(
            select(func.count()).select_from(Batch).where(Batch.project_id == test_project.id)
        ).scalar_one()
        assert after_count == before_count

    def test_batch_approve_transitions_batch(self, db_session: Any, test_project: Project):
        """Verifies that batch_approve changes batch status to approved."""
        self._make_approved_item(db_session, test_project.id, "F-00033")
        _set_allow_policy(db_session, test_project.id, "batch_create")
        _set_allow_policy(db_session, test_project.id, "batch_approve")
        from orch.mcp.tools.write_tools import batch_approve, batch_create

        create_result = asyncio.run(batch_create(test_project.id, ["F-00033"]))
        batch_id = create_result["batch_id"]

        approve_result = asyncio.run(batch_approve(test_project.id, batch_id))
        assert approve_result["status"] == "approved"
        assert approve_result["batch_id"] == batch_id

    def test_batch_approve_audit_row_written(self, db_session: Any, test_project: Project):
        """Verifies that batch_approve writes an audit row with outcome='success'."""
        self._make_approved_item(db_session, test_project.id, "F-00034")
        _set_allow_policy(db_session, test_project.id, "batch_create")
        _set_allow_policy(db_session, test_project.id, "batch_approve")
        from orch.mcp.tools.write_tools import batch_approve, batch_create

        create_result = asyncio.run(batch_create(test_project.id, ["F-00034"]))
        batch_id = create_result["batch_id"]

        before = _count_audit_rows(db_session, "batch_approve")
        asyncio.run(batch_approve(test_project.id, batch_id))
        after = _count_audit_rows(db_session, "batch_approve")
        assert after == before + 1

    def test_full_lifecycle_via_plain_functions(self, db_session: Any, test_project: Project):
        """Verifies the next_id → register → approve → batch_create → batch_approve lifecycle."""
        # Set allow policies for all Tier-2 tools used in this test
        for tool_name in ["work_item_approve", "batch_create", "batch_approve"]:
            _set_allow_policy(db_session, test_project.id, tool_name)

        from orch.mcp.tools.write_tools import (
            batch_approve,
            batch_create,
            work_item_approve,
            work_item_next_id,
            work_item_register,
        )

        # Allocate ID (Tier-1, sync)
        next_id_result = work_item_next_id(test_project.id, "feature")
        item_id = next_id_result["item_id"]
        assert item_id.find("F-") != -1

        # Register item (Tier-1 sync tool)
        reg_result = work_item_register(
            test_project.id,
            item_id,
            "Lifecycle Feature",
            "feature",
        )
        assert reg_result["created"] is True

        # Approve item (Tier-2, async)
        approve_result = asyncio.run(work_item_approve(test_project.id, item_id))
        assert approve_result["status"] == "approved"

        # Create batch (Tier-2, async)
        batch_result = asyncio.run(batch_create(test_project.id, [item_id]))
        batch_id = batch_result["batch_id"]
        assert batch_result["item_count"] == 1

        # Approve batch (Tier-2, async)
        b_approve = asyncio.run(batch_approve(test_project.id, batch_id))
        assert b_approve["status"] == "approved"

        # Check total audit rows were written for each tool call
        for tool_name in [
            "work_item_next_id",
            "work_item_register",
            "work_item_approve",
            "batch_create",
            "batch_approve",
        ]:
            count = _count_audit_rows(db_session, tool_name)
            assert count >= 1, f"No audit row for tool '{tool_name}'"


class TestBatchControl:
    """Covers the batch_control tool function (async, Tier-2 gated)."""

    def _make_executing_batch(self, session: Any, project_id: str) -> str:
        """Create an executing batch (planning → approved → executing manually).

        Args:
            session: Active SQLAlchemy session.
            project_id: Project scope.

        Returns:
            The batch ID string.
        """
        from orch.cli.id_commands import allocate_next_id
        from orch.db.models import (
            Batch,
            BatchItem,
            BatchItemStatus,
            BatchStatus,
            WorkItem,
            WorkItemPhase,
            WorkItemStatus,
            WorkItemType,
        )

        item = WorkItem(
            project_id=project_id,
            id="F-00041",
            type=WorkItemType.Feature,
            title="Executing batch item",
            status=WorkItemStatus.approved,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.add(item)
        session.flush()

        _, batch_id = allocate_next_id(session, project_id, "BATCH")
        batch = Batch(
            project_id=project_id,
            id=batch_id,
            status=BatchStatus.executing,
            max_parallel=4,
            auto_publish=False,
            auto_merge=True,
        )
        session.add(batch)
        session.flush()

        session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id="F-00041",
                execution_group=1,
                status=BatchItemStatus.pending,
            )
        )
        session.flush()
        return batch_id

    def test_batch_control_pause_transitions_to_paused(
        self, db_session: Any, test_project: Project
    ):
        """Verifies that batch_control('pause') transitions an executing batch to paused."""
        batch_id = self._make_executing_batch(db_session, test_project.id)
        _set_allow_policy(db_session, test_project.id, "batch_control")
        from orch.mcp.tools.write_tools import batch_control

        result = asyncio.run(batch_control(test_project.id, batch_id, "pause"))
        assert result["status"] == "paused"
        assert result["batch_id"] == batch_id

    def test_batch_control_invalid_action_raises_tool_error(
        self, db_session: Any, test_project: Project
    ):
        """Verifies that an invalid action raises ToolError."""
        from fastmcp.exceptions import ToolError

        batch_id = self._make_executing_batch(db_session, test_project.id)
        # Invalid action check happens before policy gate — no allow policy needed
        from orch.mcp.tools.write_tools import batch_control

        with pytest.raises(ToolError, match="Invalid action"):
            asyncio.run(batch_control(test_project.id, batch_id, "explode"))


class TestItemRetry:
    """Covers item_retry tool function (async, Tier-2 gated)."""

    def test_item_retry_raises_tool_error_for_nonexistent_item(
        self, db_session: Any, test_project: Project
    ):
        """Verifies that item_retry on a non-existent item raises ToolError."""
        from fastmcp.exceptions import ToolError

        _set_allow_policy(db_session, test_project.id, "item_retry")
        from orch.mcp.tools.write_tools import item_retry

        with pytest.raises(ToolError, match="not found"):
            asyncio.run(item_retry(test_project.id, "F-99999"))

    def test_item_retry_writes_error_audit_row_on_failure(
        self, db_session: Any, test_project: Project
    ):
        """Verifies that a failed item_retry writes an audit row with outcome='error'."""
        from fastmcp.exceptions import ToolError

        _set_allow_policy(db_session, test_project.id, "item_retry")
        from orch.mcp.tools.write_tools import item_retry

        before = _count_audit_rows(db_session, "item_retry")
        with pytest.raises(ToolError):
            asyncio.run(item_retry(test_project.id, "F-99999"))
        after = _count_audit_rows(db_session, "item_retry")
        assert after == before + 1
        row = _get_last_audit_row(db_session, "item_retry")
        assert row is not None
        assert row.outcome == "error"


class TestSecretScrubbing:
    """Covers that sensitive arguments are scrubbed from audit log entries."""

    def test_password_in_args_is_redacted_in_audit_log(
        self, db_session: Any, test_project: Project
    ):
        """Verifies that a 'password' key in arguments is stored as *** in the audit log."""
        # We call work_item_next_id and inspect the audit row's arguments JSON.
        # Since no write tool currently takes a 'password', we test the audit module directly.
        from orch.mcp.audit import record_audit

        record_audit(
            tool_name="test_tool_scrub",
            project_id=test_project.id,
            arguments={"project_id": test_project.id, "password": "top-secret"},
            outcome="success",
        )

        row = _get_last_audit_row(db_session, "test_tool_scrub")
        assert row is not None
        # The password must NOT appear in the stored JSON
        stored = json.dumps(row.arguments)
        assert stored.find("top-secret") == -1
        assert stored.find("***") != -1
