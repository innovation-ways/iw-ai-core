"""Integration tests for the tab-scoped chat API (F-00086).

Covers AC6, AC7, AC8 and invariants #3, #4, #7, #8 from the design.
Uses the testcontainer-backed ``db_session`` fixture (per tests/CLAUDE.md)
and a mocked OpenCode runtime/client/relay so no subprocess is spawned.

The pre-S06 RED evidence (``test_post_tabs_rejects_unknown_runtime``) is
preserved verbatim — it remains the contract for invariant #3.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers import chat as chat_mod
from orch.db.models import ChatTab, Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _healthy_runtime_mock(sessions: list[dict[str, Any]] | None = None) -> Any:
    """Build a runtime mock that is healthy and lists ``sessions`` (default empty)."""
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    rt.list_sessions = AsyncMock(return_value=list(sessions or []))
    return rt


def _client_mock(*, models: list[str] | None = None, default_model: str = "prov-a/model-a") -> Any:
    """Build an OpenCode client mock with sensible defaults."""
    c = MagicMock()
    c.create_session = AsyncMock(return_value="oc-sess-new")
    c.get_session = AsyncMock(return_value={"id": "oc-sess-new", "status": "idle"})
    c.get_messages = AsyncMock(return_value=[])
    c.list_sessions = AsyncMock(return_value=[])
    c.prompt = AsyncMock(return_value=None)
    c.abort = AsyncMock(return_value=None)
    c.reply_permission = AsyncMock(return_value=None)
    c.get_config = AsyncMock(return_value={"model": default_model})
    if models is None:
        models = ["prov-a/model-a", "prov-a/model-b"]
    # Build a flattened-providers shape that matches what
    # ``_flatten_provider_models`` understands.
    providers: dict[str, dict[str, Any]] = {}
    for combo in models:
        if "/" not in combo:
            continue
        pid, mid = combo.split("/", 1)
        providers.setdefault(pid, {"id": pid, "models": {}})
        providers[pid]["models"][mid] = {}
    c.get_providers = AsyncMock(
        return_value={
            "providers": list(providers.values()),
            "default": {
                default_model.split("/", 1)[0]: default_model.split("/", 1)[1],
            },
        }
    )
    return c


def _seed_project(db: Session, project_id: str = "test-proj") -> Project:
    """Insert (or re-use) a Project row.

    Uses ``test_project`` fixture id by default so most tests can call
    ``GET /api/chat/tabs?project_id=test-proj`` without extra setup.
    """
    existing = db.get(Project, project_id)
    if existing is not None:
        return existing
    project = Project(
        id=project_id,
        display_name=project_id,
        repo_root=f"/repos/{project_id}",
        config={},
    )
    db.add(project)
    db.flush()
    return project


@pytest.fixture(autouse=True)
def _clear_chat_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop any cached config / skills / providers between tests so each test starts fresh."""
    monkeypatch.setattr(chat_mod, "_CONFIG_TTL", 0)
    chat_mod._config_cache.clear()
    chat_mod._skills_cache.clear()
    chat_mod._providers_cache.clear()


@pytest.fixture
def chat_app(
    db_session: Session, test_project: Project
) -> Generator[tuple[Any, Any, Any, Any], None, None]:
    """Yield (app, runtime, client, relay_manager) wired with healthy mocks."""
    os.environ["IW_CORE_TEST_CONTEXT"] = "true"
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        runtime = _healthy_runtime_mock()
        client = _client_mock()
        relay_manager = MagicMock()
        app.state.opencode_runtime = runtime
        app.state.opencode_client = client
        app.state.relay_manager = relay_manager
        app.dependency_overrides[get_db] = lambda: db_session
        yield app, runtime, client, relay_manager
        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture
def chat_test_client(chat_app: tuple[Any, Any, Any, Any]) -> Generator[TestClient, None, None]:
    app, *_ = chat_app
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc


def _healthy_runtime_mock_simple() -> Any:
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    rt.list_sessions = AsyncMock(return_value=[])
    return rt


# ---------------------------------------------------------------------------
# Pre-S06 RED evidence — preserved verbatim
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_tabs_rejects_unknown_runtime(db_session: Any) -> None:
    """RED evidence: POST /api/chat/tabs with runtime='pi' must return HTTP 400.

    Before S06's implementation the endpoint does not exist → 404.
    After S06's implementation it validates the allowlist → 400.
    """
    os.environ["IW_CORE_TEST_CONTEXT"] = "true"
    os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)

    app = create_app()
    app.state.opencode_runtime = _healthy_runtime_mock_simple()
    app.state.opencode_client = MagicMock()
    app.state.relay_manager = MagicMock()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            resp = await http.post(
                "/api/chat/tabs",
                json={
                    "project_id": "iw-ai-core",
                    "runtime": "pi",
                    "model": "some-model",
                },
            )
            assert resp.status_code == 400, (
                f"Expected 400 for unknown runtime 'pi'; got {resp.status_code}: {resp.text}"
            )
            body = resp.json()
            assert "error" in body, f"Expected 'error' key in response body; got {body}"
            assert "pi" in body["error"], (
                f"Expected 'pi' mentioned in error message; got {body['error']!r}"
            )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Happy path: POST /api/chat/tabs
# ---------------------------------------------------------------------------


def test_post_tabs_creates_active_tab(chat_test_client: TestClient, test_project: Project) -> None:
    """POST /api/chat/tabs persists a row and returns 201 with the tab body."""
    resp = chat_test_client.post(
        "/api/chat/tabs",
        json={
            "project_id": test_project.id,
            "model": "prov-a/model-a",
            "title": "My Tab",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "tab" in body, body
    tab = body["tab"]
    assert tab["project_id"] == test_project.id
    assert tab["title"] == "My Tab"
    assert tab["runtime"] == "opencode"
    assert tab["model"] == "prov-a/model-a"
    assert tab["status"] == "active"
    assert tab["closed_at"] is None
    # No header on the first insert (count == 1).
    assert "X-Tab-Soft-Cap-Exceeded" not in resp.headers


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_post_tabs_rejects_unknown_model(
    chat_test_client: TestClient, test_project: Project
) -> None:
    """Model not in the runtime's available models list → HTTP 400."""
    resp = chat_test_client.post(
        "/api/chat/tabs",
        json={
            "project_id": test_project.id,
            "model": "no-such/provider-model",
        },
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert "error" in body
    assert "no-such/provider-model" in body["error"]


# ---------------------------------------------------------------------------
# Soft cap (invariant #4 / AC7)
# ---------------------------------------------------------------------------


def test_post_tabs_soft_cap_header_on_eleventh(
    chat_test_client: TestClient, test_project: Project
) -> None:
    """The 11th tab gets ``X-Tab-Soft-Cap-Exceeded: true``; tabs 1-10 do not."""
    headers_per_tab: list[str | None] = []
    for i in range(11):
        resp = chat_test_client.post(
            "/api/chat/tabs",
            json={
                "project_id": test_project.id,
                "model": "prov-a/model-a",
                "title": f"T{i}",
            },
        )
        assert resp.status_code == 201, f"tab {i} create failed: {resp.text}"
        headers_per_tab.append(resp.headers.get("X-Tab-Soft-Cap-Exceeded"))

    # First ten responses: header absent.
    assert all(h is None for h in headers_per_tab[:10]), (
        f"unexpected soft-cap header on tabs 1-10: {headers_per_tab[:10]!r}"
    )
    # Eleventh: header present and "true".
    assert headers_per_tab[10] == "true", (
        f"expected X-Tab-Soft-Cap-Exceeded=true on tab 11, got {headers_per_tab[10]!r}"
    )

    # A 12th tab also exceeds.
    resp = chat_test_client.post(
        "/api/chat/tabs",
        json={"project_id": test_project.id, "model": "prov-a/model-a", "title": "T11"},
    )
    assert resp.status_code == 201
    assert resp.headers.get("X-Tab-Soft-Cap-Exceeded") == "true"


# ---------------------------------------------------------------------------
# GET /api/chat/tabs filtering and ordering
# ---------------------------------------------------------------------------


def test_get_tabs_excludes_closed_by_default(
    chat_test_client: TestClient, test_project: Project
) -> None:
    """A closed tab is hidden from ``GET /api/chat/tabs`` by default."""
    resp = chat_test_client.post(
        "/api/chat/tabs",
        json={"project_id": test_project.id, "model": "prov-a/model-a"},
    )
    tab_id = resp.json()["tab"]["id"]

    # Close it.
    del_resp = chat_test_client.delete(f"/api/chat/tabs/{tab_id}")
    assert del_resp.status_code == 204

    # Default list omits closed tabs.
    list_resp = chat_test_client.get(f"/api/chat/tabs?project_id={test_project.id}")
    assert list_resp.status_code == 200
    assert list_resp.json()["tabs"] == [], (
        f"expected empty default list when only tab is closed; got {list_resp.json()}"
    )


def test_get_tabs_includes_closed_when_requested(
    chat_test_client: TestClient, test_project: Project
) -> None:
    """``include_closed=true`` returns closed tabs alongside active ones."""
    resp = chat_test_client.post(
        "/api/chat/tabs",
        json={"project_id": test_project.id, "model": "prov-a/model-a"},
    )
    tab_id = resp.json()["tab"]["id"]
    chat_test_client.delete(f"/api/chat/tabs/{tab_id}")

    list_resp = chat_test_client.get(
        f"/api/chat/tabs?project_id={test_project.id}&include_closed=true"
    )
    assert list_resp.status_code == 200
    tabs = list_resp.json()["tabs"]
    assert len(tabs) == 1
    assert tabs[0]["id"] == tab_id
    assert tabs[0]["status"] == "closed"


def test_get_tabs_orders_by_last_active_desc(
    chat_test_client: TestClient,
    db_session: Session,
    test_project: Project,
) -> None:
    """Three active tabs come back in ``last_active_at DESC`` order."""
    import time as _time

    ids: list[str] = []
    for i in range(3):
        resp = chat_test_client.post(
            "/api/chat/tabs",
            json={
                "project_id": test_project.id,
                "model": "prov-a/model-a",
                "title": f"T{i}",
            },
        )
        ids.append(resp.json()["tab"]["id"])
        _time.sleep(0.01)

    # Touch the tabs in a deliberate order: tab 1, then tab 0, then tab 2
    # (tab 2 already has the freshest last_active_at from creation, so
    # touch tab 1 then tab 0 to invert).
    from orch.chat import tab_service

    tab_service.touch_last_active(db_session, ids[1])
    db_session.flush()
    db_session.commit()
    _time.sleep(0.01)
    tab_service.touch_last_active(db_session, ids[0])
    db_session.flush()
    db_session.commit()

    list_resp = chat_test_client.get(f"/api/chat/tabs?project_id={test_project.id}")
    assert list_resp.status_code == 200
    returned_ids = [t["id"] for t in list_resp.json()["tabs"]]
    # last-active-first ordering: tab 0 (most recently touched), then tab 1,
    # then tab 2 (oldest touch from initial creation).
    assert returned_ids == [ids[0], ids[1], ids[2]], (
        f"expected last_active_at DESC ordering {[ids[0], ids[1], ids[2]]}; got {returned_ids}"
    )


# ---------------------------------------------------------------------------
# PATCH semantics (invariant #8)
# ---------------------------------------------------------------------------


def test_patch_tabs_empty_body_does_not_bump_updated_at(
    chat_test_client: TestClient, test_project: Project
) -> None:
    """An empty PATCH body returns the tab unchanged with original ``updated_at``."""
    import time as _time

    resp = chat_test_client.post(
        "/api/chat/tabs",
        json={"project_id": test_project.id, "model": "prov-a/model-a", "title": "orig"},
    )
    tab_id = resp.json()["tab"]["id"]
    original_updated_at = resp.json()["tab"]["updated_at"]

    _time.sleep(0.02)

    patch_resp = chat_test_client.patch(f"/api/chat/tabs/{tab_id}", json={})
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["tab"]["updated_at"] == original_updated_at, (
        f"empty PATCH bumped updated_at: was {original_updated_at!r}, "
        f"now {body['tab']['updated_at']!r}"
    )
    assert body["tab"]["title"] == "orig"


def test_patch_tabs_updates_title_and_model_independently(
    chat_test_client: TestClient, test_project: Project
) -> None:
    """PATCH with title-only / model-only patches each field in isolation."""
    resp = chat_test_client.post(
        "/api/chat/tabs",
        json={"project_id": test_project.id, "model": "prov-a/model-a", "title": "orig"},
    )
    tab_id = resp.json()["tab"]["id"]

    title_only = chat_test_client.patch(f"/api/chat/tabs/{tab_id}", json={"title": "renamed"})
    assert title_only.status_code == 200
    assert title_only.json()["tab"]["title"] == "renamed"
    assert title_only.json()["tab"]["model"] == "prov-a/model-a"

    model_only = chat_test_client.patch(
        f"/api/chat/tabs/{tab_id}", json={"model": "prov-a/model-b"}
    )
    assert model_only.status_code == 200
    assert model_only.json()["tab"]["title"] == "renamed"
    assert model_only.json()["tab"]["model"] == "prov-a/model-b"


# ---------------------------------------------------------------------------
# DELETE / Reopen / recent-closed (AC8)  # noqa: ERA001
# ---------------------------------------------------------------------------


def test_delete_tabs_soft_deletes_and_idempotent(
    chat_test_client: TestClient, db_session: Session, test_project: Project
) -> None:
    """DELETE soft-closes the row; the row is preserved and DELETE is idempotent."""
    resp = chat_test_client.post(
        "/api/chat/tabs",
        json={"project_id": test_project.id, "model": "prov-a/model-a"},
    )
    tab_id = resp.json()["tab"]["id"]

    first = chat_test_client.delete(f"/api/chat/tabs/{tab_id}")
    assert first.status_code == 204

    db_session.expire_all()
    row = db_session.get(ChatTab, tab_id)
    assert row is not None
    assert row.status == "closed"
    assert row.closed_at is not None
    closed_at_first = row.closed_at

    # Second delete is idempotent: still 204, no closed_at bump.
    second = chat_test_client.delete(f"/api/chat/tabs/{tab_id}")
    assert second.status_code == 204
    db_session.expire_all()
    row_again = db_session.get(ChatTab, tab_id)
    assert row_again is not None
    assert row_again.closed_at == closed_at_first


def test_post_reopen_restores_active_status(
    chat_test_client: TestClient, db_session: Session, test_project: Project
) -> None:
    """POST .../reopen flips status back to 'active' and clears ``closed_at``."""
    resp = chat_test_client.post(
        "/api/chat/tabs",
        json={"project_id": test_project.id, "model": "prov-a/model-a"},
    )
    tab_id = resp.json()["tab"]["id"]

    chat_test_client.delete(f"/api/chat/tabs/{tab_id}")
    reopen = chat_test_client.post(f"/api/chat/tabs/{tab_id}/reopen")
    assert reopen.status_code == 200
    assert reopen.json()["tab"]["status"] == "active"
    assert reopen.json()["tab"]["closed_at"] is None

    db_session.expire_all()
    row = db_session.get(ChatTab, tab_id)
    assert row is not None
    assert row.status == "active"
    assert row.closed_at is None


def test_recent_closed_lists_closed_tabs_by_closed_at_desc(
    chat_test_client: TestClient, test_project: Project
) -> None:
    """``GET /api/chat/tabs/recent-closed`` orders by ``closed_at DESC``."""
    import time as _time

    ids: list[str] = []
    for i in range(3):
        resp = chat_test_client.post(
            "/api/chat/tabs",
            json={
                "project_id": test_project.id,
                "model": "prov-a/model-a",
                "title": f"T{i}",
            },
        )
        ids.append(resp.json()["tab"]["id"])

    # Close in order 0, 2, 1 → last-closed-first should yield [1, 2, 0].
    for idx in (0, 2, 1):
        chat_test_client.delete(f"/api/chat/tabs/{ids[idx]}")
        _time.sleep(0.01)

    recent = chat_test_client.get(f"/api/chat/tabs/recent-closed?project_id={test_project.id}")
    assert recent.status_code == 200
    returned_titles = [t["title"] for t in recent.json()["tabs"]]
    assert returned_titles == ["T1", "T2", "T0"], (
        f"unexpected recent-closed order: {returned_titles}"
    )


# ---------------------------------------------------------------------------
# Context percentage (AC1 / AC2)
# ---------------------------------------------------------------------------


def test_get_tab_injects_context_pct_when_token_data_present(
    chat_test_client: TestClient,
    db_session: Session,
    test_project: Project,
) -> None:
    """When an assistant message carries token usage and the model limit is known,
    ``GET /api/chat/tabs/{id}`` returns ``session.context_pct`` as a numeric value."""
    # Create a tab so we have a valid tab_id + session_id.
    create_resp = chat_test_client.post(
        "/api/chat/tabs",
        json={
            "project_id": test_project.id,
            "model": "prov-a/model-a",
            "title": "Context Test",
        },
    )
    assert create_resp.status_code == 201
    tab = create_resp.json()["tab"]
    tab_id = tab["id"]

    # Patch the client mock so get_messages returns a message with token usage.
    actual_client = getattr(chat_test_client.app.state, "opencode_client", None)
    assert actual_client is not None

    # Override get_messages to return an assistant message with tokens.
    assistant_msg = {
        "role": "assistant",
        "content": "Here is a detailed response.",
        "tokens": {
            "input": 5000,
            "output": 8000,
            "reasoning": 1000,
            "cache": {"read": 500, "write": 200},
        },
    }
    # Build a messages list with a user message first, then the assistant.
    messages_with_tokens = [
        {"role": "user", "content": "Hello"},
        assistant_msg,
    ]
    actual_client.get_messages = AsyncMock(return_value=messages_with_tokens)

    # Override get_providers to include a context limit for the model.
    actual_client.get_providers = AsyncMock(
        return_value={
            "providers": [
                {
                    "id": "prov-a",
                    "models": {
                        "model-a": {"limit": {"context": 100000}},
                        "model-b": {},
                    },
                }
            ],
            "default": {"prov-a": "model-a"},
        }
    )

    resp = chat_test_client.get(f"/api/chat/tabs/{tab_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "session" in body
    # 5000+8000+1000+500+200 = 14700; 14700/100000*100 = 14.7
    assert "context_pct" in body["session"], f"context_pct missing from session; body={body}"
    pct = body["session"]["context_pct"]
    assert isinstance(pct, float), f"Expected float, got {type(pct).__name__}: {pct}"
    assert pct == pytest.approx(14.7), f"Expected ~14.7, got {pct}"


def test_get_tab_omits_context_pct_when_no_token_data(
    chat_test_client: TestClient,
    db_session: Session,
    test_project: Project,
) -> None:
    """When no assistant message carries token usage, status is unknown_window."""
    create_resp = chat_test_client.post(
        "/api/chat/tabs",
        json={
            "project_id": test_project.id,
            "model": "prov-a/model-a",
            "title": "No Tokens",
        },
    )
    assert create_resp.status_code == 201
    tab = create_resp.json()["tab"]
    tab_id = tab["id"]

    # Override get_messages to return messages without token usage.
    actual_client = getattr(chat_test_client.app.state, "opencode_client", None)
    assert actual_client is not None
    actual_client.get_messages = AsyncMock(
        return_value=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
    )

    resp = chat_test_client.get(f"/api/chat/tabs/{tab_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "session" in body
    assert body["session"].get("context_pct") is None
    assert body["session"].get("context_pct_status") in (None, "unknown_window")
    assert body["session"].get("used_tokens") is None
    assert body["session"].get("window_tokens") is None


def test_get_tab_omits_context_pct_when_context_window_unknown(
    chat_test_client: TestClient,
    db_session: Session,
    test_project: Project,
) -> None:
    """When model limit is unknown, status is unknown_window and pct is null."""
    create_resp = chat_test_client.post(
        "/api/chat/tabs",
        json={
            "project_id": test_project.id,
            "model": "prov-a/model-a",
            "title": "No Limit",
        },
    )
    assert create_resp.status_code == 201
    tab = create_resp.json()["tab"]
    tab_id = tab["id"]

    # Override session/messages payloads.
    actual_client = getattr(chat_test_client.app.state, "opencode_client", None)
    assert actual_client is not None
    actual_client.get_session = AsyncMock(return_value={"id": "oc-sess-new", "status": "idle"})
    actual_client.get_messages = AsyncMock(
        return_value=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi", "tokens": {"input": 1000, "output": 2000}},
        ]
    )

    # Override get_providers to NOT include a limit for model-a.
    actual_client.get_providers = AsyncMock(
        return_value={
            "providers": [
                {
                    "id": "prov-a",
                    "models": {
                        "model-a": {},  # no limit.context
                        "model-b": {"limit": {"context": 200000}},
                    },
                }
            ],
            "default": {"prov-a": "model-a"},
        }
    )

    resp = chat_test_client.get(f"/api/chat/tabs/{tab_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "session" in body
    assert body["session"].get("context_pct") is None
    assert body["session"].get("context_pct_status") in (None, "unknown_window")
    assert body["session"].get("used_tokens") in (None, 3000)
    assert body["session"].get("window_tokens") is None


# ---------------------------------------------------------------------------
# No legacy session endpoints (invariant #7)
# ---------------------------------------------------------------------------


def test_no_legacy_session_endpoints(chat_test_client: TestClient) -> None:
    """The pre-F-00086 ``/api/chat/sessions/*`` surface is fully removed."""
    # GET /api/chat/sessions
    resp = chat_test_client.get("/api/chat/sessions")
    assert resp.status_code == 404, (
        f"GET /api/chat/sessions must return 404 (route removed by F-00086); got {resp.status_code}"
    )
    # GET /api/chat/sessions/anything
    resp = chat_test_client.get("/api/chat/sessions/some-sid")
    assert resp.status_code == 404
    # POST /api/chat/sessions
    resp = chat_test_client.post("/api/chat/sessions", json={})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AsyncIterator shim — kept for backwards compatibility with any callers that
# extend this file in the future (e.g., live SSE assertions).
# ---------------------------------------------------------------------------


async def _empty_event_stream() -> AsyncIterator[dict[str, Any]]:
    if False:  # pragma: no cover
        yield {}
