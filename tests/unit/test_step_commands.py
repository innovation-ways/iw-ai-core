"""Unit tests for step command validation helpers (no DB required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from orch.cli.step_commands import (
    validate_browser_evidence_present,
    validate_step_kill_transition,
    validate_step_restart_transition,
    validate_step_skip_transition,
)
from orch.db.models import StepStatus, StepType

# ---------------------------------------------------------------------------
# validate_step_restart_transition
# ---------------------------------------------------------------------------


class TestValidateStepRestartTransition:
    """step-restart is valid from failed or needs_fix only."""

    @pytest.mark.parametrize("status", [StepStatus.failed, StepStatus.needs_fix])
    def test_valid(self, status: StepStatus) -> None:
        assert validate_step_restart_transition(status) is None

    @pytest.mark.parametrize(
        "status",
        [
            StepStatus.pending,
            StepStatus.in_progress,
            StepStatus.completed,
            StepStatus.skipped,
        ],
    )
    def test_invalid(self, status: StepStatus) -> None:
        result = validate_step_restart_transition(status)
        assert result is not None
        assert "Cannot restart step" in result


# ---------------------------------------------------------------------------
# validate_step_skip_transition
# ---------------------------------------------------------------------------


class TestValidateStepSkipTransition:
    """step-skip is valid from failed only."""

    def test_valid(self) -> None:
        assert validate_step_skip_transition(StepStatus.failed) is None

    @pytest.mark.parametrize(
        "status",
        [
            StepStatus.pending,
            StepStatus.in_progress,
            StepStatus.completed,
            StepStatus.needs_fix,
            StepStatus.skipped,
        ],
    )
    def test_invalid(self, status: StepStatus) -> None:
        result = validate_step_skip_transition(status)
        assert result is not None
        assert "Cannot skip step" in result


# ---------------------------------------------------------------------------
# validate_step_kill_transition
# ---------------------------------------------------------------------------


class TestValidateStepKillTransition:
    """step-kill is valid from in_progress only."""

    def test_valid(self) -> None:
        assert validate_step_kill_transition(StepStatus.in_progress) is None

    @pytest.mark.parametrize(
        "status",
        [
            StepStatus.pending,
            StepStatus.completed,
            StepStatus.failed,
            StepStatus.needs_fix,
            StepStatus.skipped,
        ],
    )
    def test_invalid(self, status: StepStatus) -> None:
        result = validate_step_kill_transition(status)
        assert result is not None
        assert "Cannot kill step" in result


# ---------------------------------------------------------------------------
# validate_browser_evidence_present
# ---------------------------------------------------------------------------


class TestValidateBrowserEvidencePresent:
    """browser_verification step-done requires >= 1 file in evidences/post/."""

    @pytest.mark.parametrize(
        "step_type",
        [
            StepType.implementation,
            StepType.code_review,
            StepType.code_review_final,
            StepType.quality_validation,
            StepType.qv_fix,
        ],
    )
    def test_non_browser_step_types_short_circuit_to_none(
        self,
        step_type: StepType,
        tmp_path: Path,
    ) -> None:
        assert validate_browser_evidence_present(step_type, "I-00036", cwd=tmp_path) is None

    def test_browser_step_with_screenshot_passes(self, tmp_path: Path) -> None:
        post_dir = tmp_path / "ai-dev" / "active" / "I-00036" / "evidences" / "post"
        post_dir.mkdir(parents=True)
        (post_dir / "V1_shot.png").write_bytes(b"fake-png")
        assert (
            validate_browser_evidence_present(
                StepType.browser_verification, "I-00036", cwd=tmp_path
            )
            is None
        )

    def test_browser_step_with_missing_dir_fails(self, tmp_path: Path) -> None:
        result = validate_browser_evidence_present(
            StepType.browser_verification, "I-00036", cwd=tmp_path
        )
        assert result is not None
        assert "no evidences/post/" in result

    def test_browser_step_with_empty_dir_fails(self, tmp_path: Path) -> None:
        post_dir = tmp_path / "ai-dev" / "active" / "I-00036" / "evidences" / "post"
        post_dir.mkdir(parents=True)
        result = validate_browser_evidence_present(
            StepType.browser_verification, "I-00036", cwd=tmp_path
        )
        assert result is not None
        assert "is empty" in result

    def test_browser_step_with_only_subdirs_fails(self, tmp_path: Path) -> None:
        post_dir = tmp_path / "ai-dev" / "active" / "I-00036" / "evidences" / "post"
        (post_dir / "nested").mkdir(parents=True)
        result = validate_browser_evidence_present(
            StepType.browser_verification, "I-00036", cwd=tmp_path
        )
        assert result is not None
        assert "is empty" in result
