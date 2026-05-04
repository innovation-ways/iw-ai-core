"""Tests for dashboard/routers/conversations.py — session-scoped chat conversation endpoints."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app  # noqa: F401

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.orm import Session

    from orch.db.models import Project


@pytest.fixture
def app(db_session: Session) -> FastAPI:
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
    """Synchronous POST helper using httpx AsyncClient."""
    import asyncio

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
    """Synchronous GET helper using httpx AsyncClient."""
    import asyncio

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
def session_headers(app: FastAPI) -> dict[str, str]:
    """Return headers dict with a valid iw_chat_session cookie."""
    import asyncio

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
def another_session_headers(app: FastAPI) -> dict[str, str]:
    """Return headers dict with a different iw_chat_session cookie."""
    import asyncio

    transport = ASGITransport(app=app)

    async def _capture() -> dict[str, str]:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            set_cookie = resp.headers.get("set-cookie", "")
            match = re.search(r"iw_chat_session=([a-f0-9-]{36})", set_cookie)
            assert match
            return {"cookie": f"iw_chat_session={match.group(1)}"}

    return asyncio.run(_capture())


class TestConversationCreate:
    """POST /api/projects/{project_id}/conversations"""

    def test_post_creates_conversation(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """POST creates a ChatConversation and returns its id."""
        result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )

        assert result["status"] == 201, f"Expected 201, got {result}: {result.get('data')}"
        data = result["data"]
        assert "conversation_id" in data
        conv_id = data["conversation_id"]

        from orch.db.models import ChatConversation

        conv = db_session.get(ChatConversation, conv_id)
        assert conv is not None
        assert conv.project_id == test_project.id

    def test_post_with_module_path(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """POST with module_path stores it on the conversation."""
        result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"module_path": "orch/daemon/main.py", "context_level": "module"},
        )

        assert result["status"] == 201
        from orch.db.models import ChatConversation

        conv = db_session.get(ChatConversation, result["data"]["conversation_id"])
        assert conv is not None
        assert conv.module_path == "orch/daemon/main.py"


class TestConversationList:
    """GET /api/projects/{project_id}/conversations"""

    def test_list_returns_conversations(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """GET /conversations returns up to 50 non-archived conversations."""
        _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )

        result = _sync_get(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
        )

        assert result["status"] == 200
        data = result["data"]
        assert isinstance(data, list)
        assert len(data) >= 1
        item = data[0]
        assert "conversation_id" in item
        assert "last_active_at" in item
        assert "context_level" in item

    def test_list_excludes_archived(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """Archived conversations are not listed."""
        create_result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        conv_id = create_result["data"]["conversation_id"]

        _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/archive",
            session_headers,
            json={},
        )

        result = _sync_get(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
        )
        assert result["status"] == 200
        listed_ids = [item["conversation_id"] for item in result["data"]]
        assert conv_id not in listed_ids

    def test_list_ordered_by_last_active_at_desc(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """GET /conversations returns items ordered by last_active_at DESC."""
        _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "module"},
        )

        result = _sync_get(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
        )
        assert result["status"] == 200
        times = [item["last_active_at"] for item in result["data"]]
        assert times == sorted(times, reverse=True), "Should be DESC"


class TestConversationMessages:
    """GET /api/projects/{project_id}/conversations/{conversation_id}/messages"""

    def test_get_messages_returns_ordered_messages(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """GET /messages returns the conversation's messages in order."""
        create_result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        conv_id = create_result["data"]["conversation_id"]

        result = _sync_get(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/messages",
            session_headers,
        )

        assert result["status"] == 200
        data = result["data"]
        assert data["conversation_id"] == conv_id
        assert "messages" in data
        assert isinstance(data["messages"], list)

    def test_get_messages_404_if_not_found(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """Non-existent conversation_id returns 404."""
        result = _sync_get(
            app,
            f"/api/projects/{test_project.id}/conversations/"
            "00000000-0000-0000-0000-000000000000/messages",
            session_headers,
        )
        assert result["status"] == 404


class TestCrossSession:
    """Conversation is scoped to session_id — cross-session access returns 404."""

    def test_cross_session_returns_404(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
        another_session_headers: dict[str, str],
    ) -> None:
        """Session A creates a conversation; Session B cannot read it (404)."""
        create_result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        conv_id = create_result["data"]["conversation_id"]

        result = _sync_get(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/messages",
            another_session_headers,
        )
        assert result["status"] == 404, "Cross-session access should return 404, not leak existence"


class TestCrossProject:
    """Conversation is scoped to project_id — cross-project access returns 404."""

    def test_cross_project_returns_404(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """Conversation from project A is not accessible under project B URL."""
        create_result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        conv_id = create_result["data"]["conversation_id"]

        from orch.db.models import Project

        other_project = Project(
            id="other-proj-id",
            display_name="Other Project",
            repo_root="/repos/other",
            config={},
        )
        db_session.add(other_project)
        db_session.flush()

        result = _sync_get(
            app,
            f"/api/projects/other-proj-id/conversations/{conv_id}/messages",
            session_headers,
        )
        assert result["status"] == 404


class TestArchive:
    """POST /api/projects/{project_id}/conversations/{conversation_id}/archive"""

    def test_archive_sets_archived_at(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """Archive sets archived_at; subsequent GET returns 404."""
        create_result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        conv_id = create_result["data"]["conversation_id"]

        archive_result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/archive",
            session_headers,
            json={},
        )

        assert archive_result["status"] == 200
        data = archive_result["data"]
        assert "archived_at" in data
        assert data["archived_at"] is not None

        result = _sync_get(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/messages",
            session_headers,
        )
        assert result["status"] == 404

    def test_archive_idempotent(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """Calling archive twice returns the same archived_at timestamp."""
        create_result = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        conv_id = create_result["data"]["conversation_id"]

        r1 = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/archive",
            session_headers,
            json={},
        )
        r2 = _sync_post(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/archive",
            session_headers,
            json={},
        )

        assert r1["status"] == r2["status"] == 200
        assert r1["data"]["archived_at"] == r2["data"]["archived_at"]
