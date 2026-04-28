"""Shared browser test fixtures for dashboard Playwright smoke tests.

Provides module-scoped Uvicorn dashboard server and playwright-cli session
that can be shared across multiple browser test files.

Run browser tests with:
    uv run pytest tests/dashboard/browser/ -m browser -v
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_STARTUP_TIMEOUT_SECS = 30


def _pick_free_port() -> int:
    """Bind to port 0 so the kernel allocates a free port; release it for the
    server to claim. Race window is small and acceptable for test fixtures."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(base_url: str, proc: subprocess.Popen, timeout: float) -> None:
    """Poll /health until ready. Raise on timeout or premature process exit."""
    deadline = time.monotonic() + timeout
    health_url = f"{base_url}/health"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            raise RuntimeError(
                f"Dashboard server exited with code {proc.returncode} "
                f"before becoming ready:\n{stderr}"
            )
        try:
            with urllib.request.urlopen(health_url, timeout=1) as resp:  # noqa: S310
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.2)
    raise TimeoutError(f"Dashboard server at {base_url} did not become ready within {timeout}s")


def _read_dotenv(path: Path) -> dict[str, str]:
    """Read a .env file and return key=value pairs, stripping quotes."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip a single matching pair of surrounding quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def _dashboard_subprocess_env() -> dict[str, str]:
    """Build the subprocess env for the dashboard server.

    Pytest sets ``IW_CORE_TEST_CONTEXT=true`` and hijacks ``IW_CORE_DB_*``
    to unreachable values (port 1) as a defence-in-depth against tests that
    accidentally hit the live DB. The browser smoke tests are integration-
    style — they need a real dashboard talking to the real orch DB — so we
    strip the test-context flag and re-read the project's .env to restore
    real DB credentials, then arm ``IW_CORE_DAEMON_CONTEXT=true`` (the
    canonical platform context the live-DB guard accepts).
    """
    env = os.environ.copy()
    env.pop("IW_CORE_TEST_CONTEXT", None)
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("PYTEST_VERSION", None)

    # Restore real DB credentials from the project's .env (the conftest
    # hijack at session scope replaced them with port-1 unreachable values).
    # __file__ is tests/dashboard/browser/conftest.py — four parents up is
    # the repo root.
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    dotenv = _read_dotenv(repo_root / ".env")
    for key in (
        "IW_CORE_DB_HOST",
        "IW_CORE_DB_PORT",
        "IW_CORE_DB_NAME",
        "IW_CORE_DB_USER",
        "IW_CORE_DB_PASSWORD",
    ):
        if key in dotenv:
            env[key] = dotenv[key]

    env["IW_CORE_DAEMON_CONTEXT"] = "true"
    return env


@pytest.fixture(scope="module")
def dashboard_server(tmp_path_factory):
    """Start the dashboard app via Uvicorn on a kernel-picked port; yield the base URL.

    Uses /health polling for readiness instead of a fixed sleep so the test
    starts as soon as the server actually serves requests. Logs land in a
    tmp file so a startup-timeout failure surfaces the actual server error
    instead of a generic "did not become ready".
    """
    port = _pick_free_port()
    log_dir = tmp_path_factory.mktemp("dashboard-server")
    log_path = log_dir / "uvicorn.log"
    log_fh = log_path.open("w")
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
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        env=_dashboard_subprocess_env(),
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server_via_log(base_url, proc, log_path, _STARTUP_TIMEOUT_SECS)
    except (RuntimeError, TimeoutError):
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fh.close()
        raise
    try:
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fh.close()


def _wait_for_server_via_log(
    base_url: str, proc: subprocess.Popen, log_path: Path, timeout: float
) -> None:
    """Poll /health until ready. On timeout/exit, surface the captured log."""
    deadline = time.monotonic() + timeout
    health_url = f"{base_url}/health"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            log_text = log_path.read_text(errors="replace") if log_path.is_file() else ""
            raise RuntimeError(
                f"Dashboard server exited with code {proc.returncode} "
                f"before becoming ready:\n{log_text[-4000:]}"
            )
        try:
            with urllib.request.urlopen(health_url, timeout=1) as resp:  # noqa: S310
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.2)
    log_text = log_path.read_text(errors="replace") if log_path.is_file() else ""
    raise TimeoutError(
        f"Dashboard server at {base_url} did not become ready within {timeout}s. "
        f"Last log:\n{log_text[-4000:]}"
    )


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
            "eval",
            "() => localStorage.clear()",
        ],
        capture_output=True,
        timeout=10,
    )
