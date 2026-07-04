"""MCP server entry point for IW AI Core.

Exposes the ``iwcore`` FastMCP server instance (``mcp``) with the 8 read tools
and the ``iwcore_workflow_guide`` prompt registered at import.  The write tools
are registered by :func:`main`, which is wired to the ``iw-mcp`` console-script
entry point in ``pyproject.toml``.

Usage (stdio transport, for MCP clients):

    iw-mcp

The ``iw-mcp`` entry point is the agent-control surface, so it registers the
gated **write** tools **by default** — set ``IW_CORE_MCP_ENABLE_WRITE_TOOLS=false``
in its environment to run a strictly read-only server instead.  Write tools are
still individually governed by the per-project Deny→Ask→Allow policy engine, so
"registered" does not mean "unconditionally executable".

The server uses the standard ``iw_cli_orch_bridge`` context so the live-DB
guard permits connections from this process, exactly as the ``iw`` CLI does.
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from orch.mcp import prompts
from orch.mcp.tools import read_tools, write_tools

#: Environment variable that gates write-tool registration.
_WRITE_TOOLS_ENV_VAR = "IW_CORE_MCP_ENABLE_WRITE_TOOLS"

#: The FastMCP server instance.  Imported by tests to inspect registrations.
mcp: FastMCP = FastMCP("iwcore")

# Register read tools and prompts at module load time so ``mcp`` is populated
# when tests import this module.  Write tools are registered in ``main`` (gated
# by the enable flag) so the ``iw-mcp`` entry point can default the flag on
# before registration runs.
read_tools.register(mcp)
prompts.register(mcp)


def main() -> None:
    """Launch the IW AI Core MCP server over stdio.

    Defaults ``IW_CORE_MCP_ENABLE_WRITE_TOOLS`` to ``"true"`` when the operator
    has not set it explicitly — the ``iw-mcp`` entry point is the agent-control
    surface and is writable by default (set the flag to ``false`` for a
    read-only server).  Registers the write tools (a no-op when the flag is
    falsey), then opens the ``iw_cli_orch_bridge`` context for the process
    lifetime so the live-DB guard permits database connections, and starts the
    FastMCP server.
    """
    from orch.db.live_db_guard import iw_cli_orch_bridge  # noqa: PLC0415

    # iw-mcp is writable by default; an explicit falsey value still opts out.
    os.environ.setdefault(_WRITE_TOOLS_ENV_VAR, "true")
    write_tools.register(mcp)

    with iw_cli_orch_bridge():
        mcp.run()
