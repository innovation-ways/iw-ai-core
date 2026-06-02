"""I-00089 regression tests: AI Assistant panel collapse button is unusable in both states.

These tests verify:
1. Bug A (AC1): The in-header collapse button is hidden when panel is collapsed
2. Bug B (AC2): The expanded-state collapse button has discoverable affordance
   (title tooltip + distinguishing class marker)
"""

from __future__ import annotations

import os
import re
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient that overrides get_db to use the test db_session.

    Mirrors the canonical pattern from test_chat_panel_default_collapsed.py:25-42.
    """
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            """Yield the test db_session for FastAPI dependency injection."""
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def test_i00089_bug_a_collapse_button_hidden_when_collapsed(client: TestClient) -> None:
    """RED before fix: the in-header '<' collapse button is rendered even when
    the panel is collapsed (data-collapsed='true'), and clicking it is a no-op.

    The fix must ensure the collapse button is not visible (display: none, OR
    not rendered, OR hidden via a 'when-collapsed' class) while the panel is
    in its default collapsed state.
    """
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # The panel is rendered with the default data-collapsed="true" state.
    assert 'id="chat-assistant-panel"' in html
    assert 'data-collapsed="true"' in html

    # S01's fix (Bug A) adds #chat-assistant-collapse-btn to the inline <style>
    # block's display:none selector group. We assert the selector chain is
    # present in the rendered HTML — attribute-scoped regex (not bare substring)
    # so we don't false-positive on e.g. JS source or comments.
    style_block_pattern = re.compile(
        r"#chat-assistant-panel\[data-collapsed=\"true\"\][^{]*"
        r"#chat-assistant-collapse-btn",
        re.DOTALL,
    )
    assert style_block_pattern.search(html), (
        "Expected the panel's inline <style> block to include "
        "#chat-assistant-collapse-btn in the 'display: none when collapsed' "
        "selector group. Bug A is still present."
    )


def test_i00089_bug_b_collapse_button_has_discoverable_affordance(
    client: TestClient,
) -> None:
    """RED before fix: the expanded-state collapse button has no visible weight
    (14 px icon, no border, no tooltip) and is indistinguishable from the three
    toggle icons next to it. The fix must give it a discoverable visual
    treatment AND a tooltip.

    We assert two concrete, semantic markers (per S01's chosen Variant A):
      1. The button carries a `title="Collapse panel"` attribute
         so a mouse hover reveals the action.
      2. The button carries the distinguishing class marker
         `chat-assistant-collapse-btn-distinct` (custom class, not Tailwind
         border utility — per S01 report notes: Variant A chosen).
    """
    response = client.get("/")
    html = response.text

    # Locate the collapse-btn element. Attribute-scoped match (NOT bare
    # substring) per CLAUDE.md's regression-prevention note (I-00067).
    button_match = re.search(
        r'<button[^>]*id="chat-assistant-collapse-btn"[^>]*>',
        html,
    )
    assert button_match is not None, (
        "Expected the chat-assistant-collapse-btn element to be present."
    )
    button_tag = button_match.group(0)

    # (1) The collapse button must have a `title` attribute for hover tooltip.
    # Word-boundary-anchored so we don't match "title" inside aria-label value.
    assert re.search(r'\btitle="[^"]+"', button_tag), (
        "Expected the collapse button to have a `title` attribute for hover "
        "tooltip. Bug B is still present."
    )

    # (2) Variant A from S01: the button carries the custom distinguishing
    # class marker 'chat-assistant-collapse-btn-distinct'. This is NOT a
    # Tailwind border utility — per S01 report notes, the custom class path was
    # chosen over border-l.
    assert "chat-assistant-collapse-btn-distinct" in button_tag, (
        "Expected the collapse button to carry the "
        "'chat-assistant-collapse-btn-distinct' class marker (variant A from S01). "
        "Bug B is still present."
    )
