"""Smoke tests for Makefile targets and pyproject.toml coverage threshold.

Locks the public surface so future Makefile cleanups don't accidentally
remove test-parallel, e2e-*, allure-report, or the fail_under threshold.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def makefile_text() -> str:
    return Path("Makefile").read_text()


@pytest.fixture
def pyproject_text() -> str:
    return Path("pyproject.toml").read_text()


class TestMakeTargets:
    def test_makefile_has_test_parallel(self, makefile_text: str) -> None:
        assert "test-parallel" in makefile_text

    def test_makefile_has_e2e_health(self, makefile_text: str) -> None:
        assert "e2e-health" in makefile_text

    def test_makefile_has_e2e_logs(self, makefile_text: str) -> None:
        assert "e2e-logs" in makefile_text

    def test_makefile_has_e2e_stats(self, makefile_text: str) -> None:
        assert "e2e-stats" in makefile_text

    def test_makefile_has_allure_report(self, makefile_text: str) -> None:
        assert "allure-report" in makefile_text


class TestCoverageThreshold:
    def test_pyproject_has_fail_under(self, pyproject_text: str) -> None:
        assert "[tool.coverage.report]" in pyproject_text
        assert "fail_under" in pyproject_text

    def test_fail_under_is_non_negative(self, pyproject_text: str) -> None:
        import re

        match = re.search(r"fail_under\s*=\s*(\d+(?:\.\d+)?)", pyproject_text)
        assert match is not None, "fail_under setting not found in pyproject.toml"
        value = float(match.group(1))
        assert value >= 0, f"fail_under={value} is negative — must be >= 0"
