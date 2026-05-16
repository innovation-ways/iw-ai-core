"""Integration tests for the E2E OpenCode stub process."""

from __future__ import annotations

import base64
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from httpx_sse import connect_sse

if TYPE_CHECKING:
    from collections.abc import Iterator

STUB_PATH = Path(__file__).resolve().parents[2] / "scripts" / "e2e_opencode_stub.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_ready(base_url: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/global/health", timeout=0.5)
            if resp.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"stub at {base_url} did not start within {timeout}s")


def _auth_headers(password: str) -> dict[str, str]:
    token = base64.b64encode(f"opencode:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _create_session(base_url: str, password: str) -> str:
    with httpx.Client(auth=httpx.BasicAuth("opencode", password), timeout=2.0) as client:
        resp = client.post(
            f"{base_url}/session",
            json={"model": "stub/echo", "agent": "build", "directory": "/tmp"},
        )
    assert resp.status_code == 200
    sid = resp.json()["id"]
    return str(sid)


def _collect_events(iterator: object, *, count: int) -> list[object]:
    events = []
    for _ in range(count):
        events.append(next(iterator))  # type: ignore[arg-type]
    return events


@pytest.fixture(scope="module")
def stub() -> Iterator[tuple[str, str]]:
    port = _free_port()
    password = secrets.token_hex(16)
    proc = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            str(STUB_PATH),
            "serve",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env={**os.environ, "OPENCODE_SERVER_PASSWORD": password},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_ready(base_url)
        yield base_url, password
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def test_health_returns_200_unauthenticated(stub: tuple[str, str]) -> None:
    base_url, _ = stub
    resp = httpx.get(f"{base_url}/global/health", timeout=2.0)
    assert resp.status_code == 200
    assert resp.text == ""


def test_basic_auth_required_on_protected_endpoints(stub: tuple[str, str]) -> None:
    base_url, password = stub
    no_auth = httpx.get(f"{base_url}/config", timeout=2.0)
    assert no_auth.status_code == 401

    wrong_auth = httpx.get(
        f"{base_url}/config",
        headers=_auth_headers("wrong-password"),
        timeout=2.0,
    )
    assert wrong_auth.status_code == 401

    right_auth = httpx.get(f"{base_url}/config", headers=_auth_headers(password), timeout=2.0)
    assert right_auth.status_code == 200


def test_config_returns_models_array(stub: tuple[str, str]) -> None:
    base_url, password = stub
    resp = httpx.get(f"{base_url}/config", headers=_auth_headers(password), timeout=2.0)
    assert resp.status_code == 200
    data = resp.json()
    assert data["models"] == [{"id": "stub/echo", "name": "Stub Echo"}]
    assert data["default_model"] == "stub/echo"
    assert data["default_model"] in {row["id"] for row in data["models"]}


def test_session_create_returns_id(stub: tuple[str, str]) -> None:
    base_url, password = stub
    sid = _create_session(base_url, password)
    assert sid.startswith("ses_")
    assert len(sid) == 12
    assert set(sid[4:]).issubset(set("0123456789abcdef"))


def test_session_list_returns_created_sessions(stub: tuple[str, str]) -> None:
    base_url, password = stub
    sid_1 = _create_session(base_url, password)
    sid_2 = _create_session(base_url, password)

    with httpx.Client(auth=httpx.BasicAuth("opencode", password), timeout=2.0) as client:
        listed = client.get(f"{base_url}/session")

    assert listed.status_code == 200
    rows = listed.json()
    assert [row["id"] for row in rows[-2:]] == [sid_1, sid_2]


def test_session_get_unknown_returns_404(stub: tuple[str, str]) -> None:
    base_url, password = stub
    with httpx.Client(auth=httpx.BasicAuth("opencode", password), timeout=2.0) as client:
        resp = client.get(f"{base_url}/session/nonexistent")
    assert resp.status_code == 404


def test_messages_empty_for_new_session(stub: tuple[str, str]) -> None:
    base_url, password = stub
    sid = _create_session(base_url, password)
    with httpx.Client(auth=httpx.BasicAuth("opencode", password), timeout=2.0) as client:
        resp = client.get(f"{base_url}/session/{sid}/messages")
    assert resp.status_code == 200
    assert resp.json() == []


def test_prompt_async_returns_200_then_event_stream_emits_sequence(stub: tuple[str, str]) -> None:
    base_url, password = stub
    sid = _create_session(base_url, password)
    auth = httpx.BasicAuth("opencode", password)

    with (
        httpx.Client(base_url=base_url, auth=auth, timeout=3.0) as client,
        connect_sse(client, "GET", "/event") as event_source,
    ):
        event_iter = event_source.iter_sse()
        prompt = client.post(
            f"/session/{sid}/prompt_async",
            json={"parts": [{"type": "text", "text": "run ls"}]},
        )
        assert prompt.status_code == 200
        events = _collect_events(event_iter, count=3)

    assert [event.event for event in events] == [
        "message.updated",
        "message.updated",
        "permission.asked",
    ]
    ids = [int(str(event.id)) for event in events]
    assert ids[0] < ids[1] < ids[2]


def test_permissions_allow_resumes_stream(stub: tuple[str, str]) -> None:
    base_url, password = stub
    sid = _create_session(base_url, password)
    auth = httpx.BasicAuth("opencode", password)

    with (
        httpx.Client(base_url=base_url, auth=auth, timeout=3.0) as client,
        connect_sse(client, "GET", "/event") as event_source,
    ):
        event_iter = event_source.iter_sse()
        prompt = client.post(
            f"/session/{sid}/prompt_async",
            json={"parts": [{"type": "text", "text": "run ls"}]},
        )
        assert prompt.status_code == 200
        events = _collect_events(event_iter, count=3)
        permission = events[2].json()
        rid = str(permission["request_id"])

        allow = client.post(f"/session/{sid}/permissions/{rid}", json={"response": "allow"})
        assert allow.status_code == 200
        resumed = _collect_events(event_iter, count=3)

    assert resumed[0].event == "message.updated"
    assert resumed[0].json()["tool_continued"] is True
    assert resumed[1].event == "message.updated"
    assert resumed[1].json()["status"] == "complete"
    assert resumed[2].event == "session.idle"
    assert resumed[2].json() == {"session_id": sid}


def test_permissions_deny_terminates_stream(stub: tuple[str, str]) -> None:
    base_url, password = stub
    sid = _create_session(base_url, password)
    auth = httpx.BasicAuth("opencode", password)

    with (
        httpx.Client(base_url=base_url, auth=auth, timeout=3.0) as client,
        connect_sse(client, "GET", "/event") as event_source,
    ):
        event_iter = event_source.iter_sse()
        prompt = client.post(
            f"/session/{sid}/prompt_async",
            json={"parts": [{"type": "text", "text": "run ls"}]},
        )
        assert prompt.status_code == 200
        events = _collect_events(event_iter, count=3)
        rid = str(events[2].json()["request_id"])

        deny = client.post(f"/session/{sid}/permissions/{rid}", json={"response": "deny"})
        assert deny.status_code == 200
        post_deny = _collect_events(event_iter, count=2)

    assert post_deny[0].event == "message.updated"
    assert post_deny[0].json()["tool_blocked"] is True
    assert post_deny[1].event == "session.idle"
    assert post_deny[1].json() == {"session_id": sid, "permission_denied": True}


def test_abort_emits_session_idle_immediately(stub: tuple[str, str]) -> None:
    base_url, password = stub
    sid = _create_session(base_url, password)
    auth = httpx.BasicAuth("opencode", password)

    with (
        httpx.Client(base_url=base_url, auth=auth, timeout=3.0) as client,
        connect_sse(client, "GET", "/event") as event_source,
    ):
        event_iter = event_source.iter_sse()
        prompt = client.post(
            f"/session/{sid}/prompt_async",
            json={"parts": [{"type": "text", "text": "run ls"}]},
        )
        assert prompt.status_code == 200
        _collect_events(event_iter, count=3)
        aborted = client.post(f"/session/{sid}/abort")
        assert aborted.status_code == 200
        next_event = _collect_events(event_iter, count=1)[0]

    assert next_event.event == "session.idle"
    assert next_event.json() == {"session_id": sid, "aborted": True}


def test_last_event_id_replay_from_ring_buffer(stub: tuple[str, str]) -> None:
    base_url, password = stub
    sid = _create_session(base_url, password)
    auth = httpx.BasicAuth("opencode", password)

    with httpx.Client(base_url=base_url, auth=auth, timeout=3.0) as client:
        with connect_sse(client, "GET", "/event") as event_source:
            event_iter = event_source.iter_sse()
            prompt = client.post(
                f"/session/{sid}/prompt_async",
                json={"parts": [{"type": "text", "text": "run ls"}]},
            )
            assert prompt.status_code == 200
            first_three = _collect_events(event_iter, count=3)
            checkpoint = str(first_three[0].id)
            rid = str(first_three[2].json()["request_id"])
            allow = client.post(f"/session/{sid}/permissions/{rid}", json={"response": "allow"})
            assert allow.status_code == 200

        with connect_sse(client, "GET", "/event", headers={"Last-Event-ID": checkpoint}) as replay:
            replay_iter = replay.iter_sse()
            replay_events = _collect_events(replay_iter, count=4)

    replay_ids = [int(str(ev.id)) for ev in replay_events]
    assert replay_ids == sorted(replay_ids)
    assert replay_ids[0] > int(checkpoint)


def test_invalid_argv_exits_with_code_2() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(STUB_PATH), "--unknown-flag"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2


def test_no_password_in_stub_stderr() -> None:
    port = _free_port()
    password = secrets.token_hex(16)
    proc = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            str(STUB_PATH),
            "serve",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env={**os.environ, "OPENCODE_SERVER_PASSWORD": password},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_ready(base_url)
        sid = _create_session(base_url, password)
        auth = httpx.BasicAuth("opencode", password)
        with (
            httpx.Client(base_url=base_url, auth=auth, timeout=3.0) as client,
            connect_sse(client, "GET", "/event") as event_source,
        ):
            event_iter = event_source.iter_sse()
            prompt = client.post(
                f"/session/{sid}/prompt_async",
                json={"parts": [{"type": "text", "text": "run ls"}]},
            )
            assert prompt.status_code == 200
            events = _collect_events(event_iter, count=3)
            rid = str(events[2].json()["request_id"])
            allow = client.post(f"/session/{sid}/permissions/{rid}", json={"response": "allow"})
            assert allow.status_code == 200
            _collect_events(event_iter, count=2)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    stderr = proc.stderr.read() if proc.stderr is not None else ""
    assert password not in stderr
