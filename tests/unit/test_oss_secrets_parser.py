"""Unit tests for SARIF parsing and secret masking in iw-oss-publish/checks/secrets.py.

These tests exercise the helpers that turn raw gitleaks SARIF output into the
per-finding `results` array that gets surfaced in the OSS modal (file, line,
rule, masked snippet). They run under tests/unit because no DB or container is
required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# The skill scripts live outside the orch package and are loaded via sys.path
# injection inside scan.py. Tests need the same trick.
_SECRETS_DIR = Path(__file__).resolve().parents[2] / "skills" / "iw-oss-publish" / "scripts"
if str(_SECRETS_DIR) not in sys.path:
    sys.path.insert(0, str(_SECRETS_DIR))


# ---------------------------------------------------------------------------
# _mask_secret
# ---------------------------------------------------------------------------


class TestMaskSecret:
    """Tests for MaskSecret scenarios."""

    def test_short_value_fully_masked(self) -> None:
        """Verifies that short value fully masked."""
        from checks.secrets import _mask_secret

        assert _mask_secret("abcd") == "****"
        assert _mask_secret("12345678") == "********"

    def test_long_value_keeps_first_and_last_four(self) -> None:
        """Verifies that long value keeps first and last four."""
        from checks.secrets import _mask_secret

        # Length 20 — keep first 4 and last 4, mask middle.
        out = _mask_secret("sk-abcd1234ZZZZ9999XY")
        assert out.startswith("sk-a")
        assert out.endswith("99XY")
        # Middle should be entirely '*' (no original chars leaked).
        assert set(out[4:-4]) == {"*"}

    def test_empty_value(self) -> None:
        """Verifies that empty value."""
        from checks.secrets import _mask_secret

        assert _mask_secret("") == ""

    def test_none_value(self) -> None:
        """Verifies that none value."""
        from checks.secrets import _mask_secret

        assert _mask_secret(None) == ""

    def test_strips_surrounding_whitespace(self) -> None:
        """Verifies that strips surrounding whitespace."""
        from checks.secrets import _mask_secret

        # Leading/trailing whitespace shouldn't leak (it's noise from snippet
        # extraction). The mask is applied to the trimmed value.
        out = _mask_secret("   sk-abcd1234ZZZZ9999XY   ")
        assert out.startswith("sk-a")
        assert out.endswith("99XY")
        # No spaces remain after trimming + masking.
        assert " " not in out


# ---------------------------------------------------------------------------
# _parse_sarif_results
# ---------------------------------------------------------------------------


def _write_sarif(tmp_path: Path, results: list[dict], filename: str = "tree.sarif") -> Path:
    """Write a minimal valid SARIF document with the given gitleaks-style results."""
    doc = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "gitleaks"}},
                "results": results,
            }
        ],
    }
    out = tmp_path / filename
    out.write_text(json.dumps(doc), encoding="utf-8")
    return out


def _gitleaks_result(
    *,
    rule: str = "generic-api-key",
    uri: str = "src/config.py",
    line: int | None = 42,
    snippet: str = "API_KEY=sk-abcd1234ZZZZ9999XY",
) -> dict:
    """Return gitleaks result."""
    region: dict = {"snippet": {"text": snippet}}
    if line is not None:
        region["startLine"] = line
    return {
        "ruleId": rule,
        "message": {"text": f"{rule} detected secret"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": region,
                }
            }
        ],
    }


class TestParseSarifResults:
    """Tests for ParseSarifResults scenarios."""

    def test_missing_path_returns_empty(self, tmp_path: Path) -> None:
        """Verifies that missing path returns empty."""
        from checks.secrets import _parse_sarif_results

        results, total = _parse_sarif_results(None, target=tmp_path)
        assert results == []
        assert total == 0

    def test_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        """Verifies that nonexistent file returns empty."""
        from checks.secrets import _parse_sarif_results

        results, total = _parse_sarif_results(
            str(tmp_path / "does-not-exist.sarif"), target=tmp_path
        )
        assert results == []
        assert total == 0

    def test_malformed_json_returns_empty(self, tmp_path: Path) -> None:
        """Verifies that malformed json returns empty."""
        from checks.secrets import _parse_sarif_results

        bad = tmp_path / "bad.sarif"
        bad.write_text("this is not json", encoding="utf-8")
        results, total = _parse_sarif_results(str(bad), target=tmp_path)
        assert results == []
        assert total == 0

    def test_single_result_extracted(self, tmp_path: Path) -> None:
        """Verifies that single result extracted."""
        from checks.secrets import _parse_sarif_results

        sarif = _write_sarif(
            tmp_path,
            [
                _gitleaks_result(
                    rule="aws-access-token",
                    uri="src/secrets.py",
                    line=10,
                    snippet="AKIAIOSFODNN7EXAMPLE",
                )
            ],
        )
        results, total = _parse_sarif_results(str(sarif), target=tmp_path)
        assert total == 1
        assert len(results) == 1
        record = results[0]
        assert record["rule"] == "aws-access-token"
        assert record["file"] == "src/secrets.py"
        assert record["line"] == 10
        # Masked, not raw.
        assert "AKIAIOSFODNN7EXAMPLE" not in record["snippet_masked"]
        assert record["snippet_masked"].startswith("AKIA")

    def test_absolute_uri_normalized_to_relative(self, tmp_path: Path) -> None:
        """Verifies that absolute uri normalized to relative."""
        from checks.secrets import _parse_sarif_results

        # Gitleaks emits absolute paths when invoked with `--source <abs>`. The
        # parser must normalise these to project-relative strings so the modal
        # shows useful, short paths.
        abs_uri = str((tmp_path / "src" / "config.py").resolve())
        sarif = _write_sarif(tmp_path, [_gitleaks_result(uri=abs_uri)])
        results, _ = _parse_sarif_results(str(sarif), target=tmp_path)
        assert results[0]["file"] == "src/config.py"

    def test_uri_outside_target_kept_as_is(self, tmp_path: Path) -> None:
        """Verifies that uri outside target kept as is."""
        from checks.secrets import _parse_sarif_results

        # If the URI doesn't sit under target (unlikely but possible), keep it
        # verbatim rather than producing a confusing `../../...` path.
        sarif = _write_sarif(tmp_path, [_gitleaks_result(uri="/elsewhere/secret.py")])
        results, _ = _parse_sarif_results(str(sarif), target=tmp_path)
        assert results[0]["file"] == "/elsewhere/secret.py"

    def test_missing_line_number_is_none(self, tmp_path: Path) -> None:
        """Verifies that missing line number is none."""
        from checks.secrets import _parse_sarif_results

        sarif = _write_sarif(tmp_path, [_gitleaks_result(line=None)])
        results, _ = _parse_sarif_results(str(sarif), target=tmp_path)
        assert results[0]["line"] is None

    def test_results_capped_but_total_truthful(self, tmp_path: Path) -> None:
        """Verifies that results capped but total truthful."""
        from checks.secrets import RESULT_CAP, _parse_sarif_results

        many = [_gitleaks_result(line=i, uri=f"f{i}.py") for i in range(RESULT_CAP + 50)]
        sarif = _write_sarif(tmp_path, many)
        results, total = _parse_sarif_results(str(sarif), target=tmp_path)
        # Cap honored.
        assert len(results) == RESULT_CAP
        # Total still reflects the real number.
        assert total == RESULT_CAP + 50

    def test_multiple_runs_aggregated(self, tmp_path: Path) -> None:
        """Verifies that multiple runs aggregated."""
        from checks.secrets import _parse_sarif_results

        # Some SARIF producers emit multiple runs. Both must be walked.
        doc = {
            "version": "2.1.0",
            "runs": [
                {"results": [_gitleaks_result(uri="a.py")]},
                {"results": [_gitleaks_result(uri="b.py"), _gitleaks_result(uri="c.py")]},
            ],
        }
        out = tmp_path / "multi.sarif"
        out.write_text(json.dumps(doc), encoding="utf-8")
        results, total = _parse_sarif_results(str(out), target=tmp_path)
        assert total == 3
        assert {r["file"] for r in results} == {"a.py", "b.py", "c.py"}


# ---------------------------------------------------------------------------
# Integration of parser into Finding.evidence
# ---------------------------------------------------------------------------


class TestFindingEvidenceShape:
    """Tests for FindingEvidenceShape scenarios."""

    def test_evidence_carries_results_capped_and_total(self, tmp_path: Path) -> None:
        """When _gitleaks_scan finds leaks, the Finding.evidence dict should
        carry: sarif (str path), finding_count (legacy total), results (list,
        capped), total_results (true count), capped (bool).

        The real _gitleaks_scan calls subprocess; we don't drive it here. This
        test instead asserts the contract by feeding a SARIF through
        _parse_sarif_results and constructing the evidence dict the way the
        scan helper would.
        """
        from checks.secrets import _build_evidence_from_sarif

        sarif = _write_sarif(
            tmp_path,
            [_gitleaks_result(uri=f"f{i}.py", line=i) for i in range(3)],
        )
        evidence = _build_evidence_from_sarif(str(sarif), target=tmp_path)
        assert evidence["sarif"] == str(sarif)
        assert evidence["finding_count"] == 3
        assert evidence["total_results"] == 3
        assert evidence["capped"] is False
        assert isinstance(evidence["results"], list)
        assert len(evidence["results"]) == 3

    def test_evidence_capped_flag(self, tmp_path: Path) -> None:
        """Verifies that evidence capped flag."""
        from checks.secrets import RESULT_CAP, _build_evidence_from_sarif

        sarif = _write_sarif(
            tmp_path,
            [_gitleaks_result(uri=f"f{i}.py", line=i) for i in range(RESULT_CAP + 2)],
        )
        evidence = _build_evidence_from_sarif(str(sarif), target=tmp_path)
        assert evidence["capped"] is True
        assert evidence["finding_count"] == RESULT_CAP + 2
        assert evidence["total_results"] == RESULT_CAP + 2
        assert len(evidence["results"]) == RESULT_CAP


@pytest.fixture(autouse=True)
def _isolate_secrets_module() -> None:
    """Ensure each test re-imports from a clean state. The skill module isn't a
    proper package, so leftover sys.modules entries between test files can
    confuse imports during full-suite runs.
    """
    yield
    for mod in list(sys.modules):
        if mod.startswith(("checks", "lib")):
            sys.modules.pop(mod, None)
