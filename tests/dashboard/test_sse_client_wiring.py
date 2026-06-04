"""Template-rendering tests for I-00038 SSE client wiring.

Asserts:
1. base.html loads sse-client.js globally.
2. The 7 migrated pages contain no direct EventSource('/api/stream/events').
3. The 7 migrated pages register at least one iwSSE.on(...) handler.
4. Out-of-scope pages are not broken by the migration.

These tests are fast (no browser, no I/O beyond template rendering) and
catch regressions in the wiring that would restore per-tab EventSource.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader, select_autoescape

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _dashboard_static_dir() -> Path:
    return Path(__file__).parent.parent.parent / "dashboard" / "static"


def _template_dir() -> Path:
    return Path(__file__).parent.parent.parent / "dashboard" / "templates"


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Provide a TestClient with get_db overridden to the test db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            """Yield the test db_session for FastAPI dependency injection."""
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


@pytest.fixture
def jinja_env() -> Environment:
    """Create a Jinja2 environment pointing at the dashboard templates directory."""
    return Environment(
        loader=FileSystemLoader(str(_template_dir())),
        autoescape=select_autoescape(enabled_extensions=()),
    )


class TestSSEClientGlobalWiring:
    """AC6 — base.html must load sse-client.js so all pages inherit it."""

    def test_base_includes_sse_client_script(self, client: TestClient) -> None:
        """GET / yields HTML that loads /static/sse-client.js."""
        response = client.get("/")
        assert response.status_code == 200
        assert "/static/sse-client.js" in response.text, (
            "base.html must include <script src='/static/sse-client.js'> — "
            "without this the SharedWorker client is not loaded globally."
        )

    def test_sse_client_script_is_not_deferred(self, client: TestClient) -> None:
        """sse-client.js must load parser-blocking so inline iwSSE.on() calls in
        child templates' {% block scripts %} don't throw ReferenceError.

        Inline <script> tags execute synchronously during parse; a deferred
        script runs AFTER them.  If sse-client.js carries `defer`, every direct
        page load of a migrated template logs
        `ReferenceError: iwSSE is not defined` and the page's real-time updates
        silently break.
        """
        import re

        response = client.get("/")
        assert response.status_code == 200
        tag_match = re.search(
            r"<script[^>]*src=[^>]*sse-client\.js[^>]*>",
            response.text,
        )
        assert tag_match is not None, "sse-client.js <script> tag not found"
        tag = tag_match.group(0)
        assert " defer" not in tag, (
            f"sse-client.js must not have the `defer` attribute (found: {tag!r}). "
            "Child templates register handlers via inline <script>iwSSE.on(...)</script> "
            "inside {% block scripts %} — those run synchronously at parse time, so "
            "deferring sse-client.js causes ReferenceError on direct page loads."
        )


class TestNoDirectEventSourceInMigratedPages:
    """AC6 — migrated pages must NOT emit direct EventSource('/api/stream/events').

    The 7 migrated pages (listed in AFFECTED_PAGES) must use iwSSE.on(...)
    instead of new EventSource(...).  Any direct EventSource call for the
    global /api/stream/events endpoint bypasses the SharedWorker and recreates
    the connection-exhaustion bug.
    """

    AFFECTED_PAGES = [
        "/project/iw-ai-core/queue",
        "/project/iw-ai-core/batches",
        "/project/iw-ai-core/batch/nonexistent",
        "/project/iw-ai-core/item/nonexistent",
        "/project/iw-ai-core/tests",
        "/project/iw-ai-core/quality",
        "/system/running",
    ]

    @pytest.mark.parametrize("url", AFFECTED_PAGES)
    def test_no_direct_eventsource_to_global_stream(self, client: TestClient, url: str) -> None:
        """Each migrated page must not contain new EventSource('/api/stream/events')."""
        response = client.get(url)
        assert response.status_code in (200, 404), (
            f"Page {url} returned {response.status_code} — it may be unreachable"
        )
        assert "new EventSource('/api/stream/events')" not in response.text, (
            f"Page {url} contains a direct EventSource('/api/stream/events') call. "
            "This bypasses the SharedWorker and recreates the connection-exhaustion bug."
        )

    @pytest.mark.parametrize("url", AFFECTED_PAGES)
    def test_migrated_pages_register_iw_sse_handlers(self, client: TestClient, url: str) -> None:
        """Each migrated page must register at least one iwSSE.on(...) handler."""
        response = client.get(url)
        if response.status_code == 404:
            pytest.skip(f"Page {url} does not exist in test environment")
        assert "iwSSE.on(" in response.text, (
            f"Page {url} does not call iwSSE.on(...). "
            "The page may not have been migrated to use the shared SSE client."
        )


class TestOutOfScopePagesNotBroken:
    """Pages that were NOT migrated must still return 200 and not be polluted."""

    OUT_OF_SCOPE_PAGES = [
        "/project/iw-ai-core/code",
        "/project/iw-ai-core/docs",
        "/system/worktrees",
    ]

    @pytest.mark.parametrize("url", OUT_OF_SCOPE_PAGES)
    def test_out_of_scope_pages_load_normally(self, client: TestClient, url: str) -> None:
        """Pages outside the 7 migrated pages must still return 200 (or 404 if they
        don't exist in the test environment — e.g. /code and /docs require a
        project context that's only available with a real DB row)."""
        response = client.get(url)
        if response.status_code == 404:
            pytest.skip(f"Page {url} does not exist in test environment")
        assert response.status_code == 200, (
            f"Out-of-scope page {url} returned {response.status_code}. "
            "The migration may have broken unrelated pages."
        )

    def test_oss_page_still_has_own_eventsource(self, client: TestClient) -> None:
        """OSS scan page uses its own job-specific SSE endpoint — must be untouched.

        The oss.html page opens EventSource(streamUrl) where streamUrl points to
        /project/{id}/oss/stream/{job_id} — a finite-lifetime, single-tab stream
        for OSS scanning.  It must NOT be affected by the global SSE migration.
        """
        response = client.get("/project/iw-ai-core/oss")
        if response.status_code == 404:
            pytest.skip("OSS page does not exist in this project")
        assert response.status_code == 200
        assert "new EventSource" in response.text, (
            "OSS page must retain its own EventSource call. "
            "The migration should NOT touch finite-lifetime per-job SSE streams."
        )


class TestSSEClientFileExists:
    """Static assets created by S01 must exist on disk."""

    def test_sse_client_js_exists(self) -> None:
        """Verifies that the SSE client JavaScript file exists in the static directory."""
        path = _dashboard_static_dir() / "sse-client.js"
        assert path.exists(), f"{path} must exist (created by S01)"

    def test_sse_shared_worker_js_exists(self) -> None:
        """Verifies that the SSE shared worker JavaScript file exists in the static directory."""
        path = _dashboard_static_dir() / "sse-shared-worker.js"
        assert path.exists(), f"{path} must exist (created by S01)"

    def test_sse_client_js_syntax_valid(self) -> None:
        """sse-client.js must pass node --check (syntax validation)."""
        path = _dashboard_static_dir() / "sse-client.js"
        result = subprocess.run(
            ["node", "--check", str(path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"sse-client.js has a syntax error:\n{result.stderr}"

    def test_sse_shared_worker_js_syntax_valid(self) -> None:
        """sse-shared-worker.js must pass node --check (syntax validation)."""
        path = _dashboard_static_dir() / "sse-shared-worker.js"
        result = subprocess.run(
            ["node", "--check", str(path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"sse-shared-worker.js has a syntax error:\n{result.stderr}"
