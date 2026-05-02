"""RED tests for orch/self_assess.py — self_assess step type helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orch.self_assess import (  # noqa: F401  # used via isinstance() checks in test methods
    SelfAssessmentData,
    SelfAssessParseError,
    findings_path_for,
    is_self_assess_step,
    is_soft_step_failure,
    parse_findings_json,
)


class TestParseFindingsJsonHappyPath:
    """parse_findings_json happy path with complete fixture string."""

    def test_parses_complete_valid_json(self) -> None:
        """A fully-populated findings JSON is parsed correctly."""
        fixture = {
            "narrative_md": "The agent ran successfully.",
            "coverage_notes": "All logs were read fully.",
            "bottom_line": "2 findings.",
            "findings": [
                {
                    "severity": "HIGH",
                    "class": "TestFlakiness",
                    "target": "iw-ai-core",
                    "title": "Flaky test in orch/tests/",
                    "recommendation": "Add retries to the test.",
                    "paste_prompt": "/iw-new-incident title=Flaky test...",
                    "evidence": ["ai-dev/work/F-00078/logs/f-00078_s01_run1.log:124"],
                    "effort": "medium",
                },
                {
                    "severity": "MED",
                    "class": "PromptGap",
                    "target": "project",
                    "title": "Missing error handling in project/foo.py",
                    "recommendation": "Add try/except around the call.",
                    "paste_prompt": "/iw-new-cr title=Error handling...",
                    "evidence": [],
                    "effort": None,
                },
            ],
        }
        data = parse_findings_json(json.dumps(fixture))

        assert isinstance(data, SelfAssessmentData)
        assert data.narrative_md == "The agent ran successfully."
        assert data.coverage_notes == "All logs were read fully."
        assert data.bottom_line == "2 findings."
        assert len(data.findings) == 2

        f0 = data.findings[0]
        assert f0.severity == "HIGH"
        assert f0.clazz == "TestFlakiness"
        assert f0.target == "iw-ai-core"
        assert f0.title == "Flaky test in orch/tests/"
        assert f0.recommendation == "Add retries to the test."
        assert f0.paste_prompt == "/iw-new-incident title=Flaky test..."
        assert f0.evidence == ["ai-dev/work/F-00078/logs/f-00078_s01_run1.log:124"]
        assert f0.effort == "medium"

        f1 = data.findings[1]
        assert f1.severity == "MED"
        assert f1.clazz == "PromptGap"
        assert f1.target == "project"
        assert f1.evidence == []
        assert f1.effort is None

    def test_minimal_valid_json(self) -> None:
        """JSON with only required fields parses successfully."""
        fixture = {
            "narrative_md": None,
            "coverage_notes": None,
            "bottom_line": None,
            "findings": [],
        }
        data = parse_findings_json(json.dumps(fixture))

        assert isinstance(data, SelfAssessmentData)
        assert data.narrative_md is None
        assert data.findings == []
        assert data.coverage_notes is None
        assert data.bottom_line is None


class TestParseFindingsJsonRejectsInvalid:
    """parse_findings_json rejects unknown target value and malformed JSON."""

    def test_rejects_unknown_target(self) -> None:
        """A finding with target='unknown' raises SelfAssessParseError."""
        fixture = {
            "narrative_md": None,
            "coverage_notes": None,
            "bottom_line": None,
            "findings": [
                {
                    "severity": "HIGH",
                    "class": "Foo",
                    "target": "unknown-project",  # invalid
                    "title": "Bad target",
                    "recommendation": "Fix it.",
                    "paste_prompt": "/iw-new-incident title=Foo",
                    "evidence": [],
                    "effort": None,
                }
            ],
        }
        with pytest.raises(SelfAssessParseError, match="target"):
            parse_findings_json(json.dumps(fixture))

    def test_rejects_missing_required_finding_field(self) -> None:
        """A finding missing 'severity' raises SelfAssessParseError."""
        fixture = {
            "narrative_md": None,
            "coverage_notes": None,
            "bottom_line": None,
            "findings": [
                {
                    # missing severity
                    "class": "Foo",
                    "target": "iw-ai-core",
                    "title": "Bad finding",
                    "recommendation": "Fix it.",
                    "paste_prompt": "/iw-new-incident",
                    "evidence": [],
                    "effort": None,
                }
            ],
        }
        with pytest.raises(SelfAssessParseError, match="severity"):
            parse_findings_json(json.dumps(fixture))

    def test_rejects_malformed_json(self) -> None:
        """Non-JSON input raises SelfAssessParseError."""
        with pytest.raises(SelfAssessParseError, match="JSON"):
            parse_findings_json("not valid json{{{")

    def test_rejects_empty_string(self) -> None:
        """Empty string raises SelfAssessParseError."""
        with pytest.raises(SelfAssessParseError, match="JSON"):
            parse_findings_json("")

    def test_tolerates_unknown_toplevel_fields(self) -> None:
        """Extra toplevel fields are ignored without error."""
        fixture = {
            "narrative_md": "All good.",
            "coverage_notes": None,
            "bottom_line": None,
            "findings": [],
            "unknown_field": "should be ignored",
            "another_unknown": 123,
        }
        data = parse_findings_json(json.dumps(fixture))
        assert data.narrative_md == "All good."


class TestIsSoftStepFailure:
    """is_soft_step_failure returns True for self_assess+failed, False otherwise."""

    def test_self_assess_failed_is_soft(self) -> None:
        """self_assess step with failed status is a soft-step failure."""
        assert is_soft_step_failure("self_assess", "failed") is True

    def test_self_assess_completed_not_soft(self) -> None:
        """self_assess step with completed status is NOT a soft-step failure."""
        assert is_soft_step_failure("self_assess", "completed") is False

    def test_self_assess_timeout_is_soft(self) -> None:
        """self_assess step with timeout status is a soft-step failure."""
        assert is_soft_step_failure("self_assess", "timeout") is True

    def test_self_assess_killed_is_soft(self) -> None:
        """self_assess step with killed status is a soft-step failure."""
        assert is_soft_step_failure("self_assess", "killed") is True

    def test_self_assess_stalled_is_soft(self) -> None:
        """self_assess step with stalled status is a soft-step failure."""
        assert is_soft_step_failure("self_assess", "stalled") is True

    def test_implementation_failed_not_soft(self) -> None:
        """implementation step with failed status is NOT a soft-step failure."""
        assert is_soft_step_failure("implementation", "failed") is False

    def test_code_review_failed_not_soft(self) -> None:
        """code_review step with failed status is NOT a soft-step failure."""
        assert is_soft_step_failure("code_review", "failed") is False

    def test_unknown_step_type_not_soft(self) -> None:
        """Unknown step types are never soft-step failures."""
        assert is_soft_step_failure("unknown_type", "failed") is False

    def test_self_assess_skipped_not_soft(self) -> None:
        """self_assess step with skipped status is NOT a soft-step failure."""
        assert is_soft_step_failure("self_assess", "skipped") is False

    def test_self_assess_with_enum_status(self) -> None:
        """Works when run_status is passed as a StepStatus enum value string."""
        assert is_soft_step_failure("self_assess", "failed") is True

    def test_self_assess_with_enum_object(self) -> None:
        """Works when run_status is passed as a StepStatus enum object."""
        from orch.db.models import StepStatus

        assert is_soft_step_failure("self_assess", StepStatus.failed) is True
        assert is_soft_step_failure("self_assess", StepStatus.completed) is False

    def test_self_assess_with_step_status_enum(self) -> None:
        """Works when both arguments are enum values (StepType and StepStatus)."""
        from orch.db.models import StepStatus, StepType

        assert is_soft_step_failure(StepType.self_assess, StepStatus.failed) is True
        assert is_soft_step_failure(StepType.self_assess, StepStatus.completed) is False
        assert is_soft_step_failure(StepType.self_assess, StepStatus.skipped) is False


class TestFindingsPathFor:
    """findings_path_for derives the sidecar JSON path from the report path."""

    def test_replaces_report_md_suffix(self) -> None:
        """Given a report path ending in _report.md, returns the _findings.json path."""
        report = Path("ai-dev/work/F-00078/reports/F-00078_S03_report.md")
        assert findings_path_for(report) == Path(
            "ai-dev/work/F-00078/reports/F-00078_S03_findings.json"
        )

    def test_replaces_plain_md_suffix(self) -> None:
        """Given a report path ending in .md (no _report), replaces with _findings.json."""
        report = Path("ai-dev/work/F-00078/reports/F-00078_S03.md")
        assert findings_path_for(report) == Path(
            "ai-dev/work/F-00078/reports/F-00078_S03_findings.json"
        )

    def test_string_input(self) -> None:
        """Accepts a string and returns a Path."""
        report = "ai-dev/work/F-00078/reports/F-00078_S03_Backend_report.md"
        result = findings_path_for(report)
        assert isinstance(result, Path)
        assert result == Path("ai-dev/work/F-00078/reports/F-00078_S03_Backend_findings.json")

    def test_with_agent_label_report(self) -> None:
        """Agent-label-style report paths are handled correctly."""
        report = Path("ai-dev/work/F-00078/reports/F-00078_S03_Backend_report.md")
        assert findings_path_for(report) == Path(
            "ai-dev/work/F-00078/reports/F-00078_S03_Backend_findings.json"
        )

    def test_nested_report_path(self) -> None:
        """Nested report paths are handled correctly."""
        report = Path("work/innoforge/ai-dev/work/F-00078/reports/F-00078_S03_Template_report.md")
        assert findings_path_for(report) == Path(
            "work/innoforge/ai-dev/work/F-00078/reports/F-00078_S03_Template_findings.json"
        )


class TestFindingsPathForCanonical:
    """Invariant 3 / AC: canonical sidecar path derivation."""

    def test_canonical_sidecar_path(self) -> None:
        """F-00001_self_assess_report.md → F-00001_self_assess_findings.json."""
        report = Path("ai-dev/work/F-00001/reports/F-00001_self_assess_report.md")
        assert findings_path_for(report) == Path(
            "ai-dev/work/F-00001/reports/F-00001_self_assess_findings.json"
        )

    def test_findings_path_for_canonical_form(self) -> None:
        """Explicit test for the canonical invariant in the coverage matrix."""
        report = Path("/x/y/F-00001_self_assess_report.md")
        assert findings_path_for(report) == Path("/x/y/F-00001_self_assess_findings.json")

    def test_no_report_suffix(self) -> None:
        """Path without _report.md still derives correctly."""
        report = Path("work/F-00001/reports/F-00001.md")
        assert findings_path_for(report) == Path("work/F-00001/reports/F-00001_findings.json")

    def test_findings_path_for_md_without_report_suffix(self) -> None:
        """An .md file without _report gets _findings.json replacing the extension."""
        report = Path("work/F-00001/F-00001_summary.md")
        result = findings_path_for(report)
        assert result == Path("work/F-00001/F-00001_summary_findings.json")


class TestIsSelfAssessStep:
    """is_self_assess_step narrows step types to self_assess only."""

    def test_string_self_assess(self) -> None:
        assert is_self_assess_step("self_assess") is True

    def test_string_self_assess_spelled_out(self) -> None:
        assert is_self_assess_step("StepType.self_assess") is True

    def test_implementation_string(self) -> None:
        assert is_self_assess_step("implementation") is False

    def test_code_review_string(self) -> None:
        assert is_self_assess_step("code_review") is False

    def test_empty_string(self) -> None:
        assert is_self_assess_step("") is False

    def test_none_input(self) -> None:
        assert is_self_assess_step(None) is False
