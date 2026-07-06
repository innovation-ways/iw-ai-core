"""MCP server entry point for IW AI Core.

Exposes the ``iwcore`` FastMCP server instance (``mcp``) with the 8 read tools
and the ``iwcore_workflow_guide`` prompt registered at import.  The write tools
are registered by :func:`main`, which is wired to the ``iw-mcp`` console-script
entry point in ``pyproject.toml``.

Two transports are supported:

- **stdio** (default) — the MCP client launches this process as a child and
  talks over stdin/stdout.  Server and client are co-located.
- **http** — this process runs as a long-lived, independent network service and
  clients connect to ``http://<host>:<port>/mcp/``.  Use this to run ONE server
  on the same host as the daemon while remote clients (a laptop, a container)
  connect over the network with no filesystem access.

Transport is chosen by :func:`main` args, else the ``IW_CORE_MCP_TRANSPORT`` env
var (``stdio`` | ``http``), defaulting to ``stdio`` for backward compatibility.

Usage::

    iw-mcp                                   # stdio (default)
    IW_CORE_MCP_TRANSPORT=http iw-mcp        # HTTP via env
    iw mcp serve --http --host 0.0.0.0 --port 9901   # HTTP via CLI flags

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

#: Environment variables selecting the transport and HTTP bind address.
_TRANSPORT_ENV_VAR = "IW_CORE_MCP_TRANSPORT"
_HTTP_HOST_ENV_VAR = "IW_CORE_MCP_HTTP_HOST"
_HTTP_PORT_ENV_VAR = "IW_CORE_MCP_HTTP_PORT"

#: Defaults for the HTTP transport.
_DEFAULT_HTTP_HOST = "127.0.0.1"
_DEFAULT_HTTP_PORT = 9901

#: The FastMCP server instance.  Imported by tests to inspect registrations.
mcp: FastMCP = FastMCP("iwcore")

# Register read tools and prompts at module load time so ``mcp`` is populated
# when tests import this module.  Write tools are registered in ``main`` (gated
# by the enable flag) so the ``iw-mcp`` entry point can default the flag on
# before registration runs.
read_tools.register(mcp)
prompts.register(mcp)


def resolve_transport(
    transport: str | None,
    host: str | None,
    port: int | None,
) -> tuple[str, str, int]:
    """Resolve the effective transport and HTTP bind address.

    Explicit arguments win over environment variables, which win over the
    built-in defaults (``stdio`` transport; ``127.0.0.1:9901`` for HTTP).

    Args:
        transport: ``"stdio"`` or ``"http"``, or ``None`` to read the env/default.
        host: HTTP bind host, or ``None`` to read the env/default.
        port: HTTP bind port, or ``None`` to read the env/default.

    Returns:
        A ``(transport, host, port)`` tuple. ``host``/``port`` are only
        meaningful when ``transport == "http"``.

    Raises:
        ValueError: If the resolved transport is not ``"stdio"`` or ``"http"``,
            or the resolved port is not a valid integer.
    """
    resolved = (transport or os.environ.get(_TRANSPORT_ENV_VAR) or "stdio").strip().lower()
    if resolved not in {"stdio", "http"}:
        raise ValueError(f"Unknown MCP transport {resolved!r}; expected 'stdio' or 'http'")

    resolved_host = host or os.environ.get(_HTTP_HOST_ENV_VAR) or _DEFAULT_HTTP_HOST
    if port is not None:
        resolved_port = port
    else:
        raw_port = os.environ.get(_HTTP_PORT_ENV_VAR)
        try:
            resolved_port = int(raw_port) if raw_port else _DEFAULT_HTTP_PORT
        except ValueError as exc:
            raise ValueError(
                f"Invalid {_HTTP_PORT_ENV_VAR}={raw_port!r}; must be an integer"
            ) from exc

    return resolved, resolved_host, resolved_port


def main(
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Launch the IW AI Core MCP server over the selected transport.

    Defaults ``IW_CORE_MCP_ENABLE_WRITE_TOOLS`` to ``"true"`` when the operator
    has not set it explicitly — the ``iw-mcp`` entry point is the agent-control
    surface and is writable by default (set the flag to ``false`` for a
    read-only server).  Registers the write tools (a no-op when the flag is
    falsey), then opens the ``iw_cli_orch_bridge`` context for the process
    lifetime so the live-DB guard permits database connections, and starts the
    FastMCP server on the resolved transport.

    Args:
        transport: ``"stdio"`` or ``"http"``; ``None`` reads
            ``IW_CORE_MCP_TRANSPORT`` (default ``"stdio"``).
        host: HTTP bind host; ``None`` reads ``IW_CORE_MCP_HTTP_HOST``
            (default ``127.0.0.1``).  Ignored for stdio.
        port: HTTP bind port; ``None`` reads ``IW_CORE_MCP_HTTP_PORT``
            (default ``9901``).  Ignored for stdio.
    """
    from orch.db.live_db_guard import iw_cli_orch_bridge  # noqa: PLC0415

    # iw-mcp is writable by default; an explicit falsey value still opts out.
    os.environ.setdefault(_WRITE_TOOLS_ENV_VAR, "true")
    write_tools.register(mcp)

    resolved_transport, resolved_host, resolved_port = resolve_transport(transport, host, port)

    with iw_cli_orch_bridge():
        if resolved_transport == "http":
            mcp.run(transport="http", host=resolved_host, port=resolved_port)
        else:
            mcp.run()
