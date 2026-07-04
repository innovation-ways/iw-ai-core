"""MCP policy engine — resolves effective allow/ask/deny for a given tool invocation.

Provides:
- ``TOOL_TIERS`` — maps every write/gated tool name to its blast-radius tier (1–3).
- ``TIER_DEFAULTS`` — the built-in default decision for each tier.
- ``resolve_policy_decision`` — looks up the effective decision in priority order.

Precedence (first match wins):
  1. DB ``McpPolicy`` row matching ``(project_id, tool_name)`` — highest priority.
  2. ``Project.config['mcp_policy']`` dict, with internal key priority:
       exact tool name > ``"tier2"`` / ``"tier3"`` tier key > ``"default"`` key.
     Unknown decision strings in the config are ignored (fall through to next layer).
  3. Built-in ``TIER_DEFAULTS[TOOL_TIERS.get(tool_name, 2)]`` — lowest priority.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import McpPolicyDecision

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Tier mapping — blast-radius classification of write/gated tools
# ---------------------------------------------------------------------------

#: Maps every write/gated tool name to its blast-radius tier.
TOOL_TIERS: dict[str, int] = {
    # Tier 1 — low blast radius, sequential/idempotent
    "work_item_next_id": 1,
    "work_item_register": 1,
    # Tier 2 — moderate blast radius, workflow mutations
    "work_item_approve": 2,
    "batch_create": 2,
    "batch_approve": 2,
    "batch_control": 2,
    "item_retry": 2,
    # Tier 3 — high blast radius, irreversible or destructive
    "approve_merge": 3,
    "batch_cancel": 3,
    "work_item_archive": 3,
    "work_item_cancel": 3,
}

#: Built-in default decision for each tier.
TIER_DEFAULTS: dict[int, McpPolicyDecision] = {
    0: McpPolicyDecision.allow,
    1: McpPolicyDecision.allow,
    2: McpPolicyDecision.ask,
    3: McpPolicyDecision.deny,
}

#: Maps project config tier keys to their tier numbers.
_TIER_KEY_TO_INT: dict[str, int] = {
    "tier1": 1,
    "tier2": 2,
    "tier3": 3,
}

#: Valid policy decision string values from config.
_VALID_DECISIONS: dict[str, McpPolicyDecision] = {
    "allow": McpPolicyDecision.allow,
    "ask": McpPolicyDecision.ask,
    "deny": McpPolicyDecision.deny,
}


def resolve_policy_decision(
    session: Session,
    project_id: str | None,
    tool_name: str,
) -> McpPolicyDecision:
    """Resolve the effective policy decision for a given MCP tool invocation.

    Checks three priority layers in order, returning the first match found:

    1. **DB McpPolicy row** — a ``McpPolicy`` row matching ``(project_id, tool_name)``
       in the database.  Requires ``project_id`` to be non-None; if it is ``None``
       this layer is skipped.

    2. **Project.config['mcp_policy']** — a dict on the project's ``config`` JSONB
       column, keyed by ``'mcp_policy'``.  Within this dict, sub-keys are resolved
       in the following priority order (first valid match wins):

       - Exact tool name (e.g. ``"batch_create": "allow"``).
       - Tier key ``"tier2"`` or ``"tier3"`` (matching the tool's tier).
       - General ``"default"`` key.

       Unknown/misspelled decision strings (anything other than ``"allow"``,
       ``"ask"``, ``"deny"``) are silently ignored — the layer falls through.
       Requires ``project_id`` to be non-None and the project row to exist.

    3. **Built-in tier defaults** — ``TIER_DEFAULTS[TOOL_TIERS.get(tool_name, 2)]``.
       Unknown tool names default to Tier 2 (ask).

    Args:
        session: Active SQLAlchemy session used for DB lookups.
        project_id: Project scope, or ``None`` for non-project-scoped contexts.
            When ``None``, layers 1 and 2 are skipped.
        tool_name: The MCP tool name being invoked.

    Returns:
        The effective ``McpPolicyDecision`` for this (project, tool) pair.
    """
    if project_id is not None:
        # --- Layer 1: DB McpPolicy row ---
        db_decision = _lookup_db_policy(session, project_id, tool_name)
        if db_decision is not None:
            return db_decision

        # --- Layer 2: Project.config['mcp_policy'] dict ---
        config_decision = _lookup_config_policy(session, project_id, tool_name)
        if config_decision is not None:
            return config_decision

    # --- Layer 3: Built-in tier defaults ---
    tier = TOOL_TIERS.get(tool_name, 2)
    return TIER_DEFAULTS[tier]


def _lookup_db_policy(
    session: Session,
    project_id: str,
    tool_name: str,
) -> McpPolicyDecision | None:
    """Look up a McpPolicy row for (project_id, tool_name).

    Args:
        session: Active SQLAlchemy session.
        project_id: Project identifier to filter on.
        tool_name: Tool name to look up.

    Returns:
        The ``McpPolicyDecision`` from the row, or ``None`` if no row exists.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from orch.db.models import McpPolicy  # noqa: PLC0415

    row = session.execute(
        select(McpPolicy).where(
            McpPolicy.project_id == project_id,
            McpPolicy.tool_name == tool_name,
        )
    ).scalar_one_or_none()

    if row is None:
        return None
    return row.decision


def _lookup_config_policy(
    session: Session,
    project_id: str,
    tool_name: str,
) -> McpPolicyDecision | None:
    """Look up an effective decision from Project.config['mcp_policy'].

    Applies internal priority: exact tool name > tier key > 'default' key.
    Invalid decision strings are silently ignored (returns None for that key).

    Args:
        session: Active SQLAlchemy session.
        project_id: Project identifier to look up config for.
        tool_name: Tool name to resolve policy for.

    Returns:
        The resolved ``McpPolicyDecision``, or ``None`` when no valid config
        override applies.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from orch.db.models import Project  # noqa: PLC0415

    project = session.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()

    if project is None:
        return None

    config = project.config
    if not isinstance(config, dict):
        return None

    policy_dict = config.get("mcp_policy")
    if not isinstance(policy_dict, dict):
        return None

    tool_tier = TOOL_TIERS.get(tool_name, 2)

    # Priority 1: exact tool name key
    if tool_name in policy_dict:
        decision = _parse_decision_string(policy_dict[tool_name])
        if decision is not None:
            return decision

    # Priority 2: tier key (e.g. "tier2", "tier3")
    tier_key = f"tier{tool_tier}"
    if tier_key in policy_dict:
        decision = _parse_decision_string(policy_dict[tier_key])
        if decision is not None:
            return decision

    # Priority 3: "default" key
    if "default" in policy_dict:
        decision = _parse_decision_string(policy_dict["default"])
        if decision is not None:
            return decision

    return None


def _parse_decision_string(value: object) -> McpPolicyDecision | None:
    """Parse a config value string into a McpPolicyDecision, or return None if invalid.

    Args:
        value: The raw config value to parse (expected to be a string).

    Returns:
        The corresponding ``McpPolicyDecision``, or ``None`` when the value is
        not a recognised decision string.
    """
    if not isinstance(value, str):
        return None
    return _VALID_DECISIONS.get(value.strip().lower())
