"""Integration tests for write tool gating — IW_CORE_MCP_ENABLE_WRITE_TOOLS flag.

Verifies that register(mcp) adds write tools ONLY when the enable flag is set,
and registers ZERO write tools when unset.  Uses FastMCP introspection matching
the approach of test_server_registration.py.
"""

from __future__ import annotations

import asyncio

import pytest

_EXPECTED_WRITE_TOOLS = {
    "work_item_next_id",
    "work_item_register",
    "work_item_approve",
    "batch_create",
    "batch_approve",
    "batch_control",
    "item_retry",
    # Tier-3 tools
    "approve_merge",
    "batch_cancel",
    "work_item_archive",
    "work_item_cancel",
}

_EXPECTED_TIER3_TOOLS = {
    "approve_merge",
    "batch_cancel",
    "work_item_archive",
    "work_item_cancel",
}


class TestWriteToolGating:
    """Covers registration gating based on IW_CORE_MCP_ENABLE_WRITE_TOOLS."""

    def test_write_tools_absent_when_flag_unset(self, monkeypatch: pytest.MonkeyPatch):
        """Verifies that register() adds zero write tools when the env flag is absent."""
        from fastmcp import FastMCP

        from orch.mcp.tools import write_tools

        monkeypatch.delenv("IW_CORE_MCP_ENABLE_WRITE_TOOLS", raising=False)

        fresh_mcp = FastMCP("test-unset")
        write_tools.register(fresh_mcp)
        tools = asyncio.run(fresh_mcp.list_tools())
        registered_names = {t.name for t in tools}
        assert registered_names.isdisjoint(_EXPECTED_WRITE_TOOLS), (
            f"Write tools leaked when flag is unset: {_EXPECTED_WRITE_TOOLS & registered_names}"
        )

    def test_write_tools_present_when_flag_is_true(self, monkeypatch: pytest.MonkeyPatch):
        """Verifies that register() adds all write tools when the env flag is 'true'."""
        from fastmcp import FastMCP

        from orch.mcp.tools import write_tools

        monkeypatch.setenv("IW_CORE_MCP_ENABLE_WRITE_TOOLS", "true")

        fresh_mcp = FastMCP("test-enabled")
        write_tools.register(fresh_mcp)
        tools = asyncio.run(fresh_mcp.list_tools())
        registered_names = {t.name for t in tools}
        assert registered_names >= _EXPECTED_WRITE_TOOLS, (
            f"Missing write tools when flag='true': {_EXPECTED_WRITE_TOOLS - registered_names}"
        )

    def test_write_tools_present_when_flag_is_1(self, monkeypatch: pytest.MonkeyPatch):
        """Verifies that register() adds all write tools when the env flag is '1'."""
        from fastmcp import FastMCP

        from orch.mcp.tools import write_tools

        monkeypatch.setenv("IW_CORE_MCP_ENABLE_WRITE_TOOLS", "1")

        fresh_mcp = FastMCP("test-enabled-1")
        write_tools.register(fresh_mcp)
        tools = asyncio.run(fresh_mcp.list_tools())
        registered_names = {t.name for t in tools}
        assert registered_names >= _EXPECTED_WRITE_TOOLS, (
            f"Missing write tools when flag='1': {_EXPECTED_WRITE_TOOLS - registered_names}"
        )

    def test_write_tools_present_when_flag_is_yes(self, monkeypatch: pytest.MonkeyPatch):
        """Verifies that register() adds all write tools when the env flag is 'yes'."""
        from fastmcp import FastMCP

        from orch.mcp.tools import write_tools

        monkeypatch.setenv("IW_CORE_MCP_ENABLE_WRITE_TOOLS", "yes")

        fresh_mcp = FastMCP("test-enabled-yes")
        write_tools.register(fresh_mcp)
        tools = asyncio.run(fresh_mcp.list_tools())
        registered_names = {t.name for t in tools}
        assert registered_names >= _EXPECTED_WRITE_TOOLS, (
            f"Missing write tools when flag='yes': {_EXPECTED_WRITE_TOOLS - registered_names}"
        )

    def test_write_tools_absent_when_flag_is_false(self, monkeypatch: pytest.MonkeyPatch):
        """Verifies that register() adds zero write tools when the env flag is 'false'."""
        from fastmcp import FastMCP

        from orch.mcp.tools import write_tools

        monkeypatch.setenv("IW_CORE_MCP_ENABLE_WRITE_TOOLS", "false")

        fresh_mcp = FastMCP("test-disabled")
        write_tools.register(fresh_mcp)
        tools = asyncio.run(fresh_mcp.list_tools())
        registered_names = {t.name for t in tools}
        assert registered_names.isdisjoint(_EXPECTED_WRITE_TOOLS), (
            f"Write tools leaked when flag='false': {_EXPECTED_WRITE_TOOLS & registered_names}"
        )

    def test_write_tools_are_not_read_only(self, monkeypatch: pytest.MonkeyPatch):
        """Verifies that registered write tools have readOnlyHint=False."""
        from fastmcp import FastMCP

        from orch.mcp.tools import write_tools

        monkeypatch.setenv("IW_CORE_MCP_ENABLE_WRITE_TOOLS", "true")

        fresh_mcp = FastMCP("test-annotations")
        write_tools.register(fresh_mcp)
        tools = asyncio.run(fresh_mcp.list_tools())
        for tool in tools:
            if tool.name in _EXPECTED_WRITE_TOOLS:
                assert tool.annotations is not None, f"Write tool '{tool.name}' has no annotations"
                assert tool.annotations.readOnlyHint is False, (
                    f"Write tool '{tool.name}' should have readOnlyHint=False"
                )
