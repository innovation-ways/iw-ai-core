"""Standalone verifier for a running IW AI Core MCP HTTP server.

Connects as an MCP client over HTTP, lists the tools, and calls ``daemon_status``,
then prints a short summary and exits 0 when the handshake succeeds and the daemon
reports ``running`` (non-zero otherwise). Invoked by ``./ai-core.sh mcp verify``.
"""

from __future__ import annotations

import asyncio
import sys

#: Write tools whose presence confirms the server is the agent-control surface.
_REQUIRED_WRITE_TOOLS = {"work_item_register", "work_item_approve", "batch_create"}


async def _verify(url: str) -> bool:
    """Connect to the MCP server at ``url`` and report tool + daemon status.

    Args:
        url: The MCP HTTP endpoint, e.g. ``http://127.0.0.1:9901/mcp/``.

    Returns:
        True when the handshake succeeds and the daemon reports ``running``.
    """
    from fastmcp import Client  # noqa: PLC0415

    async with Client(url) as client:
        tool_names = {t.name for t in await client.list_tools()}
        result = await client.call_tool("daemon_status", {})
        data = result.data
        status = data.get("status")
        source = data.get("liveness_source")
        writes_present = tool_names >= _REQUIRED_WRITE_TOOLS
        print(f"  endpoint    : {url}")
        print(f"  tools       : {len(tool_names)}")
        print(f"  write tools : {'present' if writes_present else 'MISSING'}")
        print(f"  daemon      : {status} ({source})")
        return bool(status == "running")


def main() -> int:
    """Verify the MCP server whose URL is passed as ``argv[1]``.

    Returns:
        0 on success, 1 on failure, 2 on bad usage.
    """
    if len(sys.argv) < 2:
        print("usage: mcp_verify.py <url>", file=sys.stderr)
        return 2
    try:
        ok = asyncio.run(_verify(sys.argv[1]))
    except Exception as exc:  # noqa: BLE001 — surface any client/transport error as failure
        print(f"  ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
