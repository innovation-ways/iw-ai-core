"""Unit tests for fix_cycle — pure logic functions, no DB required."""

from __future__ import annotations

from orch.daemon.fix_cycle import (
    _FIXABLE_STEP_TYPES,
    _build_fix_prompt_content,
    _build_qv_fix_prompt_content,
    _extract_mandatory_findings,
)
from orch.db.models import StepType

# ---------------------------------------------------------------------------
# _FIXABLE_STEP_TYPES
# ---------------------------------------------------------------------------


def test_fixable_step_types_includes_code_review() -> None:
    assert StepType.code_review in _FIXABLE_STEP_TYPES


def test_fixable_step_types_includes_code_review_final() -> None:
    assert StepType.code_review_final in _FIXABLE_STEP_TYPES


def test_fixable_step_types_excludes_implementation() -> None:
    assert StepType.implementation not in _FIXABLE_STEP_TYPES


def test_fixable_step_types_includes_quality_validation() -> None:
    assert StepType.quality_validation in _FIXABLE_STEP_TYPES


# ---------------------------------------------------------------------------
# _extract_mandatory_findings
# ---------------------------------------------------------------------------


def test_extract_findings_from_json_zero_mandatory() -> None:
    content = '{"verdict": "fail", "mandatory_fix_count": 0, "findings": []}'
    assert _extract_mandatory_findings(content) == ""


def test_extract_findings_from_markdown_headings() -> None:
    content = (
        "## Findings\n\n"
        "### Finding 1: CRITICAL -- security\n"
        "SQL injection in login.py line 42\n\n"
        "### Finding 2: LOW -- style\n"
        "Missing docstring\n"
    )
    result = _extract_mandatory_findings(content)
    assert "CRITICAL" in result
    assert "SQL injection" in result
    # LOW findings should NOT be extracted
    assert "Missing docstring" not in result


def test_extract_findings_from_high_severity() -> None:
    content = (
        "### Finding 1: HIGH -- conventions\n"
        "Wrong naming pattern in utils.py\n\n"
        "### Finding 2: MEDIUM (fixable) -- testing\n"
        "Missing test for edge case\n"
    )
    result = _extract_mandatory_findings(content)
    assert "HIGH" in result
    assert "MEDIUM (fixable)" in result


def test_extract_findings_empty_content() -> None:
    assert _extract_mandatory_findings("") == ""


def test_extract_findings_no_mandatory_in_content() -> None:
    content = "### Finding 1: LOW -- style\nMinor formatting issue\n"
    # No CRITICAL/HIGH/MEDIUM-fixable headings → empty
    assert _extract_mandatory_findings(content) == ""


def test_extract_findings_verdict_fail_no_headings() -> None:
    """When verdict is fail but no parseable headings, return truncated content."""
    content = '{"verdict": "fail", "mandatory_fix_count": 2}\nSome raw findings text here.'
    result = _extract_mandatory_findings(content)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# _build_fix_prompt_content
# ---------------------------------------------------------------------------


def test_build_fix_prompt_includes_findings() -> None:
    prompt = _build_fix_prompt_content(
        "CR-00002",
        "S06",
        1,
        "### Finding 1: CRITICAL\nBug here",
        5,
    )
    assert "CR-00002" in prompt
    assert "S06" in prompt
    assert "Fix Cycle 1/5" in prompt
    assert "CRITICAL" in prompt
    assert "Bug here" in prompt


def test_build_fix_prompt_escalation_on_last_cycle() -> None:
    prompt = _build_fix_prompt_content(
        "F-00001",
        "S03",
        5,
        "some findings",
        5,
    )
    assert "ESCALATION" in prompt
    assert "FINAL fix cycle" in prompt


def test_build_fix_prompt_no_escalation_on_early_cycle() -> None:
    prompt = _build_fix_prompt_content(
        "F-00001",
        "S03",
        2,
        "some findings",
        5,
    )
    assert "ESCALATION" not in prompt


def test_build_fix_prompt_no_iw_cli_instructions() -> None:
    """Fix agents should NOT call iw step-done/step-fail."""
    prompt = _build_fix_prompt_content(
        "CR-00002",
        "S06",
        1,
        "findings",
        5,
    )
    assert "Do NOT call" in prompt
    assert "iw step-done" in prompt


# ---------------------------------------------------------------------------
# _build_qv_fix_prompt_content
# ---------------------------------------------------------------------------


def test_qv_fix_prompt_includes_gate_command() -> None:
    prompt = _build_qv_fix_prompt_content(
        "CR-00002",
        "S09",
        1,
        "format errors here",
        5,
        "ruff format --check orch/ dashboard/ tests/",
    )
    assert "QV Fix Cycle 1/5" in prompt
    assert "ruff format --check" in prompt
    assert "format errors here" in prompt
    assert "Do NOT call" in prompt


def test_qv_fix_prompt_escalation_on_last_cycle() -> None:
    prompt = _build_qv_fix_prompt_content(
        "CR-00002", "S10", 5, "mypy errors", 5, "mypy orch/ dashboard/"
    )
    assert "ESCALATION" in prompt
    assert "FINAL fix cycle" in prompt


def test_qv_fix_prompt_no_gate_command() -> None:
    """Works even if gate_command is empty."""
    prompt = _build_qv_fix_prompt_content("CR-00002", "S09", 1, "errors", 5, "")
    assert "QV Fix Cycle 1/5" in prompt
    assert "Gate Command" not in prompt
