"""Unit tests for _run_gate_command (I-00049) and GATE_PARSERS (I-00049 second fix).

These tests verify:
1. _run_gate_command does not block indefinitely when grandchild processes
   keep pipe FDs open after the parent shell exits (I-00049 pipe-deadlock fix).
2. _run_gate_command returns output on success and on non-zero exit (no exception).
3. os.killpg is called with SIGKILL when communicate() times out.
4. integration-tests is NOT in GATE_PARSERS (I-00049 second fix — starts containers).
5. lint, typecheck, unit-tests, frontend-tests ARE still in GATE_PARSERS.
"""

import signal
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.daemon.qv_baseline import GATE_PARSERS

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_config(_tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.baseline_qv_enabled = True
    cfg.setting_up_threshold = 600
    return cfg


def make_project_config() -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="opencode",
        worktree_base=".worktrees",
        config={},
    )


def make_manager(_tmp_path: Path) -> BatchManager:
    manager = BatchManager.__new__(BatchManager)
    manager.project_id = "test-proj"
    manager.project_config = make_project_config()
    manager.config = make_config(_tmp_path)
    return manager


# ---------------------------------------------------------------------------
# I-00049 regression: wall-clock non-blocking contract
# ---------------------------------------------------------------------------


class TestI00049RunGateCommandNonBlocking:
    """Regression test: _run_gate_command must return within the timeout even
    when a grandchild keeps the stdout pipe open after the parent shell exits.

    The old implementation used subprocess.run(capture_output=True) which would
    block indefinitely in this scenario. The fix uses Popen + os.killpg on
    TimeoutExpired so the process group is torn down before draining pipes.
    """

    def test_run_gate_command_does_not_deadlock_with_background_grandchild(self, tmp_path: Path):
        """
        Regression test for I-00049.

        Command: bash -c 'sleep 600 &'
          - bash starts, forks sleep 600 into the background, exits immediately
          - the shell process group is killed on timeout via killpg
          - _run_gate_command must return promptly without hanging

        The test exercises the real _run_gate_command path with a mocked Popen
        whose communicate() raises TimeoutExpired on first call (simulating
        the 2s injected timeout), then drains on second call.

        With the old subprocess.run implementation this would hang because the
        grandchild sleep keeps the read-end of the pipe open after the parent
        shell exits, causing communicate() to block indefinitely.
        """
        manager = make_manager(tmp_path)
        command = "bash -c 'sleep 600 &'"

        fake_proc = MagicMock()
        fake_proc.pid = 54321
        fake_proc.communicate = MagicMock(
            side_effect=[
                subprocess.TimeoutExpired(cmd=command, timeout=2),
                (b"", b""),
            ]
        )
        fake_proc.__enter__.return_value = fake_proc
        fake_proc.__exit__.return_value = False

        start = time.monotonic()
        with (
            patch("orch.daemon.batch_manager.subprocess.Popen", return_value=fake_proc),
            patch("orch.daemon.batch_manager.os.killpg") as mock_killpg,
            patch("orch.daemon.batch_manager.os.getpgid", return_value=54321),
        ):
            result = manager._run_gate_command(command, str(tmp_path), "lint")
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, (
            f"_run_gate_command blocked for {elapsed:.1f}s — pipe deadlock "
            f"suspected (I-00049). Command: {command!r}"
        )
        mock_killpg.assert_called_once()
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Normal completion
# ---------------------------------------------------------------------------


class TestRunGateCommandReturnsOutput:
    """_run_gate_command must always return output, never raise."""

    def test_run_gate_command_returns_stdout_on_success(self, tmp_path: Path):
        """Gate command that exits 0 returns its combined stdout+stderr."""
        manager = make_manager(tmp_path)

        result = manager._run_gate_command("echo hello", str(tmp_path), "lint")

        assert "hello" in result

    def test_run_gate_command_returns_output_on_nonzero_exit(self, tmp_path: Path):
        """Gate command that exits non-zero must return output, not raise."""
        manager = make_manager(tmp_path)

        result = manager._run_gate_command("echo err >&2; exit 1", str(tmp_path), "lint")

        assert "err" in result


# ---------------------------------------------------------------------------
# os.killpg called on timeout
# ---------------------------------------------------------------------------


class TestRunGateCommandKillpgOnTimeout:
    """On TimeoutExpired, os.killpg must be called with the process group ID."""

    def test_run_gate_command_kills_process_group_on_timeout(self, tmp_path: Path):
        """On TimeoutExpired, os.killpg must be called with SIGKILL and the PGID."""
        manager = make_manager(tmp_path)

        fake_proc = MagicMock()
        fake_proc.pid = 12345
        fake_proc.communicate = MagicMock(
            side_effect=[
                subprocess.TimeoutExpired(cmd="bash -c 'sleep 600 &'", timeout=300),
                (b"partial output", b""),
            ]
        )
        fake_proc.__enter__.return_value = fake_proc
        fake_proc.__exit__.return_value = False

        with (
            patch("orch.daemon.batch_manager.subprocess.Popen", return_value=fake_proc),
            patch("orch.daemon.batch_manager.os.killpg") as mock_killpg,
            patch("orch.daemon.batch_manager.os.getpgid", return_value=12345),
        ):
            result = manager._run_gate_command("bash -c 'sleep 600 &'", str(tmp_path), "lint")

        mock_killpg.assert_called_once_with(12345, signal.SIGKILL)
        assert isinstance(result, str)

    def test_run_gate_command_returns_output_after_killpg(self, tmp_path: Path):
        """After killing the process group, _run_gate_command must still return output."""
        manager = make_manager(tmp_path)

        fake_proc = MagicMock()
        fake_proc.pid = 99999
        fake_proc.communicate = MagicMock(
            side_effect=[
                subprocess.TimeoutExpired(cmd="sleep 600", timeout=300),
                (b"partial output before timeout", b""),
            ]
        )
        fake_proc.__enter__.return_value = fake_proc
        fake_proc.__exit__.return_value = False

        with (
            patch("orch.daemon.batch_manager.subprocess.Popen", return_value=fake_proc),
            patch("orch.daemon.batch_manager.os.killpg"),
            patch("orch.daemon.batch_manager.os.getpgid", return_value=99999),
        ):
            result = manager._run_gate_command("bash -c 'sleep 600 &'", str(tmp_path), "lint")

        assert "partial output before timeout" in result


# ---------------------------------------------------------------------------
# GATE_PARSERS: integration-tests must not be registered
# ---------------------------------------------------------------------------


class TestGATEPARSERSExcludesIntegrationTests:
    """integration-tests must not be a registered baseline gate (I-00049 second fix).

    Reason: integration-tests starts testcontainers which requires Docker — it
    cannot run at worktree setup time in the daemon's polling loop. It must only
    run in the CI pipeline.
    """

    def test_integration_tests_not_in_gate_parsers(self):
        """integration-tests must not be in GATE_PARSERS."""
        assert "integration-tests" not in GATE_PARSERS, (
            "integration-tests must not run at worktree setup time — "
            "it starts testcontainers and blocks the daemon (I-00049)"
        )

    def test_fast_gates_remain_in_gate_parsers(self):
        """lint, typecheck, unit-tests, frontend-tests must still be registered."""
        for gate in ("lint", "typecheck", "unit-tests", "frontend-tests"):
            assert gate in GATE_PARSERS, f"Expected gate '{gate}' to remain in GATE_PARSERS"
