"""Tests for daemon_control async handlers (D3)."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dashboard.routers.daemon_control import daemon_restart, daemon_start, daemon_stop


class TestDaemonControlAsync:
    """Tests for DaemonControlAsync scenarios."""

    def test_daemon_start_is_async(self) -> None:
        """Verifies that daemon start is async."""
        assert inspect.iscoroutinefunction(daemon_start)

    def test_daemon_stop_is_async(self) -> None:
        """Verifies that daemon stop is async."""
        assert inspect.iscoroutinefunction(daemon_stop)

    def test_daemon_restart_is_async(self) -> None:
        """Verifies that daemon restart is async."""
        assert inspect.iscoroutinefunction(daemon_restart)


class TestDaemonControlSleeps:
    """Tests for DaemonControlSleeps scenarios."""

    def test_daemon_start_source_contains_asyncio_sleep(self) -> None:
        """Verifies that daemon start source contains asyncio sleep."""
        source = inspect.getsource(daemon_start)
        assert "asyncio.sleep" in source, "daemon_start should use asyncio.sleep for async delays"

    def test_daemon_stop_source_contains_asyncio_sleep(self) -> None:
        """Verifies that daemon stop source contains asyncio sleep."""
        source = inspect.getsource(daemon_stop)
        assert "asyncio.sleep" in source, "daemon_stop should use asyncio.sleep for async delays"

    def test_daemon_restart_source_contains_asyncio_sleep(self) -> None:
        """Verifies that daemon restart source contains asyncio sleep."""
        source = inspect.getsource(daemon_restart)
        assert "asyncio.sleep" in source, "daemon_restart should use asyncio.sleep for async delays"

    @pytest.mark.asyncio
    async def test_daemon_start_calls_asyncio_sleep(self) -> None:
        """Verifies that daemon start calls asyncio sleep."""
        mock_request = MagicMock()
        mock_db = MagicMock()

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("orch.cli.daemon_commands.get_pid_file_path") as mock_pid_path,
            patch("orch.cli.daemon_commands.read_pid") as mock_read_pid,
            patch("orch.cli.daemon_commands.is_process_alive") as mock_alive,
            patch("dashboard.routers.daemon_control.subprocess.Popen") as mock_popen,
        ):
            mock_pid_path.return_value = MagicMock()
            mock_read_pid.return_value = None
            mock_alive.return_value = False
            mock_popen.return_value = MagicMock()

            await daemon_start(mock_request, mock_db)

            assert mock_sleep.called, "asyncio.sleep should be called in daemon_start"

    @pytest.mark.asyncio
    async def test_daemon_stop_calls_asyncio_sleep(self) -> None:
        """Verifies that daemon stop calls asyncio sleep."""
        mock_request = MagicMock()
        mock_db = MagicMock()

        call_count = 0

        def mock_is_alive(pid: int) -> bool:
            """Return mock is alive."""
            nonlocal call_count
            call_count += 1
            return call_count == 1

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("orch.cli.daemon_commands.get_pid_file_path") as mock_pid_path,
            patch("orch.cli.daemon_commands.read_pid") as mock_read_pid,
            patch(
                "orch.cli.daemon_commands.is_process_alive",
                side_effect=mock_is_alive,
            ),
            patch("dashboard.routers.daemon_control.os.kill"),
            patch(
                "dashboard.routers.daemon_control._render_panel",
                return_value=MagicMock(),
            ),
        ):
            mock_pid_path.return_value = MagicMock()
            mock_read_pid.return_value = 12345

            await daemon_stop(mock_request, mock_db)

            assert mock_sleep.called, "asyncio.sleep should be called in daemon_stop"

    @pytest.mark.asyncio
    async def test_daemon_restart_calls_asyncio_sleep(self) -> None:
        """Verifies that daemon restart calls asyncio sleep."""
        mock_request = MagicMock()
        mock_db = MagicMock()

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("orch.cli.daemon_commands.get_pid_file_path") as mock_pid_path,
            patch("orch.cli.daemon_commands.read_pid") as mock_read_pid,
            patch("orch.cli.daemon_commands.is_process_alive") as mock_alive,
            patch("dashboard.routers.daemon_control.os.kill"),
            patch("dashboard.routers.daemon_control.subprocess.Popen") as mock_popen,
        ):
            mock_pid_path.return_value = MagicMock()
            mock_read_pid.return_value = 12345
            mock_alive.return_value = False
            mock_popen.return_value = MagicMock()

            await daemon_restart(mock_request, mock_db)

            assert mock_sleep.called, "asyncio.sleep should be called in daemon_restart"
