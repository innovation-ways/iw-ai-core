"""Unit tests for the shared `lib/results.py` helper used by OSS checks.

The helper turns ripgrep ``path:line:text`` output into the canonical
``[{file, line, rule, snippet_masked}, ...]`` shape that
``orch/oss/persistence.py`` pops out of ``evidence`` and writes to the
``oss_finding_detail`` table. Without that shape the modal's per-hit table
stays empty, which is exactly the bug the user hit on RFC-1918 findings.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Skill scripts live outside the orch package and use sys.path injection.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "iw-oss-publish" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


class TestParseRgLines:
    """Tests for ParseRgLines scenarios."""

    def test_parses_path_line_text(self) -> None:
        """Verifies that parses path line text."""
        from lib.results import parse_rg_lines

        rows = parse_rg_lines(
            ["src/foo.py:42:    ip = '10.0.0.1'"],
            rule_id="OSS-REF-01",
        )
        assert rows == [
            {
                "file": "src/foo.py",
                "line": 42,
                "rule": "OSS-REF-01",
                "snippet_masked": "ip = '10.0.0.1'",
            }
        ]

    def test_skips_unparseable_lines(self) -> None:
        """Verifies that skips unparseable lines."""
        from lib.results import parse_rg_lines

        rows = parse_rg_lines(
            [
                "binary file matches",
                "src/a.py:1:hit",
                "",
            ],
            rule_id="OSS-REF-01",
        )
        assert len(rows) == 1
        assert rows[0]["file"] == "src/a.py"

    def test_truncates_long_snippets(self) -> None:
        """Verifies that truncates long snippets."""
        from lib.results import parse_rg_lines

        long_text = "x" * 1000
        rows = parse_rg_lines(
            [f"src/a.py:1:{long_text}"],
            rule_id="OSS-REF-01",
            snippet_max_chars=50,
        )
        assert rows[0]["snippet_masked"].endswith("…")
        assert len(rows[0]["snippet_masked"]) == 51  # 50 chars + ellipsis


class TestBuildResultsEvidence:
    """Tests for BuildResultsEvidence scenarios."""

    def test_total_defaults_to_record_count(self) -> None:
        """Verifies that total defaults to record count."""
        from lib.results import build_results_evidence

        records = [{"file": "a", "line": None, "rule": "R", "snippet_masked": ""}]
        ev = build_results_evidence(records)
        assert ev["finding_count"] == 1
        assert ev["total_results"] == 1
        assert ev["capped"] is False
        assert ev["results"] == records

    def test_capped_when_total_exceeds_cap(self) -> None:
        """Verifies that capped when total exceeds cap."""
        from lib.results import RESULT_CAP, build_results_evidence

        records = [
            {"file": f"f{i}", "line": None, "rule": "R", "snippet_masked": ""} for i in range(10)
        ]
        ev = build_results_evidence(records, total=RESULT_CAP + 100)
        assert ev["capped"] is True
        assert ev["finding_count"] == RESULT_CAP + 100
        assert len(ev["results"]) == 10

    def test_results_truncated_to_cap(self) -> None:
        """Verifies that results truncated to cap."""
        from lib.results import RESULT_CAP, build_results_evidence

        records = [
            {"file": f"f{i}", "line": None, "rule": "R", "snippet_masked": ""}
            for i in range(RESULT_CAP + 50)
        ]
        ev = build_results_evidence(records)
        assert len(ev["results"]) == RESULT_CAP

    def test_extras_merged(self) -> None:
        """Verifies that extras merged."""
        from lib.results import build_results_evidence

        ev = build_results_evidence([], extras={"sarif": "/tmp/x.sarif"})
        assert ev["sarif"] == "/tmp/x.sarif"
        assert ev["results"] == []


class TestInternalRefsEvidenceShape:
    """End-to-end-ish: drive the check's _result_to_finding helper with a
    canned ``_rg_search`` payload and confirm the produced Finding carries an
    ``evidence['results']`` list that persistence will accept."""

    def test_rfc1918_finding_carries_results(self) -> None:
        """Verifies that rfc1918 finding carries results."""
        from checks.internal_refs import _result_to_finding
        from lib.types import Severity

        payload = {
            "count": 3,
            "lines": [
                "config/dev.yaml:7:host: 10.0.0.1",
                "config/dev.yaml:8:peer: 192.168.1.10",
                "infra/setup.sh:42:VPN_NET=172.16.0.0/12",
            ],
        }
        finding = _result_to_finding(
            "OSS-REF-01",
            Severity.MUST,
            "RFC 1918 private IP addresses",
            payload,
            remediation_hit="Replace.",
        )
        assert finding.evidence is not None
        results = finding.evidence["results"]
        assert len(results) == 3
        assert results[0]["file"] == "config/dev.yaml"
        assert results[0]["line"] == 7
        assert results[0]["rule"] == "OSS-REF-01"
        assert results[0]["snippet_masked"] == "host: 10.0.0.1"
        # Aggregate metadata kept on evidence_json (not popped to detail rows).
        assert finding.evidence["finding_count"] == 3
        assert finding.evidence["total_results"] == 3
        assert finding.evidence["capped"] is False
