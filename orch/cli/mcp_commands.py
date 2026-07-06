"""MCP operator CLI commands — iw mcp group.

Commands:
  mcp serve         Launch the MCP server over stdio.
  mcp approve       Approve a pending MCP approval request.
  mcp deny          Deny a pending MCP approval request.
  mcp approvals     List MCP approval requests.
  mcp policy set    Upsert a per-project per-tool policy override.
  mcp policy list   List per-project per-tool policy overrides.
"""

from __future__ import annotations

import getpass
import json

import click
from sqlalchemy import select

from orch.cli.utils import output_error
from orch.mcp.approvals import approve_request, deny_request, list_approval_requests
from orch.mcp.policy import TOOL_TIERS
from orch.services._common import ServiceError

# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group("mcp")
def mcp_group() -> None:
    """MCP server and approval management commands."""


# ---------------------------------------------------------------------------
# mcp serve
# ---------------------------------------------------------------------------


@mcp_group.command("serve")
@click.option(
    "--http",
    "use_http",
    is_flag=True,
    default=False,
    help="Serve over HTTP as an independent network service instead of stdio.",
)
@click.option(
    "--host",
    default=None,
    help="HTTP bind host (default 127.0.0.1, or IW_CORE_MCP_HTTP_HOST). "
    "Use 0.0.0.0 to accept LAN clients.",
)
@click.option(
    "--port",
    default=None,
    type=int,
    help="HTTP bind port (default 9901, or IW_CORE_MCP_HTTP_PORT).",
)
def serve(use_http: bool, host: str | None, port: int | None) -> None:
    """Launch the IW AI Core MCP server (blocks until stopped/disconnected).

    Default transport is **stdio**: the MCP client launches this process and
    talks over stdin/stdout (server co-located with client).  With ``--http``,
    the server runs as a long-lived network service and clients connect to
    ``http://<host>:<port>/mcp/`` over the network — one server on the host,
    remote clients with no filesystem access.

    It does not require a database session — the server opens its own session
    for each tool call.

    Args:
        use_http: When True, serve over HTTP instead of stdio.
        host: HTTP bind host override, or None to use env/default.
        port: HTTP bind port override, or None to use env/default.
    """
    from orch.mcp.server import main  # noqa: PLC0415

    main(transport="http" if use_http else "stdio", host=host, port=port)


# ---------------------------------------------------------------------------
# mcp approve
# ---------------------------------------------------------------------------


@mcp_group.command("approve")
@click.argument("token")
@click.option(
    "--by",
    default=None,
    help="Operator identifier recorded in decided_by (defaults to OS user).",
)
@click.pass_context
def approve(ctx: click.Context, token: str, by: str | None) -> None:
    """Approve a pending MCP approval request identified by TOKEN.

    The token is the opaque string returned in the approval-required envelope
    that the MCP server sent to the client.  After approval the MCP agent can
    retry the gated tool call and it will be allowed through.

    Args:
        token: Opaque approval token to approve.
        by: Optional operator identifier; defaults to the current OS username.
    """
    operator = by or _current_user()
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            result = approve_request(session, token, by=operator)
            session.commit()
    except ServiceError as exc:
        output_error(ctx, exc.message, exc.code)

    if ctx.obj.get("json"):
        click.echo(json.dumps(result))
    else:
        click.echo(f"Approved: {result['token']} (by {result['decided_by']})")


# ---------------------------------------------------------------------------
# mcp deny
# ---------------------------------------------------------------------------


@mcp_group.command("deny")
@click.argument("token")
@click.option(
    "--by",
    default=None,
    help="Operator identifier recorded in decided_by (defaults to OS user).",
)
@click.pass_context
def deny(ctx: click.Context, token: str, by: str | None) -> None:
    """Deny a pending MCP approval request identified by TOKEN.

    After denial the MCP server will inform the client that the tool call
    was denied and no retry will succeed for this token.

    Args:
        token: Opaque approval token to deny.
        by: Optional operator identifier; defaults to the current OS username.
    """
    operator = by or _current_user()
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            result = deny_request(session, token, by=operator)
            session.commit()
    except ServiceError as exc:
        output_error(ctx, exc.message, exc.code)

    if ctx.obj.get("json"):
        click.echo(json.dumps(result))
    else:
        click.echo(f"Denied: {result['token']} (by {result['decided_by']})")


# ---------------------------------------------------------------------------
# mcp approvals
# ---------------------------------------------------------------------------


@mcp_group.command("approvals")
@click.option(
    "--status",
    default=None,
    help="Filter by status: pending, approved, denied, consumed, expired.",
)
@click.pass_context
def approvals(ctx: click.Context, status: str | None) -> None:
    """List MCP approval requests, optionally filtered by STATUS.

    Displays all approval requests in reverse-chronological order.  Use
    ``--status pending`` to see only requests awaiting a decision.

    Args:
        status: Optional approval status filter string.
    """
    get_session = ctx.obj["get_session"]

    with get_session() as session:
        result = list_approval_requests(session, status=status)

    if ctx.obj.get("json"):
        click.echo(json.dumps(result))
    else:
        items = result.get("approvals", [])
        if not items:
            click.echo("No approval requests found.")
            return
        click.echo(f"{'TOKEN':<36}  {'TOOL':<24}  {'STATUS':<10}  {'BY':<16}  CREATED")
        click.echo("-" * 100)
        for req in items:
            tok = req["token"][:34] + ".." if len(req["token"]) > 36 else req["token"]
            click.echo(
                f"{tok:<36}  {req['tool_name']:<24}  {req['status']:<10}"
                f"  {(req['decided_by'] or ''):<16}  {req['created_at'] or ''}"
            )


# ---------------------------------------------------------------------------
# mcp policy group
# ---------------------------------------------------------------------------


@mcp_group.group("policy")
def policy() -> None:
    """Manage per-project per-tool MCP policy overrides."""


@policy.command("set")
@click.argument("project_id")
@click.argument("tool_name")
@click.argument("decision", type=click.Choice(["allow", "ask", "deny"]))
@click.option(
    "--by",
    default=None,
    help="Operator identifier stored in updated_by (defaults to OS user).",
)
@click.pass_context
def policy_set(
    ctx: click.Context,
    project_id: str,
    tool_name: str,
    decision: str,
    by: str | None,
) -> None:
    """Upsert a policy override for TOOL_NAME in PROJECT_ID to DECISION.

    Valid DECISION values: ``allow``, ``ask``, ``deny``.
    TOOL_NAME must be a known MCP tool — run ``iw mcp policy list`` to see
    current overrides or check ``orch.mcp.policy.TOOL_TIERS`` for the full list.

    Args:
        project_id: Project identifier the override applies to.
        tool_name: MCP tool name to override.
        decision: Policy decision string: allow, ask, or deny.
        by: Optional operator identifier; defaults to the current OS username.
    """
    if tool_name not in TOOL_TIERS:
        output_error(
            ctx,
            f"Unknown tool_name {tool_name!r}. Valid tools: {sorted(TOOL_TIERS)}",
            2,
        )

    from datetime import UTC, datetime  # noqa: PLC0415

    from orch.db.models import McpPolicy, McpPolicyDecision  # noqa: PLC0415

    operator = by or _current_user()
    decision_enum = McpPolicyDecision(decision)
    get_session = ctx.obj["get_session"]

    with get_session() as session:
        existing = session.execute(
            select(McpPolicy).where(
                McpPolicy.project_id == project_id,
                McpPolicy.tool_name == tool_name,
            )
        ).scalar_one_or_none()

        now = datetime.now(UTC)
        if existing is not None:
            existing.decision = decision_enum
            existing.updated_at = now
            existing.updated_by = operator
        else:
            row = McpPolicy(
                project_id=project_id,
                tool_name=tool_name,
                decision=decision_enum,
                updated_at=now,
                updated_by=operator,
            )
            session.add(row)

        session.flush()
        result = {
            "project_id": project_id,
            "tool_name": tool_name,
            "decision": decision,
            "updated_by": operator,
        }
        session.commit()

    if ctx.obj.get("json"):
        click.echo(json.dumps(result))
    else:
        click.echo(f"Policy set: {project_id} / {tool_name} = {decision} (by {operator})")


@policy.command("list")
@click.argument("project_id", required=False, default=None)
@click.pass_context
def policy_list(ctx: click.Context, project_id: str | None) -> None:
    """List MCP policy overrides, optionally filtered by PROJECT_ID.

    When PROJECT_ID is omitted all overrides across all projects are shown.

    Args:
        project_id: Optional project identifier to filter by.
    """
    from orch.db.models import McpPolicy  # noqa: PLC0415

    get_session = ctx.obj["get_session"]

    with get_session() as session:
        query = select(McpPolicy).order_by(McpPolicy.project_id, McpPolicy.tool_name)
        if project_id is not None:
            query = query.where(McpPolicy.project_id == project_id)
        rows = session.execute(query).scalars().all()

        # Materialise dicts inside the session — rows detach on exit and would
        # raise DetachedInstanceError on any lazy attribute access afterwards.
        policies = [
            {
                "project_id": r.project_id,
                "tool_name": r.tool_name,
                "decision": r.decision.value,
                "updated_by": r.updated_by,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]

    if ctx.obj.get("json"):
        click.echo(json.dumps({"policies": policies}))
    else:
        if not policies:
            click.echo("No policy overrides found.")
            return
        click.echo(f"{'PROJECT':<20}  {'TOOL':<24}  {'DECISION':<8}  {'BY':<16}  UPDATED")
        click.echo("-" * 90)
        for p in policies:
            click.echo(
                f"{p['project_id']:<20}  {p['tool_name']:<24}  {p['decision']:<8}"
                f"  {(p['updated_by'] or ''):<16}  {p['updated_at'] or ''}"
            )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _current_user() -> str:
    """Return the current OS username, falling back to 'unknown'.

    Returns:
        The username from ``getpass.getuser()``, or ``'unknown'`` if unavailable.
    """
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return "unknown"
