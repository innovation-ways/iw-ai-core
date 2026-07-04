"""MCP server entry point for IW AI Core.

Exposes the ``iwcore`` FastMCP server instance (``mcp``) with 8 read-only
tools and the ``iwcore_workflow_guide`` prompt.  The ``main`` function is
wired to the ``iw-mcp`` console-script entry point in ``pyproject.toml``.

Usage (stdio transport, for MCP clients):

    iw-mcp

The server uses the standard ``iw_cli_orch_bridge`` context so the live-DB
guard permits connections from this process, exactly as the ``iw`` CLI does.
"""

from __future__ import annotations

from fastmcp import FastMCP

from orch.mcp import prompts
from orch.mcp.tools import read_tools, write_tools

#: The FastMCP server instance.  Imported by tests to inspect registrations.
mcp: FastMCP = FastMCP("iwcore")

# Register tools and prompts at module load time so ``mcp`` is fully
# configured when tests import this module.
read_tools.register(mcp)
write_tools.register(mcp)
prompts.register(mcp)


def main() -> None:
    """Launch the IW AI Core MCP server over stdio.

    Opens the ``iw_cli_orch_bridge`` context for the process lifetime so the
    live-DB guard permits database connections, then starts the FastMCP
    server.  Intended to be called by the ``iw-mcp`` console-script entry
    point.
    """
    from orch.db.live_db_guard import iw_cli_orch_bridge  # noqa: PLC0415

    with iw_cli_orch_bridge():
        mcp.run()
