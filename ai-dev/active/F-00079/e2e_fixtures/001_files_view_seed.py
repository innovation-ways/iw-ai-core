"""Files view fixture: add diff data to F-00055 for browser verification.

This fixture creates the diff data needed by S19 browser verification
(V1-V10: Files tab, per-file diff, step toggle, filter, PDF export, etc.).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from orch.db.models import (
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"
ITEM_ID = "F-00055"

# ---------------------------------------------------------------------------
# Aggregate diff (stored on the work item - represents the squash-merge diff)
# ---------------------------------------------------------------------------
# NOTE: every hunk uses `@@ -0,0 +1 @@` (insert into empty range) so the
# unified diff is well-formed and `unidiff.PatchSet(...)` can parse it.
# A previous version used `@@ -1 +1 @@` with only an addition line, which
# is malformed — the parser raises UnidiffParseError and the PDF export
# route 500s (F-00079 / S19 V7).
AGGREGATE_DIFF = (
    "diff --git a/dashboard/routers/items.py b/dashboard/routers/items.py\n"
    "--- a/dashboard/routers/items.py\n"
    "+++ b/dashboard/routers/items.py\n"
    "@@ -0,0 +1 @@\n"
    "+def files_tab(): pass\n"
    "diff --git a/dashboard/templates/item_files.html b/dashboard/templates/item_files.html\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/dashboard/templates/item_files.html\n"
    "@@ -0,0 +1 @@\n"
    "+<div class=files-tab></div>\n"
    "diff --git a/orch/diff_service.py b/orch/diff_service.py\n"
    "--- a/orch/diff_service.py\n"
    "+++ b/orch/diff_service.py\n"
    "@@ -0,0 +1 @@\n"
    "+def parse_diff_summary(): pass\n"
)

AGGREGATE_SUMMARY = [
    {
        "path": "dashboard/routers/items.py",
        "status": "M",
        "added": 1,
        "removed": 0,
        "is_generated": False,
        "is_binary": False,
        "old_path": None,
    },
    {
        "path": "dashboard/templates/item_files.html",
        "status": "A",
        "added": 1,
        "removed": 0,
        "is_generated": True,
        "is_binary": False,
        "old_path": None,
    },
    {
        "path": "orch/diff_service.py",
        "status": "M",
        "added": 1,
        "removed": 0,
        "is_generated": False,
        "is_binary": False,
        "old_path": None,
    },
]

# ---------------------------------------------------------------------------
# Per-step diffs (stored on step_runs - one for "backend-impl" step)
# ---------------------------------------------------------------------------
BACKEND_STEP_DIFF = (
    "diff --git a/dashboard/routers/items.py b/dashboard/routers/items.py\n"
    "--- a/dashboard/routers/items.py\n"
    "+++ b/dashboard/routers/items.py\n"
    "@@ -0,0 +1 @@\n"
    "+def files_tab(): pass\n"
    "diff --git a/orch/diff_service.py b/orch/diff_service.py\n"
    "--- a/orch/diff_service.py\n"
    "+++ b/orch/diff_service.py\n"
    "@@ -0,0 +1 @@\n"
    "+def parse_diff_summary(): pass\n"
)

BACKEND_STEP_SUMMARY = [
    {
        "path": "dashboard/routers/items.py",
        "status": "M",
        "added": 1,
        "removed": 0,
        "is_generated": False,
        "is_binary": False,
        "old_path": None,
    },
    {
        "path": "orch/diff_service.py",
        "status": "M",
        "added": 1,
        "removed": 0,
        "is_generated": False,
        "is_binary": False,
        "old_path": None,
    },
]

# ---------------------------------------------------------------------------
# Second step diff (frontend)
# ---------------------------------------------------------------------------
FRONTEND_STEP_DIFF = (
    "diff --git a/dashboard/templates/item_files.html b/dashboard/templates/item_files.html\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/dashboard/templates/item_files.html\n"
    "@@ -0,0 +1 @@\n"
    "+<div class=files-tab></div>\n"
    "diff --git a/dashboard/static/css/files.css b/dashboard/static/css/files.css\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/dashboard/static/css/files.css\n"
    "@@ -0,0 +1 @@\n"
    "+.files-tab { }\n"
)

FRONTEND_STEP_SUMMARY = [
    {
        "path": "dashboard/templates/item_files.html",
        "status": "A",
        "added": 1,
        "removed": 0,
        "is_generated": True,
        "is_binary": False,
        "old_path": None,
    },
    {
        "path": "dashboard/static/css/files.css",
        "status": "A",
        "added": 1,
        "removed": 0,
        "is_generated": True,
        "is_binary": False,
        "old_path": None,
    },
]


def seed(db: Session) -> None:
    from sqlalchemy import select

    now = datetime.now(UTC)

    # ------------------------------------------------------------------
    # 1. Ensure F-00055 exists and add aggregate diff data
    # ------------------------------------------------------------------
    item = db.get(WorkItem, (PROJECT_ID, ITEM_ID))
    if item is None:
        item = WorkItem(
            project_id=PROJECT_ID,
            id=ITEM_ID,
            type=WorkItemType.Feature,
            title="Work-item-aware Code Q&A pipeline",
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.done,
            design_doc_content="Seed fixture for files view verification.",
            summary="Work-item-aware Code Q&A with citations and history feed",
            created_at=now,
            updated_at=now,
            completed_at=now,
            archived_at=now,  # Mark as archived to use diff_text
            diff_text=AGGREGATE_DIFF,
            diff_summary=AGGREGATE_SUMMARY,
        )
        db.add(item)
    else:
        # Update existing item with diff data
        item.diff_text = AGGREGATE_DIFF
        item.diff_summary = AGGREGATE_SUMMARY
        item.status = WorkItemStatus.completed
        item.phase = WorkItemPhase.done
        item.completed_at = now
        item.archived_at = now  # Mark as archived to use diff_text

    db.flush()

    # ------------------------------------------------------------------
    # 2. Find or create workflow steps for the item
    # ------------------------------------------------------------------
    # Step 1: backend-impl (S01)
    backend_step = db.scalar(
        select(WorkflowStep).where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == ITEM_ID,
            WorkflowStep.step_number == 1,
        )
    )
    if backend_step is None:
        backend_step = WorkflowStep(
            project_id=PROJECT_ID,
            work_item_id=ITEM_ID,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            opencode_agent="backend-impl",
            step_type=StepType.implementation,
            step_label="backend-impl",
            status=StepStatus.completed,
            started_at=now,
            completed_at=now,
        )
        db.add(backend_step)
        db.flush()

    # Step 2: frontend-impl (S02)
    frontend_step = db.scalar(
        select(WorkflowStep).where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == ITEM_ID,
            WorkflowStep.step_number == 2,
        )
    )
    if frontend_step is None:
        frontend_step = WorkflowStep(
            project_id=PROJECT_ID,
            work_item_id=ITEM_ID,
            step_number=2,
            step_id="S02",
            agent_label="Frontend",
            opencode_agent="frontend-impl",
            step_type=StepType.implementation,
            step_label="frontend-impl",
            status=StepStatus.completed,
            started_at=now,
            completed_at=now,
        )
        db.add(frontend_step)
        db.flush()

    # ------------------------------------------------------------------
    # 3. Find or create step runs with diff data
    # ------------------------------------------------------------------
    # Backend step run - check if exists
    backend_run = db.scalar(
        select(StepRun).where(
            StepRun.step_id == backend_step.id,
            StepRun.run_number == 1,
        )
    )
    if backend_run is None:
        backend_run = StepRun(
            step_id=backend_step.id,
            run_number=1,
            status=RunStatus.completed,
            diff_text=BACKEND_STEP_DIFF,
            diff_summary=BACKEND_STEP_SUMMARY,
            started_at=now,
            completed_at=now,
            duration_secs=120.0,
            exit_code=0,
        )
        db.add(backend_run)
        db.flush()
    else:
        # Update existing run with diff data
        backend_run.diff_text = BACKEND_STEP_DIFF
        backend_run.diff_summary = BACKEND_STEP_SUMMARY
        backend_run.status = RunStatus.completed

    # Frontend step run - check if exists
    frontend_run = db.scalar(
        select(StepRun).where(
            StepRun.step_id == frontend_step.id,
            StepRun.run_number == 1,
        )
    )
    if frontend_run is None:
        frontend_run = StepRun(
            step_id=frontend_step.id,
            run_number=1,
            status=RunStatus.completed,
            diff_text=FRONTEND_STEP_DIFF,
            diff_summary=FRONTEND_STEP_SUMMARY,
            started_at=now,
            completed_at=now,
            duration_secs=90.0,
            exit_code=0,
        )
        db.add(frontend_run)
        db.flush()
    else:
        # Update existing run with diff data
        frontend_run.diff_text = FRONTEND_STEP_DIFF
        frontend_run.diff_summary = FRONTEND_STEP_SUMMARY
        frontend_run.status = RunStatus.completed
