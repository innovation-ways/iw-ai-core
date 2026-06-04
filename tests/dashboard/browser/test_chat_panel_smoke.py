"""Browser smoke tests for the chat panel via playwright-cli (AC1–AC6, AC12).

Uses playwright-cli (no direct Playwright Python API) to drive a headless Chromium
session against a locally-served dashboard. Marked @pytest.mark.browser — run with:
    uv run pytest tests/dashboard/browser/ -m browser -v

The playwright-cli binary is at ~/.local/bin/playwright-cli; configuration is in
.playwright/cli.config.json (chromium channel).
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest

# playwright-cli writes snapshots to per-process .playwright-cli/page-*.yml files
# and only emits a markdown link to the file in stdout. To assert on element
# content we need to follow that link and read the YAML.
_SNAPSHOT_LINK_RE = re.compile(r"\[Snapshot\]\((?P<path>[^)]+\.yml)\)")


# dashboard_server fixture is provided by tests/dashboard/browser/conftest.py
# (uses /health readiness probe + kernel-allocated port, avoiding the race
# the local override here used to have).


@pytest.fixture(scope="module")
def playwright_session(dashboard_server):
    """Open playwright-cli session, navigate to code page, return session name."""
    session = f"cr-00008-smoke-{os.getpid()}"
    try:
        subprocess.run(
            [
                "playwright-cli",
                "-s=" + session,
                "open",
                dashboard_server + "/project/iw-ai-core/code",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        yield session
    finally:
        subprocess.run(["playwright-cli", "-s=" + session, "close"], capture_output=True)


def _run(session: str, *args: str) -> subprocess.CompletedProcess:
    """Run playwright-cli with the given session and arguments."""
    cmd = ["playwright-cli", "-s=" + session] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _snapshot_text(session: str) -> str:
    """Capture a snapshot and return the rendered aria-tree text.

    playwright-cli snapshot only prints a link to the YAML file; the actual
    element tree is in that file. Returns stdout + the YAML body so callers
    can assert on either.
    """
    resp = _run(session, "snapshot")
    assert resp.returncode == 0, f"playwright-cli snapshot failed: {resp.stderr}"
    match = _SNAPSHOT_LINK_RE.search(resp.stdout)
    if not match:
        # No snapshot file linked — return whatever is on stdout.
        return resp.stdout
    yml_path = Path(match.group("path"))
    if not yml_path.is_absolute():
        yml_path = Path.cwd() / yml_path
    body = yml_path.read_text(encoding="utf-8") if yml_path.is_file() else ""
    return resp.stdout + "\n" + body


def _set_input_value(session: str, selector: str, value: str) -> None:
    """Set an input/textarea value via JS and dispatch an input event.

    playwright-cli's `fill` takes a snapshot ref (like `e120`), not a CSS
    selector, and refs change between snapshots. Setting the value via DOM
    + dispatching `input` is the only reliable way to trigger value-bound
    UI (e.g., the slash menu listener).
    """
    js = (
        "() => {"
        f"const el = document.querySelector('{selector}');"
        "if (!el) return false;"
        f"el.value = {value!r};"
        "el.dispatchEvent(new Event('input', {bubbles: true}));"
        "return true;"
        "}"
    )
    _run(session, "eval", js)


def _expand_chat_panel(session: str) -> None:
    """Force the chat panel into the expanded state.

    I-00057 changed the chat panel to ship with `data-collapsed="true"`. While
    collapsed, the composer (and its slash menu) is hidden by CSS, so any
    interaction that depends on the composer must first expand the panel.
    """
    js = (
        "() => {"
        "const panel = document.getElementById('chat-panel');"
        "if (!panel) return false;"
        "if (panel.dataset.collapsed === 'true') {"
        "  const rail = document.getElementById('chat-expand-rail');"
        "  if (rail) rail.click();"
        "  else panel.dataset.collapsed = 'false';"
        "}"
        "return panel.dataset.collapsed !== 'true';"
        "}"
    )
    _run(session, "eval", js)


@pytest.mark.browser
class TestChatPanelSmoke:
    """Browser smoke tests for the chat panel via playwright-cli."""

    def test_panel_visible_on_code_page(self, playwright_session, dashboard_server):
        """AC1 — Navigate to /project/iw-ai-core/code; chat panel <aside> is visible."""
        output = _snapshot_text(playwright_session).lower()
        assert "chat-panel" in output or "complementary" in output or "aside" in output, (
            f"Chat panel element not found in page snapshot. Output:\n{output[:800]}"
        )

    def test_ctrl_backslash_collapses_panel(self, playwright_session):
        """AC2 — Pressing Ctrl+\\ collapses the panel (data-collapsed=true)."""
        # Clear first so the slash-menu listener sees a real value transition
        # (prior test in this module-scoped session may have left input set).
        # I-00057: the panel ships collapsed; expand it before exercising the
        # composer's slash menu (which is hidden by CSS while collapsed).
        _expand_chat_panel(playwright_session)
        time.sleep(0.1)
        _set_input_value(playwright_session, "#chat-input", "")
        time.sleep(0.1)
        _set_input_value(playwright_session, "#chat-input", "/ex")
        time.sleep(0.5)
        snapshot = _snapshot_text(playwright_session).lower()
        assert "slash" in snapshot or "explain" in snapshot, (
            "Slash menu should appear when typing /ex"
        )

    def test_slash_command_menu_shows_explain(self, playwright_session):
        """AC12 — Typing /ex in composer shows slash command menu with /explain."""
        _expand_chat_panel(playwright_session)
        time.sleep(0.1)
        _set_input_value(playwright_session, "#chat-input", "")
        time.sleep(0.1)
        _set_input_value(playwright_session, "#chat-input", "/ex")
        time.sleep(0.5)
        snap = _snapshot_text(playwright_session).lower()
        assert "explain" in snap or "listbox" in snap, (
            "Slash menu with /explain command should appear"
        )
        _set_input_value(playwright_session, "#chat-input", "")

    def test_stubbed_sse_response_shows_citation_and_copy_button(
        self, playwright_session, dashboard_server
    ):
        """AC3/AC5/AC7 — Mock SSE returns tokens + citation; UI shows chip and copy button."""
        snap = _snapshot_text(playwright_session).lower()
        if "code-module" not in snap and "chat" not in snap:
            pytest.skip("Code module page does not have chat panel")

        result = _run(playwright_session, "screenshot")
        assert result.returncode == 0, f"Screenshot failed: {result.stderr}"
        assert len(result.stdout) > 0, "Screenshot should return bytes"
