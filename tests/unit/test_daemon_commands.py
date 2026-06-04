"""Unit tests for daemon CLI commands.

Tests PID file handling and signal dispatch without a real database.
"""

from __future__ import annotations

import signal
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from orch.cli.daemon_commands import get_pid_file_path, is_process_alive, read_pid
from orch.cli.main import cli

if TYPE_CHECKING:
    from collections.abc import Generator

    import pytest


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


def test_read_pid_returns_none_for_missing_file(tmp_path: Path) -> None:
    """Verifies that read pid returns none for missing file."""
    pid_file = tmp_path / "daemon.pid"
    assert read_pid(pid_file) is None


def test_read_pid_returns_none_for_invalid_content(tmp_path: Path) -> None:
    """Verifies that read pid returns none for invalid content."""
    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text("not-a-number")
    assert read_pid(pid_file) is None


def test_read_pid_returns_integer(tmp_path: Path) -> None:
    """Verifies that read pid returns integer."""
    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text("12345\n")
    assert read_pid(pid_file) == 12345


def test_is_process_alive_false_for_nonexistent_pid() -> None:
    """Verifies that is process alive false for nonexistent pid."""
    # PID 0 is never a user process; kill(0, 0) signals the calling process group.
    # Use a very high PID unlikely to exist.
    with patch("os.kill", side_effect=ProcessLookupError):
        assert is_process_alive(999999) is False


def test_is_process_alive_true_when_kill_succeeds() -> None:
    """Verifies that is process alive true when kill succeeds."""
    with patch("os.kill", return_value=None):
        assert is_process_alive(12345) is True


def test_get_pid_file_path_uses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that get pid file path uses env var."""
    monkeypatch.setenv("IW_CORE_PID_FILE", "/var/run/iw-orch.pid")
    assert get_pid_file_path() == Path("/var/run/iw-orch.pid")


def test_get_pid_file_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that get pid file path default."""
    monkeypatch.delenv("IW_CORE_PID_FILE", raising=False)
    assert get_pid_file_path() == Path("/tmp/iw-orch-daemon.pid")  # noqa: S108


# ---------------------------------------------------------------------------
# daemon start — detects existing process
# ---------------------------------------------------------------------------


def _no_db_get_session():  # type: ignore[no-untyped-def]
    """Dummy session factory that should never be called for start/stop."""

    @contextmanager
    def _inner() -> Generator[None, None, None]:
        raise RuntimeError("DB should not be accessed in daemon start/stop tests")
        yield  # pragma: no cover

    return _inner


def test_daemon_start_detects_existing_process(tmp_path: Path) -> None:
    """If a PID file exists and the process is alive, start exits with error."""
    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text("99999")

    runner = CliRunner()
    with (
        patch("orch.cli.daemon_commands.get_pid_file_path", return_value=pid_file),
        patch("orch.cli.daemon_commands.is_process_alive", return_value=True),
    ):
        result = runner.invoke(
            cli,
            ["daemon", "start"],
            obj={"get_session": _no_db_get_session(), "json": False},
        )

    assert result.exit_code == 1
    assert "already running" in result.output


def test_daemon_start_proceeds_when_no_process(tmp_path: Path) -> None:
    """If no existing process is found, start spawns daemon subprocess."""
    pid_file = tmp_path / "daemon.pid"  # does not exist

    fake_proc = MagicMock()
    fake_proc.pid = 99999
    fake_proc.poll.return_value = None  # still alive after 1s check

    runner = CliRunner()
    with (
        patch("orch.cli.daemon_commands.get_pid_file_path", return_value=pid_file),
        patch("subprocess.Popen", return_value=fake_proc) as mock_popen,
        patch("orch.cli.daemon_commands.time.sleep"),  # don't actually sleep in tests
    ):
        result = runner.invoke(
            cli,
            ["daemon", "start"],
            obj={"get_session": _no_db_get_session(), "json": False},
        )

    assert result.exit_code == 0
    assert "started" in result.output or "99999" in result.output
    mock_popen.assert_called_once()


# ---------------------------------------------------------------------------
# daemon stop — reads PID and sends SIGTERM
# ---------------------------------------------------------------------------


def test_daemon_stop_sends_sigterm(tmp_path: Path) -> None:
    """daemon stop reads PID from file, sends SIGTERM, waits, then removes PID file."""
    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text("42000")

    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        """Return fake kill."""
        kill_calls.append((pid, sig))

    runner = CliRunner()
    # Simulate: process alive on first check, dead after SIGTERM
    alive_sequence = [True, False]

    with (
        patch("orch.cli.daemon_commands.get_pid_file_path", return_value=pid_file),
        patch("orch.cli.daemon_commands.is_process_alive", side_effect=alive_sequence),
        patch("os.kill", side_effect=fake_kill),
        patch("time.sleep"),
    ):
        result = runner.invoke(
            cli,
            ["daemon", "stop"],
            obj={"get_session": _no_db_get_session(), "json": False},
        )

    assert result.exit_code == 0, result.output
    assert "stopped" in result.output
    assert (42000, signal.SIGTERM) in kill_calls
    assert not pid_file.exists()


def test_daemon_stop_fails_when_no_pid_file(tmp_path: Path) -> None:
    """daemon stop exits with error when PID file is missing."""
    pid_file = tmp_path / "daemon.pid"  # does not exist

    runner = CliRunner()
    with patch("orch.cli.daemon_commands.get_pid_file_path", return_value=pid_file):
        result = runner.invoke(
            cli,
            ["daemon", "stop"],
            obj={"get_session": _no_db_get_session(), "json": False},
        )

    assert result.exit_code == 1
    assert "PID file not found" in result.output


def test_daemon_stop_handles_stale_pid_file(tmp_path: Path) -> None:
    """If the PID in the file is not alive, stop removes the stale file and exits."""
    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text("55555")

    runner = CliRunner()
    with (
        patch("orch.cli.daemon_commands.get_pid_file_path", return_value=pid_file),
        patch("orch.cli.daemon_commands.is_process_alive", return_value=False),
    ):
        result = runner.invoke(
            cli,
            ["daemon", "stop"],
            obj={"get_session": _no_db_get_session(), "json": False},
        )

    assert result.exit_code == 1
    assert "stale" in result.output
    assert not pid_file.exists()
