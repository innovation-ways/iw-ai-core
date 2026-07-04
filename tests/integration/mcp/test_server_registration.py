"""Integration tests for orch.mcp.server — tool registration and e2e smoke test.

Verifies that all 8 read tools and the iwcore_workflow_guide prompt are
registered on the FastMCP server instance, and that a Client round-trip
call returns the expected response shape.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from orch.db.models import Project

_EXPECTED_TOOLS = {
    "project_list",
    "work_item_list",
    "work_item_get",
    "batch_list",
    "batch_status",
    "job_list",
    "worktree_status",
    "daemon_status",
}

_EXPECTED_PROMPT = "iwcore_workflow_guide"


class TestToolRegistration:
    """Covers that all 8 read tools are registered on the server."""

    def test_all_expected_tools_are_registered(self) -> None:
        """Verifies that the mcp server exposes exactly the 8 expected tool names."""
        from orch.mcp.server import mcp

        tools = asyncio.run(mcp.list_tools())
        registered_names = {t.name for t in tools}
        assert registered_names >= _EXPECTED_TOOLS, (
            f"Missing expected tools: {_EXPECTED_TOOLS - registered_names}"
        )

    def test_tools_are_read_only(self) -> None:
        """Verifies that all registered tools have readOnlyHint=True."""
        from orch.mcp.server import mcp

        tools = asyncio.run(mcp.list_tools())
        for tool in tools:
            if tool.name in _EXPECTED_TOOLS:
                assert tool.annotations is not None, f"Tool '{tool.name}' has no annotations"
                assert tool.annotations.readOnlyHint is True, (
                    f"Tool '{tool.name}' readOnlyHint is not True"
                )

    def test_tools_are_not_destructive(self) -> None:
        """Verifies that all registered tools have destructiveHint=False."""
        from orch.mcp.server import mcp

        tools = asyncio.run(mcp.list_tools())
        for tool in tools:
            if tool.name in _EXPECTED_TOOLS:
                assert tool.annotations is not None
                assert tool.annotations.destructiveHint is False, (
                    f"Tool '{tool.name}' destructiveHint is not False"
                )


class TestPromptRegistration:
    """Covers that the iwcore_workflow_guide prompt is registered."""

    def test_workflow_guide_prompt_is_registered(self) -> None:
        """Verifies that the iwcore_workflow_guide prompt is on the server."""
        from orch.mcp.server import mcp

        prompts = asyncio.run(mcp.list_prompts())
        names = {p.name for p in prompts}
        assert {_EXPECTED_PROMPT} <= names, (
            f"Prompt '{_EXPECTED_PROMPT}' not registered; present: {names}"
        )


class TestEndToEndToolCall:
    """Covers end-to-end tool invocation through the FastMCP Client."""

    def test_project_list_via_client(self, db_session: Any, test_project: Project) -> None:
        """Verifies that calling project_list via Client returns the expected shape."""
        from fastmcp import Client

        from orch.mcp.server import mcp

        async def _run() -> Any:
            async with Client(mcp) as client:
                return await client.call_tool("project_list", {})

        result = asyncio.run(_run())
        data = result.data
        matching = [p for p in data["projects"] if p["id"] == test_project.id]
        assert len(matching) == 1, (
            f"expected exactly one project '{test_project.id}' in result: {data}"
        )
        assert matching[0]["display_name"] == test_project.display_name

    def test_work_item_list_via_client_empty(self, db_session: Any, test_project: Project) -> None:
        """Verifies that calling work_item_list via Client for an empty project returns total=0."""
        from fastmcp import Client

        from orch.mcp.server import mcp

        async def _run() -> Any:
            async with Client(mcp) as client:
                return await client.call_tool("work_item_list", {"project_id": test_project.id})

        result = asyncio.run(_run())
        data = result.data
        assert "items" in data
        assert data["total"] == 0
