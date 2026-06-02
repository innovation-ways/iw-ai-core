"""Unit tests for PiRuntime LRU eviction (F-00087).

Invariant #4 — MAX_PI_TABS cap is honoured by LRU eviction, never by rejection:
    - Creating an arbitrary number of Pi tabs always succeeds.
    - Active-subprocess count is min(active_tab_count, MAX_PI_TABS).

Tests:
    test_seventh_tab_evicts_lru  — 7 tabs created; the LRU client's close() is called.
    test_eviction_picks_oldest_last_activity — eviction picks the client with
        the oldest last_activity, not necessarily the first created.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from orch.chat.pi.pi_runtime import MAX_PI_TABS, PiRuntime

# ---------------------------------------------------------------------------
# Helper: build a minimal mock PiRpcClient
# ---------------------------------------------------------------------------


def _make_mock_client(last_activity: float | None = None) -> MagicMock:
    """Return a minimal mock PiRpcClient with controllable last_activity.

    Args:
        last_activity: Monotonic timestamp to assign; defaults to time.monotonic() if None.

    Returns:
        A MagicMock with close, start, and send_command AsyncMocks attached.
    """
    client = MagicMock()
    client.close = AsyncMock()
    client.start = AsyncMock()
    client.send_command = AsyncMock()
    client.last_activity = last_activity if last_activity is not None else time.monotonic()
    return client


# ---------------------------------------------------------------------------
# Invariant #4 — 7th tab evicts the LRU
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seventh_tab_evicts_lru() -> None:
    """Creating a 7th Pi tab when MAX_PI_TABS=6 must evict the LRU client.

    The LRU client is the one with the oldest ``last_activity`` timestamp.
    Its ``close()`` coroutine must be awaited exactly once.
    """
    assert MAX_PI_TABS == 6, f"Test assumes MAX_PI_TABS==6, got {MAX_PI_TABS}"

    runtime = PiRuntime(base_session_dir=Path("/tmp/pi_test_sessions"))

    # Cancel the idle reaper so it does not interfere with the test.
    if runtime._reaper_task is not None:
        runtime._reaper_task.cancel()
        with pytest.raises((asyncio.CancelledError, Exception)):
            await runtime._reaper_task

    now = time.monotonic()

    # Pre-populate _clients with 6 mock clients, each with a distinct
    # last_activity. session_ids[0] will be the LRU (oldest).
    session_ids: list[str] = []
    lru_client: MagicMock | None = None

    for i in range(MAX_PI_TABS):
        sid = await runtime.create_session()
        session_ids.append(sid)
        mock_client = _make_mock_client(last_activity=now - (MAX_PI_TABS - i) * 10)
        runtime._clients[sid] = mock_client
        runtime._client_tab_meta[sid] = {
            "last_activity": mock_client.last_activity,
            "pi_session_path": None,
        }
        if i == 0:
            lru_client = mock_client  # oldest last_activity

    assert len(runtime._clients) == MAX_PI_TABS
    assert lru_client is not None

    # Create the 7th session. This should evict session_ids[0] (LRU).
    # We patch _spawn_client so no real subprocess is started.
    new_sid = await runtime.create_session()
    # Wire in a new mock client for the 7th session so _get_or_spawn_client works.
    new_mock = _make_mock_client(last_activity=time.monotonic())
    runtime._clients[new_sid] = new_mock
    runtime._client_tab_meta[new_sid] = {
        "last_activity": new_mock.last_activity,
        "pi_session_path": None,
    }

    # Trigger eviction explicitly (create_session is lazy — eviction happens on
    # _get_or_spawn_client). We call it directly.
    await runtime._evict_lru_if_needed()

    # The LRU client's close() must have been called.
    lru_client.close.assert_awaited_once()

    # Active client count must not exceed MAX_PI_TABS.
    assert len(runtime._clients) <= MAX_PI_TABS


# ---------------------------------------------------------------------------
# Eviction picks oldest last_activity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eviction_picks_oldest_last_activity() -> None:
    """When multiple clients exist, the one with the smallest last_activity is evicted."""
    runtime = PiRuntime(base_session_dir=Path("/tmp/pi_test_sessions"))

    if runtime._reaper_task is not None:
        runtime._reaper_task.cancel()
        with pytest.raises((asyncio.CancelledError, Exception)):
            await runtime._reaper_task

    now = time.monotonic()

    # Insert MAX_PI_TABS + 1 clients — only MAX_PI_TABS + 1 to trigger one eviction.
    sids: list[str] = []
    oldest_sid: str | None = None
    oldest_client: MagicMock | None = None

    for i in range(MAX_PI_TABS + 1):
        sid = await runtime.create_session()
        sids.append(sid)
        # Make client i=3 the oldest (smallest last_activity).
        activity = now - (100 if i == 3 else i * 5)
        mock = _make_mock_client(last_activity=activity)
        runtime._clients[sid] = mock
        runtime._client_tab_meta[sid] = {
            "last_activity": activity,
            "pi_session_path": None,
        }
        if i == 3:
            oldest_sid = sid
            oldest_client = mock

    assert oldest_client is not None

    await runtime._evict_lru_if_needed()

    # The oldest client must have been evicted.
    oldest_client.close.assert_awaited_once()
    # Its session must be removed from _clients.
    assert oldest_sid not in runtime._clients


# ---------------------------------------------------------------------------
# Evicted tab preserves session metadata (for lazy respawn)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evicted_tab_persists_session_metadata() -> None:
    """After LRU eviction the tab's metadata (pi_session_path) is retained in
    ``_client_tab_meta`` so a subsequent _get_or_spawn_client can resume via
    ``pi --session <path>``.
    """
    runtime = PiRuntime(base_session_dir=Path("/tmp/pi_test_meta"))

    if runtime._reaper_task is not None:
        runtime._reaper_task.cancel()
        with pytest.raises((asyncio.CancelledError, Exception)):
            await runtime._reaper_task

    now = time.monotonic()

    # Create MAX_PI_TABS sessions with known pi_session_path values.
    session_ids: list[str] = []
    for i in range(MAX_PI_TABS):
        sid = await runtime.create_session()
        session_ids.append(sid)
        mock_client = _make_mock_client(last_activity=now - (MAX_PI_TABS - i) * 10)
        runtime._clients[sid] = mock_client
        runtime._client_tab_meta[sid] = {
            "last_activity": mock_client.last_activity,
            "pi_session_path": f"/sessions/{sid}.jsonl",
        }

    lru_sid = session_ids[0]  # oldest last_activity

    # Add the (MAX_PI_TABS + 1)th session, triggering eviction.
    new_sid = await runtime.create_session()
    new_mock = _make_mock_client(last_activity=time.monotonic())
    runtime._clients[new_sid] = new_mock
    runtime._client_tab_meta[new_sid] = {
        "last_activity": new_mock.last_activity,
        "pi_session_path": None,
    }

    await runtime._evict_lru_if_needed()

    # LRU client is gone from _clients …
    assert lru_sid not in runtime._clients

    # … but its metadata is PRESERVED so we can respawn with --session.
    assert lru_sid in runtime._client_tab_meta, (
        "pi_session_path metadata must survive eviction for lazy respawn"
    )
    assert runtime._client_tab_meta[lru_sid]["pi_session_path"] == f"/sessions/{lru_sid}.jsonl"


# ---------------------------------------------------------------------------
# IW_CORE_MAX_PI_TABS env-var override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_pi_tabs_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting IW_CORE_MAX_PI_TABS=3 must cause eviction to fire on the 4th tab."""
    monkeypatch.setenv("IW_CORE_MAX_PI_TABS", "3")

    import importlib

    import orch.chat.pi.pi_runtime as _rt_mod

    importlib.reload(_rt_mod)

    try:
        effective_cap = _rt_mod.MAX_PI_TABS
        assert effective_cap == 3, (
            f"expected MAX_PI_TABS==3 after env override, got {effective_cap}"
        )

        PiRuntimeLocal = _rt_mod.PiRuntime  # noqa: N806 — reloaded class binding
        runtime = PiRuntimeLocal(base_session_dir=Path("/tmp/pi_test_cap_env"))

        if runtime._reaper_task is not None:
            runtime._reaper_task.cancel()
            with pytest.raises((asyncio.CancelledError, Exception)):
                await runtime._reaper_task

        now = time.monotonic()

        # Fill exactly 3 sessions (the new cap).
        session_ids: list[str] = []
        for i in range(3):
            sid = await runtime.create_session()
            session_ids.append(sid)
            mock_client = _make_mock_client(last_activity=now - (3 - i) * 10)
            runtime._clients[sid] = mock_client
            runtime._client_tab_meta[sid] = {
                "last_activity": mock_client.last_activity,
                "pi_session_path": None,
            }

        lru_sid = session_ids[0]
        lru_client: MagicMock = runtime._clients[lru_sid]

        # Add a 4th session — eviction must fire.
        new_sid = await runtime.create_session()
        new_mock = _make_mock_client(last_activity=time.monotonic())
        runtime._clients[new_sid] = new_mock
        runtime._client_tab_meta[new_sid] = {
            "last_activity": new_mock.last_activity,
            "pi_session_path": None,
        }

        await runtime._evict_lru_if_needed()

        lru_client.close.assert_awaited_once()
        assert lru_sid not in runtime._clients
        assert len(runtime._clients) <= 3
    finally:
        monkeypatch.delenv("IW_CORE_MAX_PI_TABS", raising=False)
        importlib.reload(_rt_mod)
