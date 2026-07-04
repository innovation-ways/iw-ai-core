"""Runtime configuration for the IW AI Core MCP server.

Provides feature-flag helpers read from environment variables so that
write tools can be enabled/disabled without restarting the process.
"""

from __future__ import annotations

import os

#: Environment variable name that enables gated write tools.
_WRITE_TOOLS_ENV_VAR = "IW_CORE_MCP_ENABLE_WRITE_TOOLS"

#: Environment variable name for approval request TTL in seconds.
_APPROVAL_TTL_ENV_VAR = "IW_CORE_MCP_APPROVAL_TTL_SECONDS"

#: Default TTL for approval requests (1 hour).
_DEFAULT_APPROVAL_TTL_SECONDS = 3600

#: Canonical truthy strings accepted from the environment (case-insensitive).
_TRUTHY_VALUES = frozenset({"1", "true", "yes"})


def write_tools_enabled() -> bool:
    """Return True when write tools are enabled via the environment flag.

    Reads ``IW_CORE_MCP_ENABLE_WRITE_TOOLS`` from the process environment.
    Accepts ``"1"``, ``"true"``, or ``"yes"`` (case-insensitive) as truthy;
    any other value (including absent) is treated as False (disabled).

    Returns:
        ``True`` when the env var is set to a truthy value, ``False`` otherwise.
    """
    raw = os.environ.get(_WRITE_TOOLS_ENV_VAR, "")
    return raw.strip().lower() in _TRUTHY_VALUES


def approval_ttl_seconds() -> int:
    """Return the TTL in seconds for MCP approval requests.

    Reads ``IW_CORE_MCP_APPROVAL_TTL_SECONDS`` from the process environment.
    Accepts any positive integer string; falls back to the default of 3600
    (one hour) when the variable is absent or not a valid positive integer.

    Returns:
        TTL in seconds as an integer (>= 1).
    """
    raw = os.environ.get(_APPROVAL_TTL_ENV_VAR, "")
    try:
        value = int(raw.strip())
        if value > 0:
            return value
    except (ValueError, AttributeError):
        pass
    return _DEFAULT_APPROVAL_TTL_SECONDS
