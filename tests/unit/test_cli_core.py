"""Unit tests for CLI core — pure logic, no DB or I/O required."""

import json
from pathlib import Path

import pytest

from orch.cli.item_commands import (
    agent_to_label,
    agent_to_step_type,
    validate_approve_transition,
    validate_unapprove_transition,
)
from orch.cli.utils import find_project_root, format_id, validate_id_prefix
from orch.db.models import StepType, WorkItemStatus

# ---------------------------------------------------------------------------
# find_project_root
# ---------------------------------------------------------------------------


def test_find_project_root_found_in_cwd(tmp_path: Path) -> None:
    config = tmp_path / ".iw-orch.json"
    config.write_text('{"project_id": "myproject"}')

    result = find_project_root(tmp_path)

    assert result is not None
    project_id, root = result
    assert project_id == "myproject"
    assert root == tmp_path


def test_find_project_root_found_in_ancestor(tmp_path: Path) -> None:
    config = tmp_path / ".iw-orch.json"
    config.write_text('{"project_id": "ancestor-proj"}')

    subdir = tmp_path / "a" / "b" / "c"
    subdir.mkdir(parents=True)

    result = find_project_root(subdir)

    assert result is not None
    project_id, root = result
    assert project_id == "ancestor-proj"
    assert root == tmp_path


def test_find_project_root_not_found(tmp_path: Path) -> None:
    result = find_project_root(tmp_path)
    assert result is None


def test_find_project_root_invalid_json(tmp_path: Path) -> None:
    config = tmp_path / ".iw-orch.json"
    config.write_text("not valid json {{{")

    result = find_project_root(tmp_path)
    assert result is None


def test_find_project_root_missing_project_id(tmp_path: Path) -> None:
    config = tmp_path / ".iw-orch.json"
    config.write_text('{"other_key": "value"}')

    result = find_project_root(tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# format_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prefix", "number", "expected"),
    [
        ("F", 1, "F-00001"),
        ("F", 42, "F-00042"),
        ("F", 999, "F-00999"),
        ("I", 1, "I-00001"),
        ("CR", 3, "CR-00003"),
        ("BATCH", 1, "BATCH-00001"),
        ("BATCH", 12, "BATCH-00012"),
        ("BATCH", 999, "BATCH-00999"),
    ],
)
def test_format_id(prefix: str, number: int, expected: str) -> None:
    assert format_id(prefix, number) == expected


# ---------------------------------------------------------------------------
# validate_id_prefix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("item_id", "item_type", "expected"),
    [
        ("I-00001", "incident", True),
        ("I-00999", "incident", True),
        ("F-00001", "feature", True),
        ("CR-00001", "cr", True),
        ("CR-00042", "cr", True),
        # Wrong prefix for type
        ("I-00001", "feature", False),
        ("F-00001", "incident", False),
        ("CR-00001", "feature", False),
        ("F-00001", "cr", False),
        # Prefix with no digits
        ("I", "incident", False),
        ("F", "feature", False),
        # Completely wrong format
        ("BATCH-00001", "incident", False),
        ("001", "incident", False),
    ],
)
def test_validate_id_prefix(item_id: str, item_type: str, expected: bool) -> None:
    assert validate_id_prefix(item_id, item_type) == expected


# ---------------------------------------------------------------------------
# validate_approve_transition
# ---------------------------------------------------------------------------


def test_approve_draft_is_valid() -> None:
    assert validate_approve_transition(WorkItemStatus.draft) is None


@pytest.mark.parametrize(
    "status",
    [
        WorkItemStatus.approved,
        WorkItemStatus.in_progress,
        WorkItemStatus.completed,
        WorkItemStatus.failed,
        WorkItemStatus.paused,
    ],
)
def test_approve_non_draft_returns_error(status: WorkItemStatus) -> None:
    error = validate_approve_transition(status)
    assert error is not None
    assert status.value in error


# ---------------------------------------------------------------------------
# validate_unapprove_transition
# ---------------------------------------------------------------------------


def test_unapprove_approved_no_batch_is_valid() -> None:
    assert validate_unapprove_transition(WorkItemStatus.approved, None) is None


def test_unapprove_rejects_non_approved_status() -> None:
    error = validate_unapprove_transition(WorkItemStatus.draft, None)
    assert error is not None
    assert "draft" in error


def test_unapprove_rejects_item_in_active_batch() -> None:
    error = validate_unapprove_transition(WorkItemStatus.approved, "BATCH-00003")
    assert error is not None
    assert "BATCH-00003" in error


def test_unapprove_status_error_takes_precedence_over_batch() -> None:
    error = validate_unapprove_transition(WorkItemStatus.in_progress, "BATCH-00001")
    assert error is not None
    assert "in_progress" in error


# ---------------------------------------------------------------------------
# agent_to_step_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent", "expected"),
    [
        ("backend-impl", StepType.implementation),
        ("frontend-impl", StepType.implementation),
        ("code-review-impl", StepType.code_review),
        ("code-review-fix-impl", StepType.code_review_fix),
        ("code-review-final-impl", StepType.code_review_final),
        ("code-review-fix-final-impl", StepType.code_review_fix_final),
        ("quality-validation-impl", StepType.quality_validation),
        ("qv-gate", StepType.quality_validation),
        ("qv-fix-impl", StepType.qv_fix),
        ("qv-browser", StepType.browser_verification),
        ("browser-verification-impl", StepType.browser_verification),
        ("something-else", StepType.implementation),
    ],
)
def test_agent_to_step_type(agent: str, expected: StepType) -> None:
    assert agent_to_step_type(agent) == expected


# ---------------------------------------------------------------------------
# agent_to_label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent", "expected"),
    [
        ("backend-impl", "Backend"),
        ("frontend-impl", "Frontend"),
        ("code-review-impl", "CodeReview"),
        ("code-review-final-impl", "CodeReviewFinal"),
        ("quality-validation-impl", "QualityValidation"),
        ("qv-gate", "QvGate"),
        ("qv-browser", "QvBrowser"),
    ],
)
def test_agent_to_label(agent: str, expected: str) -> None:
    assert agent_to_label(agent) == expected


# ---------------------------------------------------------------------------
# parse_manifest_steps (with tmp_path)
# ---------------------------------------------------------------------------


def test_parse_manifest_steps(tmp_path: Path) -> None:
    from orch.cli.item_commands import parse_manifest_steps

    manifest = tmp_path / "workflow-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "steps": [
                    {"step": "S01", "agent": "backend-impl"},
                    {"step": "S02", "agent": "code-review-impl"},
                ]
            }
        )
    )

    steps = parse_manifest_steps(manifest)

    assert len(steps) == 2
    assert steps[0]["step"] == "S01"
    assert steps[1]["agent"] == "code-review-impl"
