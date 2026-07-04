"""MCP enforcement gate — enforces policy before running a tool's service call.

Provides :func:`enforce_and_run`, the single entry point that:

1. Resolves the effective policy decision via :mod:`orch.mcp.policy`.
2. Dispatches to allow / deny / ask logic accordingly.
3. Records an audit row via :func:`orch.mcp.audit.record_audit` for every path.

The ``ask`` path supports three sub-modes (tried in order):
  a. ``approval_token`` provided → redeem it and execute.
  b. Client supports elicitation → call ``ctx.elicit()`` and execute on accept.
  c. No elicitation / no ctx → create an approval request and return the
     ``{"status": "approval_required", ...}`` envelope without executing.

The ``McpError`` with code ``-32601`` (JSON-RPC method-not-found) is the
signal that the MCP client does not support elicitation; it is caught narrowly
and falls through to the approval-required branch.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastmcp import Context
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def enforce_and_run(
    ctx: Context | None,
    *,
    tool_name: str,
    project_id: str | None,
    arguments: dict[str, Any],
    approval_token: str | None,
    execute: Callable[[Session], dict[str, Any]],
) -> dict[str, Any]:
    """Enforce the effective MCP policy and, if permitted, execute the service call.

    Opens a single session scope, resolves the policy decision, then dispatches:

    - **allow** — calls ``execute(session)``; audits ``outcome="success"``; returns
      the result.  On ``ServiceError`` audits ``outcome="error"`` and raises
      ``ToolError``.
    - **deny** — audits ``outcome="denied"`` and raises
      ``ToolError("<tool> is denied by policy for project '<project_id>'.")``.
      ``execute`` is never called.
    - **ask** (no ``approval_token``, no working elicitation):
      Creates a ``McpApprovalRequest`` row and returns the approval-required
      envelope: a dict with ``status = "approval_required"``, an opaque
      approval-token value, the ``tool`` name, ``expires_in_seconds``, and a
      ``how_to_approve`` instruction pointing at ``iw mcp approve``.
    - **ask** + valid ``approval_token``:
      Redeems the token via :func:`orch.mcp.approvals.redeem_approval` (raises
      ``ToolError`` on invalid/expired/denied), then executes.
    - **ask** + ``ctx`` with elicitation support:
      Calls ``await ctx.elicit(...)``; on ``accept`` executes; on decline/cancel
      audits ``outcome="denied"`` and raises ``ToolError("declined by user")``.

    Args:
        ctx: FastMCP ``Context`` for the current tool call, or ``None`` when
            called outside a live MCP session (e.g. tests, approval-token path).
        tool_name: Name of the MCP tool being gated.
        project_id: Project scope, or ``None`` for non-project-scoped tools.
        arguments: Raw tool argument dict (used for audit and approval storage).
        approval_token: Pre-issued approval token from a previous
            ``approval_required`` response, or ``None``.
        execute: Callable that accepts an active ``Session`` and returns the tool
            result dict.  Called only when the effective decision permits execution.

    Returns:
        Either the result dict from ``execute`` (on allow/approved execution),
        or the ``approval_required`` envelope dict (when human approval is needed).

    Raises:
        ToolError: When the policy is ``deny``, when the approval token is
            invalid/expired/denied/wrong-tool, when elicitation is declined, or
            when ``execute`` raises ``ServiceError``.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.approvals import create_approval_request, redeem_approval  # noqa: PLC0415
    from orch.mcp.audit import record_audit  # noqa: PLC0415
    from orch.mcp.config import approval_ttl_seconds  # noqa: PLC0415
    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.mcp.policy import resolve_policy_decision  # noqa: PLC0415
    from orch.services._common import ServiceError  # noqa: PLC0415

    with session_scope() as session:
        decision = resolve_policy_decision(session, project_id, tool_name)
        decision_str = decision.value

        # -----------------------------------------------------------------
        # ALLOW
        # -----------------------------------------------------------------
        if decision_str == "allow":
            try:
                result = execute(session)
            except ServiceError as exc:
                record_audit(
                    tool_name=tool_name,
                    project_id=project_id,
                    arguments=arguments,
                    outcome="error",
                    decision="allow",
                    error=exc.message,
                )
                raise ToolError(exc.message) from exc

            record_audit(
                tool_name=tool_name,
                project_id=project_id,
                arguments=arguments,
                outcome="success",
                decision="allow",
            )
            return result

        # -----------------------------------------------------------------
        # DENY
        # -----------------------------------------------------------------
        if decision_str == "deny":
            record_audit(
                tool_name=tool_name,
                project_id=project_id,
                arguments=arguments,
                outcome="denied",
                decision="deny",
            )
            raise ToolError(f"Tool '{tool_name}' is denied by policy for project '{project_id}'.")

        # -----------------------------------------------------------------
        # ASK — approval_token provided: redeem then execute
        # -----------------------------------------------------------------
        if approval_token is not None:
            try:
                redeem_approval(session, approval_token, tool_name)
            except ServiceError as exc:
                record_audit(
                    tool_name=tool_name,
                    project_id=project_id,
                    arguments=arguments,
                    outcome="error",
                    decision="ask",
                    error=exc.message,
                )
                raise ToolError(exc.message) from exc

            try:
                result = execute(session)
            except ServiceError as exc:
                record_audit(
                    tool_name=tool_name,
                    project_id=project_id,
                    arguments=arguments,
                    outcome="error",
                    decision="ask",
                    error=exc.message,
                )
                raise ToolError(exc.message) from exc

            record_audit(
                tool_name=tool_name,
                project_id=project_id,
                arguments=arguments,
                outcome="success",
                decision="ask",
                result_summary="approved via token",
            )
            return result

        # -----------------------------------------------------------------
        # ASK — try elicitation when ctx is available
        # -----------------------------------------------------------------
        if ctx is not None:
            elicit_result = await _try_elicit(ctx, tool_name, arguments)
            if elicit_result == "accepted":
                try:
                    result = execute(session)
                except ServiceError as exc:
                    record_audit(
                        tool_name=tool_name,
                        project_id=project_id,
                        arguments=arguments,
                        outcome="error",
                        decision="ask",
                        error=exc.message,
                    )
                    raise ToolError(exc.message) from exc

                record_audit(
                    tool_name=tool_name,
                    project_id=project_id,
                    arguments=arguments,
                    outcome="success",
                    decision="ask",
                    result_summary="approved via elicitation",
                )
                return result
            if elicit_result == "declined":
                record_audit(
                    tool_name=tool_name,
                    project_id=project_id,
                    arguments=arguments,
                    outcome="denied",
                    decision="ask",
                )
                raise ToolError("Tool execution declined by user.")
            # elicit_result == "unsupported" — fall through to approval-required

        # -----------------------------------------------------------------
        # ASK — create approval request and return envelope
        # -----------------------------------------------------------------
        ttl = approval_ttl_seconds()
        token = create_approval_request(
            session,
            project_id=project_id,
            tool_name=tool_name,
            arguments=arguments,
            ttl_seconds=ttl,
        )

        record_audit(
            tool_name=tool_name,
            project_id=project_id,
            arguments=arguments,
            outcome="approval_required",
            decision="ask",
        )

        return {
            "status": "approval_required",
            "approval_token": token,
            "tool": tool_name,
            "expires_in_seconds": ttl,
            "how_to_approve": (
                f"A human must run `iw mcp approve {token}` (or deny with "
                f"`iw mcp deny {token}`), then retry this tool call passing "
                f"approval_token={token}."
            ),
        }


async def _try_elicit(
    ctx: Any,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Attempt to elicit confirmation from the MCP client.

    Calls ``ctx.elicit()`` with a human-readable confirmation prompt.
    Catches ``McpError`` with code ``-32601`` (method-not-found — elicitation
    not supported by the client) and returns ``"unsupported"`` so the caller
    can fall back to the approval-required path.

    Args:
        ctx: FastMCP ``Context`` for the current request.
        tool_name: Tool name for the confirmation message.
        arguments: Tool arguments shown in the prompt.

    Returns:
        ``"accepted"`` when the user confirmed, ``"declined"`` when they
        declined or cancelled, ``"unsupported"`` when the client does not
        support elicitation.
    """
    from mcp.shared.exceptions import McpError  # noqa: PLC0415
    from mcp.types import METHOD_NOT_FOUND  # noqa: PLC0415

    try:
        key_args = {k: v for k, v in arguments.items() if k not in ("design_doc_content",)}
        message = (
            f"Confirm execution of '{tool_name}' with arguments: {key_args}. "
            "This action requires human approval."
        )
        elicitation_result = await ctx.elicit(message, response_type=bool)
    except McpError as exc:
        # -32601 = method not found = client does not support elicitation
        if exc.error.code == METHOD_NOT_FOUND:
            return "unsupported"
        # Any other McpError — treat as unsupported to avoid breaking the tool
        logger.warning("Unexpected McpError during elicitation for tool=%s: %s", tool_name, exc)
        return "unsupported"
    except Exception:  # noqa: BLE001
        # Any non-McpError exception (e.g. AttributeError on a mock ctx) — unsupported
        logger.warning("Elicitation failed unexpectedly for tool=%s", tool_name, exc_info=True)
        return "unsupported"

    from fastmcp.server.elicitation import (  # noqa: PLC0415
        AcceptedElicitation,
        CancelledElicitation,
        DeclinedElicitation,
    )

    if isinstance(elicitation_result, AcceptedElicitation):
        # User accepted — the data field contains the bool response
        return "accepted"
    if isinstance(elicitation_result, (DeclinedElicitation, CancelledElicitation)):
        return "declined"

    # Unexpected result type — treat as declined to be safe
    return "declined"
