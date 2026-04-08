"""Unit tests for step command validation helpers (no DB required)."""

from __future__ import annotations

import pytest

from orch.cli.step_commands import (
    validate_step_kill_transition,
    validate_step_restart_transition,
    validate_step_skip_transition,
)
from orch.db.models import StepStatus

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
