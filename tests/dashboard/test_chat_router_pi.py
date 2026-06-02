"""Tests for the chat router's Pi runtime dispatch path (F-00087 S07).

Exercises the HTTP API layer for Pi tabs end-to-end:

* POST /api/chat/tabs with runtime=pi creates a tab via PiRuntime (NOT
  OpencodeClient).
* POST /api/chat/tabs/{id}/prompt routes to PiRuntime.prompt() (NOT
  OpencodeClient.prompt()).
* POST /api/chat/tabs/{id}/permissions/{rid} routes to
  PiRuntime.reply_permission() (NOT OpencodeClient.reply_permission()).
* POST /api/chat/tabs/{id}/abort routes to PiRuntime.abort().
* GET  /api/chat/tabs/{id} routes session/messages via PiRuntime.

Pi runtime is dependency-injected as an AsyncMock; the OpenCode client is also
set on app.state but should NOT be exercised when tab.runtime='pi'.  Each test
verifies (a) the correct runtime gets the call, and (b) the other runtime
does NOT get the call (no cross-runtime leakage).

Closes S06 finding HIGH #3 (router-level Pi tab tests were missing) and is
the regression guard for CRITICAL #1 (router-level Pi dispatch).
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.chat import tab_service as _tab_service
from orch.db.models import AgentRuntimeOption, Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pi_runtime() -> Any:
    """Return a mock PiRuntime whose health() returns True and methods are AsyncMocks."""
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    rt.create_session = AsyncMock(return_value="pi-sess-1")
    rt.get_session = AsyncMock(return_value={"id": "pi-sess-1", "pi_session_path": None})
    rt.get_messages = AsyncMock(return_value=[])
    rt.prompt = AsyncMock(return_value=None)
    rt.abort = AsyncMock(return_value=None)
    rt.reply_permission = AsyncMock(return_value=None)
    rt.close_session = AsyncMock(return_value=None)
    return rt


def _make_opencode_client() -> Any:
    """Mock OpencodeClient — used to assert non-dispatch from Pi tabs."""
    c = MagicMock()
    c.create_session = AsyncMock(return_value="oc-sess-should-not-be-called")
    c.prompt = AsyncMock(return_value=None)
    c.abort = AsyncMock(return_value=None)
    c.reply_permission = AsyncMock(return_value=None)
    c.get_session = AsyncMock(return_value={"id": "oc-sess", "status": "idle"})
    c.get_messages = AsyncMock(return_value=[])
    c.get_config = AsyncMock(return_value={})
    c.get_providers = AsyncMock(return_value={"providers": [], "default": {}})
    return c


def _make_opencode_runtime_healthy() -> Any:
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    return rt


def _seed_pi_models(db: Session) -> None:
    """Ensure at least two Pi rows exist in ``agent_runtime_options``.

    CR-00062 migration may already seed Pi rows; this fixture is idempotent
    so it co-exists with the live seed.  We discover what's already there and
    return the first Pi model string so the test can use it for tab creation.
    """
    from sqlalchemy import select as _select

    existing = (
        db.execute(_select(AgentRuntimeOption).where(AgentRuntimeOption.cli_tool == "pi"))
        .scalars()
        .all()
    )
    if existing:
        return
    db.add(
        AgentRuntimeOption(
            cli_tool="pi",
            model="minimax/MiniMax-M2.7",
            cli_label="Pi",
            model_label="MiniMax M2.7",
            display_name="MiniMax M2.7 (Pi)",
            enabled=True,
            is_default=False,
            sort_order=0,
        )
    )
    db.add(
        AgentRuntimeOption(
            cli_tool="pi",
            model="openai/gpt-5.3-codex",
            cli_label="Pi",
            model_label="GPT-5.3 Codex",
            display_name="GPT-5.3 Codex (Pi)",
            enabled=True,
            is_default=False,
            sort_order=1,
        )
    )
    db.flush()


def _first_pi_model(db: Session) -> str:
    """Return the first ``"<cli>/<model>"`` string from the Pi catalogue."""
    from sqlalchemy import select as _select

    row = db.execute(
        _select(AgentRuntimeOption)
        .where(AgentRuntimeOption.cli_tool == "pi", AgentRuntimeOption.enabled.is_(True))
        .order_by(AgentRuntimeOption.sort_order)
        .limit(1)
    ).scalar_one()
    return f"{row.cli_tool}/{row.model}"


def _create_pi_tab_in_db(
    db: Session,
    *,
    project_id: str,
    model: str | None = None,
    pi_session_id: str = "pi-sess-1",
) -> Any:
    """Insert a Pi ChatTab row (using opencode_session_id column for the Pi sid)."""
    tab, _ = _tab_service.create_tab(
        db,
        project_id=project_id,
        runtime="pi",
        model=model or _first_pi_model(db),
        opencode_session_id=pi_session_id,
    )
    db.commit()
    return tab


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pi_chat_app(
    db_session: Session, test_project: Project
) -> Generator[tuple[TestClient, Any, Any], None, None]:
    """TestClient with both Pi runtime (mock) and OpenCode (mock) wired on app.state.

    Returns ``(test_client, pi_runtime_mock, opencode_client_mock)`` so tests
    can assert which one received the call.
    """
    _seed_pi_models(db_session)

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        pi_runtime = _make_pi_runtime()
        oc_client = _make_opencode_client()

        app = create_app()
        app.state.opencode_runtime = _make_opencode_runtime_healthy()
        app.state.opencode_client = oc_client
        app.state.relay_manager = MagicMock(get_or_create_relay=AsyncMock(), drop_relay=AsyncMock())
        app.state.pi_runtime = pi_runtime
        app.dependency_overrides[get_db] = lambda: db_session
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc, pi_runtime, oc_client
        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# create_tab: runtime=pi dispatches to PiRuntime, not OpencodeClient
# ---------------------------------------------------------------------------


class TestCreatePiTab:
    """Tests for creating Pi-runtime chat tabs."""

    def test_create_pi_tab_calls_pi_runtime_not_opencode(
        self,
        pi_chat_app: tuple[TestClient, Any, Any],
        db_session: Session,
        test_project: Project,
    ) -> None:
        """POST /api/chat/tabs with runtime='pi' MUST go through PiRuntime."""
        tc, pi_runtime, oc_client = pi_chat_app
        pi_model = _first_pi_model(db_session)
        resp = tc.post(
            "/api/chat/tabs",
            json={
                "project_id": test_project.id,
                "runtime": "pi",
                "model": pi_model,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        tab = body["tab"]
        assert tab["runtime"] == "pi"
        assert tab["opencode_session_id"] == "pi-sess-1"

        # The Pi runtime received create_session.
        pi_runtime.create_session.assert_awaited_once()
        # OpenCode client must NOT have been called for tab creation.
        oc_client.create_session.assert_not_called()

    def test_create_pi_tab_rejects_non_pi_model(
        self, pi_chat_app: tuple[TestClient, Any, Any], test_project: Project
    ) -> None:
        """Pi tab with a model outside the agent_runtime_options Pi catalogue → 400."""
        tc, _pi, _oc = pi_chat_app
        resp = tc.post(
            "/api/chat/tabs",
            json={
                "project_id": test_project.id,
                "runtime": "pi",
                "model": "anthropic/claude-sonnet-4-7",  # OpenCode model, not Pi
            },
        )
        assert resp.status_code == 400
        assert "not available for runtime 'pi'" in resp.json()["error"]

    def test_create_pi_tab_503_when_pi_runtime_unhealthy(
        self, db_session: Session, test_project: Project
    ) -> None:
        """When Pi runtime is unhealthy (binary missing), POST returns 503."""
        _seed_pi_models(db_session)
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            pi_runtime = _make_pi_runtime()
            pi_runtime.health = AsyncMock(return_value=False)

            app = create_app()
            app.state.opencode_runtime = _make_opencode_runtime_healthy()
            app.state.opencode_client = _make_opencode_client()
            app.state.relay_manager = MagicMock()
            app.state.pi_runtime = pi_runtime
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.post(
                "/api/chat/tabs",
                json={"project_id": test_project.id, "runtime": "pi"},
            )
            assert resp.status_code == 503
            assert "Pi runtime unavailable" in resp.json()["error"]
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# send_prompt: Pi tab routes to PiRuntime.prompt
# ---------------------------------------------------------------------------


class TestPromptDispatch:
    """Tests that prompt requests are dispatched to the correct runtime."""

    def test_prompt_on_pi_tab_calls_pi_runtime(
        self,
        pi_chat_app: tuple[TestClient, Any, Any],
        db_session: Session,
        test_project: Project,
    ) -> None:
        """POST /prompt on a Pi tab dispatches to PiRuntime.prompt()."""
        tc, pi_runtime, oc_client = pi_chat_app
        tab = _create_pi_tab_in_db(db_session, project_id=test_project.id)

        resp = tc.post(f"/api/chat/tabs/{tab.id}/prompt", json={"text": "hello pi"})
        assert resp.status_code == 204, resp.text

        pi_runtime.prompt.assert_awaited_once()
        args, kwargs = pi_runtime.prompt.call_args
        # PiRuntime.prompt(session_id, text, *, model=None, system=None)
        assert args[0] == "pi-sess-1"
        assert args[1] == "hello pi"
        # OpenCode client must NOT receive the prompt.
        oc_client.prompt.assert_not_called()

    def test_prompt_threads_context_chip_for_pi_tab(
        self,
        pi_chat_app: tuple[TestClient, Any, Any],
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Context-chip system arg is threaded for Pi tabs the same as OpenCode."""
        tc, pi_runtime, _oc = pi_chat_app
        tab = _create_pi_tab_in_db(db_session, project_id=test_project.id)

        resp = tc.post(
            f"/api/chat/tabs/{tab.id}/prompt",
            json={
                "text": "do thing",
                "context": {"type": "doc", "id": "D-42", "title": "Plan"},
            },
        )
        assert resp.status_code == 204
        _args, kwargs = pi_runtime.prompt.call_args
        assert kwargs["system"] == "[Context: viewing Plan (doc D-42)]"


# ---------------------------------------------------------------------------
# reply_permission: Pi tab routes to PiRuntime.reply_permission
# (AC3 — approval round-trip through the HTTP layer)
# ---------------------------------------------------------------------------


class TestPermissionDispatch:
    """Tests that permission replies are dispatched to the correct runtime."""

    def test_permission_approve_on_pi_tab_calls_pi_runtime(
        self,
        pi_chat_app: tuple[TestClient, Any, Any],
        db_session: Session,
        test_project: Project,
    ) -> None:
        """AC3: POST /permissions/{rid} on a Pi tab calls PiRuntime.reply_permission."""
        tc, pi_runtime, oc_client = pi_chat_app
        tab = _create_pi_tab_in_db(db_session, project_id=test_project.id)

        resp = tc.post(
            f"/api/chat/tabs/{tab.id}/permissions/iw-chat-approvals.req-001",
            json={"response": "approve"},
        )
        assert resp.status_code == 204

        pi_runtime.reply_permission.assert_awaited_once_with(
            "pi-sess-1",
            "iw-chat-approvals.req-001",
            "approve",
            remember=False,
        )
        oc_client.reply_permission.assert_not_called()

    def test_permission_deny_on_pi_tab_passes_through(
        self,
        pi_chat_app: tuple[TestClient, Any, Any],
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Verifies that a permission deny on a Pi tab passes through to the Pi runtime."""
        tc, pi_runtime, _oc = pi_chat_app
        tab = _create_pi_tab_in_db(db_session, project_id=test_project.id)
        resp = tc.post(
            f"/api/chat/tabs/{tab.id}/permissions/iw-chat-approvals.req-002",
            json={"response": "deny", "remember": True},
        )
        assert resp.status_code == 204
        pi_runtime.reply_permission.assert_awaited_once_with(
            "pi-sess-1",
            "iw-chat-approvals.req-002",
            "deny",
            remember=True,
        )


# ---------------------------------------------------------------------------
# abort_tab: Pi tab routes to PiRuntime.abort
# ---------------------------------------------------------------------------


class TestAbortDispatch:
    """Tests that abort requests are dispatched to the Pi runtime."""

    def test_abort_pi_tab_calls_pi_runtime(
        self,
        pi_chat_app: tuple[TestClient, Any, Any],
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Verifies that aborting a Pi tab calls the Pi runtime's abort method."""
        tc, pi_runtime, oc_client = pi_chat_app
        tab = _create_pi_tab_in_db(db_session, project_id=test_project.id)
        resp = tc.post(f"/api/chat/tabs/{tab.id}/abort")
        assert resp.status_code == 204
        pi_runtime.abort.assert_awaited_once_with("pi-sess-1")
        oc_client.abort.assert_not_called()


# ---------------------------------------------------------------------------
# get_tab: Pi tab routes to PiRuntime.get_session + get_messages
# ---------------------------------------------------------------------------


class TestGetTabDispatch:
    """Tests that GET tab requests are dispatched to the Pi runtime."""

    def test_get_pi_tab_calls_pi_runtime(
        self,
        pi_chat_app: tuple[TestClient, Any, Any],
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Verifies that GET for a Pi tab calls the Pi runtime's get_session method."""
        tc, pi_runtime, oc_client = pi_chat_app
        tab = _create_pi_tab_in_db(db_session, project_id=test_project.id)
        resp = tc.get(f"/api/chat/tabs/{tab.id}")
        assert resp.status_code == 200
        pi_runtime.get_session.assert_awaited_once_with("pi-sess-1")
        pi_runtime.get_messages.assert_awaited_once_with("pi-sess-1")
        oc_client.get_session.assert_not_called()


# ---------------------------------------------------------------------------
# Cross-runtime isolation: OpenCode tab still uses OpencodeClient
# ---------------------------------------------------------------------------


class TestNoCrossRuntimeLeakage:
    """Tests that Pi and OpenCode runtimes do not share state."""

    def test_opencode_tab_still_routes_to_opencode(
        self,
        pi_chat_app: tuple[TestClient, Any, Any],
        db_session: Session,
        test_project: Project,
    ) -> None:
        """OpenCode tabs MUST keep routing to OpencodeClient, not PiRuntime."""
        tc, pi_runtime, oc_client = pi_chat_app
        tab, _ = _tab_service.create_tab(
            db_session,
            project_id=test_project.id,
            runtime="opencode",
            model="prov-a/model-a",
            opencode_session_id="oc-sess-existing",
        )
        db_session.commit()

        resp = tc.post(f"/api/chat/tabs/{tab.id}/prompt", json={"text": "hi"})
        assert resp.status_code == 204
        oc_client.prompt.assert_awaited_once()
        pi_runtime.prompt.assert_not_called()


# ---------------------------------------------------------------------------
# clear_tab: Pi tab routes to PiRuntime.create_session
# ---------------------------------------------------------------------------


class TestClearPiTabDispatch:
    """Tests that clear-tab requests are dispatched to the Pi runtime."""

    def test_clear_pi_tab_calls_pi_runtime_not_opencode(
        self,
        pi_chat_app: tuple[TestClient, Any, Any],
        db_session: Session,
        test_project: Project,
    ) -> None:
        """POST /tabs/{tab_id}/clear on a Pi tab dispatches to PiRuntime.create_session()."""
        tc, pi_runtime, oc_client = pi_chat_app
        tab = _create_pi_tab_in_db(db_session, project_id=test_project.id)

        # Override create_session to return a predictable new session ID.
        pi_runtime.create_session = AsyncMock(return_value="pi-sess-new-xyz")

        resp = tc.post(f"/api/chat/tabs/{tab.id}/clear")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["tab"]["opencode_session_id"] == "pi-sess-new-xyz"

        # Pi runtime received create_session.
        pi_runtime.create_session.assert_awaited_once()
        # OpenCode client must NOT have been called.
        oc_client.create_session.assert_not_called()

    def test_clear_pi_tab_503_when_pi_runtime_unhealthy(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """POST /tabs/{tab_id}/clear returns 503 when Pi runtime is unhealthy."""
        _seed_pi_models(db_session)
        original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            pi_runtime = _make_pi_runtime()
            pi_runtime.health = AsyncMock(return_value=False)

            app = create_app()
            app.state.opencode_runtime = _make_opencode_runtime_healthy()
            app.state.opencode_client = _make_opencode_client()
            app.state.relay_manager = MagicMock()
            app.state.pi_runtime = pi_runtime
            app.dependency_overrides[get_db] = lambda: db_session
            tc = TestClient(app, raise_server_exceptions=False)

            tab = _create_pi_tab_in_db(db_session, project_id=test_project.id)
            resp = tc.post(f"/api/chat/tabs/{tab.id}/clear")
            assert resp.status_code == 503
            assert "Pi runtime unavailable" in resp.json()["error"]
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
