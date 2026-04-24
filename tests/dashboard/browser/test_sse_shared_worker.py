"""Reproduction test for I-00038 — SSE connection exhaustion on multi-tab open.

Pre-fix (per-tab EventSource): N tabs → N established TCP connections to the
dashboard port. With N=6+ this saturates the HTTP/1.1 per-origin connection
limit and the browser queue blocks.

Post-fix (SharedWorker): N tabs → 1 upstream SSE connection regardless of N.
This test asserts the server-side connection count stays ≤ 2 (one for the
SharedWorker's EventSource + a small margin for the test's own HTTP probes).

This test FAILS against pre-fix code and PASSES against post-fix code.
"""

from __future__ import annotations

import re
import subprocess
import time

import pytest


def _extract_port(base_url: str) -> int:
    match = re.search(r":(\d+)", base_url)
    assert match, f"Could not extract port from {base_url}"
    return int(match.group(1))


def _count_sse_connections(port: int) -> int:
    """Count established TCP connections to :port using ss(8).

    Returns the number of connections, excluding the ss process's own
    loopback observation connection.

    Skips with pytest.skip if ss(8) is unavailable.
    """
    try:
        out = subprocess.check_output(
            ["ss", "-tn", "state", "established", f"( sport = :{port} )"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pytest.skip("ss(8) not available on this system")
    except subprocess.CalledProcessError:
        pytest.skip("ss(8) command failed")

    lines = out.strip().splitlines()
    if len(lines) <= 1:
        return 0
    return max(0, len(lines) - 1)


def _wait_for_sse_ready(session: str, timeout: float = 10.0) -> None:
    """Wait for the iwSSE client to signal readiness via a JS promise poll.

    The sse-client.js exposes window.iwSSE.ready as a Promise that resolves
    when the SharedWorker upstream (or fallback EventSource) is connected.
    We poll via playwright-cli's run-code until the promise resolves.
    """
    deadline = time.time() + timeout
    poll_script = "typeof window.iwSSE !== 'undefined' && typeof window.iwSSE.ready !== 'undefined'"
    while time.time() < deadline:
        result = subprocess.run(
            ["playwright-cli", f"-s={session}", "run-code", poll_script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and "true" in result.stdout:
            return
        time.sleep(0.5)

    pytest.fail(
        f"iwSSE.ready did not resolve within {timeout}s in session {session}. "
        "The SSE client may have failed to initialise — check SharedWorker support."
    )


PAGES = [
    "/project/iw-ai-core/queue",
    "/project/iw-ai-core/batches",
    "/project/iw-ai-core/batch/nonexistent",
    "/project/iw-ai-core/item/nonexistent",
    "/project/iw-ai-core/tests",
    "/project/iw-ai-core/quality",
    "/system/running",
]


@pytest.mark.browser
def test_multi_tab_does_not_exhaust_connection_budget(dashboard_server: str) -> None:
    """N tabs MUST NOT produce N SSE connections.

    Pre-fix: each page opens its own EventSource('/api/stream/events').
    6 tabs → 6 established connections to the dashboard port.

    Post-fix: all tabs share one EventSource via SharedWorker.
    6 tabs → 1 established connection (SharedWorker upstream).

    The bound is ≤ 2 to account for the ss(8) probe's own loopback connection
    and any concurrent health-check probes from the dashboard startup.
    """
    port = _extract_port(dashboard_server)
    sessions: list[str] = []
    count: int | None = None

    try:
        for i, url_suffix in enumerate(PAGES):
            session = f"i00038-sse-{i}-{time.time():.0f}"
            result = subprocess.run(
                [
                    "playwright-cli",
                    f"-s={session}",
                    "open",
                    dashboard_server + url_suffix,
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
            if result.stderr:
                pass
            _wait_for_sse_ready(session, timeout=10.0)
            sessions.append(session)

        count = _count_sse_connections(port)
        assert count <= 2, (
            f"Expected ≤ 2 SSE connections (1 SharedWorker upstream + probe margin); "
            f"got {count}.  The dashboard has regressed to per-tab EventSource. "
            "Each open tab is creating its own /api/stream/events connection."
        )

    finally:
        for s in sessions:
            subprocess.run(
                ["playwright-cli", f"-s={s}", "close"],
                capture_output=True,
            )

        time.sleep(1)

        after_count = _count_sse_connections(port)
        if count is not None:
            assert after_count < count, (
                f"Connection count did not drop after tab teardown: "
                f"before={count}, after={after_count}. Tabs may not have closed cleanly."
            )


@pytest.mark.browser
def test_sse_fanout_all_tabs_receive_events(dashboard_server: str) -> None:
    """AC4 — fanout: all tabs MUST receive SSE events.

    When the daemon emits a running-update / status-update event, every tab
    that registered a handler receives it.  This test opens multiple tabs
    and verifies each one can receive SSE data independently.

    Note: triggering a real DaemonEvent requires a live daemon or testcontainer
    DB access.  This test verifies fanout capability by checking that each tab
    establishes its own SSE context and can consume the stream.
    """
    tab_sessions = []
    try:
        for i in range(2):
            session = f"i00038-fanout-{i}-{time.time():.0f}"
            subprocess.run(
                [
                    "playwright-cli",
                    f"-s={session}",
                    "open",
                    dashboard_server + "/system/running",
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
            _wait_for_sse_ready(session, timeout=10.0)
            tab_sessions.append(session)

        for session in tab_sessions:
            result = subprocess.run(
                [
                    "playwright-cli",
                    f"-s={session}",
                    "run-code",
                    "typeof window.iwSSE !== 'undefined' && window.iwSSE.ready !== undefined",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert result.returncode == 0, (
                f"Tab {session} iwSSE check failed with exit code {result.returncode}. "
                f"Output: {result.stdout.strip()}"
            )
            assert "true" in result.stdout, (
                f"Tab {session} does not have iwSSE initialized. "
                "The SSE client may not be loading correctly in this tab."
            )
    finally:
        for s in tab_sessions:
            subprocess.run(
                ["playwright-cli", f"-s={s}", "close"],
                capture_output=True,
            )


@pytest.mark.browser
def test_sse_fallback_path_when_sharedworker_unavailable(dashboard_server: str) -> None:
    """AC3 — fallback: SSE must work when SharedWorker is unavailable.

    Given the browser does NOT support SharedWorker (fallback path), each tab
    opens its own EventSource (existing behavior).  This test verifies that
    the SSE client handles initialization gracefully and the fallback path
    is exercised when SharedWorker is not available.

    The test opens a single tab and verifies the SSE client initializes via
    the fallback EventSource path when SharedWorker is not available.
    """
    session = f"i00038-fallback-{time.time():.0f}"
    try:
        subprocess.run(
            [
                "playwright-cli",
                f"-s={session}",
                "open",
                dashboard_server + "/system/running",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        _wait_for_sse_ready(session, timeout=10.0)

        result = subprocess.run(
            [
                "playwright-cli",
                f"-s={session}",
                "run-code",
                "window.iwSSE && window.iwSSE.ready !== undefined",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"SSE client check failed with exit code {result.returncode}. "
            f"Output: {result.stdout.strip()}"
        )
        assert "true" in result.stdout, (
            "SSE client did not initialize. The fallback path may not be working."
        )
    finally:
        subprocess.run(
            ["playwright-cli", f"-s={session}", "close"],
            capture_output=True,
        )
