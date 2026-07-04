"""Contract tests for `iw mcp` command group against a real PostgreSQL testcontainer.

Tests: mcp approve, mcp deny, mcp approvals, mcp policy set, mcp policy list.
All tests use the testcontainer db_session fixture — never the live DB.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import (
    McpApprovalRequest,
    McpApprovalStatus,
    McpPolicy,
    McpPolicyDecision,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke(
    runner: CliRunner,
    args: list[str],
    cli_get_session: object,
    project_id: str = "test-proj",
) -> object:
    """Invoke the MCP CLI commands with a pre-injected session factory.

    Args:
        runner: Click CliRunner instance.
        args: Command arguments (after ``--project``).
        cli_get_session: The testcontainer session factory to inject.
        project_id: Project ID to pass via ``--project``.

    Returns:
        The Click ``Result`` object from ``runner.invoke``.
    """
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )


def _seed_pending_request(
    db_session: Session,
    project_id: str,
    tool_name: str = "batch_cancel",
    ttl_seconds: int = 3600,
) -> str:
    """Insert a pending McpApprovalRequest and return its token.

    Args:
        db_session: Active SQLAlchemy session.
        project_id: Project the request belongs to.
        tool_name: Tool being gated.
        ttl_seconds: Seconds until the request expires.

    Returns:
        The opaque token string.
    """
    import secrets  # noqa: PLC0415

    token = secrets.token_urlsafe(24)
    now = datetime.now(UTC)
    row = McpApprovalRequest(
        token=token,
        project_id=project_id,
        tool_name=tool_name,
        arguments={"project_id": project_id},
        status=McpApprovalStatus.pending,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db_session.add(row)
    db_session.flush()
    return token


# ---------------------------------------------------------------------------
# mcp approve
# ---------------------------------------------------------------------------


class TestMcpApprove:
    """Covers ``iw mcp approve <token>`` contract."""

    def test_approve_pending_token_exits_0(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Approving a pending token exits 0 and sets status to approved."""
        token = _seed_pending_request(db_session, test_project.id)
        runner = CliRunner()
        result = _invoke(runner, ["mcp", "approve", token], cli_get_session, test_project.id)
        assert result.exit_code == 0, f"stdout: {result.output}"
        db_session.expire_all()
        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        assert row.status == McpApprovalStatus.approved

    def test_approve_json_output_shape(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Approving with --json emits a valid JSON envelope with token and status."""
        token = _seed_pending_request(db_session, test_project.id)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", test_project.id, "--json", "mcp", "approve", token],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        data = json.loads(result.output)
        assert data["token"] == token
        assert data["status"] == "approved"

    def test_approve_unknown_token_exits_nonzero(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Approving an unknown token exits with a non-zero code and reports error."""
        runner = CliRunner()
        result = _invoke(
            runner,
            ["mcp", "approve", "does-not-exist-token"],
            cli_get_session,
            test_project.id,
        )
        assert result.exit_code != 0
        assert (
            result.output.lower().find("not found") != -1
            or result.output.lower().find("error") != -1
        )


# ---------------------------------------------------------------------------
# mcp deny
# ---------------------------------------------------------------------------


class TestMcpDeny:
    """Covers ``iw mcp deny <token>`` contract."""

    def test_deny_pending_token_exits_0(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Denying a pending token exits 0 and sets status to denied."""
        token = _seed_pending_request(db_session, test_project.id, tool_name="approve_merge")
        runner = CliRunner()
        result = _invoke(runner, ["mcp", "deny", token], cli_get_session, test_project.id)
        assert result.exit_code == 0, f"stdout: {result.output}"
        db_session.expire_all()
        row = db_session.query(McpApprovalRequest).filter_by(token=token).one()
        assert row.status == McpApprovalStatus.denied

    def test_deny_json_output_shape(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Denying with --json emits a valid JSON envelope with token and status denied."""
        token = _seed_pending_request(db_session, test_project.id)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", test_project.id, "--json", "mcp", "deny", token],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        data = json.loads(result.output)
        assert data["token"] == token
        assert data["status"] == "denied"

    def test_deny_unknown_token_exits_nonzero(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Denying an unknown token exits with a non-zero code."""
        runner = CliRunner()
        result = _invoke(
            runner,
            ["mcp", "deny", "ghost-token-xyz"],
            cli_get_session,
            test_project.id,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# mcp approvals
# ---------------------------------------------------------------------------


class TestMcpApprovals:
    """Covers ``iw mcp approvals`` contract."""

    def test_approvals_list_all_exits_0(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Listing all approval requests exits 0."""
        _seed_pending_request(db_session, test_project.id)
        runner = CliRunner()
        result = _invoke(runner, ["mcp", "approvals"], cli_get_session, test_project.id)
        assert result.exit_code == 0, f"stdout: {result.output}"

    def test_approvals_json_contains_approvals_key(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Listing with --json returns a dict with an 'approvals' list."""
        _seed_pending_request(db_session, test_project.id, tool_name="batch_create")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", test_project.id, "--json", "mcp", "approvals"],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        data = json.loads(result.output)
        assert "approvals" in data
        assert isinstance(data["approvals"], list)
        # At least the one we seeded
        assert len(data["approvals"]) >= 1

    def test_approvals_status_filter_pending(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """--status=pending returns only pending requests."""
        _seed_pending_request(db_session, test_project.id, tool_name="batch_approve")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", test_project.id, "--json", "mcp", "approvals", "--status", "pending"],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        data = json.loads(result.output)
        statuses = [a["status"] for a in data["approvals"]]
        assert len(statuses) >= 1
        for s in statuses:
            assert s == "pending"


# ---------------------------------------------------------------------------
# mcp policy set
# ---------------------------------------------------------------------------


class TestMcpPolicySet:
    """Covers ``iw mcp policy set <project_id> <tool_name> <decision>`` contract."""

    def test_policy_set_inserts_row(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Setting a policy for a known tool inserts a McpPolicy row."""
        runner = CliRunner()
        result = _invoke(
            runner,
            ["mcp", "policy", "set", test_project.id, "batch_cancel", "deny"],
            cli_get_session,
            test_project.id,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        db_session.expire_all()
        row = (
            db_session.query(McpPolicy)
            .filter_by(project_id=test_project.id, tool_name="batch_cancel")
            .one_or_none()
        )
        assert row is not None
        assert row.decision == McpPolicyDecision.deny

    def test_policy_set_upserts_existing_row(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Setting a policy twice updates the decision (upsert)."""
        existing = McpPolicy(
            project_id=test_project.id,
            tool_name="batch_approve",
            decision=McpPolicyDecision.ask,
            updated_by="old-operator",
        )
        db_session.add(existing)
        db_session.flush()

        runner = CliRunner()
        result = _invoke(
            runner,
            ["mcp", "policy", "set", test_project.id, "batch_approve", "allow"],
            cli_get_session,
            test_project.id,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        db_session.expire_all()
        row = (
            db_session.query(McpPolicy)
            .filter_by(project_id=test_project.id, tool_name="batch_approve")
            .one()
        )
        assert row.decision == McpPolicyDecision.allow

    def test_policy_set_unknown_tool_exits_2(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Setting a policy for an unknown tool_name exits with code 2."""
        runner = CliRunner()
        result = _invoke(
            runner,
            ["mcp", "policy", "set", test_project.id, "nonexistent_tool", "allow"],
            cli_get_session,
            test_project.id,
        )
        assert result.exit_code == 2

    def test_policy_set_json_output_shape(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Policy set with --json emits a valid JSON envelope."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--project",
                test_project.id,
                "--json",
                "mcp",
                "policy",
                "set",
                test_project.id,
                "approve_merge",
                "ask",
            ],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        data = json.loads(result.output)
        assert data["project_id"] == test_project.id
        assert data["tool_name"] == "approve_merge"
        assert data["decision"] == "ask"


# ---------------------------------------------------------------------------
# mcp policy list
# ---------------------------------------------------------------------------


class TestMcpPolicyList:
    """Covers ``iw mcp policy list [<project_id>]`` contract."""

    def test_policy_list_exits_0_empty(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Listing policies with no rows exits 0."""
        runner = CliRunner()
        result = _invoke(runner, ["mcp", "policy", "list"], cli_get_session, test_project.id)
        assert result.exit_code == 0, f"stdout: {result.output}"

    def test_policy_list_json_returns_policies_key(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Listing with --json returns a dict with a 'policies' list."""
        db_session.add(
            McpPolicy(
                project_id=test_project.id,
                tool_name="work_item_cancel",
                decision=McpPolicyDecision.deny,
            )
        )
        db_session.flush()
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", test_project.id, "--json", "mcp", "policy", "list"],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        data = json.loads(result.output)
        assert "policies" in data
        assert len(data["policies"]) >= 1
        assert data["policies"][0]["tool_name"] == "work_item_cancel"
        assert data["policies"][0]["decision"] == "deny"

    def test_policy_list_survives_session_close(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """policy list materialises rows inside the session (no detach error after close)."""
        from contextlib import contextmanager  # noqa: PLC0415

        db_session.add(
            McpPolicy(
                project_id=test_project.id,
                tool_name="batch_create",
                decision=McpPolicyDecision.allow,
            )
        )
        db_session.flush()

        @contextmanager
        def _closing_get_session() -> object:
            """Mirror production get_session(): expire + detach ORM rows on exit."""
            try:
                yield db_session
            finally:
                # Reproduces the real get_session() lifecycle: attributes are
                # expired and instances detached on __exit__, so any lazy access
                # to an ORM row after the `with` block raises DetachedInstanceError.
                db_session.expire_all()
                db_session.expunge_all()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", test_project.id, "--json", "mcp", "policy", "list", test_project.id],
            obj={"get_session": _closing_get_session},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        data = json.loads(result.output)
        tool_names = [p["tool_name"] for p in data["policies"]]
        assert tool_names.count("batch_create") == 1

    def test_policy_list_filtered_by_project(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """Listing filtered by project_id returns only that project's policies."""
        db_session.add(
            McpPolicy(
                project_id=test_project.id,
                tool_name="batch_create",
                decision=McpPolicyDecision.allow,
            )
        )
        db_session.add(
            McpPolicy(
                project_id="other-proj",
                tool_name="batch_cancel",
                decision=McpPolicyDecision.deny,
            )
        )
        db_session.flush()
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", test_project.id, "--json", "mcp", "policy", "list", test_project.id],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"stdout: {result.output}"
        data = json.loads(result.output)
        project_ids = [p["project_id"] for p in data["policies"]]
        for pid in project_ids:
            assert pid == test_project.id
