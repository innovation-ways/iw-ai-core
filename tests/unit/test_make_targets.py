"""Smoke tests for Makefile targets and pyproject.toml coverage threshold.

Locks the public surface so future Makefile cleanups don't accidentally
remove test-parallel, e2e-*, allure-report, or the fail_under threshold.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
MAKEFILE = REPO_ROOT / "Makefile"
TEST_QUALITY = REPO_ROOT / ".github" / "workflows" / "test-quality.yml"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@pytest.fixture
def makefile_text() -> str:
    """Provide makefile text for tests."""
    return Path("Makefile").read_text()


@pytest.fixture
def pyproject_text() -> str:
    """Provide pyproject text for tests."""
    return Path("pyproject.toml").read_text()


class TestMakeTargets:
    """Tests for MakeTargets scenarios."""

    def test_makefile_has_test_parallel(self, makefile_text: str) -> None:
        """Verifies that makefile has test parallel."""
        assert "test-parallel" in makefile_text

    def test_makefile_has_e2e_health(self, makefile_text: str) -> None:
        """Verifies that makefile has e2e health."""
        assert "e2e-health" in makefile_text

    def test_makefile_has_e2e_logs(self, makefile_text: str) -> None:
        """Verifies that makefile has e2e logs."""
        assert "e2e-logs" in makefile_text

    def test_makefile_has_e2e_stats(self, makefile_text: str) -> None:
        """Verifies that makefile has e2e stats."""
        assert "e2e-stats" in makefile_text

    def test_makefile_has_allure_report(self, makefile_text: str) -> None:
        """Verifies that makefile has allure report."""
        assert "allure-report" in makefile_text


class TestCoverageThreshold:
    """Tests for CoverageThreshold scenarios."""

    def test_pyproject_has_fail_under(self, pyproject_text: str) -> None:
        """Verifies that pyproject has fail under."""
        assert "[tool.coverage.report]" in pyproject_text
        assert "fail_under" in pyproject_text

    def test_fail_under_is_non_negative(self, pyproject_text: str) -> None:
        """Verifies that fail under is non negative."""
        import re as _re

        match = _re.search(r"fail_under\s*=\s*(\d+(?:\.\d+)?)", pyproject_text)
        assert match is not None, "fail_under setting not found in pyproject.toml"
        value = float(match.group(1))
        assert value >= 0, f"fail_under={value} is negative — must be >= 0"


class TestF00073SmokeGate:
    """Tests for F00073SmokeGate scenarios."""

    def test_smoke_marker_registered(self) -> None:
        """Verifies that smoke marker registered."""
        data = tomllib.loads(PYPROJECT.read_text())
        markers = data["tool"]["pytest"]["ini_options"].get("markers", [])
        assert any(m.startswith("smoke:") for m in markers), (
            "Marker 'smoke' must be registered in pyproject.toml — see F-00073"
        )

    def test_make_smoke_target_exists(self) -> None:
        """Verifies that make smoke target exists."""
        text = MAKEFILE.read_text()
        assert re.search(r"^smoke:\s", text, re.MULTILINE), (
            "Makefile target `smoke` missing — see F-00073"
        )

    def test_make_smoke_uses_strict_markers(self) -> None:
        """Verifies that make smoke uses strict markers."""
        text = MAKEFILE.read_text()
        smoke_section = re.search(r"^smoke:\s(.+?)(?:\n[\w-]+:|\Z)", text, re.MULTILINE | re.DOTALL)
        assert smoke_section, "Could not locate smoke target body"
        assert "--strict-markers" in smoke_section.group(1), "make smoke must pass --strict-markers"

    def test_test_quality_workflow_exists(self) -> None:
        """Verifies that test quality workflow exists."""
        assert TEST_QUALITY.is_file()

    def test_test_quality_workflow_has_job(self) -> None:
        """Verifies that test quality workflow has job."""
        data = yaml.safe_load(TEST_QUALITY.read_text())
        for job in ["lint-typecheck", "unit", "integration", "smoke"]:
            assert job in data["jobs"], f"test-quality.yml missing job {job!r}"

    def test_test_quality_workflow_actions_pinned(self) -> None:
        """Verifies that test quality workflow actions pinned."""
        text = TEST_QUALITY.read_text()
        pattern = re.compile(r"uses:\s*([\w./-]+)@([\w./-]+)")
        for action, ref in pattern.findall(text):
            assert SHA_RE.match(ref), f"Action {action!r} pinned to non-SHA ref {ref!r}"

    def test_test_quality_workflow_permissions_minimal(self) -> None:
        """Verifies that test quality workflow permissions minimal."""
        data = yaml.safe_load(TEST_QUALITY.read_text())
        perms = data.get("permissions", {})
        assert perms == {"contents": "read"}, (
            f"test-quality.yml permissions must be `contents: read` only — got {perms}"
        )

    def test_smoke_set_at_least_10_tests(self) -> None:
        """Lock that we have at least 10 tests with the smoke marker.

        This guards against accidental marker removal.
        """
        import ast
        import os

        smoke_marker = "pytest.mark.smoke"
        count = 0

        # Walk test files and count actual decorator usages via AST.
        # AST parsing avoids false positives from docstrings or comments and
        # does not depend on IW_CORE_TEST_CONTEXT (no imports are executed).
        for root, _dirs, files in os.walk(REPO_ROOT / "tests"):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = Path(root) / fname
                try:
                    tree = ast.parse(fpath.read_text())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    for deco in node.decorator_list:
                        deco_str = ast.unparse(deco)
                        if deco_str == smoke_marker or deco_str.startswith(smoke_marker + "("):
                            count += 1

        assert count >= 10, f"Expected >=10 tests decorated with @pytest.mark.smoke; found {count}."
