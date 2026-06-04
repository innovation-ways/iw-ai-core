"""Integration tests: Pi runtime lifecycle (F-00087).

Uses the stub ``pi`` binary on PATH.

Tests:
    - test_first_prompt_spawns_subprocess_lazily
    - test_idle_reaper_terminates_then_reactivate_respawns
    - test_lru_eviction_when_creating_nth_tab
    - test_pi_binary_missing_returns_runtime_error
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from pathlib import Path

import pytest

from orch.chat.pi.pi_runtime import PiRuntime

_STUBS_DIR = Path(__file__).resolve().parent / "stubs"


@pytest.fixture
def stub_pi_on_path(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Prepend tests/integration/stubs/ to PATH so 'pi' resolves to the stub."""
    monkeypatch.setenv("PATH", f"{_STUBS_DIR}{os.pathsep}{os.environ.get('PATH', '')}")
    return _STUBS_DIR / "pi"


@pytest.fixture
def no_pi_on_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Set PATH to ONLY an empty directory so no 'pi' binary is found.

    A real ``pi`` binary may be installed system-wide at ``/usr/bin/pi``;
    we must clobber PATH entirely (not just prepend) to guarantee a clean
    'binary not found' state for the test.
    """
    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))
    return empty_dir


async def _cancel_reaper(runtime: PiRuntime) -> None:
    """Cancel the reaper task if started."""
    if runtime._reaper_task is not None:
        runtime._reaper_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await runtime._reaper_task
        runtime._reaper_task = None


# ---------------------------------------------------------------------------
# Lazy spawn — no subprocess before first prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_prompt_spawns_subprocess_lazily(
    stub_pi_on_path: Path,
    tmp_path: Path,
) -> None:
    """create_session() must NOT spawn a subprocess; the first prompt() must."""
    runtime = PiRuntime(base_session_dir=tmp_path / "sessions", binary="pi")
    await _cancel_reaper(runtime)

    try:
        sid = await runtime.create_session(model="minimax/MiniMax-M2.7")

        # After create_session, no client should exist yet.
        assert sid not in runtime._clients, (
            "create_session must NOT spawn a subprocess (lazy spawn invariant)"
        )

        # First prompt triggers the spawn.
        await runtime.prompt(sid, "hello")

        # Now the client must exist.
        assert sid in runtime._clients, "first prompt must spawn the subprocess"
        # The client must have a live process.
        client = runtime._clients[sid]
        assert client._proc is not None, "subprocess must be running after first prompt"
        assert client._proc.returncode is None, "subprocess must not have exited yet"
    finally:
        await runtime.close_all_clients()


# ---------------------------------------------------------------------------
# Idle reaper terminates subprocess; reactivate respawns it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idle_reaper_terminates_then_reactivate_respawns(
    stub_pi_on_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With IDLE_TIMEOUT_SECONDS=1, a subprocess idle for 2s is reaped.

    After reaping, sending another prompt must respawn a NEW subprocess.
    """
    monkeypatch.setenv("IW_CORE_PI_IDLE_TIMEOUT", "1")

    import importlib

    import orch.chat.pi.pi_runtime as _rt_mod

    importlib.reload(_rt_mod)
    PiRuntimeLocal = _rt_mod.PiRuntime  # noqa: N806 — reloaded class binding for env-var test

    try:
        runtime = PiRuntimeLocal(base_session_dir=tmp_path / "sessions", binary="pi")
        await _cancel_reaper(runtime)

        try:
            sid = await runtime.create_session()
            await runtime.prompt(sid, "initial prompt")
            assert sid in runtime._clients

            first_client = runtime._clients[sid]

            # Back-date the last_activity to simulate 2s idle.
            first_client._last_activity = time.monotonic() - 2
            runtime._client_tab_meta[sid]["last_activity"] = first_client._last_activity

            # Run one eviction pass (mirrors what the reaper loop does).
            now = time.monotonic()
            timeout = _rt_mod.IDLE_TIMEOUT_SECONDS
            to_evict = [
                s for s, c in list(runtime._clients.items()) if (now - c.last_activity) >= timeout
            ]
            for evict_sid in to_evict:
                evict_client = runtime._clients.pop(evict_sid, None)
                if evict_client is not None:
                    await evict_client.close()

            # The subprocess must be gone from the pool.
            assert sid not in runtime._clients, (
                "idle subprocess must be removed from _clients by the reaper"
            )

            # Metadata must be preserved for respawn.
            assert sid in runtime._client_tab_meta, (
                "session metadata must survive reaping (needed for respawn)"
            )

            # Sending another prompt must respawn a NEW subprocess.
            await runtime.prompt(sid, "second prompt after reap")
            assert sid in runtime._clients, "second prompt must respawn the subprocess"

            second_client = runtime._clients[sid]
            assert second_client is not first_client, (
                "respawned subprocess must be a NEW PiRpcClient object"
            )
        finally:
            await runtime.close_all_clients()
    finally:
        monkeypatch.delenv("IW_CORE_PI_IDLE_TIMEOUT", raising=False)
        importlib.reload(_rt_mod)


# ---------------------------------------------------------------------------
# LRU eviction when creating N+1 tabs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lru_eviction_when_creating_nth_tab(
    stub_pi_on_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With IW_CORE_MAX_PI_TABS=3, the 4th prompt evicts the LRU subprocess.

    The evicted tab's session metadata must survive (pi_session_path preserved).
    """
    monkeypatch.setenv("IW_CORE_MAX_PI_TABS", "3")

    import importlib

    import orch.chat.pi.pi_runtime as _rt_mod

    importlib.reload(_rt_mod)
    PiRuntimeLocal = _rt_mod.PiRuntime  # noqa: N806 — reloaded class binding for env-var test

    try:
        runtime = PiRuntimeLocal(base_session_dir=tmp_path / "sessions", binary="pi")
        await _cancel_reaper(runtime)

        try:
            # Create and prompt 3 sessions (filling the cap).
            sids: list[str] = []
            now = time.monotonic()
            for i in range(3):
                sid = await runtime.create_session()
                sids.append(sid)
                await runtime.prompt(sid, f"prompt {i}")
                # Make each session progressively more recently used.
                runtime._client_tab_meta[sid]["last_activity"] = now - (3 - i) * 100
                if sid in runtime._clients:
                    runtime._clients[sid]._last_activity = now - (3 - i) * 100

            # sids[0] is the LRU (oldest last_activity).
            lru_sid = sids[0]
            assert lru_sid in runtime._clients

            # Create and prompt a 4th session — triggers eviction.
            sid4 = await runtime.create_session()
            sids.append(sid4)
            await runtime.prompt(sid4, "prompt 4th")

            # LRU must be evicted from active clients.
            assert lru_sid not in runtime._clients, (
                "LRU session must be evicted when cap is exceeded"
            )

            # Active client count must not exceed cap.
            assert len(runtime._clients) <= 3, (
                f"active client count must not exceed MAX_PI_TABS=3, got {len(runtime._clients)}"
            )

            # LRU session metadata must be preserved.
            assert lru_sid in runtime._client_tab_meta, (
                "evicted session's metadata must survive eviction for lazy respawn"
            )
        finally:
            await runtime.close_all_clients()
    finally:
        monkeypatch.delenv("IW_CORE_MAX_PI_TABS", raising=False)
        importlib.reload(_rt_mod)


# ---------------------------------------------------------------------------
# Pi binary missing → RuntimeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pi_binary_missing_raises_runtime_error(
    no_pi_on_path: Path,
    tmp_path: Path,
) -> None:
    """When the pi binary is not on PATH, prompt() must raise RuntimeError.

    The error message must mention 'pi binary not found on PATH' as documented
    in §Boundary Behavior.
    """
    runtime = PiRuntime(base_session_dir=tmp_path / "sessions", binary="pi")
    await _cancel_reaper(runtime)

    try:
        sid = await runtime.create_session()

        with pytest.raises(RuntimeError, match="pi binary not found on PATH"):
            await runtime.prompt(sid, "this should fail")
    finally:
        await runtime.close_all_clients()


# ---------------------------------------------------------------------------
# health() returns False when pi is not on PATH
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_false_when_pi_missing(
    no_pi_on_path: Path,
    tmp_path: Path,
) -> None:
    """health() must return False when the pi binary is absent from PATH."""
    runtime = PiRuntime(base_session_dir=tmp_path / "sessions", binary="pi")
    await _cancel_reaper(runtime)

    try:
        result = await runtime.health()
        assert result is False, (
            f"health() should be False when pi binary is missing, got {result!r}"
        )
    finally:
        await runtime.close_all_clients()


@pytest.mark.asyncio
async def test_health_returns_true_when_pi_present(
    stub_pi_on_path: Path,
    tmp_path: Path,
) -> None:
    """health() must return True when the pi stub binary is on PATH."""
    runtime = PiRuntime(base_session_dir=tmp_path / "sessions", binary="pi")
    await _cancel_reaper(runtime)

    try:
        result = await runtime.health()
        assert result is True, (
            f"health() should be True when stub pi binary is on PATH, got {result!r}"
        )
    finally:
        await runtime.close_all_clients()
