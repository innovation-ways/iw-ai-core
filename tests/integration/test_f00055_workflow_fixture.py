"""End-to-end integration test for the F-00055 workflow history fixture.

This is the proof that F-00056's S18 browser verification will have the data
it needs: we seed a testcontainer DB via the exact same path the E2E stack
uses (scripts/e2e_seed.seed) and then assert the execution_report data model
returns the retry hotspots the V1 verification expects.

If this passes, the browser step's empty-state failure mode is resolved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from sqlalchemy import select

from orch.daemon.execution_report import assemble_execution_report
from orch.db.models import FixCycle, StepRun, WorkflowStep

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def seeded_db(db_session: Session) -> Session:
    """Run the central seed + per-item fixtures against the testcontainer."""
    # Patch get_session so the seed module uses our transactional test session.
    # The fixture discovery loop calls db.commit() internally — override so
    # the transaction survives for assertions.
    from contextlib import contextmanager

    from scripts import e2e_seed as seed_module

    @contextmanager
    def _fake_get_session():
        yield db_session

    real_commit = db_session.commit
    db_session.commit = db_session.flush  # type: ignore[method-assign]
    try:
        with (
            patch.object(seed_module, "get_session", _fake_get_session),
            patch.object(seed_module, "_check_production_guardrail", lambda: None),
        ):
            seed_module.seed()
    finally:
        db_session.commit = real_commit  # type: ignore[method-assign]

    return db_session


def test_fixture_seeds_18_workflow_steps_for_f00055(seeded_db: Session) -> None:
    steps = (
        seeded_db.execute(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == "iw-ai-core",
                WorkflowStep.work_item_id == "F-00055",
            )
            .order_by(WorkflowStep.step_number)
        )
        .scalars()
        .all()
    )
    assert len(steps) == 19, (
        f"Expected 19 steps (18 workflow + S19 self_assess from I-00070), got {len(steps)}"
    )
    assert steps[0].step_id == "S01"
    assert steps[-1].step_id == "S19", (
        f"Last step should be S19 (self_assess from I-00070), got {steps[-1].step_id}"
    )


def test_fixture_encodes_correct_retry_counts(seeded_db: Session) -> None:
    """The whole point: S13×3, S10×2, S11×2, S16×2, S18×6 from the markdown."""
    expected = {"S10": 2, "S11": 2, "S13": 3, "S16": 2, "S18": 6}
    for step_id, want in expected.items():
        step = seeded_db.execute(
            select(WorkflowStep).where(
                WorkflowStep.project_id == "iw-ai-core",
                WorkflowStep.work_item_id == "F-00055",
                WorkflowStep.step_id == step_id,
            )
        ).scalar_one()
        runs = seeded_db.execute(select(StepRun).where(StepRun.step_id == step.id)).scalars().all()
        assert len(runs) == want, f"{step_id}: expected {want} runs, got {len(runs)}"


def test_fixture_seeds_fix_cycles_for_retry_steps(seeded_db: Session) -> None:
    """S11×1, S13×2, S16×1, S18×2 fix cycles from the markdown."""
    expected = {"S11": 1, "S13": 2, "S16": 1, "S18": 2}
    for step_id, want in expected.items():
        step = seeded_db.execute(
            select(WorkflowStep).where(
                WorkflowStep.project_id == "iw-ai-core",
                WorkflowStep.work_item_id == "F-00055",
                WorkflowStep.step_id == step_id,
            )
        ).scalar_one()
        cycles = (
            seeded_db.execute(select(FixCycle).where(FixCycle.step_id == step.id)).scalars().all()
        )
        assert len(cycles) == want, f"{step_id}: expected {want} cycles, got {len(cycles)}"


def test_execution_report_returns_expected_hotspots(seeded_db: Session) -> None:
    """The key V1 assertion: the execution report surfaces the retry hotspots."""
    data = assemble_execution_report(seeded_db, "iw-ai-core", "F-00055")
    hotspot_ids = {h.step_id: h.retry_count for h in data.hotspots}
    assert hotspot_ids.get("S18") == 6
    assert hotspot_ids.get("S13") == 3
    assert hotspot_ids.get("S10") == 2
    assert hotspot_ids.get("S11") == 2
    assert hotspot_ids.get("S16") == 2


def test_seed_is_idempotent(db_session: Session) -> None:
    """Re-running the seed does not duplicate rows — required because
    ``scripts/e2e_up.sh`` may rebuild the stack between failed browser runs.
    """
    from contextlib import contextmanager

    from scripts import e2e_seed as seed_module

    @contextmanager
    def _fake_get_session():
        yield db_session

    real_commit = db_session.commit
    db_session.commit = db_session.flush  # type: ignore[method-assign]
    try:
        with (
            patch.object(seed_module, "get_session", _fake_get_session),
            patch.object(seed_module, "_check_production_guardrail", lambda: None),
        ):
            seed_module.seed()
            first_step_count = db_session.scalar(
                select(WorkflowStep).where(
                    WorkflowStep.project_id == "iw-ai-core",
                    WorkflowStep.work_item_id == "F-00055",
                )
            )
            assert first_step_count is not None

            seed_module.seed()  # second run
    finally:
        db_session.commit = real_commit  # type: ignore[method-assign]

    all_steps = (
        db_session.execute(
            select(WorkflowStep).where(
                WorkflowStep.project_id == "iw-ai-core",
                WorkflowStep.work_item_id == "F-00055",
            )
        )
        .scalars()
        .all()
    )
    assert len(all_steps) == 19, (
        f"Idempotency broken: expected 19 steps after two seed runs, got {len(all_steps)}"
    )
