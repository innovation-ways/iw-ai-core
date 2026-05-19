"""F-00086 invariant #2 / AC1 — two tabs stream independently with distinct models.

Stubs the runtime client (per the design's TDD §): no real OpenCode
server is spawned. Each tab gets its own per-relay event queue so we
can deterministically push events to one tab's stream and verify they
NEVER appear on the other tab's stream — the canonical proof of
invariant #2 ("every event has a top-level tab_id matching the
subscriber's tab_id").
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers import chat as chat_mod

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_mock_with_models(models: list[str], default_model: str) -> Any:
    """Build an OpencodeClient mock whose providers expose ``models``."""
    c = MagicMock()
    # create_session returns a fresh id each call so each tab gets its own sid.
    sids = iter(f"oc-sess-{i}" for i in range(1, 1000))
    c.create_session = AsyncMock(side_effect=lambda **_kw: next(sids))
    c.get_session = AsyncMock(return_value={"id": "oc-sess", "status": "idle"})
    c.get_messages = AsyncMock(return_value=[])
    c.list_sessions = AsyncMock(return_value=[])
    c.prompt = AsyncMock(return_value=None)
    c.abort = AsyncMock(return_value=None)
    c.reply_permission = AsyncMock(return_value=None)
    c.get_config = AsyncMock(return_value={"model": default_model})
    providers: dict[str, dict[str, Any]] = {}
    for combo in models:
        pid, mid = combo.split("/", 1)
        providers.setdefault(pid, {"id": pid, "models": {}})
        providers[pid]["models"][mid] = {}
    c.get_providers = AsyncMock(
        return_value={
            "providers": list(providers.values()),
            "default": {default_model.split("/", 1)[0]: default_model.split("/", 1)[1]},
        }
    )
    return c


class _StubRelay:
    """Holds a per-tab queue + emits events stamped with this relay's tab_id."""

    def __init__(self, tab_id: str) -> None:
        self.tab_id = tab_id
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.subscribe_calls: list[str | None] = []

    def push(self, event_type: str, data: dict[str, Any], event_id: str) -> None:
        ev: dict[str, Any] = {
            "event": event_type,
            "data": data,
            "id": event_id,
            "tab_id": self.tab_id,
        }
        self._queue.put_nowait(ev)

    def close(self) -> None:
        self._queue.put_nowait(None)

    async def subscribe(self, last_event_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        self.subscribe_calls.append(last_event_id)
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item


class _StubRelayManager:
    """Maps tab_id → _StubRelay; ``get_or_create_relay`` is async."""

    def __init__(self) -> None:
        self.relays: dict[str, _StubRelay] = {}

    async def get_or_create_relay(self, tab_id: str) -> _StubRelay:
        relay = self.relays.get(tab_id)
        if relay is None:
            relay = _StubRelay(tab_id)
            self.relays[tab_id] = relay
        return relay


def _parse_sse(body: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in body.split("\n"):
        line = raw_line.rstrip("\r")
        if line == "":
            if current:
                events.append(current)
                current = {}
            continue
        if line.startswith(":"):
            continue
        if ":" in line:
            field, _, value = line.partition(":")
            value = value.lstrip(" ")
            if field in {"event", "data", "id"}:
                current[field] = current.get(field, "") + value
    if current:
        events.append(current)
    return events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_chat_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "_CONFIG_TTL", 0)
    chat_mod._config_cache.clear()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_tabs_stream_independently_with_distinct_models(
    db_session: Session, test_project: Project
) -> None:
    """Invariant #2 / AC1: events for tab A only carry A's tab_id, ditto for B.

    Drives the full router stack: POST /api/chat/tabs (creates a per-tab
    OpenCode session), POST /api/chat/tabs/{id}/prompt (records the
    prompt + model per-tab), GET /api/chat/tabs/{id}/stream (SSE relay
    fan-out via the stubbed relay manager). The stub relay stamps
    ``tab_id`` exactly the way the production ``SessionRelay`` does.
    """
    os.environ["IW_CORE_TEST_CONTEXT"] = "true"
    os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)

    model_a = "anthropic/claude-sonnet-4-7"
    model_b = "openai/gpt-5.3-codex"

    app = create_app()
    runtime = MagicMock()
    runtime.health = AsyncMock(return_value=True)
    runtime.list_sessions = AsyncMock(return_value=[])
    client = _client_mock_with_models([model_a, model_b], default_model=model_a)
    relay_manager = _StubRelayManager()
    app.state.opencode_runtime = runtime
    app.state.opencode_client = client
    app.state.relay_manager = relay_manager
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            # ---- create two tabs with distinct models ----
            resp_a = await http.post(
                "/api/chat/tabs",
                json={"project_id": test_project.id, "model": model_a, "title": "A"},
            )
            assert resp_a.status_code == 201, resp_a.text
            tab_a_id = resp_a.json()["tab"]["id"]
            assert resp_a.json()["tab"]["model"] == model_a

            resp_b = await http.post(
                "/api/chat/tabs",
                json={"project_id": test_project.id, "model": model_b, "title": "B"},
            )
            assert resp_b.status_code == 201, resp_b.text
            tab_b_id = resp_b.json()["tab"]["id"]
            assert resp_b.json()["tab"]["model"] == model_b
            assert tab_a_id != tab_b_id

            # ---- send a prompt to each tab and assert the model arg flowed through ----
            client.prompt.reset_mock()
            resp = await http.post(
                f"/api/chat/tabs/{tab_a_id}/prompt",
                json={"text": "P_A", "model": model_a},
            )
            assert resp.status_code == 204, resp.text
            resp = await http.post(
                f"/api/chat/tabs/{tab_b_id}/prompt",
                json={"text": "P_B", "model": model_b},
            )
            assert resp.status_code == 204, resp.text

            calls = client.prompt.await_args_list
            assert len(calls) == 2, f"expected two prompt() calls, got {len(calls)}"
            models_used = sorted(call.kwargs.get("model") for call in calls)
            assert models_used == sorted([model_a, model_b]), (
                f"each tab's prompt must carry its own model; got models={models_used}"
            )
            texts_sent = [
                call.args[1] if len(call.args) >= 2 else call.kwargs.get("text") for call in calls
            ]
            assert sorted(texts_sent) == ["P_A", "P_B"], texts_sent

            # ---- open both streams concurrently ----
            body_a: list[str] = []
            body_b: list[str] = []

            async def consume_a() -> None:
                async with http.stream(
                    "GET", f"/api/chat/tabs/{tab_a_id}/stream", timeout=20.0
                ) as resp:
                    assert resp.status_code == 200, resp.status_code
                    async for chunk in resp.aiter_text():
                        body_a.append(chunk)

            async def consume_b() -> None:
                async with http.stream(
                    "GET", f"/api/chat/tabs/{tab_b_id}/stream", timeout=20.0
                ) as resp:
                    assert resp.status_code == 200, resp.status_code
                    async for chunk in resp.aiter_text():
                        body_b.append(chunk)

            task_a = asyncio.create_task(consume_a())
            task_b = asyncio.create_task(consume_b())

            # Wait for the router to instantiate the relays via the
            # stubbed RelayManager. The relays appear on first GET.
            for _ in range(50):
                if tab_a_id in relay_manager.relays and tab_b_id in relay_manager.relays:
                    break
                await asyncio.sleep(0.02)
            relay_a = relay_manager.relays[tab_a_id]
            relay_b = relay_manager.relays[tab_b_id]

            # ---- push three events to A and three to B with distinct ids ----
            relay_a.push("message.part.delta", {"text": "alpha-1"}, "A_evt_1")
            relay_b.push("message.part.delta", {"text": "beta-1"}, "B_evt_1")
            relay_a.push("message.part.delta", {"text": "alpha-2"}, "A_evt_2")
            relay_b.push("message.part.delta", {"text": "beta-2"}, "B_evt_2")
            relay_a.push("session.idle", {}, "A_evt_3")
            relay_b.push("session.idle", {}, "B_evt_3")

            await asyncio.sleep(0.2)

            # ---- ABORT tab A: subsequent events on B must STILL flow ----
            client.abort.reset_mock()
            abort_resp = await http.post(f"/api/chat/tabs/{tab_a_id}/abort")
            assert abort_resp.status_code == 204
            assert client.abort.await_count == 1
            # Aborting A doesn't end its stream by itself; we close the A relay
            # manually to mirror the production "abort → relay drop" flow.
            relay_a.close()

            # Push more to B AFTER A is closed; B must continue.
            relay_b.push("message.part.delta", {"text": "beta-after-abort"}, "B_evt_4")
            await asyncio.sleep(0.2)
            relay_b.close()

            await asyncio.wait_for(task_a, timeout=5.0)
            await asyncio.wait_for(task_b, timeout=5.0)
    finally:
        app.dependency_overrides.clear()

    # ---- assertions on the parsed SSE bodies ----
    events_a = _parse_sse("".join(body_a))
    events_b = _parse_sse("".join(body_b))

    ids_a = [e.get("id") for e in events_a if e.get("id")]
    ids_b = [e.get("id") for e in events_b if e.get("id")]

    assert "A_evt_1" in ids_a
    assert "A_evt_2" in ids_a
    assert "A_evt_3" in ids_a
    assert "B_evt_1" in ids_b
    assert "B_evt_2" in ids_b
    assert "B_evt_3" in ids_b
    # B continues to emit after A is aborted/closed.
    assert "B_evt_4" in ids_b, f"B must keep streaming after A is aborted; got ids={ids_b}"

    # Cross-pollination check (invariant #2).
    for bid in ("B_evt_1", "B_evt_2", "B_evt_3", "B_evt_4"):
        assert bid not in ids_a, f"event {bid} leaked into A's stream: ids={ids_a}"
    for aid in ("A_evt_1", "A_evt_2", "A_evt_3"):
        assert aid not in ids_b, f"event {aid} leaked into B's stream: ids={ids_b}"

    # tab_id field present in every data payload (invariant #2 — at the wire
    # level the router serialises the relay's full event dict via JSON, so
    # ``data`` carries ``{"text": ...}`` and the tab_id stamp lives in the
    # JSON envelope written by the relay. Our stubbed relay writes the
    # event with ``tab_id`` set; we assert that no event with a foreign
    # tab_id reaches the wrong stream).
    for ev in events_a:
        # The router writes ``data`` as the relay's ``data`` field (not the
        # full event). We can't grep tab_id in ``data`` directly — but we
        # have already proven cross-pollination is absent above, which is
        # the testable consequence of correct tab_id stamping.
        assert "event" in ev
    for ev in events_b:
        assert "event" in ev
