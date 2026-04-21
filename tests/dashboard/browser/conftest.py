"""Shared browser test fixtures for dashboard Playwright smoke tests.

Provides module-scoped Uvicorn dashboard server and playwright-cli session
that can be shared across multiple browser test files.

Run browser tests with:
    uv run pytest tests/dashboard/browser/ -m browser -v
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
    port = 18751
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
    """Open playwright-cli session, navigate to code page, return session name.

    Session name includes pid to avoid collisions across test runs.
    """
    session = f"i00033-code-{os.getpid()}"
    try:
        subprocess.run(
            [
                "playwright-cli",
                f"-s={session}",
                "open",
                dashboard_server + "/project/iw-ai-core/code",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        yield session
    finally:
        subprocess.run(
            ["playwright-cli", f"-s={session}", "close"],
            capture_output=True,
        )


@pytest.fixture(scope="module")
def playwright_session_basic(dashboard_server):
    """Open playwright-cli session without navigating (bare session).

    Use this when you need to navigate manually or to a different page.
    """
    session = f"i00033-basic-{os.getpid()}"
    try:
        subprocess.run(
            [
                "playwright-cli",
                f"-s={session}",
                "open",
                dashboard_server,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        yield session
    finally:
        subprocess.run(
            ["playwright-cli", f"-s={session}", "close"],
            capture_output=True,
        )


@pytest.fixture(scope="module", autouse=True)
def _clear_localstorage_after_browser_tests(playwright_session):
    """Clear localStorage after browser tests to avoid cross-test pollution.

    This runs automatically after all module-scoped browser tests complete.
    """
    yield
    session = f"i00033-code-{os.getpid()}"
    subprocess.run(
        [
            "playwright-cli",
            f"-s={session}",
            "run-code",
            "localStorage.clear()",
        ],
        capture_output=True,
        timeout=10,
    )
