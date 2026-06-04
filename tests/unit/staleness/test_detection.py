"""Unit tests for orch.staleness.detection.

Tests process detection, cwd cross-check, and start-time parsing.
Uses tmp_path to mock /proc filesystem entries and unittest.mock to patch subprocess.run.
"""

from __future__ import annotations

import contextlib
import subprocess
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orch.staleness.config import ServiceDetect
from orch.staleness.detection import (
    find_running_container,
    find_running_pid,
    is_cwd_under,
    read_container_start_time,
    read_process_start_time,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc_entry(
    proc_dir: Path,
    pid: int,
    cwd_target: Path,
    cmdline: str = "python app.py",
    stat_starttime_jiffies: int = 10000,
) -> None:
    """Create a fake /proc/<pid>/ directory with cwd symlink, cmdline, and stat."""
    pid_dir = proc_dir / str(pid)
    pid_dir.mkdir(parents=True, exist_ok=True)

    # Write cmdline (NUL-separated)
    (pid_dir / "cmdline").write_bytes(cmdline.replace(" ", "\x00").encode() + b"\x00")

    # Write stat: field 22 is starttime (0-indexed at position 21)
    # Real stat has many fields; we only need the first 22.
    # Format: pid (comm) state ppid pgroup sess tty_nr tpgid flags
    #         minflt cminflt majflt cmajflt utime stime cutime cstime
    #         priority nice num_threads itrealvalue starttime
    stat_fields = ["1"] * 22
    stat_fields[0] = str(pid)
    stat_fields[1] = "(python)"
    stat_fields[21] = str(stat_starttime_jiffies)
    (pid_dir / "stat").write_text(" ".join(stat_fields))

    # Create cwd as a real directory (we'll readlink it)
    cwd_target.mkdir(parents=True, exist_ok=True)
    cwd_link = pid_dir / "cwd"
    with contextlib.suppress(FileExistsError):
        cwd_link.symlink_to(cwd_target)


# ---------------------------------------------------------------------------
# is_cwd_under
# ---------------------------------------------------------------------------


class TestIsCwdUnder:
    """Tests for is_cwd_under — verifies /proc cwd symlink resolution against repo_root."""

    def test_cwd_inside_repo_root(self, tmp_path: Path) -> None:
        """Returns True when /proc/<pid>/cwd resolves inside repo_root."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        cwd = repo_root  # process cwd is the repo root itself

        proc_dir = tmp_path / "proc"
        _make_proc_entry(proc_dir, 1234, cwd)

        with patch("orch.staleness.detection.PROC_ROOT", proc_dir):
            result = is_cwd_under(1234, repo_root)

        assert result is True

    def test_cwd_outside_repo_root(self, tmp_path: Path) -> None:
        """Returns False when /proc/<pid>/cwd resolves outside repo_root."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        other_dir = tmp_path / "other"
        other_dir.mkdir()

        proc_dir = tmp_path / "proc"
        _make_proc_entry(proc_dir, 5678, other_dir)

        with patch("orch.staleness.detection.PROC_ROOT", proc_dir):
            result = is_cwd_under(5678, repo_root)

        assert result is False

    def test_cwd_in_worktree_subdir_of_repo(self, tmp_path: Path) -> None:
        """A process in a subdirectory of repo_root is also 'inside' it."""
        repo_root = tmp_path / "myproject"
        worktree = repo_root / ".worktrees" / "feature-x"
        worktree.mkdir(parents=True)

        proc_dir = tmp_path / "proc"
        _make_proc_entry(proc_dir, 9999, worktree)

        with patch("orch.staleness.detection.PROC_ROOT", proc_dir):
            result = is_cwd_under(9999, repo_root)

        assert result is True

    def test_missing_proc_entry_returns_false(self, tmp_path: Path) -> None:
        """Returns False when /proc/<pid>/cwd does not exist."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        proc_dir = tmp_path / "proc"
        proc_dir.mkdir()

        with patch("orch.staleness.detection.PROC_ROOT", proc_dir):
            result = is_cwd_under(9999, repo_root)

        assert result is False


# ---------------------------------------------------------------------------
# read_process_start_time
# ---------------------------------------------------------------------------


class TestReadProcessStartTime:
    """Tests for read_process_start_time — verifies jiffies-to-wall-clock conversion from
    /proc/stat.
    """

    def test_reads_start_time_from_proc(self, tmp_path: Path) -> None:
        """read_process_start_time returns a datetime computed from /proc/<pid>/stat."""
        proc_dir = tmp_path / "proc"
        repo_root = tmp_path / "repo"
        # Use a known starttime in jiffies; CLK_TCK=100 Hz is standard
        # boot_time = 1700000000 (some epoch), starttime_jiffies = 100*10 = 1000 (10s after boot)
        # Expected wall time = boot_time + 10s
        boot_seconds = 1700000000
        uptime_seconds = 86400.0  # 1 day uptime
        starttime_jiffies = 100 * 10  # 10s after boot, at CLK_TCK=100

        _make_proc_entry(proc_dir, 42, repo_root, stat_starttime_jiffies=starttime_jiffies)

        # /proc/uptime: "86400.00 120.00\n"
        uptime_file = proc_dir / "uptime"
        uptime_file.write_text(f"{uptime_seconds} 120.00\n")

        with (
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("os.sysconf", return_value=100),
            patch("orch.staleness.detection._boot_time_epoch", return_value=float(boot_seconds)),
        ):
            result = read_process_start_time(42)

        assert result is not None
        # boot_seconds + starttime_jiffies / 100 = boot_seconds + 10
        expected_epoch = boot_seconds + 10
        assert result.timestamp() == pytest.approx(expected_epoch, abs=1)
        assert result.tzinfo == UTC

    def test_missing_stat_file_raises(self, tmp_path: Path) -> None:
        """Raises OSError when /proc/<pid>/stat is absent."""
        proc_dir = tmp_path / "proc"
        proc_dir.mkdir()

        with (
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            pytest.raises(OSError, match="9999"),
        ):
            read_process_start_time(9999)


# ---------------------------------------------------------------------------
# find_running_pid — pidfile detect
# ---------------------------------------------------------------------------


class TestFindRunningPidPidfile:
    """Tests for find_running_pid with pidfile detect — covers running, stale, missing, and wrong-
    cwd cases.
    """

    def test_pidfile_valid_running_pid_inside_repo(self, tmp_path: Path) -> None:
        """Returns pid when pidfile holds a live pid whose cwd is inside repo_root."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        pid_file = repo_root / ".daemon.pid"
        pid_file.write_text("1234\n")

        proc_dir = tmp_path / "proc"
        _make_proc_entry(proc_dir, 1234, repo_root)

        detect = ServiceDetect.from_dict({"type": "pidfile", "path": ".daemon.pid"})

        with (
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("orch.staleness.detection._pid_alive", return_value=True),
        ):
            result = find_running_pid(detect, repo_root)

        assert result == 1234

    def test_pidfile_stale_pid_returns_none(self, tmp_path: Path) -> None:
        """Returns None when pidfile holds a dead pid."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        pid_file = repo_root / ".daemon.pid"
        pid_file.write_text("9999\n")

        proc_dir = tmp_path / "proc"
        proc_dir.mkdir()

        detect = ServiceDetect.from_dict({"type": "pidfile", "path": ".daemon.pid"})

        with (
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("orch.staleness.detection._pid_alive", return_value=False),
        ):
            result = find_running_pid(detect, repo_root)

        assert result is None

    def test_pidfile_missing_returns_none(self, tmp_path: Path) -> None:
        """Returns None when pidfile does not exist."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()

        detect = ServiceDetect.from_dict({"type": "pidfile", "path": ".daemon.pid"})

        result = find_running_pid(detect, repo_root)
        assert result is None

    def test_pidfile_cwd_outside_repo_returns_none(self, tmp_path: Path) -> None:
        """Returns None when pid is alive but cwd is outside repo_root."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        other_dir = tmp_path / "other"
        other_dir.mkdir()

        pid_file = repo_root / ".daemon.pid"
        pid_file.write_text("1234\n")

        proc_dir = tmp_path / "proc"
        _make_proc_entry(proc_dir, 1234, other_dir)

        detect = ServiceDetect.from_dict({"type": "pidfile", "path": ".daemon.pid"})

        with (
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("orch.staleness.detection._pid_alive", return_value=True),
        ):
            result = find_running_pid(detect, repo_root)

        assert result is None


# ---------------------------------------------------------------------------
# find_running_pid — port detect
# ---------------------------------------------------------------------------


class TestFindRunningPidPort:
    """Tests for find_running_pid with port detect — uses mocked ss output."""

    def test_port_detect_finds_pid_in_repo(self, tmp_path: Path) -> None:
        """Returns pid when ss output shows a process listening on the port."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        proc_dir = tmp_path / "proc"
        _make_proc_entry(proc_dir, 5678, repo_root)

        # ss -ltnp output line with pid=5678 and port 9900
        ss_output = (
            "Netid State Recv-Q Send-Q Local Address:Port  Peer Address:Port Process\n"
            "tcp   LISTEN 0      128    0.0.0.0:9900       0.0.0.0:*"
            '          users:(("uvicorn",pid=5678,fd=7))\n'
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ss_output

        detect = ServiceDetect.from_dict({"type": "port", "port": 9900})

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("orch.staleness.detection._pid_alive", return_value=True),
        ):
            result = find_running_pid(detect, repo_root)

        assert result == 5678

    def test_port_detect_no_listener_returns_none(self, tmp_path: Path) -> None:
        """Returns None when nothing is listening on the port."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Netid State Recv-Q Send-Q Local Address:Port  Peer Address:Port\n"

        detect = ServiceDetect.from_dict({"type": "port", "port": 9900})

        with patch("subprocess.run", return_value=mock_result):
            result = find_running_pid(detect, repo_root)

        assert result is None

    def test_port_detect_cwd_outside_repo_returns_none(self, tmp_path: Path) -> None:
        """Returns None when the listening pid's cwd is outside repo_root."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        proc_dir = tmp_path / "proc"
        _make_proc_entry(proc_dir, 5678, other_dir)

        ss_output = (
            "tcp   LISTEN 0      128    0.0.0.0:9900       0.0.0.0:*"
            '          users:(("uvicorn",pid=5678,fd=7))\n'
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ss_output

        detect = ServiceDetect.from_dict({"type": "port", "port": 9900})

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("orch.staleness.detection._pid_alive", return_value=True),
        ):
            result = find_running_pid(detect, repo_root)

        assert result is None


# ---------------------------------------------------------------------------
# find_running_pid — pgrep detect
# ---------------------------------------------------------------------------


class TestFindRunningPidPgrep:
    """Tests for find_running_pid with pgrep detect — covers match, no-match, wrong-cwd, and multi-
    match.
    """

    def test_pgrep_finds_matching_pid_in_repo(self, tmp_path: Path) -> None:
        """Returns pid when cmdline matches pattern and cwd is in repo_root."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        proc_dir = tmp_path / "proc"
        # PID 100 has a matching cmdline and is inside repo
        _make_proc_entry(proc_dir, 100, repo_root, cmdline="python -m orch.daemon")

        detect = ServiceDetect.from_dict({"type": "pgrep", "pattern": "orch.daemon"})

        with (
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("orch.staleness.detection._pid_alive", return_value=True),
            patch("orch.staleness.detection._iter_proc_pids", return_value=[100]),
        ):
            result = find_running_pid(detect, repo_root)

        assert result == 100

    def test_pgrep_no_match_returns_none(self, tmp_path: Path) -> None:
        """Returns None when no process matches the pattern."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        proc_dir = tmp_path / "proc"
        _make_proc_entry(proc_dir, 100, repo_root, cmdline="python something_else")

        detect = ServiceDetect.from_dict({"type": "pgrep", "pattern": "orch.daemon"})

        with (
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("orch.staleness.detection._iter_proc_pids", return_value=[100]),
        ):
            result = find_running_pid(detect, repo_root)

        assert result is None

    def test_pgrep_cwd_outside_repo_returns_none(self, tmp_path: Path) -> None:
        """Returns None when process matches pattern but cwd is outside repo_root."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        proc_dir = tmp_path / "proc"
        # PID 100 matches pattern but lives in other_dir, not repo_root
        _make_proc_entry(proc_dir, 100, other_dir, cmdline="python -m orch.daemon")

        detect = ServiceDetect.from_dict({"type": "pgrep", "pattern": "orch.daemon"})

        with (
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("orch.staleness.detection._pid_alive", return_value=True),
            patch("orch.staleness.detection._iter_proc_pids", return_value=[100]),
        ):
            result = find_running_pid(detect, repo_root)

        assert result is None

    def test_pgrep_multiple_matches_returns_oldest_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When multiple processes match, returns the oldest PID and logs a warning."""
        import logging

        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        proc_dir = tmp_path / "proc"
        # Two matching PIDs, both in repo_root
        _make_proc_entry(
            proc_dir, 100, repo_root, cmdline="python -m orch.daemon", stat_starttime_jiffies=2000
        )
        _make_proc_entry(
            proc_dir, 200, repo_root, cmdline="python -m orch.daemon", stat_starttime_jiffies=1000
        )

        detect = ServiceDetect.from_dict({"type": "pgrep", "pattern": "orch.daemon"})

        uptime_file = proc_dir / "uptime"
        uptime_file.write_text("86400.0 100.0\n")

        with (
            patch("orch.staleness.detection.PROC_ROOT", proc_dir),
            patch("orch.staleness.detection._pid_alive", return_value=True),
            patch("orch.staleness.detection._iter_proc_pids", return_value=[100, 200]),
            patch("os.sysconf", return_value=100),
            patch(
                "orch.staleness.detection._boot_time_epoch",
                return_value=1700000000.0,
            ),
            caplog.at_level(logging.WARNING, logger="orch.staleness.detection"),
        ):
            result = find_running_pid(detect, repo_root)

        # PID 200 has jiffies=1000 (10s after boot), PID 100 has jiffies=2000 (20s after boot)
        # Oldest = PID 200 (started earlier)
        assert result == 200
        assert any("matched" in r.message and "oldest" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# find_running_container — docker detect
# ---------------------------------------------------------------------------


class TestFindRunningContainer:
    """Tests for find_running_container — covers running, stopped, inspect failure, and timeout."""

    def test_running_container_returns_container_id(self) -> None:
        """Returns container id when docker inspect shows it is running."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "true 2024-01-15T10:00:00Z\n"

        detect = ServiceDetect.from_dict({"type": "docker", "container": "my-container"})

        with patch("subprocess.run", return_value=mock_result):
            result = find_running_container(detect)

        assert result == "my-container"

    def test_stopped_container_returns_none(self) -> None:
        """Returns None when docker inspect shows the container is NOT running."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "false 2024-01-15T10:00:00Z\n"

        detect = ServiceDetect.from_dict({"type": "docker", "container": "my-container"})

        with patch("subprocess.run", return_value=mock_result):
            result = find_running_container(detect)

        assert result is None

    def test_docker_inspect_failure_returns_none(self) -> None:
        """Returns None when docker inspect fails (e.g. container not found)."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: No such container: my-container"

        detect = ServiceDetect.from_dict({"type": "docker", "container": "my-container"})

        with patch("subprocess.run", return_value=mock_result):
            result = find_running_container(detect)

        assert result is None

    def test_docker_timeout_returns_none(self) -> None:
        """Returns None on subprocess timeout."""
        detect = ServiceDetect.from_dict({"type": "docker", "container": "my-container"})

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 2)):
            result = find_running_container(detect)

        assert result is None


# ---------------------------------------------------------------------------
# read_container_start_time
# ---------------------------------------------------------------------------


class TestReadContainerStartTime:
    """Tests for read_container_start_time — verifies ISO8601 parsing and error handling."""

    def test_parses_container_start_time(self) -> None:
        """Parses docker inspect StartedAt ISO8601 timestamp."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "2024-01-15T10:30:00.123456789Z\n"

        with patch("subprocess.run", return_value=mock_result):
            result = read_container_start_time("my-container")

        assert result is not None

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.tzinfo == UTC

    def test_docker_inspect_failure_raises(self) -> None:
        """Raises RuntimeError when docker inspect fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error"

        with (
            patch("subprocess.run", return_value=mock_result),
            pytest.raises(RuntimeError, match="docker inspect failed"),
        ):
            read_container_start_time("bad-container")
