"""End-to-end integration tests for the Dashboard AI Assistant — happy path.

Exercises the full pipeline:

    POST /api/chat/tabs                           → real OpencodeClient → fake `opencode serve`
    POST /api/chat/tabs/{tab_id}/prompt
    GET  /api/chat/tabs/{tab_id}/stream            ← SSE bytes flow back through the
                                                     real RelayManager + SessionRelay
    POST /api/chat/tabs/{tab_id}/abort

The fake server (see ``_fake_opencode.py``) is a real ASGI app served by
``uvicorn`` on a background thread on a random loopback port. The dashboard
relay opens a real TCP/SSE connection to it, so the test exercises the
production wire path — only the upstream binary is replaced.

Per ``tests/CLAUDE.md`` we use the testcontainer ``db_session`` fixture for
DB pinning; the chat endpoints themselves touch the DB only for tab creation
and last_active_at updates.

Adapted from F-00083 (pre-tab surface) to F-00086 (tab-scoped surface):
- POST /api/chat/sessions → POST /api/chat/tabs
- /api/chat/sessions/{sid}/... → /api/chat/tabs/{tab_id}/...
- directory in request body → resolved from Project.repo_root
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.chat.opencode.client import OpencodeClient
from orch.chat.opencode.relay_manager import RelayManager
from orch.db.models import Project
from tests.integration._fake_opencode import FakeOpencodeServer, fake_opencode_server

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _healthy_runtime_mock() -> Any:
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    return rt


async def _build_chat_app(
    fake: FakeOpencodeServer,
    db_session: Session,
) -> tuple[Any, OpencodeClient, RelayManager]:
    """Construct a dashboard app wired to the fake OpenCode + DB session."""
    os.environ["IW_CORE_TEST_CONTEXT"] = "true"
    original_eii = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    if original_eii is not None:
        # tests/conftest.py doesn't clear this; restore on teardown via finalizer
        # (the fixture-level cleanup handles env restoration if needed).
        os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)

    app = create_app()
    client = OpencodeClient(base_url=fake.base_url, password="test-password")  # noqa: S106
    relay_manager = RelayManager(client)
    app.state.opencode_runtime = _healthy_runtime_mock()
    app.state.opencode_client = client
    app.state.relay_manager = relay_manager
    app.dependency_overrides[get_db] = lambda: db_session
    return app, client, relay_manager


def _parse_sse(body: str) -> list[dict[str, str]]:
    """Parse SSE wire bytes into a list of ``{event, data, id}`` dicts.

    Tolerates the keep-alive comment lines (``": keepalive"``) that the
    dashboard interleaves.
    """
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
            continue  # keep-alive comment
        if ":" in line:
            field, _, value = line.partition(":")
            value = value.lstrip(" ")
            if field in {"event", "data", "id"}:
                current[field] = current.get(field, "") + value
    if current:
        events.append(current)
    return events


async def _read_until_relay_drops(
    http: AsyncClient,
    tab_id: str,
    relay_manager: RelayManager,
    fake: FakeOpencodeServer,
    *,
    push_then_drop: Any,
) -> list[dict[str, str]]:
    """Open SSE stream, run a coroutine that pushes events + drops relay, return parsed events."""
    body_parts: list[str] = []

    async def _consume() -> None:
        async with http.stream("GET", f"/api/chat/tabs/{tab_id}/stream", timeout=20.0) as resp:
            assert resp.status_code == 200
            async for chunk in resp.aiter_text():
                body_parts.append(chunk)

    consumer = asyncio.create_task(_consume())
    # Allow the relay's upstream pump to connect to the fake server.
    # Use the ASYNC waiter so the test loop yields while polling — otherwise
    # the consumer task never gets a chance to issue the SSE request.
    await fake.control.await_stream(0, timeout=5.0)
    try:
        await push_then_drop()
    finally:
        # Ensure the consumer exits even if push_then_drop didn't trigger close.
        if not consumer.done():
            await relay_manager.drop_relay(tab_id)
        await asyncio.wait_for(consumer, timeout=5.0)
    return _parse_sse("".join(body_parts))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_lifecycle_create_prompt_stream_abort(
    db_session: Session,
    test_project: Project,
) -> None:
    """AC2 happy path: create tab → prompt → stream 3+ events → abort cleanly.

    Adapted: POST /api/chat/sessions → POST /api/chat/tabs; subsequent URLs
    use tab_id (not the raw OpenCode session id).
    """
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                # ---- create tab ----
                resp = await http.post(
                    "/api/chat/tabs",
                    json={"project_id": test_project.id},
                )
                assert resp.status_code == 201, resp.text
                tab = resp.json()["tab"]
                tab_id = tab["id"]
                sid = tab["opencode_session_id"]
                assert sid.startswith("ses_")
                # The fake server logs this as an inbound POST.
                create_posts = fake.control.posts_matching_path("/session")
                assert len(create_posts) == 1

                # ---- send prompt ----
                resp = await http.post(
                    f"/api/chat/tabs/{tab_id}/prompt",
                    json={"text": "list files in dashboard/routers"},
                )
                assert resp.status_code == 204
                # Fake server received the prompt forward.
                prompt_posts = fake.control.posts_matching_path(f"/session/{sid}/prompt_async")
                assert len(prompt_posts) == 1
                assert prompt_posts[0].body is not None
                # OpencodeClient wraps the text in a `parts` array.
                assert prompt_posts[0].body["parts"][0]["text"] == (
                    "list files in dashboard/routers"
                )

                # ---- open stream, push 3 events, drop relay ----
                async def push_then_drop() -> None:
                    fake.control.push_event_to(
                        0,
                        event_id="evt_001",
                        event_type="message.part.delta",
                        properties={"sessionID": sid, "delta": "Sure, "},
                    )
                    fake.control.push_event_to(
                        0,
                        event_id="evt_002",
                        event_type="message.part.delta",
                        properties={"sessionID": sid, "delta": "here you go."},
                    )
                    fake.control.push_event_to(
                        0,
                        event_id="evt_003",
                        event_type="session.idle",
                        properties={"sessionID": sid},
                    )
                    # Let the events flow through the pump → relay → SSE.
                    await asyncio.sleep(0.3)
                    await relay_manager.drop_relay(tab_id)

                events = await _read_until_relay_drops(
                    http, tab_id, relay_manager, fake, push_then_drop=push_then_drop
                )

                # Assert: at least the three pushed events appear, in order,
                # with the correct ids and types.
                event_ids = [e.get("id") for e in events if e.get("id")]
                assert "evt_001" in event_ids
                assert "evt_002" in event_ids
                assert "evt_003" in event_ids
                # Strict ordering (evt_001 before evt_002 before evt_003).
                assert event_ids.index("evt_001") < event_ids.index("evt_002")
                assert event_ids.index("evt_002") < event_ids.index("evt_003")

                # Event-type lines exist for each.
                event_types = [e.get("event") for e in events]
                assert "message.part.delta" in event_types
                assert "session.idle" in event_types

                # Payload survives JSON round-trip — the `delta` text is in
                # the rendered data line for evt_001.
                evt1 = next(e for e in events if e.get("id") == "evt_001")
                assert "Sure," in evt1["data"]

                # ---- abort ----
                resp = await http.post(f"/api/chat/tabs/{tab_id}/abort")
                assert resp.status_code == 204
                abort_posts = fake.control.posts_matching_path(f"/session/{sid}/abort")
                assert len(abort_posts) == 1
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_concurrent_sessions_independent_streams(
    db_session: Session,
    test_project: Project,
) -> None:
    """AC3: two tabs, two streams, events don't bleed across sessions.

    Adapted: POST /api/chat/sessions → POST /api/chat/tabs (×2). Each tab
    gets its own opencode_session_id; relay is keyed by tab_id.
    """
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp_a = await http.post(
                    "/api/chat/tabs",
                    json={"project_id": test_project.id},
                )
                resp_b = await http.post(
                    "/api/chat/tabs",
                    json={"project_id": test_project.id},
                )
                assert resp_a.status_code == 201, resp_a.text
                assert resp_b.status_code == 201, resp_b.text
                tab_a = resp_a.json()["tab"]
                tab_b = resp_b.json()["tab"]
                tab_id_a = tab_a["id"]
                tab_id_b = tab_b["id"]
                sid_a = tab_a["opencode_session_id"]
                sid_b = tab_b["opencode_session_id"]
                assert tab_id_a != tab_id_b
                assert sid_a != sid_b

                body_a: list[str] = []
                body_b: list[str] = []

                async def consume_a() -> None:
                    async with http.stream(
                        "GET", f"/api/chat/tabs/{tab_id_a}/stream", timeout=20.0
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            body_a.append(chunk)

                async def consume_b() -> None:
                    async with http.stream(
                        "GET", f"/api/chat/tabs/{tab_id_b}/stream", timeout=20.0
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            body_b.append(chunk)

                task_a = asyncio.create_task(consume_a())
                # Pin the upstream-connection ordering: open A's stream
                # first, wait for its pump to register, THEN open B's.
                await fake.control.await_stream(0, timeout=5.0)
                task_b = asyncio.create_task(consume_b())
                await fake.control.await_stream(1, timeout=5.0)

                # Push 3 events to A's queue and 3 to B's queue, distinct ids.
                fake.control.push_event_to(
                    0,
                    event_id="A_evt_1",
                    event_type="message.part.delta",
                    properties={"sessionID": sid_a, "delta": "alpha"},
                )
                fake.control.push_event_to(
                    1,
                    event_id="B_evt_1",
                    event_type="message.part.delta",
                    properties={"sessionID": sid_b, "delta": "beta"},
                )
                fake.control.push_event_to(
                    0,
                    event_id="A_evt_2",
                    event_type="session.idle",
                    properties={"sessionID": sid_a},
                )
                fake.control.push_event_to(
                    1,
                    event_id="B_evt_2",
                    event_type="session.idle",
                    properties={"sessionID": sid_b},
                )

                await asyncio.sleep(0.4)
                await relay_manager.drop_relay(tab_id_a)
                await relay_manager.drop_relay(tab_id_b)

                await asyncio.wait_for(task_a, timeout=5.0)
                await asyncio.wait_for(task_b, timeout=5.0)

                events_a = _parse_sse("".join(body_a))
                events_b = _parse_sse("".join(body_b))

                ids_a = [e.get("id") for e in events_a if e.get("id")]
                ids_b = [e.get("id") for e in events_b if e.get("id")]

                # Session A sees ONLY its own events; B sees ONLY its own.
                assert "A_evt_1" in ids_a
                assert "A_evt_2" in ids_a
                assert "B_evt_1" not in ids_a, f"B's events leaked into A's stream: {ids_a}"
                assert "B_evt_2" not in ids_a

                assert "B_evt_1" in ids_b
                assert "B_evt_2" in ids_b
                assert "A_evt_1" not in ids_b, f"A's events leaked into B's stream: {ids_b}"
                assert "A_evt_2" not in ids_b
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_session_error_event_surfaces_to_sse_stream(
    db_session: Session,
    test_project: Project,
) -> None:
    """Boundary row H1: ``session.error`` (and unknown error types like
    ``provider_unauthenticated``) must flow from the fake upstream through the
    relay and appear in the dashboard SSE stream intact.

    Adapted: POST /api/chat/sessions → POST /api/chat/tabs; stream URL uses tab_id.
    """
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp = await http.post(
                    "/api/chat/tabs",
                    json={"project_id": test_project.id},
                )
                assert resp.status_code == 201, resp.text
                tab = resp.json()["tab"]
                tab_id = tab["id"]
                sid = tab["opencode_session_id"]

                async def push_error_events_then_drop() -> None:
                    # Emit a session.error event (what OpenCode likely emits
                    # when the provider is unauthenticated).
                    fake.control.push_event_to(
                        0,
                        event_id="err_001",
                        event_type="session.error",
                        properties={
                            "sessionID": sid,
                            "error": "provider not authenticated",
                            "provider": "anthropic",
                        },
                    )
                    # Also emit a hypothetical provider-specific event to
                    # verify unknown types also pass through at the wire level.
                    fake.control.push_event_to(
                        0,
                        event_id="err_002",
                        event_type="provider_unauthenticated",
                        properties={
                            "sessionID": sid,
                            "provider": "anthropic",
                            "message": "API key not configured",
                        },
                    )
                    await asyncio.sleep(0.3)
                    await relay_manager.drop_relay(tab_id)

                events = await _read_until_relay_drops(
                    http,
                    tab_id,
                    relay_manager,
                    fake,
                    push_then_drop=push_error_events_then_drop,
                )

                # Both error events must appear in the SSE stream.
                event_map = {e.get("id"): e for e in events if e.get("id")}
                assert "err_001" in event_map, (
                    f"session.error event missing from stream; got ids: {list(event_map)}"
                )
                assert "err_002" in event_map, (
                    f"provider_unauthenticated event missing from stream (relay must not drop "
                    f"unknown error event types); got ids: {list(event_map)}"
                )
                # Verify the event type labels survive end-to-end.
                assert event_map["err_001"].get("event") == "session.error"
                assert event_map["err_002"].get("event") == "provider_unauthenticated"
                # Verify payload contents survive JSON round-trip.
                assert "anthropic" in event_map["err_001"]["data"]
                assert "anthropic" in event_map["err_002"]["data"]
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_session_forwards_directory_to_opencode(
    db_session: Session,
    test_project: Project,
) -> None:
    """CR-00057: the dashboard must forward the project's repo_root to opencode's
    ``POST /session`` as the ``directory`` field.

    Adapted: the pre-S06 surface accepted ``directory`` in the POST /api/chat/sessions
    body and forwarded it verbatim. The new POST /api/chat/tabs surface resolves
    directory from ``Project.repo_root`` instead. We set ``test_project.repo_root``
    to a known path and assert opencode receives it via the project lookup.

    The second sub-test: when ``Project.repo_root`` is None (or empty), the
    ``directory`` key must NOT appear in the opencode request — same fail-open
    semantics as the legacy "omit directory when client sends none" case.
    """
    project_dir = "/srv/projects/iw-ai-core"
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                # Set up project with a known repo_root.
                test_project.repo_root = project_dir
                db_session.add(test_project)
                db_session.commit()

                # Clear any stale config cache from prior tests — the cache
                # may hold project_directory="/repos/test" (test_project's
                # default) which would shadow the repo_root we just set.
                from dashboard.routers import chat as _chat_mod  # noqa: PLC0415

                _chat_mod._config_cache.clear()

                resp = await http.post(
                    "/api/chat/tabs",
                    json={"project_id": test_project.id},
                )
                assert resp.status_code == 201, resp.text

                create_posts = fake.control.posts_matching_path("/session")
                assert len(create_posts) == 1
                body = create_posts[0].body
                assert isinstance(body, dict), f"expected JSON body, got {body!r}"
                assert body.get("directory") == project_dir, (
                    f"directory not forwarded to opencode from project.repo_root; got body={body!r}"
                )

                # Sanity: when project.repo_root is empty, directory must NOT be
                # sent to opencode — the production code maps "" → directory=None
                # → key absent from the POST body. repo_root is NOT NULL in the DB
                # schema, so we use "" (empty string) to represent "no directory".
                project_no_dir = Project(
                    id="proj-no-dir",
                    display_name="No Dir",
                    repo_root="",
                    config={},
                )
                db_session.add(project_no_dir)
                db_session.commit()

                resp_no_dir = await http.post(
                    "/api/chat/tabs",
                    json={"project_id": "proj-no-dir"},
                )
                assert resp_no_dir.status_code == 201, resp_no_dir.text
                create_posts_all = fake.control.posts_matching_path("/session")
                assert len(create_posts_all) == 2
                body_no_dir = create_posts_all[1].body
                assert isinstance(body_no_dir, dict)
                assert "directory" not in body_no_dir, (
                    f"directory key leaked when project.repo_root is empty; body={body_no_dir!r}"
                )
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()
