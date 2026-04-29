"""Unit tests for fix_cycle — pure logic functions, no DB required."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from orch.daemon.fix_cycle import (
    _FIXABLE_STEP_TYPES,
    _build_fix_prompt_content,
    _build_qv_fix_prompt_content,
    _extract_mandatory_findings,
    _get_browser_findings,
)
from orch.db.models import RunStatus, StepType


def _make_step_run(
    run_number: int, status: RunStatus, report_file: str | None, error_message: str | None
) -> MagicMock:
    """Create a MagicMock StepRun with the given fields."""
    run = MagicMock()
    run.run_number = run_number
    run.status = status
    run.report_file = report_file
    run.error_message = error_message
    return run


def _make_step(report_file: str | None = None, report_content: str | None = None) -> MagicMock:
    """Create a MagicMock WorkflowStep with the given fields."""
    step = MagicMock()
    step.id = 1
    step.report_file = report_file
    step.report_content = report_content
    return step


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


def test_fixable_step_types_includes_browser_verification() -> None:
    # Browser verification is fixable: V(n) failures are real code defects,
    # not transient environment issues, so the daemon opens a fix cycle
    # instead of plain-retrying the same browser prompt.
    assert StepType.browser_verification in _FIXABLE_STEP_TYPES


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


# ---------------------------------------------------------------------------
# _get_browser_findings
# ---------------------------------------------------------------------------


def test_get_browser_findings_prefers_step_report_file(tmp_path: Path) -> None:
    """When step.report_file exists and file is readable, return that content."""
    step = _make_step(report_file="reports/v1.md")
    report_file = tmp_path / "reports" / "v1.md"
    report_file.parent.mkdir()
    report_file.write_text("## V1 FAILED\nSome browser failure")

    result = _get_browser_findings(MagicMock(), step, str(tmp_path))

    assert "V1 FAILED" in result
    assert "Some browser failure" in result


def test_get_browser_findings_falls_back_to_step_report_content(tmp_path: Path) -> None:
    """When step.report_file not set but step.report_content is, return that."""
    step = _make_step(report_file=None, report_content="## V2 FAILED\nDashboard not loading")
    db = MagicMock()

    result = _get_browser_findings(db, step, str(tmp_path))

    assert "V2 FAILED" in result
    assert "Dashboard not loading" in result


def test_get_browser_findings_newer_daemon_failure_prepended_from_report_file(
    tmp_path: Path,
) -> None:
    """When step.report_file is set from run 1 but run 2 has a newer daemon failure,
    the newer error is prepended as the leading context."""
    step = _make_step(report_file="reports/run1.md")
    report_file = tmp_path / "reports" / "run1.md"
    report_file.parent.mkdir(parents=True)
    report_file.write_text("## Original Report\nRun 1 failure: login button not found")

    latest_failed_run = _make_step_run(
        run_number=2,
        status=RunStatus.failed,
        report_file=None,
        error_message="browser env setup failed: dashboard container exited (1)",
    )
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = latest_failed_run

    result = _get_browser_findings(db, step, str(tmp_path))

    assert "Most Recent Failure (run 2)" in result
    assert "browser env setup failed: dashboard container exited (1)" in result
    assert "Original Browser Report" in result
    assert "Run 1 failure: login button not found" in result
    assert result.index("Most Recent Failure") < result.index("Original Browser Report")


def test_get_browser_findings_newer_daemon_failure_prepended_from_report_content(
    tmp_path: Path,
) -> None:
    """When step.report_content is set from run 1 but run 2 has a newer daemon failure,
    the newer error is prepended as the leading context."""
    step = _make_step(
        report_file=None,
        report_content="## Run 1 Content\nAgent reported failure: element not clickable",
    )

    latest_failed_run = _make_step_run(
        run_number=2,
        status=RunStatus.failed,
        report_file=None,
        error_message="container crashed: browser process OOM",
    )
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = latest_failed_run

    result = _get_browser_findings(db, step, str(tmp_path))

    assert "Most Recent Failure (run 2)" in result
    assert "container crashed: browser process OOM" in result
    assert "Original Browser Report" in result
    assert "Agent reported failure: element not clickable" in result


def test_get_browser_findings_no_prepend_when_latest_has_report_file(tmp_path: Path) -> None:
    """When the latest failed StepRun also has report_file set (agent-reported),
    no prepending occurs — original behavior preserved."""
    step = _make_step(report_file="reports/v1.md")
    report_file = tmp_path / "reports" / "v1.md"
    report_file.parent.mkdir(parents=True)
    report_file.write_text("## V1 FAILED\nOriginal agent failure")

    latest_failed_run = _make_step_run(
        run_number=2,
        status=RunStatus.failed,
        report_file="reports/v2.md",
        error_message="Should not appear because run 2 has its own report_file",
    )
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = latest_failed_run

    result = _get_browser_findings(db, step, str(tmp_path))

    assert "Most Recent Failure" not in result
    assert "Original agent failure" in result
    assert "Should not appear" not in result


def test_get_browser_findings_last_resort_error_message(tmp_path: Path) -> None:
    """When step.report_file and step.report_content are both None,
    fall back to the latest failed StepRun's error_message."""
    step = _make_step(report_file=None, report_content=None)

    latest_failed_run = _make_step_run(
        run_number=1,
        status=RunStatus.failed,
        report_file=None,
        error_message="Last resort error: step timed out",
    )
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = latest_failed_run

    result = _get_browser_findings(db, step, str(tmp_path))

    assert "Last resort error: step timed out" in result


def test_get_browser_findings_no_report_available(tmp_path: Path) -> None:
    """When everything is None/empty, return the no-findings message."""
    step = _make_step(report_file=None, report_content=None)
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    result = _get_browser_findings(db, step, str(tmp_path))

    assert "No browser report available" in result


def test_get_browser_findings_truncation_at_8000_chars(tmp_path: Path) -> None:
    """Content is truncated at 8000 characters."""
    long_content = "## V1 FAILED\n" + "x" * 10000
    step = _make_step(report_content=long_content)

    result = _get_browser_findings(MagicMock(), step, str(tmp_path))

    assert len(result) <= 8000 + 50  # 8000 + "...(report truncated...)" overhead
    assert "...(report truncated for prompt length)..." in result


def test_i00050_get_browser_findings_uses_latest_run_error(tmp_path: Path) -> None:
    """I-00050: when latest run has report_file=None but error_message set
    (daemon-detected failure), its error must lead the findings string.

    This reproduces the F-00067 S17 bug where fix-cycle prompt 2 still showed
    run-1's ENV_DATA_MISSING report while runs 2-4 were failing with a
    dashboard container crash.
    """
    step = _make_step(report_file="reports/v1.md", report_content=None)
    report_file = tmp_path / "reports" / "v1.md"
    report_file.parent.mkdir(parents=True)
    report_file.write_text("## V1 FAIL\n| V1 | FAIL | expected |\n...")

    latest_failed_run = _make_step_run(
        run_number=2,
        status=RunStatus.failed,
        report_file=None,
        error_message="browser env setup failed: e2e-dashboard-1 exited (1)",
    )
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = latest_failed_run

    result = _get_browser_findings(db, step, str(tmp_path))

    assert "browser env setup failed" in result
    assert "e2e-dashboard-1 exited (1)" in result
    assert result.startswith("## ⚠️ Most Recent Failure (run 2)")
    assert "V1 FAIL" in result
    assert result.index("browser env setup failed") < result.index("V1 FAIL")


def test_i00050_get_browser_findings_unchanged_when_latest_run_has_report(tmp_path: Path) -> None:
    """I-00050 AC3: when the latest failed StepRun also has report_file set
    (agent-reported, not daemon-detected), no prepend occurs — the original
    report content is returned unchanged."""
    step = _make_step(report_file="reports/v1.md", report_content=None)
    report_file = tmp_path / "reports" / "v1.md"
    report_file.parent.mkdir(parents=True)
    report_file.write_text("## V1 FAIL original\n| V1 | FAIL | original content |")

    latest_failed_run = _make_step_run(
        run_number=2,
        status=RunStatus.failed,
        report_file="reports/v2.md",
        error_message="Should not appear because run 2 has its own report_file",
    )
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = latest_failed_run

    result = _get_browser_findings(db, step, str(tmp_path))

    assert "Most Recent Failure" not in result
    assert "## V1 FAIL original" in result
    assert "Should not appear" not in result
