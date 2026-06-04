"""Unit tests for step lifecycle CLI commands — pure logic, no DB required."""

import pytest

from orch.cli.step_commands import (
    validate_step_done_transition,
    validate_step_fail_transition,
    validate_step_start_transition,
)
from orch.db.models import StepStatus

# ---------------------------------------------------------------------------
# validate_step_start_transition
# ---------------------------------------------------------------------------


def test_step_start_pending_is_valid() -> None:
    """Verifies that step start pending is valid."""
    error, already = validate_step_start_transition(StepStatus.pending)
    assert error is None
    assert already is False


def test_step_start_in_progress_is_idempotent() -> None:
    """Verifies that step start in progress is idempotent."""
    error, already = validate_step_start_transition(StepStatus.in_progress)
    assert error is None
    assert already is True


@pytest.mark.parametrize(
    "status",
    [
        StepStatus.completed,
        StepStatus.failed,
        StepStatus.needs_fix,
        StepStatus.skipped,
    ],
)
def test_step_start_rejects_non_pending(status: StepStatus) -> None:
    """Verifies that step start rejects non pending."""
    error, _already = validate_step_start_transition(status)
    assert error is not None
    assert status.value in error


# ---------------------------------------------------------------------------
# validate_step_done_transition
# ---------------------------------------------------------------------------


def test_step_done_in_progress_is_valid() -> None:
    """Verifies that step done in progress is valid."""
    assert validate_step_done_transition(StepStatus.in_progress) is None


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
def test_step_done_rejects_non_in_progress(status: StepStatus) -> None:
    """Verifies that step done rejects non in progress."""
    error = validate_step_done_transition(status)
    assert error is not None
    assert status.value in error


# ---------------------------------------------------------------------------
# validate_step_fail_transition
# ---------------------------------------------------------------------------


def test_step_fail_in_progress_is_valid() -> None:
    """Verifies that step fail in progress is valid."""
    assert validate_step_fail_transition(StepStatus.in_progress) is None


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
def test_step_fail_rejects_non_in_progress(status: StepStatus) -> None:
    """Verifies that step fail rejects non in progress."""
    error = validate_step_fail_transition(status)
    assert error is not None
    assert status.value in error
