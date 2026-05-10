"""Integration regression tests for I-00075 fix-cycle fixture.

These tests verify that ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py
seeds the correct WorkItem + WorkflowStep + FixCycle rows and is idempotent on
re-run. They guard against the regression where a future refactor of
scripts/e2e_seed.py:_run_fixture breaks fixture-loading semantics, or where the
fixture file is renamed/moved and the qv-browser step fails to find it.

Tests run against a real PostgreSQL testcontainer — no mocking, no live DB.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from orch.db.models import (
    FixCycle,
    FixStatus,
    FixTrigger,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
)
from scripts.e2e_seed import _run_fixture

# ---------------------------------------------------------------------------
# Path constants — robust against the runner's CWD
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "ai-dev" / "active" / "I-00075" / "e2e_fixtures" / "001_fix_cycle_demo.py"
)

# Synthetic item IDs and project constants (must match the fixture)
PROJECT_ID = "iw-ai-core"
WORK_ITEM_ID = "I-99001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def iw_core_project(db_session: Session) -> Project:
    """Create the iw-ai-core project row.

    The 001_fix_cycle_demo.py fixture inserts rows with project_id='iw-ai-core'.
    The standard test_project fixture creates 'test-proj', not 'iw-ai-core',
    so we need this separate fixture to satisfy the FK constraint.
    """
    project = Project(
        id=PROJECT_ID,
        display_name="IW AI Core",
        repo_root=str(REPO_ROOT),
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


# ---------------------------------------------------------------------------
# Test 1: file-presence guard
# ---------------------------------------------------------------------------


def test_i00075_fixture_file_exists() -> None:
    """Pre-fix this assertion FAILS (file is absent); post-fix it PASSES.

    Reproduction test for I-00075 — proves the fixture file is present at the
    exact path the daemon's _apply_per_item_fixtures resolves at browser-
    verification time.
    """
    assert FIXTURE_PATH.is_file(), (
        f"Fixture {FIXTURE_PATH} must exist so qv-browser can render fix-cycle "
        f"amber pills against a seeded item — see I-00075 root cause analysis."
    )


# ---------------------------------------------------------------------------
# Test 2: semantic assertion — FixCycle rows exist and are correctly shaped
# ---------------------------------------------------------------------------


def test_i00075_fixture_seeds_at_least_one_fix_cycle(
    db_session: Session, iw_core_project: Project
) -> None:
    """After the fixture runs, the DB MUST contain exactly 2 FixCycle rows
    attached to WorkflowStep S02 which belongs to I-99001.

    This is a SEMANTIC assertion — we verify the specific cycle numbers and
    trigger types the design mandates, not just that ≥1 row exists.
    """
    _run_fixture(FIXTURE_PATH, db_session)
    db_session.flush()

    # Join FixCycle -> WorkflowStep and filter by the synthetic item
    stmt = (
        select(FixCycle)
        .join(WorkflowStep, FixCycle.step_id == WorkflowStep.id)
        .where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == WORK_ITEM_ID,
        )
    )
    cycles = db_session.scalars(stmt).all()

    # AC1 / design intent: exactly 2 cycles on S02
    assert len(cycles) == 2, (
        f"Expected exactly 2 FixCycle rows for I-99001, got {len(cycles)}. "
        "The design mandates 2 cycles to exercise the multi-pill rendering branch."
    )

    # Semantic: cycle numbers must be {1, 2} (not e.g. two rows with cycle_number=1)
    cycle_numbers = {c.cycle_number for c in cycles}
    assert cycle_numbers == {1, 2}, (
        f"Expected cycle_numbers {{1, 2}}, got {cycle_numbers}. Both cycles must be distinct."
    )

    # Semantic: all cycles must be on S02
    s02_steps = db_session.scalars(
        select(WorkflowStep).where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == WORK_ITEM_ID,
            WorkflowStep.step_id == "S02",
        )
    ).all()
    assert len(s02_steps) == 1, f"Expected exactly 1 S02 step, got {len(s02_steps)}"
    s02_step_ids = {s.id for s in s02_steps}

    for cycle in cycles:
        assert cycle.step_id in s02_step_ids, (
            f"FixCycle id={cycle.id} step_id={cycle.step_id} must belong to S02 "
            f"(ids={s02_step_ids})"
        )

    # Semantic: trigger_type == code_review for all cycles
    assert all(c.trigger_type == FixTrigger.code_review for c in cycles), (
        "All fix cycles must have trigger_type == FixTrigger.code_review per the design intent."
    )

    # Semantic: status == completed for all cycles
    assert all(c.status == FixStatus.completed for c in cycles), (
        "All fix cycles must have status == FixStatus.completed."
    )


# ---------------------------------------------------------------------------
# Test 3: idempotency — re-running the fixture must not raise or duplicate
# ---------------------------------------------------------------------------


def test_i00075_fixture_idempotent(db_session: Session, iw_core_project: Project) -> None:
    """Running the fixture a second time on the same session is a safe no-op.

    Guards against the regression where the idempotency guard is removed or
    broken, causing IntegrityError on re-run or duplicate row accumulation.
    """
    _run_fixture(FIXTURE_PATH, db_session)
    db_session.flush()

    # Count rows in the three tables the fixture touches
    def _count_rows() -> dict[str, int]:
        return {
            "WorkItem": db_session.query(WorkItem)
            .filter(
                WorkItem.project_id == PROJECT_ID,
                WorkItem.id == WORK_ITEM_ID,
            )
            .count(),
            "WorkflowStep": db_session.query(WorkflowStep)
            .filter(
                WorkflowStep.project_id == PROJECT_ID,
                WorkflowStep.work_item_id == WORK_ITEM_ID,
            )
            .count(),
            "FixCycle": db_session.query(FixCycle)
            .filter(
                FixCycle.step_id.in_(
                    select(WorkflowStep.id).where(
                        WorkflowStep.project_id == PROJECT_ID,
                        WorkflowStep.work_item_id == WORK_ITEM_ID,
                    )
                )
            )
            .count(),
        }

    counts_before = _count_rows()

    # Re-run — must NOT raise
    _run_fixture(FIXTURE_PATH, db_session)
    db_session.flush()

    counts_after = _count_rows()

    # No new rows inserted on second run
    assert counts_after == counts_before, (
        f"Fixture must be idempotent: counts before={counts_before}, "
        f"counts after={counts_after}. "
        "The fixture's idempotency guard may have been broken."
    )


# ---------------------------------------------------------------------------
# Test 4: WorkflowStep topology — exactly 3 steps (S01, S02, S03)
# ---------------------------------------------------------------------------


def test_i00075_fixture_seeds_workflow_steps(db_session: Session, iw_core_project: Project) -> None:
    """The fixture seeds exactly 3 WorkflowStep rows so the pipeline strip
    is meaningfully wide (the qv-browser V1 verifies a multi-step pipeline).

    Semantic assertions verify step_id, step_number order, and step_type values.
    """
    _run_fixture(FIXTURE_PATH, db_session)
    db_session.flush()

    steps = db_session.scalars(
        select(WorkflowStep).where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == WORK_ITEM_ID,
        )
    ).all()

    assert len(steps) == 3, (
        f"Expected exactly 3 WorkflowStep rows for I-99001, got {len(steps)}. "
        "The design mandates S01 + S02 + S03 for a meaningfully wide pipeline."
    )

    # Sort by step_number for order-sensitive assertions
    sorted_steps = sorted(steps, key=lambda s: s.step_number)

    step_ids = [s.step_id for s in sorted_steps]
    assert step_ids == ["S01", "S02", "S03"], (
        f"Expected step_ids ['S01', 'S02', 'S03'], got {step_ids}."
    )

    step_types = [s.step_type for s in sorted_steps]
    expected_types = [
        StepType.implementation,
        StepType.code_review,
        StepType.quality_validation,
    ]
    assert step_types == expected_types, (
        "Expected step_types in implementation/code_review/quality_validation "
        f"order, got {step_types}."
    )

    # All steps must be completed
    assert all(s.status == StepStatus.completed for s in steps), (
        "All WorkflowStep rows must have status == StepStatus.completed."
    )
