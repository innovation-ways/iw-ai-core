"""MCP audit logging — argument scrubbing and append-only audit trail.

Provides two public functions:

- :func:`scrub_arguments` — redact sensitive key values from a tool-argument
  dict before storing or logging.
- :func:`record_audit` — insert one ``McpAuditLog`` row in its own DB session
  so the audit persists even when the surrounding tool transaction rolled back.

The audit subsystem is designed to never surface failures to callers: any
error opening a DB session or writing the audit row is caught, logged as a
warning, and silently swallowed so the tool invocation is unaffected.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Key substrings that trigger value redaction (matched case-insensitively).
_SENSITIVE_KEY_SUBSTRINGS = frozenset(
    {"password", "token", "secret", "api_key", "apikey", "credential"}
)


def scrub_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of args with sensitive values replaced by ``'***'``.

    Recursively descends into nested dicts.  A key is considered sensitive
    when its lowercased form contains any of: ``password``, ``token``,
    ``secret``, ``api_key``, ``apikey``, ``credential``.

    The original dict is not mutated — a shallow copy of each level is made.

    Args:
        args: Tool argument dict to scrub.

    Returns:
        New dict where sensitive values are replaced with ``'***'``.
    """
    result: dict[str, Any] = {}
    for key, value in args.items():
        if _is_sensitive_key(key):
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = scrub_arguments(value)
        else:
            result[key] = value
    return result


def _is_sensitive_key(key: str) -> bool:
    """Return True when key contains a sensitive substring (case-insensitive).

    Args:
        key: Dict key to test.

    Returns:
        True when the lowercased key contains any sensitive substring.
    """
    lowered = key.lower()
    return any(substr in lowered for substr in _SENSITIVE_KEY_SUBSTRINGS)


def record_audit(
    *,
    tool_name: str,
    project_id: str | None,
    arguments: dict[str, Any],
    outcome: str,
    decision: str | None = None,
    result_summary: str | None = None,
    error: str | None = None,
    actor: str | None = None,
) -> None:
    """Insert one McpAuditLog row, opening its own DB session.

    The audit row is written in an independent session so it persists even
    when the caller's own transaction rolled back.  Any failure here is caught
    and logged as a warning — audit errors must never propagate to the caller.

    Arguments are scrubbed via :func:`scrub_arguments` before storage.

    Args:
        tool_name: Name of the MCP tool being audited.
        project_id: Project scope, or ``None`` for non-project-scoped tools.
        arguments: Raw tool arguments dict (will be scrubbed before storing).
        outcome: Result category string (``"success"``, ``"error"``, etc.).
        decision: Optional policy decision string (``"allow"``/``"ask"``/``"deny"``).
        result_summary: Optional short human-readable summary of the outcome.
        error: Error message when outcome is ``"error"``.
        actor: Optional client/agent identifier.
    """
    # Scrub first — even if DB write fails we never log raw sensitive args.
    scrubbed = scrub_arguments(arguments)

    try:
        # Import inside function to keep module import lightweight and allow
        # test injection via set_session_factory.
        from orch.db.models import McpAuditLog  # noqa: PLC0415
        from orch.mcp.context import session_scope  # noqa: PLC0415

        with session_scope() as session:
            row = McpAuditLog(
                tool_name=tool_name,
                project_id=project_id,
                actor=actor,
                arguments=scrubbed,
                decision=decision,
                outcome=outcome,
                result_summary=result_summary,
                error=error,
            )
            session.add(row)
            session.flush()
    except Exception:  # noqa: BLE001
        # Audit failure must NEVER break the tool call — swallow + warn only.
        logger.warning(
            "MCP audit write failed for tool=%s outcome=%s", tool_name, outcome, exc_info=True
        )
