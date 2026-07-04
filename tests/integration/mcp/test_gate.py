"""Integration tests for the MCP enforcement gate (orch/mcp/gate.py).

Covers: allow branch (executes + audits success), deny branch (ToolError + audits denied),
ask→approval-required (no token, ctx=None → approval_required envelope + row created),
ask+valid token (executes + consumed), and the no-elicitation fallback path.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest


def _make_execute(return_value: dict) -> object:
    """Return a lambda that opens the session and returns return_value.

    Args:
        return_value: Dict to return from the execute callable.

    Returns:
        Callable accepting a session and returning return_value.
    """
    return lambda _session: return_value


class TestAllowBranch:
    """Covers the allow policy decision path in enforce_and_run."""

    def test_allow_executes_and_returns_result(self, db_session, test_project):
        """Verifies that an allow policy causes the tool to execute and return result dict."""
        from orch.db.models import McpPolicy, McpPolicyDecision
        from orch.mcp.gate import enforce_and_run

        # Force allow on a Tier-2 tool (default would be ask)
        row = McpPolicy(
            project_id=test_project.id,
            tool_name="work_item_approve",
            decision=McpPolicyDecision.allow,
            updated_by="test",
        )
        db_session.add(row)
        db_session.flush()

        expected = {"id": "F-00001", "status": "approved"}
        result = asyncio.run(
            enforce_and_run(
                ctx=None,
                tool_name="work_item_approve",
                project_id=test_project.id,
                arguments={"project_id": test_project.id, "item_id": "F-00001"},
                approval_token=None,
                execute=_make_execute(expected),
            )
        )

        assert result["id"] == "F-00001"
        assert result["status"] == "approved"

    def test_allow_writes_success_audit_row(self, db_session, test_project):
        """Verifies that an allow policy creates an audit row with outcome=success."""
        from orch.db.models import McpAuditLog, McpPolicy, McpPolicyDecision
        from orch.mcp.gate import enforce_and_run

        row = McpPolicy(
            project_id=test_project.id,
            tool_name="work_item_approve",
            decision=McpPolicyDecision.allow,
            updated_by="test",
        )
        db_session.add(row)
        db_session.flush()

        asyncio.run(
            enforce_and_run(
                ctx=None,
                tool_name="work_item_approve",
                project_id=test_project.id,
                arguments={"project_id": test_project.id},
                approval_token=None,
                execute=_make_execute({"id": "X"}),
            )
        )

        # Audit row should have been written in a separate session by record_audit.
        # Query from the test session — audit uses its own session_scope.
        # Allow a moment for the record_audit session to flush.
        audit_rows = (
            db_session.query(McpAuditLog)
            .filter_by(tool_name="work_item_approve", outcome="success")
            .all()
        )
        assert len(audit_rows) >= 1
        assert audit_rows[0].decision == "allow"

    def test_allow_service_error_raises_tool_error(self, db_session, test_project):
        """Verifies that a ServiceError from the executor is re-raised as ToolError on allow."""
        from fastmcp.exceptions import ToolError

        from orch.db.models import McpPolicy, McpPolicyDecision
        from orch.mcp.gate import enforce_and_run
        from orch.services._common import ServiceError

        row = McpPolicy(
            project_id=test_project.id,
            tool_name="work_item_approve",
            decision=McpPolicyDecision.allow,
            updated_by="test",
        )
        db_session.add(row)
        db_session.flush()

        def failing_execute(session):
            raise ServiceError("item not found", code=1)

        with pytest.raises(ToolError, match=r"item not found"):
            asyncio.run(
                enforce_and_run(
                    ctx=None,
                    tool_name="work_item_approve",
                    project_id=test_project.id,
                    arguments={},
                    approval_token=None,
                    execute=failing_execute,
                )
            )


class TestDenyBranch:
    """Covers the deny policy decision path in enforce_and_run."""

    def test_deny_raises_tool_error(self, db_session, test_project):
        """Verifies that a deny policy raises ToolError without calling execute."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.gate import enforce_and_run

        # approve_merge is Tier-3, defaults to deny
        called = []

        def tracking_execute(session):
            called.append(True)
            return {}

        with pytest.raises(ToolError, match=r"denied by policy"):
            asyncio.run(
                enforce_and_run(
                    ctx=None,
                    tool_name="approve_merge",
                    project_id=test_project.id,
                    arguments={"project_id": test_project.id, "item_id": "F-001"},
                    approval_token=None,
                    execute=tracking_execute,
                )
            )

        assert len(called) == 0

    def test_deny_writes_denied_audit_row(self, db_session, test_project):
        """Verifies that a deny policy writes an audit row with outcome=denied."""
        from fastmcp.exceptions import ToolError

        from orch.db.models import McpAuditLog
        from orch.mcp.gate import enforce_and_run

        with pytest.raises(ToolError):
            asyncio.run(
                enforce_and_run(
                    ctx=None,
                    tool_name="approve_merge",
                    project_id=test_project.id,
                    arguments={},
                    approval_token=None,
                    execute=_make_execute({}),
                )
            )

        audit_rows = (
            db_session.query(McpAuditLog)
            .filter_by(tool_name="approve_merge", outcome="denied")
            .all()
        )
        assert len(audit_rows) >= 1
        assert audit_rows[0].decision == "deny"


class TestAskBranchApprovalRequired:
    """Covers ask policy + no token → approval_required envelope."""

    def test_ask_no_token_returns_approval_required(self, db_session, test_project):
        """Verifies that ask policy with no token and ctx=None returns approval_required dict."""
        from orch.mcp.gate import enforce_and_run

        # batch_create is Tier-2, defaults to ask
        result = asyncio.run(
            enforce_and_run(
                ctx=None,
                tool_name="batch_create",
                project_id=test_project.id,
                arguments={"project_id": test_project.id, "item_ids": ["F-001"]},
                approval_token=None,
                execute=_make_execute({"batch_id": "B-001"}),
            )
        )

        assert result["status"] == "approval_required"
        assert len(result["approval_token"]) >= 16
        assert result["tool"] == "batch_create"
        assert "how_to_approve" in result
        assert result["how_to_approve"].find("iw mcp approve") != -1

    def test_ask_no_token_creates_approval_request_row(self, db_session, test_project):
        """Verifies that the approval_required path inserts a McpApprovalRequest row."""
        from orch.db.models import McpApprovalRequest, McpApprovalStatus
        from orch.mcp.gate import enforce_and_run

        result = asyncio.run(
            enforce_and_run(
                ctx=None,
                tool_name="batch_create",
                project_id=test_project.id,
                arguments={"project_id": test_project.id},
                approval_token=None,
                execute=_make_execute({}),
            )
        )

        token = result["approval_token"]
        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        assert row.status == McpApprovalStatus.pending
        assert row.tool_name == "batch_create"

    def test_ask_no_token_writes_approval_required_audit(self, db_session, test_project):
        """Verifies the approval_required path writes an audit row with that outcome."""
        from orch.db.models import McpAuditLog
        from orch.mcp.gate import enforce_and_run

        asyncio.run(
            enforce_and_run(
                ctx=None,
                tool_name="batch_create",
                project_id=test_project.id,
                arguments={},
                approval_token=None,
                execute=_make_execute({}),
            )
        )

        audit_rows = (
            db_session.query(McpAuditLog)
            .filter_by(tool_name="batch_create", outcome="approval_required")
            .all()
        )
        assert len(audit_rows) >= 1
        assert audit_rows[0].decision == "ask"


class TestAskBranchWithToken:
    """Covers ask policy + valid approval token → executes and consumes token."""

    def test_ask_with_valid_token_executes(self, db_session, test_project):
        """Verifies that a valid approved token causes the tool to execute."""
        from orch.mcp.approvals import approve_request, create_approval_request
        from orch.mcp.gate import enforce_and_run

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_create",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        approve_request(db_session, token, by="op")
        db_session.flush()

        expected = {"batch_id": "B-001", "status": "planning"}
        result = asyncio.run(
            enforce_and_run(
                ctx=None,
                tool_name="batch_create",
                project_id=test_project.id,
                arguments={"project_id": test_project.id},
                approval_token=token,
                execute=_make_execute(expected),
            )
        )

        assert result["batch_id"] == "B-001"
        assert result["status"] == "planning"

    def test_ask_with_valid_token_consumes_request(self, db_session, test_project):
        """Verifies that using a valid token sets the request status to consumed."""
        from orch.db.models import McpApprovalRequest, McpApprovalStatus
        from orch.mcp.approvals import approve_request, create_approval_request
        from orch.mcp.gate import enforce_and_run

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_create",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        approve_request(db_session, token, by="op")
        db_session.flush()

        asyncio.run(
            enforce_and_run(
                ctx=None,
                tool_name="batch_create",
                project_id=test_project.id,
                arguments={},
                approval_token=token,
                execute=_make_execute({"ok": True}),
            )
        )

        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        assert row.status == McpApprovalStatus.consumed

    def test_ask_with_denied_token_raises_tool_error(self, db_session, test_project):
        """Verifies that passing a denied token raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.approvals import create_approval_request, deny_request
        from orch.mcp.gate import enforce_and_run

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_create",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        deny_request(db_session, token, by="op")
        db_session.flush()

        with pytest.raises(ToolError, match=r"denied"):
            asyncio.run(
                enforce_and_run(
                    ctx=None,
                    tool_name="batch_create",
                    project_id=test_project.id,
                    arguments={},
                    approval_token=token,
                    execute=_make_execute({}),
                )
            )

    def test_ask_with_expired_token_raises_tool_error(self, db_session, test_project):
        """Verifies that passing an expired token raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.db.models import McpApprovalRequest
        from orch.mcp.approvals import create_approval_request
        from orch.mcp.gate import enforce_and_run

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_create",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()

        # Force expiry
        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=5)
        db_session.flush()

        with pytest.raises(ToolError, match=r"expired"):
            asyncio.run(
                enforce_and_run(
                    ctx=None,
                    tool_name="batch_create",
                    project_id=test_project.id,
                    arguments={},
                    approval_token=token,
                    execute=_make_execute({}),
                )
            )

    def test_ask_with_wrong_tool_token_raises_tool_error(self, db_session, test_project):
        """Verifies that passing a token approved for a different tool raises ToolError."""
        from fastmcp.exceptions import ToolError

        from orch.mcp.approvals import approve_request, create_approval_request
        from orch.mcp.gate import enforce_and_run

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_approve",  # wrong tool
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        approve_request(db_session, token, by="op")
        db_session.flush()

        with pytest.raises(ToolError, match=r"tool"):
            asyncio.run(
                enforce_and_run(
                    ctx=None,
                    tool_name="batch_create",
                    project_id=test_project.id,
                    arguments={},
                    approval_token=token,
                    execute=_make_execute({}),
                )
            )


class TestAskBranchNoElicitation:
    """Covers fallback from ctx without elicitation → approval_required."""

    def test_ctx_without_elicitation_support_falls_back_to_approval_required(
        self, db_session, test_project
    ):
        """Verifies that a ctx that raises on elicit falls back to approval_required envelope."""
        from mcp.shared.exceptions import McpError

        from orch.mcp.gate import enforce_and_run

        # Build a minimal fake ctx whose elicit raises McpError (not supported)
        mock_ctx = MagicMock()

        async def _unsupported_elicit(*args, **kwargs):
            from mcp.types import ErrorData

            raise McpError(ErrorData(code=-32601, message="Method not found"))

        mock_ctx.elicit = _unsupported_elicit

        result = asyncio.run(
            enforce_and_run(
                ctx=mock_ctx,
                tool_name="batch_create",
                project_id=test_project.id,
                arguments={"project_id": test_project.id},
                approval_token=None,
                execute=_make_execute({}),
            )
        )

        assert result["status"] == "approval_required"
        assert len(result["approval_token"]) >= 16
