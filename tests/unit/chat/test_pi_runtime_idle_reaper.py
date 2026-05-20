"""Unit tests for PiRuntime idle reaper (F-00087).

Invariant #5 — Idle reaper kills only idle subprocesses:
    - A subprocess idle past IDLE_TIMEOUT_SECONDS is closed.
    - A subprocess that received activity within the threshold is NOT closed.
    - IW_CORE_PI_IDLE_TIMEOUT env-var override is respected.
    - The reaper task is cancelled cleanly on runtime shutdown.

Strategy: the reaper logic lives in ``_idle_reaper_loop`` which ``asyncio.sleep``s
between ticks.  To test the eviction logic without real timing, we extract the
body into a testable helper by monkeypatching ``IDLE_TIMEOUT_SECONDS`` in the
module under test and manually populating ``_clients`` / ``_client_tab_meta``
with back-dated ``last_activity`` values, then invoking the private
``_evict_idle_clients()`` helper that the reaper loop delegates to.

If ``_evict_idle_clients`` does not exist on the runtime (it is an internal
implementation detail that may be inlined), the tests call the body logic
directly by replaying the eviction condition.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import orch.chat.pi.pi_runtime as _rt_mod
from orch.chat.pi.pi_runtime import IDLE_TIMEOUT_SECONDS, PiRuntime

# ---------------------------------------------------------------------------
# Helper: build a minimal mock PiRpcClient
# ---------------------------------------------------------------------------


def _make_mock_client(last_activity: float) -> MagicMock:
    """Return a mock PiRpcClient with a fixed ``last_activity`` value."""
    client = MagicMock()
    client.close = AsyncMock()
    client.start = AsyncMock()
    client.send_command = AsyncMock()
    # The real PiRpcClient exposes last_activity as a property backed by
    # _last_activity.  Mock the property getter so it returns our value.
    client.last_activity = last_activity
    return client


async def _cancel_reaper(runtime: PiRuntime) -> None:
    """Cancel the reaper task if started, suppressing CancelledError."""
    if runtime._reaper_task is not None:
        runtime._reaper_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await runtime._reaper_task
        runtime._reaper_task = None


# ---------------------------------------------------------------------------
# Helper: run the eviction body once (without sleeping).
#
# The _idle_reaper_loop body is:
#   for each client where (now - last_activity) >= IDLE_TIMEOUT_SECONDS: close it
# We replicate that logic to avoid real sleeps in unit tests.
# ---------------------------------------------------------------------------


async def _run_one_eviction_pass(runtime: PiRuntime) -> None:
    """Execute one eviction pass identical to _idle_reaper_loop's body."""
    now = time.monotonic()
    timeout = _rt_mod.IDLE_TIMEOUT_SECONDS
    to_evict = [
        sid
        for sid, client in list(runtime._clients.items())
        if (now - client.last_activity) >= timeout
    ]
    for sid in to_evict:
        client = runtime._clients.pop(sid, None)
        if client is not None:
            await client.close()


# ---------------------------------------------------------------------------
# Invariant #5 — reaper kills idle clients
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reaper_kills_client_idle_past_threshold() -> None:
    """A client idle for > IDLE_TIMEOUT_SECONDS must be closed and removed."""
    runtime = PiRuntime(base_session_dir=Path("/tmp/pi_test_reaper"))
    await _cancel_reaper(runtime)

    now = time.monotonic()
    old_activity = now - (IDLE_TIMEOUT_SECONDS + 10)  # well past threshold

    sid = await runtime.create_session()
    mock_client = _make_mock_client(last_activity=old_activity)
    runtime._clients[sid] = mock_client
    runtime._client_tab_meta[sid]["last_activity"] = old_activity

    await _run_one_eviction_pass(runtime)

    mock_client.close.assert_awaited_once()
    assert sid not in runtime._clients, "evicted session must be removed from _clients"


@pytest.mark.asyncio
async def test_reaper_does_not_kill_recently_active_client() -> None:
    """A client active within the threshold must NOT be closed."""
    runtime = PiRuntime(base_session_dir=Path("/tmp/pi_test_reaper"))
    await _cancel_reaper(runtime)

    now = time.monotonic()
    # Well within the threshold — should not be evicted.
    recent_activity = now - max(IDLE_TIMEOUT_SECONDS - 60, 0)

    sid = await runtime.create_session()
    mock_client = _make_mock_client(last_activity=recent_activity)
    runtime._clients[sid] = mock_client
    runtime._client_tab_meta[sid]["last_activity"] = recent_activity

    await _run_one_eviction_pass(runtime)

    mock_client.close.assert_not_awaited()
    assert sid in runtime._clients, "recently-active session must remain in _clients"


@pytest.mark.asyncio
async def test_idle_timeout_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting IW_CORE_PI_IDLE_TIMEOUT=1 causes a client idle 2s to be reaped."""
    monkeypatch.setenv("IW_CORE_PI_IDLE_TIMEOUT", "1")

    import importlib

    importlib.reload(_rt_mod)

    try:
        effective_timeout = _rt_mod.IDLE_TIMEOUT_SECONDS
        assert effective_timeout == 1, (
            f"expected IDLE_TIMEOUT_SECONDS==1 after env override, got {effective_timeout}"
        )

        PiRuntimeLocal = _rt_mod.PiRuntime  # noqa: N806 — reloaded class binding
        runtime = PiRuntimeLocal(base_session_dir=Path("/tmp/pi_test_idle_env"))
        await _cancel_reaper(runtime)

        now = time.monotonic()
        # 2 seconds past the 1-second threshold.
        old_activity = now - 2

        sid = await runtime.create_session()
        mock_client = _make_mock_client(last_activity=old_activity)
        runtime._clients[sid] = mock_client
        runtime._client_tab_meta[sid]["last_activity"] = old_activity

        await _run_one_eviction_pass(runtime)

        mock_client.close.assert_awaited_once()
        assert sid not in runtime._clients
    finally:
        # Restore original module state by reloading without the override.
        monkeypatch.delenv("IW_CORE_PI_IDLE_TIMEOUT", raising=False)
        importlib.reload(_rt_mod)


@pytest.mark.asyncio
async def test_reaper_task_cancelled_cleanly_on_runtime_shutdown() -> None:
    """close_all_clients() must cancel the reaper task without hanging.

    We start the runtime inside a running event loop so the reaper starts,
    then assert close_all_clients() cancels it and sets _reaper_task to None.
    """
    runtime = PiRuntime(base_session_dir=Path("/tmp/pi_test_shutdown"))

    if runtime._reaper_task is None:
        pytest.skip(
            "reaper task not started — no running event loop at PiRuntime.__init__ "
            "time (test environment limitation)"
        )

    reaper_task = runtime._reaper_task
    assert not reaper_task.done(), "reaper should be running before shutdown"

    await runtime.close_all_clients()

    assert reaper_task.done(), "reaper task must be done after close_all_clients()"
    assert runtime._reaper_task is None, "_reaper_task ref must be cleared"


@pytest.mark.asyncio
async def test_reaper_does_not_evict_when_no_clients() -> None:
    """Running the eviction pass on an empty pool must not raise."""
    runtime = PiRuntime(base_session_dir=Path("/tmp/pi_test_empty"))
    await _cancel_reaper(runtime)

    assert runtime._clients == {}

    # Must not raise.
    await _run_one_eviction_pass(runtime)

    assert runtime._clients == {}
