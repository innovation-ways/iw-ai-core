"""E2E seed for I-00101 scope-blocked UI verification (S15).

Creates:
  - A synthetic project
  - A work item in status=in_progress
  - A step in status=needs_fix with a FixCycle row status=escalated and fix_metadata.scope_violations
  - A minimal workflow-manifest.json at the worktree path

The synthetic worktree is placed under /app/ai-dev/.e2e-test-worktrees/ (the e2e app
container's ai-dev bind-mount). The manifest's allowed_paths is deliberately narrow so
the amend action can be observed expanding it.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from orch.db.models import (
    FixCycle,
    FixStatus,
    FixTrigger,
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

# Synthetic worktree root inside the e2e-dashboard container.
# The container's /tmp is writable — we create the synthetic worktree there.
_WORKTREE_ROOT = Path("/tmp/iw-e2e-worktrees")
_ITEM_ID = "I-00101-SYNTH"
_STEP_ID = "S01"
_PROJECT_ID = "e2e-i00101-scope"


def seed(db: Session) -> None:
    # ── 1. Project ────────────────────────────────────────────────────────────
    project = db.get(Project, _PROJECT_ID)
    if project is None:
        project = Project(
            id=_PROJECT_ID,
            display_name="E2E I-00101 Scope Test",
            repo_root="/app/ai-dev/.e2e-test-worktrees/e2e-i00101-scope",
            config={},
            enabled=True,
            oss_enabled=False,
        )
        db.add(project)

    # ── 2. Worktree path setup ───────────────────────────────────────────────
    worktree_path = _WORKTREE_ROOT / f"{_ITEM_ID}-synth"
    manifest_dir = worktree_path / "ai-dev" / "active" / _ITEM_ID
    manifest_dir.mkdir(parents=True, exist_ok=True)

    # Write the manifest BEFORE the worktree row so amend reads a real file.
    manifest = {
        "version": "1",
        "scope": {
            "allowed_paths": [
                "src/",
                "tests/",
            ],
        },
        "steps": [
            {
                "step_id": "S01",
                "agent": "general",
                "cli": "claude",
                "prompt": "Run lint on the project.",
                "gate": "lint",
            },
        ],
    }
    manifest_path = manifest_dir / "workflow-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    # Create a minimal .git dir so _resolve_parent_manifest doesn't crash.
    git_dir = worktree_path / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)

    # ── 3. Work item ─────────────────────────────────────────────────────────
    item = db.get(WorkItem, (_PROJECT_ID, _ITEM_ID))
    if item is None:
        item = WorkItem(
            project_id=_PROJECT_ID,
            id=_ITEM_ID,
            type=WorkItemType.Feature,
            title="I-00101 Synthetic Scope-Blocked Item",
            status=WorkItemStatus.in_progress,
            design_doc_content="# Synthetic item\nUsed for browser verification of scope-blocked UI.",
        )
        db.add(item)

    # ── 4. Step in needs_fix ───────────────────────────────────────────────────
    step = db.execute(
        select(WorkflowStep).where(
            WorkflowStep.project_id == _PROJECT_ID,
            WorkflowStep.work_item_id == _ITEM_ID,
            WorkflowStep.step_id == _STEP_ID,
        )
    ).scalar_one_or_none()
    if step is None:
        step = WorkflowStep(
            project_id=_PROJECT_ID,
            work_item_id=_ITEM_ID,
            step_id=_STEP_ID,
            step_number=1,
            agent_label="general",
            step_type=StepType.code_review,
            status=StepStatus.needs_fix,
            description="Synthetic scope-blocked step",
        )
        db.add(step)
    else:
        step.status = StepStatus.needs_fix

    db.flush()  # ensure step.id is available

    # ── 5. StepRun (needed so the amend endpoint can call _get_last_run) ─────
    last_run = db.execute(
        select(StepRun).where(
            StepRun.step_id == step.id,
            StepRun.run_number == 1,
        )
    ).scalar_one_or_none()
    if last_run is None:
        last_run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,  # completed so it doesn't block restart
            worktree_path=str(worktree_path),
            command="echo synthetic",
        )
        db.add(last_run)

    # ── 6. FixCycle (escalated, scope_violations) ─────────────────────────────
    cycle = db.execute(
        select(FixCycle).where(
            FixCycle.step_id == step.id,
            FixCycle.cycle_number == 1,
        )
    ).scalar_one_or_none()
    if cycle is None:
        cycle = FixCycle(
            step_id=step.id,
            cycle_number=1,
            status=FixStatus.escalated,
            trigger_type=FixTrigger.quality_validation,
            fix_metadata={"scope_violations": [".test-target.toml"]},
        )
        db.add(cycle)
    else:
        cycle.status = FixStatus.escalated
        cycle.fix_metadata = {"scope_violations": [".test-target.toml"]}

    db.commit()
