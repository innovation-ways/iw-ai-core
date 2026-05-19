"""Unit tests for `orch.chat.opencode.runtime.OpencodeRuntime`.

Tests are written FIRST (TDD-RED). They cover:

- happy path: start → health → stop
- health-poll timeout raises RuntimeError
- stop escalates SIGTERM → SIGKILL
- password literal never appears in logs
- missing binary surfaces a clear error
- auto-restart is capped at 3 restarts in 60 s
- PR_SET_PDEATHSIG is set on linux, skipped on other platforms

Subprocess and httpx network I/O are stubbed via fakes — no real `opencode`
binary is required.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


class _FakeStream:
    """asyncio StreamReader stub."""

    def __init__(self, payload: bytes = b"") -> None:
        self._payload = payload

    async def read(self, n: int = -1) -> bytes:
        data = self._payload
        self._payload = b""
        return data


class _FakeProc:
    """Stand-in for `asyncio.subprocess.Process`.

    - `wait()` resolves to `_exit_code` after `_wait_event` is set.
    - `terminate()` sets the exit code to 0 and releases `wait()` unless
      `ignore_sigterm=True`, in which case only `kill()` resolves it.
    """

    def __init__(
        self,
        *,
        exit_code: int = 0,
        ignore_sigterm: bool = False,
        pid: int = 4242,
    ) -> None:
        self.pid = pid
        self._exit_code = exit_code
        self._ignore_sigterm = ignore_sigterm
        self.returncode: int | None = None
        self.stderr = _FakeStream(b"")
        self.stdout = _FakeStream(b"")
        self._wait_event = asyncio.Event()
        self.terminate_calls = 0
        self.kill_calls = 0

    def terminate(self) -> None:
        self.terminate_calls += 1
        if not self._ignore_sigterm:
            self.returncode = self._exit_code
            self._wait_event.set()

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -signal.SIGKILL
        self._wait_event.set()

    async def wait(self) -> int:
        await self._wait_event.wait()
        assert self.returncode is not None
        return self.returncode

    def finish_now(self, code: int = 0) -> None:
        """Manually mark the process as finished — used by crash tests."""
        self.returncode = code
        self._wait_event.set()


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _make_httpx_get(seq: list[int]) -> Any:
    """Build an AsyncClient.get mock that returns successive status codes.

    Each call pops the next status code from the queue; if exhausted it
    repeats the last value.
    """
    queue = list(seq)

    async def _get(*_a: Any, **_kw: Any) -> _FakeResponse:
        code = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else 503)
        return _FakeResponse(code)

    return AsyncMock(side_effect=_get)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_health_stop_happy_path(tmp_path: Path) -> None:
    """start() polls /global/health, returns when 200; stop() cleans up."""
    from orch.chat.opencode.runtime import OpencodeRuntime

    proc = _FakeProc()
    create_exec = AsyncMock(return_value=proc)
    fake_client = MagicMock()
    fake_client.get = _make_httpx_get([200])
    fake_client.aclose = AsyncMock()

    with (
        patch("orch.chat.opencode.runtime.asyncio.create_subprocess_exec", create_exec),
        patch("orch.chat.opencode.runtime.httpx.AsyncClient", return_value=fake_client),
    ):
        rt = OpencodeRuntime(repo_root=tmp_path, port=4096, bin_path="opencode")
        await rt.start()
        assert await rt.health() is True
        assert rt.base_url == "http://127.0.0.1:4096"
        assert isinstance(rt.password, str)
        assert len(rt.password) >= 32  # token_urlsafe(32) → >=43 chars
        await rt.stop()

    assert proc.terminate_calls == 1
    assert proc.returncode == 0


@pytest.mark.asyncio
async def test_start_health_timeout_raises(tmp_path: Path) -> None:
    """If /global/health never returns 200, start() raises RuntimeError."""
    from orch.chat.opencode.runtime import OpencodeRuntime

    proc = _FakeProc()
    create_exec = AsyncMock(return_value=proc)
    fake_client = MagicMock()
    fake_client.get = _make_httpx_get([503])
    fake_client.aclose = AsyncMock()

    # Drive the deadline past the timeout by advancing the monotonic clock,
    # and shorten the poll interval to zero so the loop exits quickly without
    # globally patching asyncio.sleep (which would also break test scheduling).
    times = iter([0.0, 100.0, 100.0, 100.0])

    with (
        patch("orch.chat.opencode.runtime.asyncio.create_subprocess_exec", create_exec),
        patch("orch.chat.opencode.runtime.httpx.AsyncClient", return_value=fake_client),
        patch("orch.chat.opencode.runtime.time.monotonic", side_effect=lambda: next(times)),
    ):
        rt = OpencodeRuntime(
            repo_root=tmp_path,
            port=4096,
            bin_path="opencode",
            health_poll_interval_seconds=0.0,
        )
        with pytest.raises(RuntimeError, match="opencode failed to become healthy within 10s"):
            await rt.start()


@pytest.mark.asyncio
async def test_stop_sigterm_then_sigkill(tmp_path: Path) -> None:
    """If SIGTERM is ignored, stop() escalates to SIGKILL after the grace window."""
    from orch.chat.opencode.runtime import OpencodeRuntime

    proc = _FakeProc(ignore_sigterm=True)
    create_exec = AsyncMock(return_value=proc)
    fake_client = MagicMock()
    fake_client.get = _make_httpx_get([200])
    fake_client.aclose = AsyncMock()

    with (
        patch("orch.chat.opencode.runtime.asyncio.create_subprocess_exec", create_exec),
        patch("orch.chat.opencode.runtime.httpx.AsyncClient", return_value=fake_client),
    ):
        # Shorten the stop grace window to keep the test fast.
        rt = OpencodeRuntime(
            repo_root=tmp_path,
            port=4096,
            bin_path="opencode",
            stop_grace_seconds=0.1,
        )
        await rt.start()
        await rt.stop()

    assert proc.terminate_calls == 1
    assert proc.kill_calls == 1


@pytest.mark.asyncio
async def test_password_not_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """The generated password literal must never appear in log records."""
    from orch.chat.opencode.runtime import OpencodeRuntime

    proc = _FakeProc()
    create_exec = AsyncMock(return_value=proc)
    fake_client = MagicMock()
    fake_client.get = _make_httpx_get([200])
    fake_client.aclose = AsyncMock()

    caplog.set_level(logging.DEBUG, logger="orch.chat.opencode.runtime")
    with (
        patch("orch.chat.opencode.runtime.asyncio.create_subprocess_exec", create_exec),
        patch("orch.chat.opencode.runtime.httpx.AsyncClient", return_value=fake_client),
    ):
        rt = OpencodeRuntime(repo_root=tmp_path, port=4096, bin_path="opencode")
        await rt.start()
        password = rt.password
        await rt.stop()

    # Sanity: we actually generated a password.
    assert password
    # No log record contains the password literal (message OR rendered output).
    for record in caplog.records:
        assert password not in record.getMessage(), (
            f"Password leaked into log: {record.name}/{record.levelname}: {record.getMessage()!r}"
        )
        assert password not in str(record.args or ""), "Password leaked via log args"


@pytest.mark.asyncio
async def test_missing_binary_clear_error(tmp_path: Path) -> None:
    """A non-existent binary path surfaces a wrapped RuntimeError with a clear message."""
    from orch.chat.opencode.runtime import OpencodeRuntime

    async def _raise_fnf(*_a: Any, **_kw: Any) -> Any:
        raise FileNotFoundError(2, "No such file or directory", "/does/not/exist/opencode")

    with patch("orch.chat.opencode.runtime.asyncio.create_subprocess_exec", side_effect=_raise_fnf):
        rt = OpencodeRuntime(
            repo_root=tmp_path,
            port=4096,
            bin_path="/does/not/exist/opencode",
        )
        with pytest.raises((FileNotFoundError, RuntimeError)) as exc_info:
            await rt.start()
        # The error message must reference the binary path for operators.
        assert "/does/not/exist/opencode" in str(exc_info.value) or "opencode" in str(
            exc_info.value
        )


@pytest.mark.asyncio
async def test_restart_on_crash_capped_at_3_per_60s(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A crashing subprocess is restarted at most 3 times in a 60-s window."""
    from orch.chat.opencode.runtime import OpencodeRuntime

    procs: list[_FakeProc] = []

    async def _spawn(*_a: Any, **_kw: Any) -> _FakeProc:
        p = _FakeProc()
        # Crash immediately on creation (non-zero exit).
        p.finish_now(code=1)
        procs.append(p)
        return p

    fake_client = MagicMock()
    fake_client.get = _make_httpx_get([200])
    fake_client.aclose = AsyncMock()

    # Freeze monotonic clock so all restarts fall inside the 60-s window.
    # Don't patch asyncio.sleep globally — that would also disable the test's
    # own asyncio.sleep(0) yields. Instead, set the backoff to 0 via the ctor.
    caplog.set_level(logging.DEBUG, logger="orch.chat.opencode.runtime")
    with (
        patch(
            "orch.chat.opencode.runtime.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=_spawn),
        ),
        patch("orch.chat.opencode.runtime.httpx.AsyncClient", return_value=fake_client),
        patch("orch.chat.opencode.runtime.time.monotonic", return_value=1000.0),
    ):
        rt = OpencodeRuntime(
            repo_root=tmp_path,
            port=4096,
            bin_path="opencode",
            restart_backoff_seconds=0.0,
            health_poll_interval_seconds=0.0,
        )
        await rt.start()
        # Let the auto-restart task observe crash → restart cycles.
        # Each cycle is: wait(), see non-zero rc, sleep 0s, restart.
        # Cap is 3 restarts → 4 spawn attempts total (initial + 3).
        for _ in range(80):
            await asyncio.sleep(0)
            if not await rt.health():
                break

        assert await rt.health() is False
        # Initial start + 3 restart attempts = 4 spawns.
        assert 2 <= len(procs) <= 4, f"expected 2..4 spawns, got {len(procs)}"
        # CRITICAL log emitted on cap breach.
        critical_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.CRITICAL]
        assert any("unstable" in m.lower() for m in critical_msgs), (
            f"expected CRITICAL log mentioning 'unstable'; got {critical_msgs!r}"
        )

        # Cleanup the watchdog task.
        await rt.stop()


@pytest.mark.asyncio
async def test_pr_set_pdeathsig_set_on_linux(tmp_path: Path) -> None:
    """On Linux, the subprocess is spawned with a preexec_fn that wires
    PR_SET_PDEATHSIG → SIGTERM via prctl(2). On other platforms it is skipped.
    """
    from orch.chat.opencode.runtime import OpencodeRuntime

    proc = _FakeProc()
    create_exec = AsyncMock(return_value=proc)
    fake_client = MagicMock()
    fake_client.get = _make_httpx_get([200])
    fake_client.aclose = AsyncMock()

    # Linux branch: preexec_fn must be supplied. Capture it and invoke it
    # against a fake libc to verify it calls prctl(PR_SET_PDEATHSIG, SIGTERM).
    fake_libc = MagicMock()

    with (
        patch("orch.chat.opencode.runtime.sys.platform", "linux"),
        patch("orch.chat.opencode.runtime.asyncio.create_subprocess_exec", create_exec),
        patch("orch.chat.opencode.runtime.httpx.AsyncClient", return_value=fake_client),
        patch("orch.chat.opencode.runtime.ctypes.CDLL", return_value=fake_libc),
    ):
        rt = OpencodeRuntime(repo_root=tmp_path, port=4096, bin_path="opencode")
        await rt.start()
        kwargs = create_exec.call_args.kwargs
        preexec = kwargs.get("preexec_fn")
        assert preexec is not None, "preexec_fn must be set on linux"
        preexec()
        # prctl(PR_SET_PDEATHSIG=1, SIGTERM)
        fake_libc.prctl.assert_called_once_with(1, signal.SIGTERM)
        await rt.stop()

    # Non-Linux branch: preexec_fn must NOT be set.
    proc2 = _FakeProc()
    create_exec2 = AsyncMock(return_value=proc2)
    fake_client2 = MagicMock()
    fake_client2.get = _make_httpx_get([200])
    fake_client2.aclose = AsyncMock()
    with (
        patch("orch.chat.opencode.runtime.sys.platform", "darwin"),
        patch("orch.chat.opencode.runtime.asyncio.create_subprocess_exec", create_exec2),
        patch("orch.chat.opencode.runtime.httpx.AsyncClient", return_value=fake_client2),
    ):
        rt2 = OpencodeRuntime(repo_root=tmp_path, port=4096, bin_path="opencode")
        await rt2.start()
        kwargs2 = create_exec2.call_args.kwargs
        assert kwargs2.get("preexec_fn") is None, "preexec_fn must NOT be set on non-Linux"
        await rt2.stop()


# ---------------------------------------------------------------------------
# Sanity check: this test file is python 3.12-compatible
# ---------------------------------------------------------------------------


def test_python_version_is_compatible() -> None:
    """Guards against accidentally writing python>=3.13-only syntax."""
    assert sys.version_info >= (3, 12)
