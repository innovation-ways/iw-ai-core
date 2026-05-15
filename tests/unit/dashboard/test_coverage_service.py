"""Tests for dashboard/services/coverage_service.py — TDD RED phase."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_coverage_dir(tmp_path: Path) -> Generator[Path, None, None]:
    coverage_dir = tmp_path / "coverage"
    coverage_dir.mkdir()
    return coverage_dir


@pytest.fixture
def sample_coverage_json(temp_coverage_dir: Path) -> Path:
    path = temp_coverage_dir / "coverage.json"
    path.write_text(
        json.dumps(
            {
                "meta": {"version": "7.0.0", "timestamp": "2026-04-29T00:00:00Z"},
                "totals": {
                    "percent_covered": 75.5,
                    "branch_percent_covered": 60.0,
                    "num_statements": 1000,
                    "num_statements_covered": 755,
                },
                "files": {
                    "orch/foo.py": {
                        "summary": {
                            "percent_covered": 80.0,
                            "branch_percent_covered": 70.0,
                            "missing_lines": 20,
                        },
                    },
                    "orch/bar.py": {
                        "summary": {
                            "percent_covered": 50.0,
                            "branch_percent_covered": 40.0,
                            "missing_lines": 100,
                        },
                    },
                    "dashboard/widget.py": {
                        "summary": {
                            "percent_covered": 90.0,
                            "branch_percent_covered": 85.0,
                            "missing_lines": 10,
                        },
                    },
                    "executor/script.sh": {
                        "summary": {
                            "percent_covered": 0.0,
                            "branch_percent_covered": 0.0,
                            "missing_lines": 50,
                        },
                    },
                },
            },
        ),
    )
    return path


@pytest.fixture
def pyproject_with_threshold(tmp_path: Path) -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        "[tool.coverage.report]\nfail_under = 70\nskip_covered = true\nshow_missing = true\n",
    )
    return path


class TestLoadCoverage:
    def test_missing_coverage_json(
        self,
        tmp_path: Path,
        pyproject_with_threshold: Path,
    ) -> None:
        from dashboard.services.coverage_service import load_coverage

        view = load_coverage(
            coverage_json_path=tmp_path / "nonexistent.json",
            pyproject_path=pyproject_with_threshold,
        )
        assert view.available is False
        assert view.error is None
        assert view.threshold == 70
        assert view.mtime_iso is None
        assert view.packages == []

    def test_malformed_coverage_json(
        self,
        temp_coverage_dir: Path,
        pyproject_with_threshold: Path,
    ) -> None:
        from dashboard.services.coverage_service import load_coverage

        bad_path = temp_coverage_dir / "coverage.json"
        bad_path.write_text("{ not valid json }")

        view = load_coverage(
            coverage_json_path=bad_path,
            pyproject_path=pyproject_with_threshold,
        )
        assert view.available is False
        assert view.error is not None

    def test_valid_coverage_json(
        self,
        sample_coverage_json: Path,
        pyproject_with_threshold: Path,
    ) -> None:
        from dashboard.services.coverage_service import load_coverage

        view = load_coverage(
            coverage_json_path=sample_coverage_json,
            pyproject_path=pyproject_with_threshold,
        )
        assert view.available is True
        assert view.error is None
        assert view.overall_line_pct == 75.5
        assert view.overall_branch_pct == 60.0
        assert view.threshold == 70
        assert view.gap_pct == 5.5
        assert len(view.packages) == 3
        assert view.mtime_iso is not None

    def test_package_rollup(
        self,
        sample_coverage_json: Path,
        pyproject_with_threshold: Path,
    ) -> None:
        from dashboard.services.coverage_service import load_coverage

        view = load_coverage(
            coverage_json_path=sample_coverage_json,
            pyproject_path=pyproject_with_threshold,
        )
        packages = {p.name: p for p in view.packages}
        assert "orch" in packages
        assert "dashboard" in packages
        assert "executor" in packages
        orch_pkg = packages["orch"]
        assert orch_pkg.line_pct == 65.0
        assert orch_pkg.missing_lines == 120

    def test_badge_green(
        self,
        sample_coverage_json: Path,
        pyproject_with_threshold: Path,
    ) -> None:
        from dashboard.services.coverage_service import load_coverage

        view = load_coverage(
            coverage_json_path=sample_coverage_json,
            pyproject_path=pyproject_with_threshold,
        )
        packages = {p.name: p for p in view.packages}
        assert packages["dashboard"].badge == "green"

    def test_badge_amber(
        self,
        sample_coverage_json: Path,
        pyproject_with_threshold: Path,
    ) -> None:
        from dashboard.services.coverage_service import load_coverage

        view = load_coverage(
            coverage_json_path=sample_coverage_json,
            pyproject_path=pyproject_with_threshold,
        )
        packages = {p.name: p for p in view.packages}
        assert packages["orch"].badge == "amber"

    def test_badge_red(
        self,
        sample_coverage_json: Path,
        pyproject_with_threshold: Path,
    ) -> None:
        from dashboard.services.coverage_service import load_coverage

        view = load_coverage(
            coverage_json_path=sample_coverage_json,
            pyproject_path=pyproject_with_threshold,
        )
        packages = {p.name: p for p in view.packages}
        assert packages["executor"].badge == "red"

    def test_files_by_package(
        self,
        sample_coverage_json: Path,
        pyproject_with_threshold: Path,
    ) -> None:
        from dashboard.services.coverage_service import load_coverage

        view = load_coverage(
            coverage_json_path=sample_coverage_json,
            pyproject_path=pyproject_with_threshold,
        )
        assert "orch" in view.files_by_package
        assert len(view.files_by_package["orch"]) == 2
        assert "dashboard" in view.files_by_package
        assert len(view.files_by_package["dashboard"]) == 1
        assert "executor" in view.files_by_package

    def test_threshold_from_pyproject(self, tmp_path: Path) -> None:
        from dashboard.services.coverage_service import load_coverage

        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(
            "[tool.coverage.report]\nfail_under = 42\n",
        )

        no_coverage = tmp_path / "nonexistent.json"
        view = load_coverage(coverage_json_path=no_coverage, pyproject_path=pyproject_path)
        assert view.threshold == 42

    def test_threshold_zero_when_missing(self, tmp_path: Path) -> None:
        from dashboard.services.coverage_service import load_coverage

        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text("[tool.other]\nno_fail_under = true\n")

        no_coverage = tmp_path / "nonexistent.json"
        view = load_coverage(coverage_json_path=no_coverage, pyproject_path=pyproject_path)
        assert view.threshold == 0

    def test_partial_coverage_json_totals_present_files_absent(
        self,
        temp_coverage_dir: Path,
        pyproject_with_threshold: Path,
    ) -> None:
        from dashboard.services.coverage_service import load_coverage

        partial_path = temp_coverage_dir / "coverage.json"
        partial_path.write_text(
            json.dumps(
                {
                    "meta": {"version": "7.0.0", "timestamp": "2026-04-29T00:00:00Z"},
                    "totals": {
                        "percent_covered": 75.5,
                        "branch_percent_covered": 60.0,
                        "num_statements": 1000,
                        "num_statements_covered": 755,
                    },
                },
            ),
        )

        view = load_coverage(
            coverage_json_path=partial_path,
            pyproject_path=pyproject_with_threshold,
        )
        assert view.available is True
        assert view.error is None
        assert view.overall_line_pct == 75.5
        assert view.overall_branch_pct == 60.0
        assert view.threshold == 70
        assert view.packages == []
        assert view.files_by_package == {}
