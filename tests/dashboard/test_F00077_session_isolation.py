"""Tests for F-00077 session-cookie scoping (Invariant 7).

Verifies that conversations are scoped to (project_id, session_id) and
that cross-session access returns 404 without leaking existence.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app  # noqa: F401

if TYPE_CHECKING:
    from fastapi import FastAPI

    from orch.db.models import Project


@pytest.fixture
def app(db_session) -> FastAPI:
    """FastAPI app for dashboard router tests with get_db overridden to db_session."""
    from dashboard.dependencies import get_db

    app_ = create_app()

    def _override_get_db():
        yield db_session

    app_.dependency_overrides[get_db] = _override_get_db
    return app_


def _sync_post(
    app: FastAPI,
    path: str,
    session_headers: dict[str, str],
    json: dict | None = None,
) -> dict:
    """Synchronous POST helper."""
    transport = ASGITransport(app=app)

    async def _do() -> dict:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(path, headers=session_headers, json=json)
            return {
                "status": resp.status_code,
                "data": resp.json() if resp.status_code < 400 else {"detail": resp.text},
            }

    return asyncio.run(_do())


def _sync_get(
    app: FastAPI,
    path: str,
    session_headers: dict[str, str],
) -> dict:
    """Synchronous GET helper."""
    transport = ASGITransport(app=app)

    async def _do() -> dict:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(path, headers=session_headers)
            return {
                "status": resp.status_code,
                "data": resp.json() if resp.status_code < 400 else {"detail": resp.text},
            }

    return asyncio.run(_do())


@pytest.fixture
def session_a_headers(app: FastAPI) -> dict[str, str]:
    """Return headers dict with a valid iw_chat_session cookie (Session A)."""
    transport = ASGITransport(app=app)

    async def _capture() -> dict[str, str]:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            set_cookie = resp.headers.get("set-cookie", "")
            match = re.search(r"iw_chat_session=([a-f0-9-]{36})", set_cookie)
            assert match
            return {"cookie": f"iw_chat_session={match.group(1)}"}

    return asyncio.run(_capture())


@pytest.fixture
def session_b_headers(app: FastAPI) -> dict[str, str]:
    """Return headers dict with a DIFFERENT iw_chat_session cookie (Session B)."""
    transport = ASGITransport(app=app)

    async def _capture() -> dict[str, str]:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            set_cookie = resp.headers.get("set-cookie", "")
            match = re.search(r"iw_chat_session=([a-f0-9-]{36})", set_cookie)
            assert match
            return {"cookie": f"iw_chat_session={match.group(1)}"}

    return asyncio.run(_capture())


class TestSessionCookieScoping:
    """Session cookie scopes conversations to (project_id, session_id)."""

    def test_session_a_creates_conversation(
        self,
        app: FastAPI,
        test_project: Project,
        session_a_headers: dict[str, str],
    ) -> None:
        """Session A can create a conversation and get its own messages."""
        result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_a_headers,
            json={"context_level": "architecture"},
        )
        assert result["status"] == 201
        conv_id = result["data"]["conversation_id"]

        # Session A can read its own conversation
        result = _sync_get(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/messages",
            session_a_headers,
        )
        assert result["status"] == 200, (
            f"Session A should read its own conversation, got {result['status']}"
        )

    def test_session_b_cannot_read_session_a_conversation(
        self,
        app: FastAPI,
        test_project: Project,
        session_a_headers: dict[str, str],
        session_b_headers: dict[str, str],
    ) -> None:
        """Session B gets 404 when accessing Session A's conversation_id."""
        # Session A creates a conversation
        result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_a_headers,
            json={"context_level": "architecture"},
        )
        assert result["status"] == 201
        conv_id_a = result["data"]["conversation_id"]

        # Session B tries to read Session A's conversation_id
        result = _sync_get(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id_a}/messages",
            session_b_headers,
        )
        assert result["status"] == 404, (
            f"Cross-session access should return 404, got {result['status']}. "
            "Must NOT leak existence (200 with empty vs 404)."
        )

    def test_session_b_cannot_archive_session_a_conversation(
        self,
        app: FastAPI,
        test_project: Project,
        session_a_headers: dict[str, str],
        session_b_headers: dict[str, str],
    ) -> None:
        """Session B gets 404 when trying to archive Session A's conversation."""
        # Session A creates a conversation
        result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_a_headers,
            json={"context_level": "architecture"},
        )
        assert result["status"] == 201
        conv_id_a = result["data"]["conversation_id"]

        # Session B tries to archive Session A's conversation
        result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id_a}/archive",
            session_b_headers,
            json={},
        )
        assert result["status"] == 404, (
            f"Cross-session archive should return 404, got {result['status']}"
        )

    def test_different_cookies_produce_different_session_ids(
        self,
        app: FastAPI,
        session_a_headers: dict[str, str],
        session_b_headers: dict[str, str],
    ) -> None:
        """The two sessions have different iw_chat_session values."""
        import re

        match_a = re.search(r"iw_chat_session=([a-f0-9-]{36})", session_a_headers["cookie"])
        match_b = re.search(r"iw_chat_session=([a-f0-9-]{36})", session_b_headers["cookie"])
        assert match_a is not None, "Session A cookie should be set"
        assert match_b is not None, "Session B cookie should be set"
        assert match_a.group(1) != match_b.group(1), (
            "Session A and B should have different session cookies"
        )
