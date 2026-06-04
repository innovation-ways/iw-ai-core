"""Unit tests for fix_cycle — pure logic functions, no DB required."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from orch.daemon.fix_cycle import (
    _FIXABLE_STEP_TYPES,
    _SPEC_MISMATCH_PREFIX,
    _build_browser_fix_prompt_content,
    _build_design_doc_block,
    _build_fix_launch_argv,
    _build_fix_prompt_content,
    _build_qv_fix_prompt_content,
    _build_scope_block,
    _extract_mandatory_findings,
    _extract_step_section,
    _find_design_doc,
    _get_browser_findings,
    _try_auto_amend_after_escalation,
    is_spec_mismatch_failure,
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
    """Verifies that fixable step types includes code review."""
    assert StepType.code_review in _FIXABLE_STEP_TYPES


def test_fixable_step_types_includes_code_review_final() -> None:
    """Verifies that fixable step types includes code review final."""
    assert StepType.code_review_final in _FIXABLE_STEP_TYPES


def test_fixable_step_types_excludes_implementation() -> None:
    """Verifies that fixable step types excludes implementation."""
    assert StepType.implementation not in _FIXABLE_STEP_TYPES


def test_fixable_step_types_includes_quality_validation() -> None:
    """Verifies that fixable step types includes quality validation."""
    assert StepType.quality_validation in _FIXABLE_STEP_TYPES


def test_fixable_step_types_includes_browser_verification() -> None:
    """Verifies that fixable step types includes browser verification."""
    # Browser verification is fixable: V(n) failures are real code defects,
    # not transient environment issues, so the daemon opens a fix cycle
    # instead of plain-retrying the same browser prompt.
    assert StepType.browser_verification in _FIXABLE_STEP_TYPES


# ---------------------------------------------------------------------------
# _extract_mandatory_findings
# ---------------------------------------------------------------------------


def test_extract_findings_from_json_zero_mandatory() -> None:
    """Verifies that extract findings from json zero mandatory."""
    content = '{"verdict": "fail", "mandatory_fix_count": 0, "findings": []}'
    assert _extract_mandatory_findings(content) == ""


def test_extract_findings_from_markdown_headings() -> None:
    """Verifies that extract findings from markdown headings."""
    content = (
        "## Findings\n\n"
        "### Finding 1: CRITICAL -- security\n"
        "SQL injection in login.py line 42\n\n"
        "### Finding 2: LOW -- style\n"
        "Missing docstring\n"
    )
    result = _extract_mandatory_findings(content)
    assert "CRITICAL" in result
    # LOW findings should NOT be extracted
    assert "Missing docstring" not in result


def test_extract_findings_from_high_severity() -> None:
    """Verifies that extract findings from high severity."""
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
    """Verifies that extract findings empty content."""
    assert _extract_mandatory_findings("") == ""


def test_extract_findings_no_mandatory_in_content() -> None:
    """Verifies that extract findings no mandatory in content."""
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
    """Verifies that build fix prompt includes findings."""
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
    """Verifies that build fix prompt escalation on last cycle."""
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
    """Verifies that build fix prompt no escalation on early cycle."""
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


def test_build_fix_prompt_includes_post_edit_format_lint_gate() -> None:
    """CR-00082 root cause #3: fix prompt must mandate make format-check + make lint
    before exit so cycle N+1 doesn't re-break the gate cycle N fixed.
    """
    prompt = _build_fix_prompt_content("CR-00002", "S06", 1, "findings", 5)
    # A regression that drops the section entirely would make the prompt very short.
    assert len(prompt) > 400
    assert "Post-Edit Gate" in prompt
    assert "make format-check" in prompt
    assert "make lint" in prompt


# ---------------------------------------------------------------------------
# _build_scope_block (CR-00082 root cause #2: implicit-allow paths must surface)
# ---------------------------------------------------------------------------


def test_build_scope_block_lists_implicit_allows_when_item_id_passed() -> None:
    """The rendered scope block must mention ai-dev/work/<id>/** etc so review and
    fix agents do not flag those paths as scope creep. Reproduces the failure mode
    that drove CR-00082 S04 to 5 fix cycles without convergence.
    """
    block = _build_scope_block(["tests/visual/**", "Makefile"], item_id="CR-00082")
    # A regression that drops the implicit-block would make the output much shorter.
    assert len(block) > 200
    assert "tests/visual/**" in block
    assert "ai-dev/active/CR-00082/**" in block
    assert "ai-dev/archive/CR-00082/**" in block
    assert "ai-dev/work/CR-00082/**" in block
    assert "allowed by daemon convention" in block


def test_build_scope_block_omits_implicit_block_when_no_item_id() -> None:
    """Backward compatibility: callers that don't pass item_id (legacy tests) still
    get the plain manifest-only scope block — no implicit-allow section."""
    block = _build_scope_block(["tests/visual/**"])
    assert "tests/visual/**" in block
    assert "ai-dev/work/" not in block
    assert "allowed by daemon convention" not in block


def test_build_scope_block_returns_empty_when_no_allowed_paths() -> None:
    """Empty allowed_paths returns an empty string (scope enforcement disabled)."""
    block = _build_scope_block([])
    assert block == ""
    # When item_id is provided but allowed is empty, still return ""
    block2 = _build_scope_block([], item_id="CR-00082")
    assert block2 == ""


# ---------------------------------------------------------------------------
# _build_qv_fix_prompt_content
# ---------------------------------------------------------------------------


def test_qv_fix_prompt_includes_gate_command() -> None:
    """Verifies that qv fix prompt includes gate command."""
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
    """Verifies that qv fix prompt escalation on last cycle."""
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


def test_qv_fix_prompt_includes_cross_gate_check() -> None:
    """QV-fix prompts must remind the agent to also run make format-check / make lint
    before exit, even when the failing gate is something else (e.g. typecheck or unit
    tests). Diagnosed in CR-00082 S04 where non-format edits silently broke format-check.
    """
    prompt = _build_qv_fix_prompt_content(
        "CR-00002", "S10", 1, "mypy errors", 5, "mypy orch/ dashboard/"
    )
    # A regression that drops the constraint section would make the prompt very short.
    assert len(prompt) > 450
    assert "make format-check" in prompt
    assert "make lint" in prompt


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


# ---------------------------------------------------------------------------
# Design-doc discovery + extraction (anti-drift fix prompts)
# ---------------------------------------------------------------------------


def _seed_design_doc(tmp_path: Path, item_id: str, body: str) -> Path:
    """Write a design doc at the conventional location and return its path."""
    item_dir = tmp_path / "ai-dev" / "active" / item_id
    item_dir.mkdir(parents=True)
    doc_path = item_dir / f"{item_id}_Issue_Design.md"
    doc_path.write_text(body, encoding="utf-8")
    return doc_path


def test_find_design_doc_returns_path_when_present(tmp_path: Path) -> None:
    """Verifies that find design doc returns path when present."""
    expected = _seed_design_doc(tmp_path, "I-00099", "# I-00099\n")
    found = _find_design_doc(str(tmp_path), "I-00099")
    assert found == expected


def test_find_design_doc_returns_none_when_dir_missing(tmp_path: Path) -> None:
    """Verifies that find design doc returns none when dir missing."""
    assert _find_design_doc(str(tmp_path), "I-99999") is None


def test_find_design_doc_returns_none_when_no_design_file(tmp_path: Path) -> None:
    """Verifies that find design doc returns none when no design file."""
    item_dir = tmp_path / "ai-dev" / "active" / "I-00099"
    item_dir.mkdir(parents=True)
    (item_dir / "notes.md").write_text("not a design doc")
    assert _find_design_doc(str(tmp_path), "I-00099") is None


def test_extract_step_section_matches_detailed_fix_specification() -> None:
    """Verifies that extract step section matches detailed fix specification."""
    text = (
        "# Title\n\n"
        "## Detailed Fix Specification for S01\n\n"
        "Step body for S01.\n"
        "More text.\n\n"
        "## Detailed Fix Specification for S02\n\n"
        "Step body for S02.\n"
    )
    slice_text = _extract_step_section(text, "S01")
    assert slice_text is not None
    assert "Step body for S01" in slice_text
    assert "Step body for S02" not in slice_text


def test_extract_step_section_matches_step_id_heading() -> None:
    """Verifies that extract step section matches step id heading."""
    text = "## S03 — Tests\n\nWrite tests.\n\n## S04\n\nReview.\n"
    slice_text = _extract_step_section(text, "S03")
    assert slice_text is not None
    assert "Write tests" in slice_text
    assert "Review" not in slice_text


def test_extract_step_section_returns_none_on_no_match() -> None:
    """When no step-specific heading is found, return None."""
    text = "# Title\n\n## Some other section\n\nIrrelevant.\n"
    result = _extract_step_section(text, "S01")
    assert result is None


def test_extract_step_section_handles_empty_inputs() -> None:
    """Verifies that extract step section handles empty inputs."""
    assert _extract_step_section("", "S01") is None
    assert _extract_step_section("text", "") is None


def test_build_design_doc_block_returns_empty_when_doc_missing(tmp_path: Path) -> None:
    """Verifies that build design doc block returns empty when doc missing."""
    assert _build_design_doc_block(str(tmp_path), "I-99999", "S01") == ""


def test_build_design_doc_block_includes_path_and_slice(tmp_path: Path) -> None:
    """Verifies that build design doc block includes path and slice."""
    body = "# Title\n\n## Detailed Fix Specification for S01\n\nSpec: do X then Y.\n"
    doc_path = _seed_design_doc(tmp_path, "I-00099", body)
    block = _build_design_doc_block(str(tmp_path), "I-00099", "S01")
    assert "Design Doc — Source of Truth" in block
    assert str(doc_path) in block
    assert "Step-specific slice" in block
    assert "Spec: do X then Y" in block


def test_build_design_doc_block_no_slice_when_step_section_absent(tmp_path: Path) -> None:
    """Doc found but no S07 heading — block still names the path, no slice."""
    body = "# Title\n\n## Overview\n\nGeneral info.\n"
    _seed_design_doc(tmp_path, "I-00099", body)
    block = _build_design_doc_block(str(tmp_path), "I-00099", "S07")
    assert "Design Doc — Source of Truth" in block
    assert "Step-specific slice" not in block


# ---------------------------------------------------------------------------
# Anti-drift copy in fix prompts (hypothesis framing + escalation tightening)
# ---------------------------------------------------------------------------


def test_build_fix_prompt_includes_design_doc_block_when_provided() -> None:
    """Verifies that build fix prompt includes design doc block when provided."""
    block = "## Design Doc — Source of Truth (READ FIRST)\n\nPath: /tmp/x.md\n"
    prompt = _build_fix_prompt_content("CR-00002", "S06", 1, "findings", 5, design_doc_block=block)
    assert "Design Doc — Source of Truth" in prompt
    assert "Diagnostic Hypothesis" in prompt
    assert "Pre-fix Procedure" in prompt
    assert "spec wins" in prompt


def test_build_fix_prompt_omits_design_section_when_empty() -> None:
    """Legacy items without a design doc still produce a usable prompt."""
    prompt = _build_fix_prompt_content("CR-00002", "S06", 1, "findings", 5)
    assert "Design Doc — Source of Truth" not in prompt
    # Hypothesis framing always present
    assert "Diagnostic Hypothesis" in prompt


def test_build_fix_prompt_escalation_prefers_honest_escalation() -> None:
    """Verifies that build fix prompt escalation prefers honest escalation."""
    prompt = _build_fix_prompt_content("F-00001", "S03", 5, "findings", 5)
    assert "ESCALATION" in prompt
    assert "PREFER honest escalation" in prompt
    assert "Hail-Mary" in prompt


def test_build_qv_fix_prompt_includes_design_doc_block_when_provided() -> None:
    """Verifies that build qv fix prompt includes design doc block when provided."""
    block = "## Design Doc — Source of Truth (READ FIRST)\n\nPath: /tmp/x.md\n"
    prompt = _build_qv_fix_prompt_content(
        "CR-00002", "S09", 1, "errors", 5, "make lint", design_doc_block=block
    )
    assert "Design Doc — Source of Truth" in prompt
    assert "Diagnostic Hypothesis" in prompt
    assert "Pre-fix Procedure" in prompt
    assert "spec wins" in prompt


def test_build_qv_fix_prompt_escalation_prefers_honest_escalation() -> None:
    """Verifies that build qv fix prompt escalation prefers honest escalation."""
    prompt = _build_qv_fix_prompt_content("CR-00002", "S09", 5, "errors", 5, "make lint")
    assert "PREFER honest escalation" in prompt
    assert "Hail-Mary" in prompt


def test_build_browser_fix_prompt_includes_design_doc_block_when_provided() -> None:
    """Verifies that build browser fix prompt includes design doc block when provided."""
    block = "## Design Doc — Source of Truth (READ FIRST)\n\nPath: /tmp/x.md\n"
    prompt = _build_browser_fix_prompt_content(
        item_id="I-00099",
        step_id="S11",
        cycle_number=1,
        findings="V1 failed",
        max_cycles=3,
        design_doc_block=block,
    )
    assert "Design Doc — Source of Truth" in prompt
    assert "Diagnostic Hypothesis" in prompt
    assert "Pre-fix Procedure" in prompt
    assert "spec wins" in prompt


def test_build_browser_fix_prompt_escalation_prefers_honest_escalation() -> None:
    """Verifies that build browser fix prompt escalation prefers honest escalation."""
    prompt = _build_browser_fix_prompt_content(
        item_id="I-00099",
        step_id="S11",
        cycle_number=3,
        findings="V1 failed",
        max_cycles=3,
    )
    assert "PREFER honest escalation" in prompt
    assert "Hail-Mary" in prompt


# ---------------------------------------------------------------------------
# SPEC_MISMATCH prefix detection (unit-level, no DB)
# ---------------------------------------------------------------------------


def test_spec_mismatch_prefix_constant_is_correct() -> None:
    """The prefix constant must match the literal string the qv-browser agent emits."""
    assert _SPEC_MISMATCH_PREFIX == "SPEC_MISMATCH:"


def test_is_spec_mismatch_failure_returns_true_for_exact_prefix() -> None:
    """Verifies that is spec mismatch failure returns true for exact prefix."""
    reason = (
        "SPEC_MISMATCH: V4 expects disabled toggle on Plan tab but "
        "design doc scopes that to non-executing states"
    )
    assert is_spec_mismatch_failure(reason) is True


def test_is_spec_mismatch_failure_returns_true_with_leading_whitespace() -> None:
    """Verifies that is spec mismatch failure returns true with leading whitespace."""
    reason = "  SPEC_MISMATCH: V3 verifies a feature the design doc says is out of scope"
    assert is_spec_mismatch_failure(reason) is True


def test_is_spec_mismatch_failure_returns_false_for_env_data_missing() -> None:
    """Verifies that is spec mismatch failure returns false for env data missing."""
    reason = "ENV_DATA_MISSING: V1 expects F-00055 step_runs"
    assert is_spec_mismatch_failure(reason) is False


def test_is_spec_mismatch_failure_returns_false_for_code_defect() -> None:
    """Verifies that is spec mismatch failure returns false for code defect."""
    reason = "V1 returned 500 on /tab/execution-report"
    assert is_spec_mismatch_failure(reason) is False


def test_is_spec_mismatch_failure_returns_false_for_none() -> None:
    """Verifies that is spec mismatch failure returns false for none."""
    assert is_spec_mismatch_failure(None) is False


def test_is_spec_mismatch_failure_returns_false_for_empty_string() -> None:
    """Verifies that is spec mismatch failure returns false for empty string."""
    assert is_spec_mismatch_failure("") is False


def test_is_spec_mismatch_failure_case_insensitive() -> None:
    """The prefix check is case-insensitive to tolerate agent variation."""
    assert is_spec_mismatch_failure("spec_mismatch: lowercase variant") is True


# ---------------------------------------------------------------------------
# _build_fix_launch_argv  (I-00074: opencode fix cycle never launched)
# ---------------------------------------------------------------------------


def test_build_fix_launch_argv_opencode_wraps_in_script_pty() -> None:
    """Verifies that build fix launch argv opencode wraps in script pty."""
    inner = (
        'timeout 600 opencode run "$(cat /wt/.tmp/I-00074_S06_fix1.prompt)" '
        "--model anthropic/claude-x --dangerously-skip-permissions"
    )
    assert _build_fix_launch_argv("opencode", inner) == ["script", "-qec", inner, "/dev/null"]


def test_build_fix_launch_argv_non_opencode_runs_under_sh() -> None:
    """Verifies that build fix launch argv non opencode runs under sh."""
    inner = (
        'timeout 600 claude -p "$(cat /wt/.tmp/I-00074_S06_fix1.prompt)" '
        "--model anthropic/claude-x --dangerously-skip-permissions"
    )
    assert _build_fix_launch_argv("claude", inner) == ["/bin/sh", "-c", inner]


def test_build_fix_launch_argv_keeps_inner_command_as_single_element() -> None:
    """Regression (I-00074): the inner command — which embeds `"$(cat …)"` and a
    Mermaid-flavoured prompt containing `-->` — must be ONE argv element, never
    folded into an outer quoted shell string (the `"` would close `script`'s own
    `-c` argument and the prompt words would leak onto `script`'s command line,
    aborting with `script: unrecognized option '-->'`)."""
    inner = (
        'timeout 600 opencode run "$(cat /wt/.tmp/I-00074_S06_fix1.prompt)" '
        "--model x/y --dangerously-skip-permissions"
    )
    argv = _build_fix_launch_argv("opencode", inner)
    # exactly one element equals the whole inner command, with its quotes intact
    assert argv.count(inner) == 1
    assert argv[2] == inner
    assert all('"$(cat ' not in tok for tok in argv if tok != inner)


# ---------------------------------------------------------------------------
# _try_auto_amend_after_escalation  (CR-00087)
# ---------------------------------------------------------------------------


def test_try_auto_amend_short_circuits_when_project_config_none() -> None:
    """When project_config is None the feature is off — short-circuit with False.

    No imports from scope_amendment are reached; db is untouched.
    """
    mock_db = MagicMock()
    result = _try_auto_amend_after_escalation(
        db=mock_db,
        project_id="TEST",
        project_config=None,
        cycle=MagicMock(),
        step=MagicMock(),
        violations=["tests/foo_test.py"],
        worktree_path=Path("/tmp/wt"),
        _now=MagicMock(),
    )
    assert result is False
    # No DB writes should have occurred
    assert mock_db.add.call_count == 0
    assert mock_db.commit.call_count == 0


def test_try_auto_amend_short_circuits_when_should_auto_amend_is_false() -> None:
    """When should_auto_amend returns False the function returns early — no DB writes.

    This covers the empty allow-patterns, over-budget, and partial-match cases.
    """
    mock_db = MagicMock()
    mock_cycle = MagicMock()
    mock_step = MagicMock()

    fake_config = MagicMock()
    fake_config.auto_amend_allow_patterns = []  # feature off: empty patterns
    fake_config.auto_amend_max_paths = None

    with patch("orch.daemon.scope_amendment.should_auto_amend", return_value=False):
        result = _try_auto_amend_after_escalation(
            db=mock_db,
            project_id="TEST",
            project_config=fake_config,
            cycle=mock_cycle,
            step=mock_step,
            violations=["tests/foo_test.py"],
            worktree_path=Path("/tmp/wt"),
            _now=MagicMock(),
        )

    assert result is False
    # No DB writes: amend_allowed_paths and new StepRun must not be reached
    assert mock_db.add.call_count == 0
    assert mock_db.commit.call_count == 0
