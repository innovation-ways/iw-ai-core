"""E2E fixture: add a self_assess step with findings to F-00055.

This fixture creates the minimum data needed for the clipboard fallback
browser verification (I-00070 S12): a work item with a completed
self_assess step and findings JSON that renders the "Copy paste prompt"
button in the Execution Report tab.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

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

PROJECT_ID = "iw-ai-core"
TARGET_ITEM_ID = "F-00055"


SAMPLE_FINDINGS_JSON = json.dumps(
    {
        "narrative_md": "# Self-Assessment Narrative\n\nThe agent repeated work.",
        "bottom_line": "Two HIGH severity findings require attention before next merge.",
        "coverage_notes": "All step logs were sampled.",
        "findings": [
            {
                "severity": "HIGH",
                "class": "Process",
                "target": "iw-ai-core",
                "title": "Agent re-read files repeatedly",
                "recommendation": "Add a summarisation step to reduce redundant I/O",
                "paste_prompt": "/iw-new-incident title='Agent re-reads same files'",
                "evidence": [],
            },
            {
                "severity": "MED",
                "class": "Process",
                "target": "project",
                "title": "Missing verification step in manifest",
                "recommendation": "Add a qv-gate step",
                "paste_prompt": "/iw-new-cr title='Add qv-gate'",
                "evidence": [],
            },
        ],
    }
)

REPORT_MD = "# Self-Assessment Report\n\nThe agent repeated work."


def seed(db: Session) -> None:
    """Add a self_assess step with findings to F-00055."""
    # Check if the step already exists
    from sqlalchemy import select

    existing_step = db.execute(
        select(WorkflowStep).where(
            WorkflowStep.work_item_id == TARGET_ITEM_ID,
            WorkflowStep.step_type == StepType.self_assess,
        )
    ).scalar_one_or_none()

    if existing_step is not None:
        # Already seeded
        return

    # Get the work item
    item = db.get(WorkItem, (PROJECT_ID, TARGET_ITEM_ID))
    if item is None:
        # Fall back: create the item if it doesn't exist
        item = WorkItem(
            project_id=PROJECT_ID,
            id=TARGET_ITEM_ID,
            title="Work-item-aware Code Q&A pipeline",
            type=WorkItemType.Feature,
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.active,
            design_doc_search="",
        )
        db.add(item)
        db.flush()

    # Create the self_assess step
    step = WorkflowStep(
        project_id=PROJECT_ID,
        work_item_id=item.id,
        step_id="S19",
        step_number=19,
        step_type=StepType.self_assess,
        agent_label="SelfAssess",
        opencode_agent="self-assess-impl",
        status=StepStatus.completed,
    )
    db.add(step)
    db.flush()

    # Create the work directory and files
    # /app is read-only in the container, use /tmp for the work dir
    work_dir = Path("/tmp/ai-dev-work") / item.id
    reports_dir = work_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_file = reports_dir / f"{item.id}_self_assess_report.md"
    report_file.write_text(REPORT_MD, encoding="utf-8")

    findings_file = reports_dir / f"{item.id}_self_assess_findings.json"
    findings_file.write_text(SAMPLE_FINDINGS_JSON, encoding="utf-8")

    # Create the step run
    step_run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.completed,
        started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
        completed_at=datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
        duration_secs=60.0,
        report_file=str(report_file),
    )
    db.add(step_run)
    db.flush()