"""MCP approval request lifecycle — create, redeem, approve, deny, and list.

Provides the four public functions used by the enforcement gate and the
(forthcoming) ``iw mcp`` CLI:

- :func:`create_approval_request` — insert a pending request and return its token.
- :func:`redeem_approval` — atomically consume an approved token.
- :func:`approve_request` — operator: approve a pending request.
- :func:`deny_request` — operator: deny a pending request.
- :func:`list_approval_requests` — list requests, optionally filtered by status.

Expiry is enforced in :func:`redeem_approval`: a pending token whose
``expires_at`` is in the past is marked ``expired`` before raising.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from orch.db.models import McpApprovalRequest, McpApprovalStatus
from orch.services._common import ServiceError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def create_approval_request(
    session: Session,
    *,
    project_id: str | None,
    tool_name: str,
    arguments: dict[str, Any],
    ttl_seconds: int,
) -> str:
    """Create a pending approval request and return its opaque token.

    Generates a URL-safe random token, inserts a ``McpApprovalRequest`` row
    with ``status=pending`` and ``expires_at = UTC now + ttl_seconds``, and
    returns the token for inclusion in the approval-required envelope.

    Args:
        session: Active SQLAlchemy session; the caller is responsible for flush/commit.
        project_id: Owning project, or ``None`` for non-project-scoped tools.
        tool_name: Gated tool the approval will authorise.
        arguments: Tool arguments dict stored on the request for operator review.
        ttl_seconds: Seconds until the request expires.

    Returns:
        Opaque URL-safe token string (32 characters, 24 bytes of entropy).
    """
    token = secrets.token_urlsafe(24)
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=ttl_seconds)

    row = McpApprovalRequest(
        token=token,
        project_id=project_id,
        tool_name=tool_name,
        arguments=arguments,
        status=McpApprovalStatus.pending,
        expires_at=expires_at,
    )
    session.add(row)
    session.flush()
    return token


def redeem_approval(session: Session, token: str, tool_name: str) -> None:
    """Consume an approved token, verifying tool name and expiry.

    Looks up the token; raises :class:`ServiceError` when:
    - The token does not exist.
    - The token's ``tool_name`` does not match ``tool_name``.
    - The request is ``denied``.
    - The request is already ``consumed``.
    - The request is ``pending`` but past its ``expires_at`` (marks it
      ``expired`` first, then raises).
    - The request is ``expired``.

    On success (status ``approved``), sets status to ``consumed`` and returns.

    Args:
        session: Active SQLAlchemy session.
        token: Opaque token returned in a previous approval-required envelope.
        tool_name: Expected tool name — must match what was requested.

    Raises:
        ServiceError: When the token is not found, has wrong tool, is denied,
            consumed, or expired.
    """
    row = session.query(McpApprovalRequest).filter_by(token=token).one_or_none()
    if row is None:
        raise ServiceError(f"Approval token not found: {token!r}", code=1)

    if row.tool_name != tool_name:
        raise ServiceError(
            f"Approval token is for tool {row.tool_name!r}, not {tool_name!r}",
            code=1,
        )

    if row.status == McpApprovalStatus.denied:
        raise ServiceError("Approval request was denied", code=1)

    if row.status == McpApprovalStatus.consumed:
        raise ServiceError("Approval token already consumed", code=1)

    if row.status == McpApprovalStatus.expired:
        raise ServiceError("Approval request has expired", code=1)

    # A pending token past its TTL is treated as expired on read.
    if (
        row.status == McpApprovalStatus.pending
        and row.expires_at is not None
        and datetime.now(UTC) > row.expires_at
    ):
        row.status = McpApprovalStatus.expired
        session.flush()
        raise ServiceError("Approval request has expired", code=1)

    if row.status != McpApprovalStatus.approved:
        # Covers any unexpected status value
        raise ServiceError(
            f"Approval request is in unexpected status: {row.status.value!r}",
            code=1,
        )

    # Consume the approved token
    row.status = McpApprovalStatus.consumed
    session.flush()


def approve_request(session: Session, token: str, *, by: str | None) -> dict[str, Any]:
    """Set an approval request's status to approved.

    Args:
        session: Active SQLAlchemy session.
        token: Opaque token identifying the request to approve.
        by: Operator identifier (stored in ``decided_by``), or ``None``.

    Returns:
        Summary dict with ``token``, ``status`` (``"approved"``), and
        ``decided_by``.

    Raises:
        ServiceError: When the token is not found or is not in ``pending`` status.
    """
    row = _get_pending_row(session, token)
    now = datetime.now(UTC)
    row.status = McpApprovalStatus.approved
    row.decided_at = now
    row.decided_by = by
    session.flush()
    return {"token": token, "status": "approved", "decided_by": by}


def deny_request(session: Session, token: str, *, by: str | None) -> dict[str, Any]:
    """Set an approval request's status to denied.

    Args:
        session: Active SQLAlchemy session.
        token: Opaque token identifying the request to deny.
        by: Operator identifier (stored in ``decided_by``), or ``None``.

    Returns:
        Summary dict with ``token``, ``status`` (``"denied"``), and
        ``decided_by``.

    Raises:
        ServiceError: When the token is not found or is not in ``pending`` status.
    """
    row = _get_pending_row(session, token)
    now = datetime.now(UTC)
    row.status = McpApprovalStatus.denied
    row.decided_at = now
    row.decided_by = by
    session.flush()
    return {"token": token, "status": "denied", "decided_by": by}


def list_approval_requests(
    session: Session,
    *,
    status: str | None = None,
) -> dict[str, Any]:
    """List MCP approval requests, optionally filtered by status.

    Args:
        session: Active SQLAlchemy session.
        status: Optional status string (e.g. ``"pending"``, ``"approved"``).
            When ``None``, all requests are returned.

    Returns:
        Dict with ``"approvals"`` key mapping to a list of request summary dicts,
        each containing ``token``, ``tool_name``, ``project_id``, ``status``,
        ``created_at``, ``expires_at``, ``decided_by``.
    """
    query = session.query(McpApprovalRequest)

    if status is not None:
        # Map string to enum value for filtering
        try:
            status_enum = McpApprovalStatus(status)
        except ValueError:
            # Unknown status — return empty list
            return {"approvals": []}
        query = query.filter(McpApprovalRequest.status == status_enum)

    rows = query.order_by(McpApprovalRequest.created_at.desc()).all()

    return {
        "approvals": [
            {
                "token": r.token,
                "tool_name": r.tool_name,
                "project_id": r.project_id,
                "status": r.status.value,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "decided_by": r.decided_by,
            }
            for r in rows
        ]
    }


def _get_pending_row(session: Session, token: str) -> McpApprovalRequest:
    """Fetch a McpApprovalRequest by token and verify it is pending.

    Args:
        session: Active SQLAlchemy session.
        token: Token to look up.

    Returns:
        The ``McpApprovalRequest`` row when found and pending.

    Raises:
        ServiceError: When the token is not found or not in ``pending`` status.
    """
    row = session.query(McpApprovalRequest).filter_by(token=token).one_or_none()
    if row is None:
        raise ServiceError(f"Approval token not found: {token!r}", code=1)
    if row.status != McpApprovalStatus.pending:
        raise ServiceError(
            f"Approval request is not pending (status: {row.status.value!r})",
            code=1,
        )
    return row
