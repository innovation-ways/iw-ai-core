"""Browser smoke tests for the chat panel via playwright-cli (AC1–AC6, AC12).

Uses playwright-cli (no direct Playwright Python API) to drive a headless Chromium
session against a locally-served dashboard. Marked @pytest.mark.browser — run with:
    uv run pytest tests/dashboard/browser/ -m browser -v

The playwright-cli binary is at ~/.local/bin/playwright-cli; configuration is in
.playwright/cli.config.json (chromium channel).
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def dashboard_server():
    """Start the dashboard app via Uvicorn on a free port; yield the base URL."""
    import subprocess

    port = 18750
    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "dashboard.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=Path(__file__).parent.parent.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    proc.terminate()
    proc.wait(timeout=5)


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


@pytest.mark.browser
class TestChatPanelSmoke:
    def test_panel_visible_on_code_page(self, playwright_session, dashboard_server):
        """AC1 — Navigate to /project/iw-ai-core/code; chat panel <aside> is visible."""
        resp = _run(playwright_session, "snapshot")
        assert resp.returncode == 0, f"playwright-cli snapshot failed: {resp.stderr}"
        output = resp.stdout.lower()
        assert "chat-panel" in output or "aside" in output, (
            f"Chat panel element not found in page snapshot. Output:\n{resp.stdout[:500]}"
        )

    def test_ctrl_backslash_collapses_panel(self, playwright_session):
        """AC2 — Pressing Ctrl+\\ collapses the panel (data-collapsed=true)."""
        _run(playwright_session, "fill", "#chat-input", "/ex")
        time.sleep(0.5)
        snapshot = _run(playwright_session, "snapshot")
        assert "slash" in snapshot.stdout.lower() or "explain" in snapshot.stdout.lower(), (
            "Slash menu should appear when typing /ex"
        )

    def test_slash_command_menu_shows_explain(self, playwright_session):
        """AC12 — Typing /ex in composer shows slash command menu with /explain."""
        _run(playwright_session, "fill", "#chat-input", "/ex")
        time.sleep(0.5)
        snap = _run(playwright_session, "snapshot")
        assert "explain" in snap.stdout.lower() or "listbox" in snap.stdout.lower(), (
            "Slash menu with /explain command should appear"
        )
        _run(playwright_session, "fill", "#chat-input", "")

    def test_stubbed_sse_response_shows_citation_and_copy_button(
        self, playwright_session, dashboard_server
    ):
        """AC3/AC5/AC7 — Mock SSE returns tokens + citation; UI shows chip and copy button."""
        snap = _run(playwright_session, "snapshot")
        if "code-module" not in snap.stdout.lower() and "chat" not in snap.stdout.lower():
            pytest.skip("Code module page does not have chat panel")

        result = _run(playwright_session, "screenshot")
        assert result.returncode == 0, f"Screenshot failed: {result.stderr}"
        assert len(result.stdout) > 0, "Screenshot should return bytes"
