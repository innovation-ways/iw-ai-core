"""Integration tests: Pi approval flow end-to-end (F-00087 AC3).

Uses the stub ``pi`` binary (tests/integration/stubs/pi → _pi_stub.py).
The stub emits an ``extension_ui_request`` with id="iw-chat-approvals.test-001"
when the prompt contains "trigger-approval".

Tests:
    - test_ask_pattern_surfaces_permission_asked_event
    - test_approve_response_writes_value_true_to_stdin
    - test_deny_response_sends_value_false
    - test_non_iw_approvals_request_passes_through
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
from typing import Any

import pytest

from orch.chat.pi.pi_runtime import PiRuntime

_STUBS_DIR = Path(__file__).resolve().parent / "stubs"


@pytest.fixture
def stub_pi_on_path(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Prepend tests/integration/stubs/ to PATH so 'pi' resolves to the stub."""
    monkeypatch.setenv("PATH", f"{_STUBS_DIR}{os.pathsep}{os.environ.get('PATH', '')}")
    return _STUBS_DIR / "pi"


async def _cancel_reaper(runtime: PiRuntime) -> None:
    """Cancel the reaper task if started."""
    if runtime._reaper_task is not None:
        runtime._reaper_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await runtime._reaper_task
        runtime._reaper_task = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_events_until(
    runtime: PiRuntime,
    session_id: str,
    predicate: Any,
    timeout: float = 5.0,
) -> list[dict[str, Any]]:
    """Collect events from a session until ``predicate(event)`` is True or timeout."""
    collected: list[dict[str, Any]] = []
    with contextlib.suppress(TimeoutError):
        async with asyncio.timeout(timeout):
            async for evt in runtime._subscribe_impl(session_id):
                collected.append(evt)
                if predicate(evt):
                    break
    return collected


# ---------------------------------------------------------------------------
# AC3 — approval request surfaces as permission.asked event
# ---------------------------------------------------------------------------


async def _subscribe_with_normalization(
    runtime: PiRuntime,
    session_id: str,
    on_event: Any,
) -> asyncio.Task[None]:
    """Pre-spawn the client and start a collect task that calls ``on_event(normalised)``.

    Returns the collect task once the events() iterator has had a chance to
    register its queue with the pump.  This avoids the fan-out race where
    stdout events arrive before any queue is registered.
    """
    from orch.chat.pi.event_normalizer import normalize_pi_event

    await runtime._get_or_spawn_client(session_id)
    client = runtime._clients[session_id]

    async def _collect() -> None:
        async for raw_event in client.events():
            runtime._touch_activity(session_id)
            normalised = normalize_pi_event(raw_event)
            if normalised is None:
                continue
            should_stop = await on_event(normalised)
            if should_stop:
                break

    task = asyncio.create_task(_collect())
    # Give the events() iterator a slice to enter its loop and register
    # its queue with the pump task.
    await asyncio.sleep(0.05)
    return task


@pytest.mark.asyncio
async def test_ask_pattern_surfaces_permission_asked_event(
    stub_pi_on_path: Path,
    tmp_path: Path,
) -> None:
    """Sending 'trigger-approval' causes the stub to emit extension_ui_request,
    which the normalizer translates to a permission.asked event.

    The permission.asked event must carry: id, tool, args, question.
    """
    runtime = PiRuntime(base_session_dir=tmp_path / "sessions", binary="pi")
    await _cancel_reaper(runtime)

    try:
        sid = await runtime.create_session()

        events: list[dict[str, Any]] = []
        event_ready = asyncio.Event()

        async def _on_event(evt: dict[str, Any]) -> bool:
            events.append(evt)
            if evt.get("event") == "permission.asked":
                event_ready.set()
                return True
            return False

        collect_task = await _subscribe_with_normalization(runtime, sid, _on_event)

        # Now send the trigger-approval prompt.
        await runtime.prompt(sid, "please trigger-approval now")

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(event_ready.wait(), timeout=5.0)

        collect_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await collect_task

        approval_events = [e for e in events if e.get("event") == "permission.asked"]
        assert approval_events, (
            f"expected at least one permission.asked event, got events: {events!r}"
        )

        evt = approval_events[0]
        data = evt["data"]
        assert data["id"] == "iw-chat-approvals.test-001", f"unexpected id: {data.get('id')!r}"
        assert data["tool"] == "bash", f"unexpected tool: {data.get('tool')!r}"
        assert data["args"] == {"cmd": "rm temp.txt"}, f"unexpected args: {data.get('args')!r}"
        assert data["question"] is not None, "question field must be present"
    finally:
        await runtime.close_all_clients()


@pytest.mark.asyncio
async def test_approve_response_writes_value_true_to_stdin(
    stub_pi_on_path: Path,
    tmp_path: Path,
) -> None:
    """reply_permission('approve') → extension_ui_response with value:true → stub proceeds.

    After approving, the stub emits tool_execution_end with result='ok'.
    We verify the tool_execution.end event arrives, confirming the approval
    round-trip completed successfully.
    """
    runtime = PiRuntime(base_session_dir=tmp_path / "sessions", binary="pi")
    await _cancel_reaper(runtime)

    try:
        sid = await runtime.create_session()

        events: list[dict[str, Any]] = []
        approval_ready = asyncio.Event()
        tool_end_ready = asyncio.Event()

        async def _on_event(evt: dict[str, Any]) -> bool:
            events.append(evt)
            if evt.get("event") == "permission.asked":
                approval_ready.set()
            if evt.get("event") == "tool.execution.end":
                tool_end_ready.set()
                return True
            return False

        collect_task = await _subscribe_with_normalization(runtime, sid, _on_event)
        await runtime.prompt(sid, "trigger-approval please")

        # Wait for the approval request.
        try:
            await asyncio.wait_for(approval_ready.wait(), timeout=5.0)
        except TimeoutError:
            collect_task.cancel()
            pytest.fail("Timed out waiting for permission.asked event")

        # Approve the request.
        await runtime.reply_permission(sid, "iw-chat-approvals.test-001", "approve")

        # Wait for the tool.execution.end event confirming the stub proceeded.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(tool_end_ready.wait(), timeout=5.0)

        collect_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await collect_task

        tool_end_events = [e for e in events if e.get("event") == "tool.execution.end"]
        assert tool_end_events, (
            f"expected tool.execution.end after approval, got events: {events!r}"
        )
        # After an approve, the stub returns result='ok'.
        assert tool_end_events[0]["data"].get("result") == "ok", (
            f"unexpected result after approve: {tool_end_events[0]!r}"
        )
    finally:
        await runtime.close_all_clients()


@pytest.mark.asyncio
async def test_deny_response_sends_value_false(
    stub_pi_on_path: Path,
    tmp_path: Path,
) -> None:
    """reply_permission('deny') → extension_ui_response with value:false.

    After denying, the stub emits tool_execution_end with result='denied'.
    """
    runtime = PiRuntime(base_session_dir=tmp_path / "sessions", binary="pi")
    await _cancel_reaper(runtime)

    try:
        sid = await runtime.create_session()

        events: list[dict[str, Any]] = []
        approval_ready = asyncio.Event()
        tool_end_ready = asyncio.Event()

        async def _on_event(evt: dict[str, Any]) -> bool:
            events.append(evt)
            if evt.get("event") == "permission.asked":
                approval_ready.set()
            if evt.get("event") == "tool.execution.end":
                tool_end_ready.set()
                return True
            return False

        collect_task = await _subscribe_with_normalization(runtime, sid, _on_event)
        await runtime.prompt(sid, "trigger-approval please")

        try:
            await asyncio.wait_for(approval_ready.wait(), timeout=5.0)
        except TimeoutError:
            collect_task.cancel()
            pytest.fail("Timed out waiting for permission.asked event")

        # Deny the request.
        await runtime.reply_permission(sid, "iw-chat-approvals.test-001", "deny")

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(tool_end_ready.wait(), timeout=5.0)

        collect_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await collect_task

        tool_end_events = [e for e in events if e.get("event") == "tool.execution.end"]
        assert tool_end_events, f"expected tool.execution.end after deny, got events: {events!r}"
        assert tool_end_events[0]["data"].get("result") == "denied", (
            f"unexpected result after deny: {tool_end_events[0]!r}"
        )
    finally:
        await runtime.close_all_clients()
