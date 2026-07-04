"""Integration tests for the MCP approval request lifecycle (orch/mcp/approvals.py).

Covers: create→approve→redeem (consumed); create→deny→redeem raises;
expiry (pending → expired on redeem); wrong tool raises; double-redeem raises.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


class TestCreateApprovalRequest:
    """Covers create_approval_request happy path."""

    def test_create_returns_opaque_token(self, db_session, test_project):
        """Verifies that create_approval_request returns a non-empty string token."""
        from orch.mcp.approvals import create_approval_request

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={"project_id": test_project.id, "batch_id": "B-001"},
            ttl_seconds=3600,
        )
        assert isinstance(token, str)
        assert len(token) >= 16

    def test_create_inserts_pending_row(self, db_session, test_project):
        """Verifies that a McpApprovalRequest row with status=pending is created."""
        from orch.db.models import McpApprovalRequest, McpApprovalStatus
        from orch.mcp.approvals import create_approval_request

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="approve_merge",
            arguments={"item_id": "F-00001"},
            ttl_seconds=3600,
        )
        db_session.flush()

        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        assert row.status == McpApprovalStatus.pending
        assert row.tool_name == "approve_merge"
        assert row.project_id == test_project.id
        assert row.expires_at is not None

    def test_create_sets_expires_at_correctly(self, db_session, test_project):
        """Verifies that expires_at is approximately now + ttl_seconds."""
        from orch.db.models import McpApprovalRequest
        from orch.mcp.approvals import create_approval_request

        ttl = 300
        before = datetime.now(UTC)
        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=ttl,
        )
        db_session.flush()
        after = datetime.now(UTC)

        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        # expires_at must be between before+ttl and after+ttl (with small tolerance)
        assert row.expires_at >= before + timedelta(seconds=ttl - 1)
        assert row.expires_at <= after + timedelta(seconds=ttl + 1)


class TestApproveRequest:
    """Covers approve_request transitions."""

    def test_approve_sets_status_to_approved(self, db_session, test_project):
        """Verifies approve_request sets status=approved and decided_at."""
        from orch.db.models import McpApprovalRequest, McpApprovalStatus
        from orch.mcp.approvals import approve_request, create_approval_request

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()

        result = approve_request(db_session, token, by="operator-1")
        db_session.flush()

        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        assert row.status == McpApprovalStatus.approved
        assert row.decided_by == "operator-1"
        assert row.decided_at is not None
        assert result["status"] == "approved"

    def test_approve_raises_if_already_approved(self, db_session, test_project):
        """Verifies approve_request raises ServiceError when request is not pending."""
        from orch.mcp.approvals import approve_request, create_approval_request
        from orch.services._common import ServiceError

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        approve_request(db_session, token, by="op")
        db_session.flush()

        with pytest.raises(ServiceError, match=r"not pending"):
            approve_request(db_session, token, by="op")


class TestDenyRequest:
    """Covers deny_request transitions."""

    def test_deny_sets_status_to_denied(self, db_session, test_project):
        """Verifies deny_request sets status=denied and decided fields."""
        from orch.db.models import McpApprovalRequest, McpApprovalStatus
        from orch.mcp.approvals import create_approval_request, deny_request

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="approve_merge",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()

        result = deny_request(db_session, token, by="operator-2")
        db_session.flush()

        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        assert row.status == McpApprovalStatus.denied
        assert row.decided_by == "operator-2"
        assert row.decided_at is not None
        assert result["status"] == "denied"

    def test_deny_raises_if_not_pending(self, db_session, test_project):
        """Verifies deny_request raises ServiceError when request is not pending."""
        from orch.mcp.approvals import create_approval_request, deny_request
        from orch.services._common import ServiceError

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        deny_request(db_session, token, by="op")
        db_session.flush()

        with pytest.raises(ServiceError, match=r"not pending"):
            deny_request(db_session, token, by="op")


class TestRedeemApproval:
    """Covers redeem_approval lifecycle paths."""

    def test_redeem_approved_token_sets_consumed(self, db_session, test_project):
        """Verifies that redeeming an approved token transitions status to consumed."""
        from orch.db.models import McpApprovalRequest, McpApprovalStatus
        from orch.mcp.approvals import approve_request, create_approval_request, redeem_approval

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        approve_request(db_session, token, by="op")
        db_session.flush()

        redeem_approval(db_session, token, "batch_cancel")
        db_session.flush()

        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        assert row.status == McpApprovalStatus.consumed

    def test_redeem_denied_token_raises(self, db_session, test_project):
        """Verifies that redeeming a denied token raises ServiceError."""
        from orch.mcp.approvals import create_approval_request, deny_request, redeem_approval
        from orch.services._common import ServiceError

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        deny_request(db_session, token, by="op")
        db_session.flush()

        with pytest.raises(ServiceError, match=r"denied"):
            redeem_approval(db_session, token, "batch_cancel")

    def test_redeem_expired_token_raises_and_marks_expired(self, db_session, test_project):
        """Verifies that a past-expiry pending token is marked expired and raises ServiceError."""
        from orch.db.models import McpApprovalRequest, McpApprovalStatus
        from orch.mcp.approvals import create_approval_request, redeem_approval
        from orch.services._common import ServiceError

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()

        # Force expires_at into the past
        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=10)
        db_session.flush()

        with pytest.raises(ServiceError, match=r"expired"):
            redeem_approval(db_session, token, "batch_cancel")

        db_session.flush()
        row2 = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        assert row2.status == McpApprovalStatus.expired

    def test_redeem_wrong_tool_raises(self, db_session, test_project):
        """Verifies that redeeming a token with the wrong tool_name raises ServiceError."""
        from orch.mcp.approvals import approve_request, create_approval_request, redeem_approval
        from orch.services._common import ServiceError

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        approve_request(db_session, token, by="op")
        db_session.flush()

        with pytest.raises(ServiceError, match=r"tool"):
            redeem_approval(db_session, token, "approve_merge")

    def test_double_redeem_raises(self, db_session, test_project):
        """Verifies that redeeming an already-consumed token raises ServiceError."""
        from orch.mcp.approvals import approve_request, create_approval_request, redeem_approval
        from orch.services._common import ServiceError

        token = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        approve_request(db_session, token, by="op")
        db_session.flush()
        redeem_approval(db_session, token, "batch_cancel")
        db_session.flush()

        with pytest.raises(ServiceError, match=r"consumed"):
            redeem_approval(db_session, token, "batch_cancel")

    def test_redeem_unknown_token_raises(self, db_session, test_project):
        """Verifies that redeeming a non-existent token raises ServiceError."""
        from orch.mcp.approvals import redeem_approval
        from orch.services._common import ServiceError

        with pytest.raises(ServiceError, match=r"not found"):
            redeem_approval(db_session, "nonexistent-token-xyz", "batch_cancel")


class TestListApprovalRequests:
    """Covers list_approval_requests."""

    def test_list_returns_all_when_no_status_filter(self, db_session, test_project):
        """Verifies list_approval_requests returns all requests when status=None."""
        from orch.mcp.approvals import (
            approve_request,
            create_approval_request,
            list_approval_requests,
        )

        t1 = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        t2 = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="approve_merge",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        approve_request(db_session, t1, by="op")
        db_session.flush()

        result = list_approval_requests(db_session, status=None)
        tokens = [r["token"] for r in result["approvals"]]
        # Both tokens should be present
        assert tokens.count(t1) == 1
        assert tokens.count(t2) == 1

    def test_list_filters_by_status(self, db_session, test_project):
        """Verifies list_approval_requests filters by status correctly."""
        from orch.mcp.approvals import (
            approve_request,
            create_approval_request,
            list_approval_requests,
        )

        t1 = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="batch_cancel",
            arguments={},
            ttl_seconds=3600,
        )
        t2 = create_approval_request(
            db_session,
            project_id=test_project.id,
            tool_name="approve_merge",
            arguments={},
            ttl_seconds=3600,
        )
        db_session.flush()
        approve_request(db_session, t1, by="op")
        db_session.flush()

        pending_result = list_approval_requests(db_session, status="pending")
        pending_tokens = [r["token"] for r in pending_result["approvals"]]
        assert pending_tokens.count(t2) == 1
        assert t1 not in pending_tokens
