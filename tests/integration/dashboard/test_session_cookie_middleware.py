"""Integration tests for the session-cookie middleware in dashboard/app.py."""

from __future__ import annotations

import re
import uuid

from fastapi.testclient import TestClient

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app  # noqa: F401


def _extract_cookie_from_set_cookie(set_cookie: str) -> str:
    """Extract iw_chat_session value from a Set-Cookie header."""
    match = re.search(r"iw_chat_session=([a-f0-9-]{36})", set_cookie)
    if not match:
        raise AssertionError(f"No session cookie in: {set_cookie}")
    return match.group(1)


class TestSessionCookieMiddleware:
    """Tests for the iw_chat_session cookie middleware."""

    def test_first_request_sets_cookie(self) -> None:
        """Request without iw_chat_session cookie results in Set-Cookie header."""
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "iw_chat_session=" in set_cookie, f"Expected Set-Cookie, got: {set_cookie}"
        # Cookie value should be a valid UUID v4
        cookie_val = _extract_cookie_from_set_cookie(set_cookie)
        uuid.UUID(cookie_val)

    def test_cookie_includes_samesite_lax(self) -> None:
        """Set-Cookie header includes SameSite=Lax."""
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        set_cookie = resp.headers.get("set-cookie", "")
        assert "SameSite=Lax" in set_cookie

    def test_cookie_includes_max_age(self) -> None:
        """Set-Cookie header includes Max-Age=7776000 (90 days)."""
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        set_cookie = resp.headers.get("set-cookie", "")
        assert "Max-Age=7776000" in set_cookie

    def test_second_request_uses_existing_cookie(self) -> None:
        """Sending the cookie back in a second request reuses it."""
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        # First request — cookie is set
        resp1 = client.get("/health")
        set_cookie = resp1.headers.get("set-cookie", "")
        cookie_val = _extract_cookie_from_set_cookie(set_cookie)

        # Second request — send the cookie back
        resp2 = client.get(
            "/health",
            cookies={"iw_chat_session": cookie_val},
        )
        assert resp2.status_code == 200
        # No new cookie should be set when the client sends a valid one
        set_cookie2 = resp2.headers.get("set-cookie", "")
        # If a cookie is set again, it should be the same value
        if set_cookie2:
            assert cookie_val in set_cookie2, (
                "Server should not set a different cookie when client sends valid one"
            )
