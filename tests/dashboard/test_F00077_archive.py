"""Tests for F-00077 archive endpoint (AC7).

Verifies that POST archive returns {archived_at}, subsequent GET returns 404,
archived conversations are excluded from listing, archive is idempotent, and
POST /code/qa with archived conversation_id creates a new conversation.
"""

from __future__ import annotations

import asyncio
import os
import re
import socket
import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app  # noqa: F401


def _ollama_reachable() -> bool:
    """Probe OLLAMA_HOST (default 127.0.0.1:11434). Cached via module-load."""
    host_env = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    host, _, port_s = host_env.rpartition(":")
    host = host or "127.0.0.1"
    try:
        port = int(port_s) if port_s else 11434
    except ValueError:
        return False
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


_OLLAMA_AVAILABLE = _ollama_reachable()

if TYPE_CHECKING:
    from fastapi import FastAPI

    from orch.db.models import Project


@pytest.fixture
def app(db_session, db_session_factory) -> FastAPI:
    """FastAPI app with get_db and code_qa.SessionLocal overridden to test session."""
    from dashboard.dependencies import get_db

    app_ = create_app()

    def _override_get_db():
        yield db_session

    app_.dependency_overrides[get_db] = _override_get_db

    with patch("dashboard.routers.code_qa.SessionLocal", db_session_factory):
        yield app_


def _sync_post_json(
    app: FastAPI,
    path: str,
    session_headers: dict[str, str],
    json: dict | None = None,
) -> dict:
    """Synchronous POST helper returning JSON dict."""
    transport = ASGITransport(app=app)

    async def _do() -> dict:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(path, headers=session_headers, json=json)
            return {
                "status": resp.status_code,
                "data": resp.json() if resp.status_code < 400 else {"detail": resp.text},
            }

    return asyncio.run(_do())


def _sync_get_json(
    app: FastAPI,
    path: str,
    session_headers: dict[str, str],
) -> dict:
    """Synchronous GET helper returning JSON dict."""
    transport = ASGITransport(app=app)

    async def _do() -> dict:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(path, headers=session_headers)
            return {
                "status": resp.status_code,
                "data": resp.json() if resp.status_code < 400 else {"detail": resp.text},
            }

    return asyncio.run(_do())


def _sync_post_qa(
    app: FastAPI,
    project_id: str,
    json_body: dict,
    session_headers: dict[str, str],
) -> tuple[int, list[str]]:
    """POST to code/qa and return (status_code, list of SSE frame strings])."""
    frames: list[str] = []

    async def _do() -> tuple[int, list[str]]:
        nonlocal frames
        transport = ASGITransport(app=app)
        async with (
            AsyncClient(transport=transport, base_url="http://test") as client,
            client.stream(
                "POST",
                f"/api/projects/{project_id}/code/qa",
                headers=session_headers,
                json=json_body,
            ) as resp,
        ):
            status = resp.status_code
            async for line in resp.aiter_lines():
                if line:
                    frames.append(line)
            return status, frames

    return asyncio.run(_do())


def _extract_conversation_id_from_meta(frames: list[str]) -> str | None:
    """Parse conversation_id from an event: meta frame."""
    for i, frame in enumerate(frames):
        if frame == "event: meta":
            next_line = i + 1
            if next_line < len(frames) and frames[next_line].startswith("data: "):
                data_str = frames[next_line][6:]
                try:
                    import json

                    obj = json.loads(data_str)
                    return obj.get("conversation_id")
                except Exception:
                    pass
    return None


@pytest.fixture
def session_headers(app: FastAPI) -> dict[str, str]:
    """Return headers dict with a valid iw_chat_session cookie."""
    transport = ASGITransport(app=app)

    async def _capture() -> dict[str, str]:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            set_cookie = resp.headers.get("set-cookie", "")
            match = re.search(r"iw_chat_session=([a-f0-9-]{36})", set_cookie)
            assert match
            return {"cookie": f"iw_chat_session={match.group(1)}"}

    return asyncio.run(_capture())


class TestArchiveEndpoint:
    """AC7: archive endpoint behavior."""

    def test_archive_returns_archived_at_and_404_on_get(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """POST archive returns {archived_at}; subsequent GET returns 404."""
        # Create conversation
        create_result = _sync_post_json(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        assert create_result["status"] == 201
        conv_id = create_result["data"]["conversation_id"]

        # Archive it
        archive_result = _sync_post_json(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/archive",
            session_headers,
            json={},
        )
        assert archive_result["status"] == 200, f"Archive failed: {archive_result}"
        data = archive_result["data"]
        assert "archived_at" in data
        assert data["archived_at"] is not None

        # GET messages now returns 404
        get_result = _sync_get_json(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/messages",
            session_headers,
        )
        assert get_result["status"] == 404, (
            f"GET after archive should return 404, got {get_result['status']}"
        )

    def test_archived_excluded_from_list(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """Archived conversation does not appear in the list endpoint."""
        # Create and archive
        create_result = _sync_post_json(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        conv_id = create_result["data"]["conversation_id"]

        _sync_post_json(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/archive",
            session_headers,
            json={},
        )

        # List — archived should not appear
        list_result = _sync_get_json(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
        )
        assert list_result["status"] == 200
        listed_ids = [item["conversation_id"] for item in list_result["data"]]
        assert conv_id not in listed_ids, "Archived conversation should not appear in list"

    def test_archive_is_idempotent(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """Calling archive twice returns the SAME archived_at timestamp."""
        # Create
        create_result = _sync_post_json(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        conv_id = create_result["data"]["conversation_id"]

        # First archive
        r1 = _sync_post_json(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/archive",
            session_headers,
            json={},
        )
        assert r1["status"] == 200
        archived_at_1 = r1["data"]["archived_at"]

        # Second archive
        r2 = _sync_post_json(
            app,
            f"/api/projects/{test_project.id}/conversations/{conv_id}/archive",
            session_headers,
            json={},
        )
        assert r2["status"] == 200
        archived_at_2 = r2["data"]["archived_at"]

        assert archived_at_1 == archived_at_2, (
            f"Archive should be idempotent — first={archived_at_1}, second={archived_at_2}"
        )

    @pytest.mark.skipif(
        not _OLLAMA_AVAILABLE,
        reason="POST /code/qa requires a code index built via Ollama embeddings",
    )
    def test_post_qa_with_archived_creates_new_conversation(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """POST /code/qa with archived conversation_id creates a NEW conversation."""
        # Create a conversation and archive it
        create_result = _sync_post_json(
            app,
            f"/api/projects/{test_project.id}/conversations",
            session_headers,
            json={"context_level": "architecture"},
        )
        archived_conv_id = create_result["data"]["conversation_id"]

        _sync_post_json(
            app,
            f"/api/projects/{test_project.id}/conversations/{archived_conv_id}/archive",
            session_headers,
            json={},
        )

        # Mock the QAEngine to avoid real LLM calls
        mock_engine_class = MagicMock()

        async def fake_stream(**kwargs):
            """Yield fake SSE tokens simulating an LLM stream."""
            yield {"kind": "token", "text": "new response"}
            yield "__DONE__"

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream
        mock_engine_class.return_value = mock_engine_instance

        with patch("orch.rag.qa.QAEngine", mock_engine_class):
            # POST /code/qa with the archived conversation_id
            _, frames = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "what does keep_alive do?",
                    "context_level": "architecture",
                    "conversation_id": archived_conv_id,
                },
                session_headers,
            )

        # Extract the new conversation_id from meta
        new_conv_id = _extract_conversation_id_from_meta(frames)
        assert new_conv_id is not None
        assert new_conv_id != archived_conv_id, (
            "Server should create a NEW conversation when the given ID is archived"
        )
        # Verify it's a valid UUID
        uuid.UUID(new_conv_id)
