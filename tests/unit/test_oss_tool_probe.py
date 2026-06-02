"""Tests for orch.oss.tool_probe."""

from __future__ import annotations

from unittest.mock import patch


class TestProbeTier1:
    """Tests for ProbeTier1 scenarios."""

    def test_all_tools_reported(self) -> None:
        """Verifies that all tools reported."""
        from orch.oss.tool_probe import ToolStatus, probe_tier1

        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            result = probe_tier1()

        assert isinstance(result, dict)
        for _tool_name, status in result.items():
            assert isinstance(status, ToolStatus)
            assert status.installed is False
            assert status.version is None

    def test_installed_tool_reports_version(self) -> None:
        """Verifies that installed tool reports version."""
        from orch.oss.tool_probe import probe_tier1

        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/gitleaks"
            mock_run.return_value.stdout = "8.21.2"
            result = probe_tier1()

        assert "gitleaks" in result
        assert result["gitleaks"].installed is True
        assert result["gitleaks"].version is not None

    def test_ripgrep_alias(self) -> None:
        """Verifies that ripgrep alias."""
        from orch.oss.tool_probe import probe_tier1

        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/rg" if cmd == "rg" else None
            result = probe_tier1()

        assert "ripgrep" in result
        assert result["ripgrep"].installed is True

    def test_install_cmd_is_populated(self) -> None:
        """Verifies that install cmd is populated."""
        from orch.oss.tool_probe import ToolStatus, probe_tier1

        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            result = probe_tier1()

        for _tool_name, status in result.items():
            assert isinstance(status, ToolStatus)
            assert status.install_cmd is not None
            assert len(status.install_cmd) > 0
