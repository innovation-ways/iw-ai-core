"""AC1/AC2: _synthetic_setup_step.restartable flag correctness.

Parametrized over BatchItem.status × WorkflowStep states to ensure
restartable=True only when BatchItem is setup_failed/failed AND all
WorkflowSteps are still pending.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from dashboard.routers.items import _synthetic_setup_step
from orch.db.models import BatchItemStatus

# ---------------------------------------------------------------------------
# Fake BatchItem builder
# ---------------------------------------------------------------------------


def _fake_bi(status: BatchItemStatus, **kwargs: Any) -> Any:
    obj = SimpleNamespace()
    obj.status = status
    obj.worktree_info = kwargs.get("worktree_info")
    obj.started_at = kwargs.get("started_at")
    obj.notes = kwargs.get("notes")
    return obj


# ---------------------------------------------------------------------------
# Parametrisation table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bi_status", "steps_state", "expected"),
    [
        # AC1: setup_only failure → restartable
        pytest.param(
            BatchItemStatus.setup_failed,
            "all_pending",
            True,
            id="setup_failed+all_pending=True",
        ),
        pytest.param(
            BatchItemStatus.failed,
            "all_pending",
            True,
            id="failed+all_pending=True",
        ),
        pytest.param(
            BatchItemStatus.failed,
            "empty",
            True,
            id="failed+empty_steps=True",
        ),
        # AC2: any step progressed → restartable=False
        pytest.param(
            BatchItemStatus.failed,
            "one_in_progress",
            False,
            id="failed+one_in_progress=False",
        ),
        pytest.param(
            BatchItemStatus.failed,
            "one_completed",
            False,
            id="failed+one_completed=False",
        ),
        pytest.param(
            BatchItemStatus.setup_failed,
            "one_in_progress",
            False,
            id="setup_failed+one_in_progress=False",
        ),
        pytest.param(
            BatchItemStatus.setup_failed,
            "one_completed",
            False,
            id="setup_failed+one_completed=False",
        ),
        pytest.param(
            BatchItemStatus.setup_failed,
            "mixed_progressed",
            False,
            id="setup_failed+mixed_progressed=False",
        ),
        # AC2: non-failed statuses → restartable=False
        pytest.param(
            BatchItemStatus.pending,
            "all_pending",
            False,
            id="pending+all_pending=False",
        ),
        pytest.param(
            BatchItemStatus.setting_up,
            "all_pending",
            False,
            id="setting_up+all_pending=False",
        ),
        pytest.param(
            BatchItemStatus.executing,
            "all_pending",
            False,
            id="executing+all_pending=False",
        ),
        pytest.param(
            BatchItemStatus.completed,
            "all_pending",
            False,
            id="completed+all_pending=False",
        ),
        pytest.param(
            BatchItemStatus.merging,
            "all_pending",
            False,
            id="merging+all_pending=False",
        ),
        pytest.param(
            BatchItemStatus.merged,
            "all_pending",
            False,
            id="merged+all_pending=False",
        ),
        # AC2: bi=None → restartable=False
        pytest.param(
            None,
            "all_pending",
            False,
            id="bi=None=False",
        ),
    ],
)
def test_synthetic_setup_step_restartable(
    bi_status: BatchItemStatus | None,
    steps_state: str,
    expected: bool,
) -> None:
    """restartable is True only for setup_failed/failed with ALL steps still pending."""
    bi = _fake_bi(bi_status) if bi_status is not None else None

    match steps_state:
        case "all_pending":
            step_statuses = ["pending", "pending", "pending"]
        case "empty":
            step_statuses = []
        case "one_in_progress":
            step_statuses = ["in_progress", "pending", "pending"]
        case "one_completed":
            step_statuses = ["completed", "pending", "pending"]
        case "mixed_progressed":
            step_statuses = ["completed", "in_progress", "pending"]
        case _:
            raise ValueError(f"Unknown steps_state: {steps_state}")

    step_detail = _synthetic_setup_step(bi, step_statuses=step_statuses)
    assert step_detail.restartable is expected, (
        f"bi={bi_status}, steps_state={steps_state}: "
        f"expected restartable={expected}, got {step_detail.restartable}"
    )


def test_restartable_false_when_step_statuses_none() -> None:
    """restartable defaults to False when step_statuses is None (backward-compat)."""
    bi = _fake_bi(BatchItemStatus.setup_failed)
    step_detail = _synthetic_setup_step(bi, step_statuses=None)
    assert step_detail.restartable is False


def test_restartable_true_for_empty_steps_list() -> None:
    """restartable is True when step_statuses=[] (no steps defined yet)."""
    bi = _fake_bi(BatchItemStatus.setup_failed)
    step_detail = _synthetic_setup_step(bi, step_statuses=[])
    assert step_detail.restartable is True


def test_synthetic_step_has_correct_fields() -> None:
    """StepDetail has is_synthetic=True, step_id=S00, and correct restartable value."""
    bi = _fake_bi(BatchItemStatus.setup_failed)
    step_detail = _synthetic_setup_step(bi, step_statuses=["pending"])
    assert step_detail.is_synthetic is True
    assert step_detail.step_id == "S00"
    assert step_detail.restartable is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
