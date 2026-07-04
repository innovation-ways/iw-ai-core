"""Fixtures for MCP integration tests.

Sets up the MCP session factory override so tool handlers use the testcontainer
session instead of the live orch DB.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _mcp_session_factory(cli_get_session: Any) -> Generator[None, None, None]:
    """Inject the testcontainer session into MCP tool handlers before each test.

    Calls :func:`orch.mcp.context.set_session_factory` with the test-scoped
    ``cli_get_session`` fixture so no tool handler can reach the live orch DB.
    Clears the override after the test via ``reset_session_factory``.

    Args:
        cli_get_session: Function-scoped factory yielding the testcontainer
            ``db_session``.

    Yields:
        Nothing — the fixture acts as setup/teardown.
    """
    from orch.mcp.context import reset_session_factory, set_session_factory

    set_session_factory(cli_get_session)
    yield
    reset_session_factory()
