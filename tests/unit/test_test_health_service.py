"""Unit tests for orch.test_health_service.

Tests the pure-logic artefacts readers without touching the database.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Mutation JSON parser tests
# ---------------------------------------------------------------------------


class TestMutationJsonParsing:
    """Parser for mutation-test JSON artefacts (CR-00080 + CR-00059 shapes)."""

    def test_read_mutation_score_new_shape(self, tmp_path: Path) -> None:
        """CR-00080 widened-scope shape: score is at root level."""
        from orch.test_health_service import _parse_mutation_json

        artifact_path = tmp_path / "mutation.json"
        artifact_path.write_text(
            json.dumps(
                {
                    "score": 81.4,
                    "total": 200,
                    "mutated": 200,
                    "killed": 163,
                    "passed": 37,
                    "skipped": 0,
                    "runtime_seconds": 120,
                }
            )
        )

        value, meta = _parse_mutation_json(artifact_path)

        assert value == 81.4
        assert meta["total"] == 200
        assert meta["mutated"] == 200
        assert meta["killed"] == 163

    def test_read_mutation_score_legacy_shape(self, tmp_path: Path) -> None:
        """CR-00059 spike shape: score is under a 'metrics' key."""
        from orch.test_health_service import _parse_mutation_json

        artifact_path = tmp_path / "mutation_legacy.json"
        artifact_path.write_text(
            json.dumps(
                {
                    "metrics": {
                        "score": 74.9,
                        "total_mutations": 143,
                        "mutations_killed": 107,
                        "mutations_timeout": 0,
                        "mutations_error": 0,
                    },
                    "summary": {"elapsed_seconds": 45},
                }
            )
        )

        value, meta = _parse_mutation_json(artifact_path)

        assert value == 74.9
        assert meta["total_mutations"] == 143
        assert meta["mutations_killed"] == 107

    def test_read_mutation_missing_file_returns_none(self, tmp_path: Path, caplog) -> None:
        """Missing mutation artefact returns None and logs one WARNING."""
        from orch.test_health_service import _read_mutation_score

        result = _read_mutation_score(tmp_path / "nonexistent.json")

        assert result is None
        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1
        assert "nonexistent" in warnings[0]

    def test_read_mutation_unparseable_json_logs_warning(self, tmp_path: Path, caplog) -> None:
        """Corrupt JSON returns None and logs one WARNING."""
        from orch.test_health_service import _read_mutation_score

        artifact_path = tmp_path / "broken.json"
        artifact_path.write_text("not valid json{{{")

        result = _read_mutation_score(artifact_path)

        assert result is None
        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1


# ---------------------------------------------------------------------------
# Assertion baseline reader tests
# ---------------------------------------------------------------------------


class TestBaselineLineCount:
    """Line-count reader for tests/assertion_free_baseline.txt (CR-00046)."""

    def test_baseline_line_count_strips_comments(self, tmp_path: Path) -> None:
        """Leading '#' comment lines are excluded from the count."""
        from orch.test_health_service import _read_baseline_size

        baseline_file = tmp_path / "baseline.txt"
        baseline_file.write_text(
            "# AST assertion-scanner baseline.\n"
            "# Purpose comment.\n"
            "# more comment\n"
            "\n"
            "tests/foo.py::test_one # no-assert\n"
            "tests/bar.py::test_two # tautology\n"
            "tests/baz.py::test_three # mock-only\n"
            "# just a comment\n"
            "tests/qux.py::test_four # broad-raises\n"
        )

        result = _read_baseline_size(baseline_file)
        assert result is not None
        count, meta = result
        assert count == 4.0  # 4 actual test entries
        assert meta["comment_lines"] == 4

    def test_baseline_all_comments_returns_zero(self, tmp_path: Path) -> None:
        """File with only comment lines returns 0."""
        from orch.test_health_service import _read_baseline_size

        baseline_file = tmp_path / "all_comments.txt"
        baseline_file.write_text("# only\n# comments\n# here\n")

        result = _read_baseline_size(baseline_file)
        assert result is not None
        count, _ = result
        assert count == 0.0

    def test_baseline_missing_file_returns_none(self, tmp_path: Path, caplog) -> None:
        """Missing baseline file returns None and logs a WARNING."""
        from orch.test_health_service import _read_baseline_size

        result = _read_baseline_size(tmp_path / "nonexistent.txt")

        assert result is None
        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1


# ---------------------------------------------------------------------------
# Coverage reader tests
# ---------------------------------------------------------------------------


class TestCoverageReader:
    """Coverage JSON reader (delegates to dashboard.services.coverage_service)."""

    def test_read_coverage_pct_extracts_line_percent(self, tmp_path: Path) -> None:
        """Coverage reader extracts overall_line_pct from the JSON artefact."""
        from orch.test_health_service import _read_coverage_pct

        # Write a minimal coverage JSON
        coverage_dir = tmp_path / "tests" / "output" / "coverage"
        coverage_dir.mkdir(parents=True)
        coverage_file = coverage_dir / "coverage.json"
        coverage_file.write_text(
            json.dumps(
                {
                    "totals": {
                        "percent_covered": 88.5,
                        "branch_percent_covered": 72.1,
                        "num_statements_covered": 1200,
                    },
                    "files": {},
                }
            )
        )

        # pyproject.toml with fail_under
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.coverage.report]\nfail_under = 80\n")

        result = _read_coverage_pct(coverage_file, pyproject)

        assert result is not None
        value, meta = result
        assert value == 88.5
        assert meta["threshold"] == 80

    def test_coverage_missing_file_returns_none(self, tmp_path: Path, caplog) -> None:
        """Missing coverage artefact returns None and logs one WARNING."""
        from orch.test_health_service import _read_coverage_pct

        result = _read_coverage_pct(tmp_path / "nonexistent.json", tmp_path / "pyproject.toml")

        assert result is None
        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1


# ---------------------------------------------------------------------------
# Flaky reader tests
# ---------------------------------------------------------------------------


class TestFlakyReader:
    """Flaky-test count reader via JSON artefact or script fallback."""

    def test_flaky_via_summary_json(self, tmp_path: Path) -> None:
        """Direct JSON artefact with flake list is parsed correctly."""
        from orch.test_health_service import _read_flaky_count

        flaky_json = tmp_path / "flake_summary.json"
        flaky_json.write_text(
            json.dumps(
                {
                    "flakes": [
                        {
                            "test_id": "tests/foo.py::test_b",
                            "outcomes": ["FAILED", "PASSED", "PASSED"],
                        },
                        {
                            "test_id": "tests/bar.py::test_c",
                            "outcomes": ["PASSED", "FAILED", "PASSED"],
                        },
                    ]
                }
            )
        )

        result = _read_flaky_count(tmp_path / "fake_root", flake_summary_json=flaky_json)

        assert result is not None
        count, meta = result
        assert count == 2.0
        assert meta["source"] == "flake_summary_json"
        assert "tests/foo.py::test_b" in meta["flakes"]

    def test_flaky_missing_all_returns_none(self, tmp_path: Path, caplog) -> None:
        """When no flaky log files exist, returns None and logs one WARNING."""
        from orch.test_health_service import _read_flaky_count

        result = _read_flaky_count(tmp_path)

        assert result is None
        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1


# ---------------------------------------------------------------------------
# read_sources aggregation tests
# ---------------------------------------------------------------------------


class TestReadSources:
    """read_sources(repo_root) aggregates all four artefact readers."""

    def test_all_four_present(self, tmp_path: Path) -> None:
        """When all four artefacts are present, all four keys have values."""
        from orch.test_health_service import read_sources

        # mutation JSON (CR-00080 shape)
        mutation_dir = tmp_path / "tests" / "output" / "mutation"
        mutation_dir.mkdir(parents=True)
        (mutation_dir / "mutation.json").write_text(
            json.dumps({"score": 85.0, "total": 300, "mutated": 300, "killed": 255})
        )

        # coverage JSON
        cov_dir = tmp_path / "tests" / "output" / "coverage"
        cov_dir.mkdir(parents=True)
        (cov_dir / "coverage.json").write_text(
            json.dumps(
                {"totals": {"percent_covered": 91.2, "branch_percent_covered": 80.0}, "files": {}}
            )
        )
        (tmp_path / "pyproject.toml").write_text("[tool.coverage.report]\nfail_under = 80\n")

        # flaky summary JSON
        flaky_json = tmp_path / "flake_summary.json"
        flaky_json.write_text(
            json.dumps(
                {
                    "flakes": [
                        {
                            "test_id": "tests/foo.py::test_b",
                            "outcomes": ["FAILED", "PASSED", "PASSED"],
                        },
                        {
                            "test_id": "tests/bar.py::test_c",
                            "outcomes": ["PASSED", "FAILED", "PASSED"],
                        },
                    ]
                }
            )
        )

        # assertion baseline
        (tmp_path / "tests" / "assertion_free_baseline.txt").write_text(
            "tests/x.py::test_x # no-assert\ntests/y.py::test_y # tautology\n"
        )

        result = read_sources(str(tmp_path), flake_summary_json=flaky_json)

        assert result["mutation_score"] is not None
        assert result["coverage_pct"] is not None
        assert result["flaky_test_count"] is not None
        assert result["assertion_baseline_size"] is not None

        # Check values are numeric
        assert isinstance(result["mutation_score"][0], float)
        assert isinstance(result["coverage_pct"][0], float)
        assert result["flaky_test_count"][0] == 2.0  # 2 flaky tests

    def test_missing_one_source_returns_none_for_that_key(self, tmp_path: Path, caplog) -> None:
        """When one artefact is missing, only that key returns None."""
        from orch.test_health_service import read_sources

        # mutation JSON only; no coverage, flaky, or baseline
        mutation_dir = tmp_path / "tests" / "output" / "mutation"
        mutation_dir.mkdir(parents=True)
        (mutation_dir / "mutation.json").write_text(
            json.dumps({"score": 85.0, "total": 300, "mutated": 300, "killed": 255})
        )

        result = read_sources(str(tmp_path))

        assert result["mutation_score"] is not None
        assert result["coverage_pct"] is None
        assert result["flaky_test_count"] is None
        assert result["assertion_baseline_size"] is None

        # Exactly 3 WARNING logs for the 3 missing sources
        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 3

    def test_no_artefacts_returns_all_none(self, tmp_path: Path, caplog) -> None:
        """When no artefacts exist, all four keys are None."""
        from orch.test_health_service import read_sources

        result = read_sources(str(tmp_path))

        assert all(v is None for v in result.values())
        # Each reader logs exactly one WARNING
        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 4
