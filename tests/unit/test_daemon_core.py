"""Unit tests for the Daemon core class.

Tests startup behavior, signal handling, and error isolation without a
real database — the session factory is injected as a mock.
"""

from __future__ import annotations

import os
import signal
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from orch.config import DaemonConfig
from orch.daemon.main import Daemon, DaemonAlreadyRunning, _is_pid_alive

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_config(tmp_path: Path) -> DaemonConfig:
    """Create a minimal DaemonConfig pointing to tmp_path."""
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")  # empty — no projects

    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=1,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )


def make_mock_session_factory() -> Any:
    """Create a mock session factory that provides a no-op DB session."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.query.return_value.filter.return_value.all.return_value = []

    @contextmanager  # type: ignore[misc]
    def _factory() -> Any:
        yield mock_session

    return _factory


def make_daemon(tmp_path: Path) -> Daemon:
    """Build a Daemon with a mock session factory."""
    config = make_config(tmp_path)
    return Daemon(config, session_factory=make_mock_session_factory())


# ---------------------------------------------------------------------------
# _is_pid_alive helper
# ---------------------------------------------------------------------------


def test_is_pid_alive_returns_true_when_process_exists() -> None:
    with patch("os.kill", return_value=None):
        assert _is_pid_alive(12345) is True


def test_is_pid_alive_returns_false_when_process_not_found() -> None:
    with patch("os.kill", side_effect=ProcessLookupError):
        assert _is_pid_alive(99999) is False


def test_is_pid_alive_returns_false_for_none() -> None:
    assert _is_pid_alive(None) is False


# ---------------------------------------------------------------------------
# PID file handling in _startup
# ---------------------------------------------------------------------------


def test_startup_writes_pid_file(tmp_path: Path) -> None:
    """_startup() writes the current process PID to the PID file."""
    daemon = make_daemon(tmp_path)

    with (
        patch.object(daemon, "_startup_health_check"),
        patch.object(daemon, "_load_projects"),
    ):
        daemon._startup()

    pid_file = Path(daemon.config.pid_file)
    assert pid_file.exists()
    assert int(pid_file.read_text()) == os.getpid()


def test_startup_removes_stale_pid_file_and_continues(tmp_path: Path) -> None:
    """If a PID file exists with a dead PID, startup removes it and continues."""
    daemon = make_daemon(tmp_path)
    pid_file = Path(daemon.config.pid_file)
    pid_file.write_text("99999")  # dead PID

    with (
        patch("orch.daemon.main._is_pid_alive", side_effect=lambda pid: pid == os.getpid()),
        patch.object(daemon, "_startup_health_check"),
        patch.object(daemon, "_load_projects"),
    ):
        daemon._startup()

    # PID file was replaced with the current PID
    assert int(pid_file.read_text()) == os.getpid()


def test_startup_raises_if_daemon_already_running(tmp_path: Path) -> None:
    """If the PID file contains a live PID, _startup() raises DaemonAlreadyRunning."""
    daemon = make_daemon(tmp_path)
    pid_file = Path(daemon.config.pid_file)
    pid_file.write_text("88888")

    with (
        patch("orch.daemon.main._is_pid_alive", return_value=True),
        pytest.raises(DaemonAlreadyRunning, match="already running"),
    ):
        daemon._startup()


def test_startup_proceeds_when_no_pid_file(tmp_path: Path) -> None:
    """If no PID file exists, startup proceeds without error."""
    daemon = make_daemon(tmp_path)

    with (
        patch.object(daemon, "_startup_health_check"),
        patch.object(daemon, "_load_projects"),
    ):
        daemon._startup()  # should not raise

    assert Path(daemon.config.pid_file).exists()


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------


def test_signal_handler_sets_running_false(tmp_path: Path) -> None:
    """SIGTERM/SIGINT handler sets _running = False."""
    daemon = make_daemon(tmp_path)
    assert daemon._running is True

    daemon._handle_shutdown(signal.SIGTERM, None)

    assert daemon._running is False


def test_signal_handler_wakes_sleep(tmp_path: Path) -> None:
    """SIGTERM wakes _sleep() immediately instead of waiting the full interval."""
    daemon = make_daemon(tmp_path)
    daemon._wake_event.clear()

    daemon._handle_shutdown(signal.SIGTERM, None)

    woken = daemon._wake_event.wait(timeout=0.1)
    assert woken, "Wake event was not set by shutdown signal"


def test_sighup_handler_sets_stale_mtime(tmp_path: Path) -> None:
    """SIGHUP handler forces a project reload by resetting the registry mtime."""
    daemon = make_daemon(tmp_path)
    daemon.registry._mtime = 999.0

    daemon._handle_reload(signal.SIGHUP, None)

    assert daemon.registry._mtime == 0.0


# ---------------------------------------------------------------------------
# Per-project error isolation
# ---------------------------------------------------------------------------


def test_poll_cycle_continues_after_project_error(tmp_path: Path) -> None:
    """One project's exception does not prevent other projects from being processed."""
    daemon = make_daemon(tmp_path)

    from orch.daemon.batch_manager import BatchManager
    from orch.daemon.project_registry import ProjectConfig

    def make_project(pid: str) -> ProjectConfig:
        return ProjectConfig(
            id=pid,
            display_name=pid,
            repo_root=str(tmp_path),
            enabled=True,
            cli_tool="opencode",
            worktree_base=".worktrees",
            config={},
        )

    daemon.projects = {
        "error-project": make_project("error-project"),
        "good-project": make_project("good-project"),
    }

    error_manager = MagicMock(spec=BatchManager)
    error_manager.monitor_running_steps.side_effect = RuntimeError("boom")

    good_manager = MagicMock(spec=BatchManager)

    daemon.managers = {
        "error-project": error_manager,
        "good-project": good_manager,
    }

    daemon._poll_cycle()  # must not raise

    good_manager.monitor_running_steps.assert_called_once()
    good_manager.process_batches.assert_called_once()


# ---------------------------------------------------------------------------
# Main loop resilience
# ---------------------------------------------------------------------------


def test_run_loop_continues_after_poll_cycle_exception(tmp_path: Path) -> None:
    """An exception in _poll_cycle does not crash the daemon's main loop."""
    daemon = make_daemon(tmp_path)

    call_count = 0

    def poll_once() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("poll error")
        daemon._running = False

    with (
        patch.object(daemon, "_poll_cycle", side_effect=poll_once),
        patch.object(daemon, "_startup"),
        patch.object(daemon, "_shutdown"),
        patch.object(daemon, "_sleep"),
    ):
        daemon.run()

    assert call_count == 2, "Loop should have continued after the first poll failure"


def test_run_calls_startup_and_shutdown(tmp_path: Path) -> None:
    """run() always calls _startup() and _shutdown()."""
    daemon = make_daemon(tmp_path)

    startup_called = False
    shutdown_called = False

    def fake_startup() -> None:
        nonlocal startup_called
        startup_called = True

    def fake_shutdown() -> None:
        nonlocal shutdown_called
        shutdown_called = True

    def fake_poll() -> None:
        daemon._running = False

    with (
        patch.object(daemon, "_startup", side_effect=fake_startup),
        patch.object(daemon, "_shutdown", side_effect=fake_shutdown),
        patch.object(daemon, "_poll_cycle", side_effect=fake_poll),
        patch.object(daemon, "_sleep"),
    ):
        daemon.run()

    assert startup_called
    assert shutdown_called


# ---------------------------------------------------------------------------
# Shutdown — PID file cleanup
# ---------------------------------------------------------------------------


def test_shutdown_removes_pid_file(tmp_path: Path) -> None:
    """_shutdown() removes the PID file."""
    daemon = make_daemon(tmp_path)
    pid_file = Path(daemon.config.pid_file)
    pid_file.write_text(str(os.getpid()))

    daemon._shutdown()

    assert not pid_file.exists()


def test_shutdown_does_not_raise_if_pid_file_missing(tmp_path: Path) -> None:
    """_shutdown() is safe even if the PID file was already removed."""
    daemon = make_daemon(tmp_path)
    # Don't create the PID file

    daemon._shutdown()  # should not raise
