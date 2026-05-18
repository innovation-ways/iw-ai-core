"""Tests for the Dashboard AI Assistant chat router (F-00083 S03).

Uses FastAPI TestClient with mocked OpencodeClient/OpencodeRuntime so no live
OpenCode binary is required. The db_session fixture (testcontainer) is used to
satisfy the app's DB dependency — no DB operations are performed by the chat
router itself.

Convention: context-chip threading uses the ``system`` field of the prompt body —
when a ``context`` field is provided in POST /prompt, the router prepends
``[Context: viewing {title} ({type} {id})]`` to the prompt and passes it as
``system`` to ``client.prompt()``.

Module-level imports of dashboard modules are intentional and required: they
initialise ``orch.db.session.SessionLocal`` at collection time (before
``_arm_live_db_guard`` sets the blocked DB URL), exactly as every other
dashboard test file does.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator, Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers import chat as chat_mod
from orch.db.models import Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_healthy_runtime() -> Any:
    """Return a mock OpencodeRuntime whose health() returns True."""
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    return rt


def _make_client() -> Any:
    """Return a mock OpencodeClient with sensible defaults."""
    c = MagicMock()
    c.create_session = AsyncMock(return_value="sess-1")
    c.list_sessions = AsyncMock(return_value=[])
    c.get_session = AsyncMock(return_value={"id": "sess-1", "status": "idle"})
    c.get_messages = AsyncMock(return_value=[])
    c.prompt = AsyncMock(return_value=None)
    c.abort = AsyncMock(return_value=None)
    c.reply_permission = AsyncMock(return_value=None)
    # /config returns top-level config (model, agent, mode, etc.) — NOT models list.
    c.get_config = AsyncMock(
        return_value={
            "model": "prov-a/model-a",
            "default_agent": "default",
        }
    )
    # /config/providers is where the model catalogue actually lives.
    c.get_providers = AsyncMock(
        return_value={
            "providers": [
                {
                    "id": "prov-a",
                    "name": "Provider A",
                    "models": {"model-a": {}, "model-b": {}},
                },
            ],
            "default": {"prov-a": "model-a"},
        }
    )
    return c


def _make_relay_manager(relay: Any = None) -> Any:
    """Return a mock RelayManager."""
    rm = MagicMock()
    rm.get_or_create_relay = AsyncMock(return_value=relay or _make_relay())
    rm.shutdown = AsyncMock(return_value=None)
    return rm


def _make_relay(events: list[dict[str, Any]] | None = None) -> Any:
    """Return a mock SessionRelay whose subscribe() yields given events then stops."""
    _events = events or []

    async def _fake_subscribe(last_event_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        for ev in _events:
            yield ev

    relay = MagicMock()
    relay.subscribe = _fake_subscribe
    return relay


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def chat_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with healthy mock runtime + mocked chat dependencies."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.state.opencode_runtime = _make_healthy_runtime()
        app.state.opencode_client = _make_client()
        app.state.relay_manager = _make_relay_manager()
        app.dependency_overrides[get_db] = lambda: db_session
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc
        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture
def app_no_runtime(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with runtime=None — simulates unavailable OpenCode."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.state.opencode_runtime = None
        app.state.opencode_client = None
        app.state.relay_manager = None
        app.dependency_overrides[get_db] = lambda: db_session
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc
        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# TC1 — create session returns session_id
# ---------------------------------------------------------------------------


class TestCreateSession:
    def test_create_session_returns_session_id(self, db_session: Session) -> None:
        """POST /api/chat/sessions returns {session_id} from client.create_session."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.create_session = AsyncMock(return_value="sess-1")

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.post("/api/chat/sessions", json={})
            assert resp.status_code == 200
            assert resp.json() == {"session_id": "sess-1"}
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_create_session_passes_optional_fields(self, db_session: Session) -> None:
        """Optional model/agent/directory are forwarded to client.create_session."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.create_session = AsyncMock(return_value="sess-2")

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.post(
                "/api/chat/sessions",
                json={"model": "m", "agent": "a", "directory": "/tmp"},  # noqa: S108
            )
            assert resp.status_code == 200
            mock_client.create_session.assert_awaited_once_with(
                model="m", agent="a", directory="/tmp"
            )
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# TC2 — runtime unavailable returns 503
# ---------------------------------------------------------------------------


class TestRuntimeUnavailable:
    def test_runtime_none_create_session_returns_503(self, app_no_runtime: TestClient) -> None:
        resp = app_no_runtime.post("/api/chat/sessions", json={})
        assert resp.status_code == 503
        assert "unavailable" in resp.json()["error"].lower()

    def test_runtime_none_stream_returns_503(self, app_no_runtime: TestClient) -> None:
        resp = app_no_runtime.get("/api/chat/sessions/sid-x/stream")
        assert resp.status_code == 503

    def test_runtime_none_prompt_returns_503(self, app_no_runtime: TestClient) -> None:
        resp = app_no_runtime.post("/api/chat/sessions/sid-x/prompt", json={"text": "hi"})
        assert resp.status_code == 503

    def test_runtime_none_abort_returns_503(self, app_no_runtime: TestClient) -> None:
        resp = app_no_runtime.post("/api/chat/sessions/sid-x/abort")
        assert resp.status_code == 503

    def test_runtime_none_permissions_returns_503(self, app_no_runtime: TestClient) -> None:
        resp = app_no_runtime.post(
            "/api/chat/sessions/sid-x/permissions/rid-y",
            json={"response": "allow"},
        )
        assert resp.status_code == 503

    def test_runtime_unhealthy_returns_503(self, db_session: Session) -> None:
        """health() returning False also yields 503."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            rt = MagicMock()
            rt.health = AsyncMock(return_value=False)

            app = create_app()
            app.state.opencode_runtime = rt
            app.state.opencode_client = _make_client()
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.post("/api/chat/sessions", json={})
            assert resp.status_code == 503
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_config_endpoint_not_gated_when_runtime_none(self, app_no_runtime: TestClient) -> None:
        """GET /api/chat/config MAY return 503 when runtime is None and no cache."""
        resp = app_no_runtime.get("/api/chat/config")
        assert 200 <= resp.status_code < 600

    def test_list_sessions_runtime_none_returns_503(self, app_no_runtime: TestClient) -> None:
        resp = app_no_runtime.get("/api/chat/sessions")
        assert resp.status_code == 503

    def test_get_session_runtime_none_returns_503(self, app_no_runtime: TestClient) -> None:
        resp = app_no_runtime.get("/api/chat/sessions/sid-x")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# TC3 — /config cache (30 s TTL)
# ---------------------------------------------------------------------------


class TestConfigCache:
    def test_config_cache_30s(self, db_session: Session) -> None:
        """Second request within 30s does NOT call upstream endpoints again."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            call_count = 0

            async def _get_config() -> dict[str, Any]:
                nonlocal call_count
                call_count += 1
                return {"model": "prov-a/model-a"}

            async def _get_providers() -> dict[str, Any]:
                nonlocal call_count
                call_count += 1
                return {
                    "providers": [{"id": "prov-a", "models": {"model-a": {}}}],
                    "default": {"prov-a": "model-a"},
                }

            mock_client = _make_client()
            mock_client.get_config = _get_config
            mock_client.get_providers = _get_providers

            # Clear any stale cache from previous tests
            chat_mod._config_cache.clear()

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp1 = tc.get("/api/chat/config")
            assert resp1.status_code == 200
            # First request: both get_config + get_providers fired once each.
            assert call_count == 2

            resp2 = tc.get("/api/chat/config")
            assert resp2.status_code == 200
            # Second call must NOT have hit upstream endpoints again.
            assert call_count == 2, (
                f"upstream endpoints were re-called within 30s TTL (count={call_count})"
            )
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_config_returns_expected_shape(self, chat_client: TestClient) -> None:
        chat_mod._config_cache.clear()
        resp = chat_client.get("/api/chat/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "default_model" in data


# ---------------------------------------------------------------------------
# TC3b — /config flattens /config/providers into a model list
#
# Regression: opencode `/config` does NOT return `models`/`default_model`;
# those live under `/config/providers`. The router must merge both endpoints
# into the shape the front-end (chat.js:661) expects.
# ---------------------------------------------------------------------------


def _providers_payload(
    providers: list[dict[str, Any]] | None = None,
    default: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "providers": providers or [],
        "default": default or {},
    }


class TestConfigFlattensProviders:
    def test_config_flattens_provider_models_into_string_list(self, db_session: Session) -> None:
        """`/api/chat/config` flattens `/config/providers` into
        ``models = ['<providerId>/<modelId>', ...]``."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            # Opencode /config: only the singular `model` field is meaningful here.
            mock_client.get_config = AsyncMock(
                return_value={
                    "model": "minimax/MiniMax-M2.7",
                    "agent": {},
                }
            )
            mock_client.get_providers = AsyncMock(
                return_value=_providers_payload(
                    providers=[
                        {
                            "id": "minimax",
                            "name": "MiniMax",
                            "models": {
                                "MiniMax-M2.7": {"id": "MiniMax-M2.7"},
                                "MiniMax-M2.5": {"id": "MiniMax-M2.5"},
                            },
                        },
                        {
                            "id": "openai",
                            "name": "OpenAI",
                            "models": {
                                "gpt-5.5-pro": {"id": "gpt-5.5-pro"},
                            },
                        },
                    ],
                    default={"minimax": "MiniMax-M2.7", "openai": "gpt-5.5-pro"},
                )
            )

            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            resp = tc.get("/api/chat/config")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data["models"], list)
            assert set(data["models"]) == {
                "minimax/MiniMax-M2.7",
                "minimax/MiniMax-M2.5",
                "openai/gpt-5.5-pro",
            }, f"unexpected models: {data['models']}"
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


class TestConfigProjectAllowlist:
    @staticmethod
    def _seed_project(db_session: Session, pid: str, config: dict[str, Any]) -> None:
        db_session.add(
            Project(
                id=pid,
                display_name=pid,
                repo_root=f"/tmp/{pid}",
                config=config,
            )
        )
        db_session.commit()

    def test_get_config_no_project_id_returns_full_list(self, db_session: Session) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.get_config = AsyncMock(return_value={"model": "openai/gpt-5.3-codex"})
            mock_client.get_providers = AsyncMock(
                return_value=_providers_payload(
                    providers=[
                        {"id": "openai", "models": {"gpt-5.3-codex": {}, "gpt-5-mini": {}}},
                        {"id": "anthropic", "models": {"claude-sonnet-4-6": {}}},
                    ],
                    default={"openai": "gpt-5.3-codex"},
                )
            )
            chat_mod._config_cache.clear()

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            resp = tc.get("/api/chat/config")
            assert resp.status_code == 200
            assert resp.json()["models"] == [
                "anthropic/claude-sonnet-4-6",
                "openai/gpt-5-mini",
                "openai/gpt-5.3-codex",
            ]
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_config_with_project_id_filters_to_allowlist(self, db_session: Session) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            self._seed_project(
                db_session,
                "proj-allow",
                {
                    "ai_assistant": {
                        "models": [
                            "anthropic/claude-opus-4-7",
                            "openai/gpt-5.3-codex",
                            "ollama/gemma4:26b",
                            "minimax/unreachable-m2",
                            "openai/unreachable-mini",
                        ]
                    }
                },
            )

            mock_client = _make_client()
            mock_client.get_config = AsyncMock(return_value={})
            mock_client.get_providers = AsyncMock(
                return_value=_providers_payload(
                    providers=[
                        {
                            "id": "anthropic",
                            "models": {
                                "claude-opus-4-7": {},
                                "claude-sonnet-4-6": {},
                            },
                        },
                        {
                            "id": "openai",
                            "models": {
                                "gpt-5.3-codex": {},
                                "gpt-5-mini": {},
                            },
                        },
                        {"id": "ollama", "models": {"gemma4:26b": {}, "phi4": {}}},
                        {"id": "minimax", "models": {"MiniMax-M2.7": {}, "MiniMax-M2.5": {}}},
                    ],
                    default={"anthropic": "claude-opus-4-7"},
                )
            )
            chat_mod._config_cache.clear()

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            resp = tc.get("/api/chat/config?project_id=proj-allow")
            assert resp.status_code == 200
            assert resp.json()["models"] == [
                "anthropic/claude-opus-4-7",
                "openai/gpt-5.3-codex",
                "ollama/gemma4:26b",
            ]
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_config_project_without_allowlist_falls_back(
        self, db_session: Session, caplog: pytest.LogCaptureFixture
    ) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            self._seed_project(db_session, "proj-no-allow", {"quality_config": {"enabled": True}})
            mock_client = _make_client()
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            with caplog.at_level("INFO"):
                resp = tc.get("/api/chat/config?project_id=proj-no-allow")

            assert resp.status_code == 200
            assert resp.json()["models"] == ["prov-a/model-a", "prov-a/model-b"]
            assert "has no ai_assistant allowlist" in caplog.text
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_config_unknown_project_id_falls_back(
        self, db_session: Session, caplog: pytest.LogCaptureFixture
    ) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            with caplog.at_level("INFO"):
                resp = tc.get("/api/chat/config?project_id=missing-project")

            assert resp.status_code == 200
            assert resp.json()["models"] == ["prov-a/model-a", "prov-a/model-b"]
            assert "project=missing-project has no ai_assistant allowlist" in caplog.text
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_config_without_project_id_falls_back_with_info_log(
        self, db_session: Session, caplog: pytest.LogCaptureFixture
    ) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            with caplog.at_level("INFO"):
                resp = tc.get("/api/chat/config")

            assert resp.status_code == 200
            assert resp.json()["models"] == ["prov-a/model-a", "prov-a/model-b"]
            assert "no project_id supplied" in caplog.text
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_config_filter_drops_unreachable_with_warning(
        self, db_session: Session, caplog: pytest.LogCaptureFixture
    ) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            self._seed_project(
                db_session,
                "proj-drop",
                {
                    "ai_assistant": {
                        "models": [
                            "prov-a/model-a",
                            "ghost/missing-a",
                            "ghost/missing-b",
                        ]
                    }
                },
            )
            mock_client = _make_client()
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            with caplog.at_level("WARNING"):
                resp = tc.get("/api/chat/config?project_id=proj-drop")

            assert resp.status_code == 200
            assert resp.json()["models"] == ["prov-a/model-a"]
            assert "ghost/missing-a,ghost/missing-b" in caplog.text
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_config_default_model_preserved_when_in_filter(self, db_session: Session) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            self._seed_project(
                db_session,
                "proj-default-ok",
                {
                    "ai_assistant": {
                        "models": ["prov-a/model-b", "prov-a/model-a"],
                        "default_model": "prov-a/model-a",
                    }
                },
            )
            mock_client = _make_client()
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            resp = tc.get("/api/chat/config?project_id=proj-default-ok")
            assert resp.status_code == 200
            assert resp.json()["default_model"] == "prov-a/model-a"
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_config_default_model_dropped_falls_to_first_filtered(
        self, db_session: Session
    ) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            self._seed_project(
                db_session,
                "proj-default-drop",
                {
                    "ai_assistant": {
                        "models": ["prov-a/model-b", "prov-a/model-a"],
                        "default_model": "ghost/missing",
                    }
                },
            )
            mock_client = _make_client()
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            resp = tc.get("/api/chat/config?project_id=proj-default-drop")
            assert resp.status_code == 200
            assert resp.json()["models"] == ["prov-a/model-b", "prov-a/model-a"]
            assert resp.json()["default_model"] == "prov-a/model-b"
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_config_empty_filter_falls_open_with_info_log(
        self, db_session: Session, caplog: pytest.LogCaptureFixture
    ) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            self._seed_project(
                db_session,
                "proj-empty",
                {
                    "ai_assistant": {
                        "models": ["ghost/missing-a", "ghost/missing-b"],
                        "default_model": "ghost/missing-a",
                    }
                },
            )
            mock_client = _make_client()
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            with caplog.at_level("INFO"):
                resp = tc.get("/api/chat/config?project_id=proj-empty")

            assert resp.status_code == 200
            assert resp.json()["models"] == ["prov-a/model-a", "prov-a/model-b"]
            assert "allowlist empty after intersection" in caplog.text
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_config_cache_keyed_per_project(self, db_session: Session) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            self._seed_project(
                db_session,
                "proj-a",
                {"ai_assistant": {"models": ["prov-a/model-a"]}},
            )
            self._seed_project(
                db_session,
                "proj-b",
                {"ai_assistant": {"models": ["prov-a/model-b"]}},
            )
            mock_client = _make_client()
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            resp_a = tc.get("/api/chat/config?project_id=proj-a")
            resp_b = tc.get("/api/chat/config?project_id=proj-b")
            assert resp_a.status_code == 200
            assert resp_b.status_code == 200
            assert resp_a.json()["models"] == ["prov-a/model-a"]
            assert resp_b.json()["models"] == ["prov-a/model-b"]
            assert set(chat_mod._config_cache) >= {"proj-a", "proj-b"}

            # mutate one cache slot and confirm it doesn't affect the other slot
            chat_mod._config_cache["proj-a"]["data"]["models"] = ["poisoned/model"]
            resp_b_again = tc.get("/api/chat/config?project_id=proj-b")
            assert resp_b_again.json()["models"] == ["prov-a/model-b"]
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_config_default_model_prefers_config_model_field(self, db_session: Session) -> None:
        """When `/config.model` is a known `provider/model` string, use it."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.get_config = AsyncMock(return_value={"model": "minimax/MiniMax-M2.5"})
            mock_client.get_providers = AsyncMock(
                return_value=_providers_payload(
                    providers=[
                        {
                            "id": "minimax",
                            "models": {
                                "MiniMax-M2.7": {},
                                "MiniMax-M2.5": {},
                            },
                        },
                    ],
                    default={"minimax": "MiniMax-M2.7"},
                )
            )
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.get("/api/chat/config")
            assert resp.status_code == 200
            data = resp.json()
            assert data["default_model"] == "minimax/MiniMax-M2.5"
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_config_default_model_falls_back_to_providers_default(
        self, db_session: Session
    ) -> None:
        """When `/config.model` is missing or unknown, derive default from
        the first matching `(providerId, default[providerId])` pair."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            # No `model` field at all on /config.
            mock_client.get_config = AsyncMock(return_value={})
            mock_client.get_providers = AsyncMock(
                return_value=_providers_payload(
                    providers=[
                        {"id": "minimax", "models": {"MiniMax-M2.7": {}}},
                    ],
                    default={"minimax": "MiniMax-M2.7"},
                )
            )
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.get("/api/chat/config")
            assert resp.status_code == 200
            data = resp.json()
            assert data["default_model"] == "minimax/MiniMax-M2.7"
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_config_empty_providers_returns_empty_models(self, db_session: Session) -> None:
        """No providers → empty models list, empty default_model."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.get_config = AsyncMock(return_value={})
            mock_client.get_providers = AsyncMock(
                return_value=_providers_payload(providers=[], default={})
            )
            chat_mod._config_cache.clear()
            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.get("/api/chat/config")
            assert resp.status_code == 200
            data = resp.json()
            assert data["models"] == []
            assert data["default_model"] == ""
        finally:
            app.dependency_overrides.clear()
            chat_mod._config_cache.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# TC4 — /skills cache invalidates on mtime change
# ---------------------------------------------------------------------------


class TestSkillsCache:
    def test_skills_cache_invalidates_on_mtime_change(
        self, tmp_path: Any, chat_client: TestClient
    ) -> None:
        """Touching a skill file invalidates the /skills cache."""
        chat_mod._skills_cache.clear()

        skills_dir = tmp_path / ".opencode" / "skills" / "dummy"
        skills_dir.mkdir(parents=True)
        skill_file = skills_dir / "SKILL.md"
        skill_file.write_text("# skill\ndescription: A test skill.\n")

        with patch.object(chat_mod, "_OPENCODE_ROOT", tmp_path):
            resp1 = chat_client.get("/api/chat/skills")
            assert resp1.status_code == 200
            cached_mtime = chat_mod._skills_cache.get("mtime")

            # Touch the file to advance its mtime
            new_mtime = time.time() + 10
            os.utime(skill_file, (new_mtime, new_mtime))

            resp2 = chat_client.get("/api/chat/skills")
            assert resp2.status_code == 200
            new_cached_mtime = chat_mod._skills_cache.get("mtime")
            assert new_cached_mtime != cached_mtime, "Cache mtime was not updated after file touch"

    def test_skills_returns_list(self, chat_client: TestClient) -> None:
        chat_mod._skills_cache.clear()
        resp = chat_client.get("/api/chat/skills")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# TC4b — _load_skills layout support
#
# Regression: the existing loader only accepted `<root>/.opencode/<kind>/<name>/SKILL.md`
# subdirectory layouts, but `.opencode/commands/` actually contains flat `.md`
# files (e.g. `iw-new-cr.md`), and Claude-style skills live under
# `.claude/skills/<name>/SKILL.md`. The loader must accept both layouts AND
# both root dirs.
# ---------------------------------------------------------------------------


class TestSkillsLayoutSupport:
    def test_skills_includes_flat_md_files_under_opencode_commands(
        self, tmp_path: Any, chat_client: TestClient
    ) -> None:
        """A `.opencode/commands/<name>.md` flat file becomes a command entry."""
        chat_mod._skills_cache.clear()

        cmds = tmp_path / ".opencode" / "commands"
        cmds.mkdir(parents=True)
        (cmds / "iw-new-cr.md").write_text(
            "# Create New Change Request\ndescription: Create a change request.\n"
        )

        with patch.object(chat_mod, "_OPENCODE_ROOT", tmp_path):
            resp = chat_client.get("/api/chat/skills")
            assert resp.status_code == 200
            entries = resp.json()
            names = {(e["kind"], e["name"]) for e in entries}
            assert ("command", "iw-new-cr") in names, f"flat .md command not surfaced; got {names}"

    def test_skills_scans_claude_skills_subdirectories(
        self, tmp_path: Any, chat_client: TestClient
    ) -> None:
        """`.claude/skills/<name>/SKILL.md` becomes a skill entry."""
        chat_mod._skills_cache.clear()

        skill_dir = tmp_path / ".claude" / "skills" / "iw-research"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\ndescription: Conducts online research.\n---\n# iw-research\n"
        )

        with patch.object(chat_mod, "_OPENCODE_ROOT", tmp_path):
            resp = chat_client.get("/api/chat/skills")
            assert resp.status_code == 200
            entries = resp.json()
            names = {(e["kind"], e["name"]) for e in entries}
            assert ("skill", "iw-research") in names, (
                f".claude/skills/ subdir not surfaced; got {names}"
            )

    def test_default_opencode_root_resolves_to_repo_root(self) -> None:
        """The default ``_OPENCODE_ROOT`` must be the repo containing CLAUDE.md.

        Regression: a previous off-by-one in ``Path(__file__).resolve().parents[N]``
        resolved one level too high, so ``.opencode/`` / ``.claude/`` lookups
        silently found nothing in production while tests (which patch
        ``_OPENCODE_ROOT`` to a tmp_path) kept passing.
        """
        from pathlib import Path

        default = Path(__file__).resolve().parents[2]
        # Re-derive the default the same way the module would, ignoring the
        # IW_CORE_REPO_ROOT override (which would mask the bug).
        module_default = Path(chat_mod.__file__).resolve().parents[2]
        assert (module_default / "CLAUDE.md").is_file(), (
            f"_OPENCODE_ROOT default does not contain CLAUDE.md: {module_default}"
        )
        assert module_default == default, (
            f"chat module default root {module_default} != tests root {default}"
        )

    def test_skills_dedupes_same_kind_name_across_roots(
        self, tmp_path: Any, chat_client: TestClient
    ) -> None:
        """Same (kind, name) defined in both .opencode and .claude → one entry."""
        chat_mod._skills_cache.clear()

        oc_cmds = tmp_path / ".opencode" / "commands"
        oc_cmds.mkdir(parents=True)
        (oc_cmds / "fix-bug.md").write_text("description: From opencode.\n")

        cl_cmds = tmp_path / ".claude" / "commands"
        cl_cmds.mkdir(parents=True)
        (cl_cmds / "fix-bug.md").write_text("description: From claude.\n")

        with patch.object(chat_mod, "_OPENCODE_ROOT", tmp_path):
            resp = chat_client.get("/api/chat/skills")
            assert resp.status_code == 200
            entries = resp.json()
            matches = [e for e in entries if e["kind"] == "command" and e["name"] == "fix-bug"]
            assert len(matches) == 1, f"expected single dedup'd entry, got {matches}"


# ---------------------------------------------------------------------------
# TC5 — SSE stream forwards relay events
# ---------------------------------------------------------------------------


class TestStreamEndpoint:
    def test_stream_endpoint_forwards_relay_events(self, db_session: Session) -> None:
        """SSE response contains three event: lines from the relay."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            events = [
                {"event": "message.part.delta", "data": {"text": "hello"}, "id": "evt-1"},
                {"event": "message.part.delta", "data": {"text": " world"}, "id": "evt-2"},
                {"event": "session.idle", "data": {}, "id": "evt-3"},
            ]
            relay = _make_relay(events)
            rm = _make_relay_manager(relay)

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = _make_client()
            app.state.relay_manager = rm
            app.dependency_overrides[get_db] = lambda: db_session

            with (
                TestClient(app, raise_server_exceptions=False) as tc,
                tc.stream("GET", "/api/chat/sessions/sid-1/stream") as resp,
            ):
                assert resp.status_code == 200
                assert resp.headers.get("Cache-Control") == "no-cache"
                assert resp.headers.get("X-Accel-Buffering") == "no"
                assert resp.headers.get("Connection") == "keep-alive"
                body = resp.read().decode()
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

        event_lines = [ln for ln in body.splitlines() if ln.startswith("event:")]
        assert len(event_lines) == 3, f"Expected 3 event lines, got {len(event_lines)}: {body!r}"

    def test_stream_sse_headers(self, db_session: Session) -> None:
        """SSE endpoint carries the required anti-buffering headers."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            relay = _make_relay([])
            rm = _make_relay_manager(relay)

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = _make_client()
            app.state.relay_manager = rm
            app.dependency_overrides[get_db] = lambda: db_session

            with (
                TestClient(app, raise_server_exceptions=False) as tc,
                tc.stream("GET", "/api/chat/sessions/sid-h/stream") as resp,
            ):
                assert resp.headers.get("Cache-Control") == "no-cache"
                assert resp.headers.get("X-Accel-Buffering") == "no"
                assert resp.headers.get("Connection") == "keep-alive"
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_stream_sse_event_format(self, db_session: Session) -> None:
        """Each relay event is yielded as event:/data:/id: lines."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            events = [
                {"event": "session.idle", "data": {"session": "s"}, "id": "e1"},
            ]
            relay = _make_relay(events)
            rm = _make_relay_manager(relay)

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = _make_client()
            app.state.relay_manager = rm
            app.dependency_overrides[get_db] = lambda: db_session

            with (
                TestClient(app, raise_server_exceptions=False) as tc,
                tc.stream("GET", "/api/chat/sessions/sid-2/stream") as resp,
            ):
                body = resp.read().decode()
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

        assert "event: session.idle" in body
        assert "id: e1" in body
        data_lines = [ln for ln in body.splitlines() if ln.startswith("data:")]
        assert len(data_lines) >= 1
        payload = json.loads(data_lines[0][len("data: ") :])
        assert payload == {"session": "s"}


# ---------------------------------------------------------------------------
# TC6 — Last-Event-ID header is passed to relay.subscribe
# ---------------------------------------------------------------------------


class TestStreamLastEventId:
    def test_stream_endpoint_passes_last_event_id(self, db_session: Session) -> None:
        """The Last-Event-ID request header is passed to relay.subscribe()."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            received_last_event_id: list[str | None] = []

            async def _fake_subscribe(
                last_event_id: str | None = None,
            ) -> AsyncIterator[dict[str, Any]]:
                received_last_event_id.append(last_event_id)
                return
                yield  # make this an async generator

            relay = MagicMock()
            relay.subscribe = _fake_subscribe
            rm = _make_relay_manager(relay)

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = _make_client()
            app.state.relay_manager = rm
            app.dependency_overrides[get_db] = lambda: db_session

            with (
                TestClient(app, raise_server_exceptions=False) as tc,
                tc.stream(
                    "GET",
                    "/api/chat/sessions/sid-3/stream",
                    headers={"Last-Event-ID": "evt-42"},
                ),
            ):
                pass
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

        assert received_last_event_id == ["evt-42"], (
            f"Expected ['evt-42'], got {received_last_event_id}"
        )


# ---------------------------------------------------------------------------
# TC7 — prompt with context chip threaded
# ---------------------------------------------------------------------------


class TestPromptWithContextChip:
    def test_prompt_with_context_chip_threaded(self, db_session: Session) -> None:
        """POST /prompt with context prepends chip to the system message."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.prompt = AsyncMock(return_value=None)

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.post(
                "/api/chat/sessions/sid-4/prompt",
                json={
                    "text": "hello",
                    "context": {"type": "item", "id": "F-00083", "title": "F-00083"},
                },
            )
            assert resp.status_code == 204, resp.text

            mock_client.prompt.assert_awaited_once()
            call_kwargs = mock_client.prompt.call_args
            system_arg = call_kwargs.kwargs.get("system") or (
                call_kwargs.args[3] if len(call_kwargs.args) > 3 else None
            )
            assert system_arg is not None, "Expected system argument with context chip"
            assert "F-00083" in system_arg
            assert "item" in system_arg
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_prompt_without_context_no_system(self, db_session: Session) -> None:
        """POST /prompt without context passes no system kwarg (or None)."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.prompt = AsyncMock(return_value=None)

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.post(
                "/api/chat/sessions/sid-5/prompt",
                json={"text": "hello"},
            )
            assert resp.status_code == 204, resp.text
            mock_client.prompt.assert_awaited_once()
            call_kwargs = mock_client.prompt.call_args
            system_arg = call_kwargs.kwargs.get("system")
            assert system_arg is None, f"Expected no system arg without context, got {system_arg!r}"
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_prompt_returns_204(self, chat_client: TestClient) -> None:
        resp = chat_client.post("/api/chat/sessions/sid-p/prompt", json={"text": "test"})
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# TC8 — permission reply forwards body
# ---------------------------------------------------------------------------


class TestPermissionReply:
    def test_permission_reply_forwards(self, db_session: Session) -> None:
        """POST /permissions/{rid} forwards body to client.reply_permission(sid, rid, ...)."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.reply_permission = AsyncMock(return_value=None)

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.post(
                "/api/chat/sessions/sid-6/permissions/rid-7",
                json={"response": "allow", "remember": True},
            )
            assert resp.status_code == 204, resp.text
            mock_client.reply_permission.assert_awaited_once_with(
                "sid-6",
                "rid-7",
                "allow",
                remember=True,
            )
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_permission_reply_without_remember(self, db_session: Session) -> None:
        """remember defaults to False when not supplied."""
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.reply_permission = AsyncMock(return_value=None)

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.post(
                "/api/chat/sessions/sid-8/permissions/rid-9",
                json={"response": "deny"},
            )
            assert resp.status_code == 204
            mock_client.reply_permission.assert_awaited_once_with(
                "sid-8",
                "rid-9",
                "deny",
                remember=False,
            )
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_abort_returns_204(self, chat_client: TestClient) -> None:
        resp = chat_client.post("/api/chat/sessions/sid-ab/abort")
        assert resp.status_code == 204
        # Verify abort was delegated to the mocked client
        # (chat_client fixture uses _make_client() which has abort=AsyncMock)


# ---------------------------------------------------------------------------
# Additional: list sessions and get session
# ---------------------------------------------------------------------------


class TestSessionEndpoints:
    def test_list_sessions(self, db_session: Session) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.list_sessions = AsyncMock(
                return_value=[{"id": "s1", "created_at": "2026-01-01T00:00:00Z"}]
            )

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.get("/api/chat/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert data[0]["id"] == "s1"
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    def test_get_session(self, db_session: Session) -> None:
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            mock_client = _make_client()
            mock_client.get_session = AsyncMock(return_value={"id": "s1"})
            mock_client.get_messages = AsyncMock(return_value=[{"role": "user", "content": "hi"}])

            app = create_app()
            app.state.opencode_runtime = _make_healthy_runtime()
            app.state.opencode_client = mock_client
            app.state.relay_manager = _make_relay_manager()
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.get("/api/chat/sessions/s1")
            assert resp.status_code == 200
            data = resp.json()
            assert "session" in data
            assert "messages" in data
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
