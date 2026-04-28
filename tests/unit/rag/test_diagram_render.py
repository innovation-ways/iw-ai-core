"""Unit tests for orch/diagram/render.py — TDD RED phase.

These tests are written BEFORE implementation and must FAIL initially.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_binary_caches():
    """Reset module-level binary caches before each test."""
    import orch.diagram.render as render_module

    render_module._MERMAID_BINARY_CACHE = None
    render_module._D2_BINARY_CACHE = None
    return


class TestRenderMermaid:
    def test_returns_none_when_binary_missing(self):
        """When mmdc is not on PATH, render_mermaid returns None without raising."""
        from orch.diagram.render import render_mermaid

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with (
            patch("shutil.which", return_value=None),
            patch("pathlib.Path", return_value=mock_path),
        ):
            result = render_mermaid("graph TD\n  A[Hello]")
        assert result is None

    def test_returns_none_on_timeout(self):
        """When mmdc times out, render_mermaid returns None and logs warning."""
        from orch.diagram.render import render_mermaid

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with (
            patch("shutil.which", return_value="/usr/bin/mmdc"),
            patch("pathlib.Path", return_value=mock_path),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="mmdc", timeout=10)),
        ):
            result = render_mermaid("graph TD\n  A[Hello]")
        assert result is None

    def test_returns_none_on_nonzero_exit(self):
        """When mmdc returns nonzero exit, render_mermaid returns None and logs warning."""
        from orch.diagram.render import render_mermaid

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = b"Error: invalid syntax"

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with (
            patch("shutil.which", return_value="/usr/bin/mmdc"),
            patch("pathlib.Path", return_value=mock_path),
            patch("subprocess.run", return_value=mock_proc),
        ):
            result = render_mermaid("graph TD\n  A[Hello]")
        assert result is None

    def test_returns_none_on_unexpected_exception(self):
        """When an unexpected exception occurs, render_mermaid returns None without raising."""
        from orch.diagram.render import render_mermaid

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with (
            patch("shutil.which", return_value="/usr/bin/mmdc"),
            patch("pathlib.Path", return_value=mock_path),
            patch("subprocess.run", side_effect=RuntimeError("unexpected")),
        ):
            result = render_mermaid("graph TD\n  A[Hello]")
        assert result is None


class TestRenderD2:
    def test_returns_none_when_binary_missing(self):
        """When d2 is not on PATH, render_d2 returns None without raising."""
        from orch.diagram.render import render_d2

        with patch("shutil.which", return_value=None):
            result = render_d2('graph TD\n  A["Hello"]')
        assert result is None

    def test_returns_none_on_timeout(self):
        """When d2 times out, render_d2 returns None and logs warning."""
        from orch.diagram.render import render_d2

        with (
            patch("shutil.which", return_value="/usr/bin/d2"),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="d2", timeout=10)),
        ):
            result = render_d2('graph TD\n  A["Hello"]')
        assert result is None

    def test_returns_none_on_nonzero_exit(self):
        """When d2 returns nonzero exit, render_d2 returns None and logs warning."""
        from orch.diagram.render import render_d2

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = b"Error: invalid input"

        with (
            patch("shutil.which", return_value="/usr/bin/d2"),
            patch("subprocess.run", return_value=mock_proc),
        ):
            result = render_d2('graph TD\n  A["Hello"]')
        assert result is None


class TestRenderDispatcher:
    def test_dispatch_mermaid(self):
        """render(dsl, 'mermaid') calls render_mermaid."""
        from orch.diagram.render import render

        with patch("orch.diagram.render.render_mermaid") as mock_m:
            mock_m.return_value = "<svg>test</svg>"
            result = render("graph TD\n  A[X]", "mermaid")
            mock_m.assert_called_once_with("graph TD\n  A[X]")
            assert result == "<svg>test</svg>"

    def test_dispatch_d2(self):
        """render(dsl, 'd2') calls render_d2."""
        from orch.diagram.render import render

        with patch("orch.diagram.render.render_d2") as mock_d:
            mock_d.return_value = "<svg>d2 output</svg>"
            result = render("graph TD\n  A[X]", "d2")
            mock_d.assert_called_once_with("graph TD\n  A[X]")
            assert result == "<svg>d2 output</svg>"

    def test_dispatch_unknown_returns_none(self):
        """render with unknown dsl_type returns None."""
        from orch.diagram.render import render

        result = render("graph TD\n  A[X]", "unknown")
        assert result is None


class TestCheckDiagramTools:
    def test_both_missing(self):
        """check_diagram_tools returns all False when binaries are absent."""
        from orch.diagram.install import check_diagram_tools

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with (
            patch("shutil.which", return_value=None),
            patch("pathlib.Path", return_value=mock_path),
        ):
            result = check_diagram_tools()
            assert result == {"mermaid": False, "d2": False}

    def test_mermaid_available(self):
        """check_diagram_tools shows mermaid True when mmdc found."""
        from orch.diagram.install import check_diagram_tools

        def which_mock(binary):
            if binary == "mmdc":
                return "/usr/bin/mmdc"
            return None

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with (
            patch("shutil.which", side_effect=which_mock),
            patch("pathlib.Path", return_value=mock_path),
        ):
            result = check_diagram_tools()
            assert result["mermaid"] is True
            assert result["d2"] is False

    def test_d2_available(self):
        """check_diagram_tools shows d2 True when d2 found."""
        from orch.diagram.install import check_diagram_tools

        def which_mock(binary):
            if binary == "d2":
                return "/usr/bin/d2"
            return None

        with patch("shutil.which", side_effect=which_mock):
            result = check_diagram_tools()
            assert result["mermaid"] is False
            assert result["d2"] is True

    def test_both_available(self):
        """check_diagram_tools returns all True when both binaries found."""
        from orch.diagram.install import check_diagram_tools

        def which_mock(binary):
            if binary in ("mmdc", "d2"):
                return f"/usr/bin/{binary}"
            return None

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with (
            patch("shutil.which", side_effect=which_mock),
            patch("pathlib.Path", return_value=mock_path),
        ):
            result = check_diagram_tools()
            assert result == {"mermaid": True, "d2": True}
