"""Unit tests for ``orch.chat.pi.pi_rpc_client.PiRpcClient`` (F-00087).

Tests:
    - send_command writes JSON + LF to subprocess stdin.
    - events() iterates JSONL from stdout via the LF-only reader.
    - request_response correlates by FIFO send order.
    - reply_extension_ui writes the correct extension_ui_response shape.
    - close() is idempotent.
    - close() escalates SIGTERM to SIGKILL when the process ignores it.
    - last_activity is updated on send AND on receive.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orch.chat.pi.pi_rpc_client import PiRpcClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_proc(stdout_data: bytes = b"") -> MagicMock:
    """Build a minimal asyncio.subprocess.Process mock with controllable stdout."""
    proc = MagicMock()
    proc.returncode = None

    # stdin
    proc.stdin = MagicMock()
    proc.stdin.is_closing = MagicMock(return_value=False)
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()
    proc.stdin.close = MagicMock()

    # stdout: real StreamReader pre-loaded with data
    reader = asyncio.StreamReader()
    reader.feed_data(stdout_data)
    reader.feed_eof()
    proc.stdout = reader

    # stderr
    proc.stderr = MagicMock()

    # signals
    proc.terminate = MagicMock()
    proc.kill = MagicMock()

    async def _wait():
        return 0

    proc.wait = _wait

    return proc


async def _make_client_with_mock_proc(
    stdout_data: bytes = b"",
) -> tuple[PiRpcClient, MagicMock]:
    """Instantiate a PiRpcClient whose subprocess is a mock."""
    client = PiRpcClient(session_dir=Path("/tmp/pi_test_rpc"))

    proc = _make_mock_proc(stdout_data)
    client._proc = proc
    client._closed = False
    client._pump_task = asyncio.create_task(client._pump_events(), name="test-pump")

    return client, proc


# ---------------------------------------------------------------------------
# send_command — writes JSON + LF to stdin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_command_writes_json_with_lf_terminator() -> None:
    """send_command encodes the dict as JSON and appends exactly one LF byte."""
    client, proc = await _make_client_with_mock_proc(b"")

    cmd: dict[str, Any] = {"type": "prompt", "message": "hi"}
    await client.send_command(cmd)

    # Grab all data written to stdin.write — it may be one or more calls.
    written_chunks = b"".join(call.args[0] for call in proc.stdin.write.call_args_list)

    # Must be valid JSON + exactly one LF at the end.
    assert written_chunks.endswith(b"\n"), f"expected LF terminator, got {written_chunks!r}"
    parsed = json.loads(written_chunks[:-1])  # strip the LF before parsing
    assert parsed == cmd

    # Cleanup
    await client.close()


@pytest.mark.asyncio
async def test_send_command_updates_last_activity() -> None:
    """send_command must advance last_activity to a value >= the pre-send baseline."""
    client, _ = await _make_client_with_mock_proc(b"")

    before = client.last_activity
    # Small sleep so monotonic clock can advance.
    await asyncio.sleep(0.001)
    await client.send_command({"type": "ping"})
    after = client.last_activity

    assert after >= before, (
        f"last_activity did not advance after send: before={before} after={after}"
    )
    await client.close()


# ---------------------------------------------------------------------------
# events() — iterates JSONL from stdout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_iterates_jsonl_from_stdout() -> None:
    """events() must yield one dict per JSONL line emitted on stdout."""
    # Build a client with a still-open stdout so we can feed data AFTER the
    # event consumer registers its queue with the pump.
    client = PiRpcClient(session_dir=Path("/tmp/pi_test_rpc"))
    proc = _make_mock_proc(b"")
    proc.stdout = asyncio.StreamReader()
    client._proc = proc
    client._closed = False
    client._pump_task = asyncio.create_task(client._pump_events(), name="test-pump")

    data = b'{"type":"agent_start"}\n{"type":"agent_end"}\n'

    async def feed_after_subscribe() -> None:
        # Give the events() iterator a moment to register its queue.
        await asyncio.sleep(0.02)
        proc.stdout.feed_data(data)

    feeder = asyncio.create_task(feed_after_subscribe())

    collected: list[dict[str, Any]] = []
    async for event in client.events():
        collected.append(event)
        if len(collected) == 2:
            break

    await feeder

    assert len(collected) == 2, f"expected 2 events, got {len(collected)}: {collected!r}"
    assert collected[0] == {"type": "agent_start"}
    assert collected[1] == {"type": "agent_end"}

    proc.stdout.feed_eof()
    await client.close()


# ---------------------------------------------------------------------------
# request_response — FIFO correlation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_response_correlates_by_send_order() -> None:
    """request_response resolves in the order commands were sent (Pi RPC FIFO)."""
    # Build client with a still-open stdout so we can feed responses AFTER the
    # request_response futures are queued (pump correlates positionally).
    client = PiRpcClient(session_dir=Path("/tmp/pi_test_rpc"))
    proc = _make_mock_proc(b"")
    proc.stdout = asyncio.StreamReader()
    client._proc = proc
    client._closed = False
    client._pump_task = asyncio.create_task(client._pump_events(), name="test-pump")

    # Feed response 1 after request 1 is awaiting, then response 2 after
    # request 2 is awaiting (serial — Pi RPC is strictly sequential).
    async def feed_one(payload: bytes) -> None:
        await asyncio.sleep(0.02)
        proc.stdout.feed_data(payload)

    asyncio.create_task(feed_one(b'{"type":"response","ok":true,"seq":1}\n'))
    resp1 = await client.request_response({"type": "cmd_a"}, timeout=5.0)

    asyncio.create_task(feed_one(b'{"type":"response","ok":true,"seq":2}\n'))
    resp2 = await client.request_response({"type": "cmd_b"}, timeout=5.0)

    assert resp1.get("seq") == 1, f"first response had wrong seq: {resp1!r}"
    assert resp2.get("seq") == 2, f"second response had wrong seq: {resp2!r}"

    proc.stdout.feed_eof()
    await client.close()


@pytest.mark.asyncio
async def test_request_response_timeout_raises() -> None:
    """request_response raises TimeoutError with a descriptive message when no reply comes."""
    client, _ = await _make_client_with_mock_proc(b"")

    with pytest.raises(TimeoutError, match="Pi RPC: no response for command 'slow_cmd'"):
        await client.request_response({"type": "slow_cmd"}, timeout=0.05)

    await client.close()


# ---------------------------------------------------------------------------
# reply_extension_ui — writes the correct extension_ui_response shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_extension_ui_writes_correct_shape() -> None:
    """reply_extension_ui writes extension_ui_response with the given id and value."""
    client, proc = await _make_client_with_mock_proc(b"")

    await client.reply_extension_ui("iw-chat-approvals.abc", True)

    written = b"".join(call.args[0] for call in proc.stdin.write.call_args_list)
    assert written.endswith(b"\n"), "expected LF-terminated output"
    payload = json.loads(written[:-1])
    assert payload == {
        "type": "extension_ui_response",
        "id": "iw-chat-approvals.abc",
        "value": True,
    }, f"unexpected payload: {payload!r}"

    await client.close()


@pytest.mark.asyncio
async def test_reply_extension_ui_deny_writes_false() -> None:
    """reply_extension_ui with value=False encodes ``value:false`` in the JSON."""
    client, proc = await _make_client_with_mock_proc(b"")

    await client.reply_extension_ui("iw-chat-approvals.deny-test", False)

    written = b"".join(call.args[0] for call in proc.stdin.write.call_args_list)
    payload = json.loads(written.strip())
    assert payload["value"] is False, f"expected False, got {payload['value']!r}"
    assert payload["id"] == "iw-chat-approvals.deny-test"

    await client.close()


# ---------------------------------------------------------------------------
# close() — idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_is_idempotent() -> None:
    """Calling close() twice must not raise."""
    client, proc = await _make_client_with_mock_proc(b"")

    await client.close()
    # Second call must not raise any exception.
    await client.close()

    # Process still only gets one terminate call (the second close() is a no-op).
    assert proc.terminate.call_count <= 1


# ---------------------------------------------------------------------------
# close() — SIGTERM → SIGKILL escalation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_escalates_sigterm_to_sigkill_when_process_stalls() -> None:
    """When the subprocess ignores SIGTERM (wait times out), SIGKILL must be sent.

    We simulate a stalled subprocess by making proc.wait() never resolve
    within the grace period.
    """
    client, proc = await _make_client_with_mock_proc(b"")

    # Override wait() so it never returns within the timeout.
    async def _stall_forever():
        await asyncio.sleep(9999)

    proc.wait = _stall_forever

    # Use a very short grace period to keep the test fast.
    with patch("orch.chat.pi.pi_rpc_client._GRACE_SECONDS", 0.05):
        await client.close()

    proc.terminate.assert_called_once()
    proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# last_activity — updated on send AND receive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_activity_updates_on_send_and_receive() -> None:
    """last_activity must advance after a send AND after an event is received.

    The mock subprocess uses a still-open StreamReader (no feed_eof) so we
    can inject a stdout event after the client has started.
    """
    # Build a client with a non-EOF stdout reader so we can stream data later.
    client = PiRpcClient(session_dir=Path("/tmp/pi_test_rpc"))
    proc = _make_mock_proc(b"")
    # Replace stdout with a fresh, NOT-eof'd reader.
    proc.stdout = asyncio.StreamReader()
    client._proc = proc
    client._closed = False
    client._pump_task = asyncio.create_task(client._pump_events(), name="test-pump")

    t0 = client.last_activity

    # Advance time and send a command.
    await asyncio.sleep(0.005)
    await client.send_command({"type": "ping"})
    t_after_send = client.last_activity
    assert t_after_send > t0, "last_activity should increase after send"

    # Pump an event through the stdout reader (reader is still open).
    proc.stdout.feed_data(b'{"type":"agent_start"}\n')

    await asyncio.sleep(0.05)
    t_after_receive = client.last_activity
    assert t_after_receive >= t_after_send, "last_activity should be updated after receiving event"

    # Cleanly tear down — feed_eof so the pump task can exit.
    proc.stdout.feed_eof()
    await client.close()
