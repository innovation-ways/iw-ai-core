"""E2E fixture for CR-00065 S11 browser verification — session log popup.

Creates:
  - WorkItem CR-00065-S11-FIXTURE (already seeded by central seed)
  - WorkflowStep entries for S01, S02
  - StepRun for S01 with cli_tool=pi and session_file pointing to a real
    pi session JSONL from ~/.pi/agent/sessions/
  - StepRun for S02 with cli_tool=claude and log_content
"""

from __future__ import annotations

import os
from pathlib import Path

from orch.db.models import (
    Batch,
    BatchItem,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
)
from orch.db.session import get_session
from sqlalchemy import select


def _find_pi_session_file() -> str:
    """Find the most recent pi session JSONL from this worktree's runs.

    The pi session slug for /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00065
    is derived as: path.strip("/").replace("/", "-") = "--home-sergiog-dev-iw-doc-plan-main-iw-ai-core-.worktrees-CR-00065--"
    """
    # Walk through known session dirs and find the one matching this worktree
    sessions_root = Path.home() / ".pi" / "agent" / "sessions"
    if not sessions_root.exists():
        return ""

    worktree_slug = "--home-sergiog-dev-iw-doc-plan-main-iw-ai-core-.worktrees-CR-00065--"
    session_dir = sessions_root / worktree_slug

    if session_dir.exists():
        jsonl_files = sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if jsonl_files:
            return str(jsonl_files[0])

    # Fallback: find any recent session (last 2 hours)
    import time
    cutoff = time.time() - 7200
    candidates: list[tuple[float, str]] = []
    try:
        for subdir in sessions_root.iterdir():
            if not subdir.is_dir():
                continue
            for jsonl in subdir.glob("*.jsonl"):
                mtime = jsonl.stat().st_mtime
                if mtime > cutoff:
                    candidates.append((mtime, str(jsonl)))
    except OSError:
        pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    return ""


def seed(db) -> None:
    item_id = "CR-00065-S11-FIXTURE"
    project_id = "iw-ai-core"

    # Ensure the WorkItem exists
    item = db.get(WorkItem, (project_id, item_id))
    if item is None:
        from datetime import UTC, datetime
        from orch.db.models import WorkItemType

        item = WorkItem(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.ChangeRequest,
            title="Browser Verification Fixture — CR-00065 S11",
            status="completed",
            phase="done",
            created_at=datetime.now(UTC),
        )
        db.add(item)
        db.flush()

    # Ensure a Batch + BatchItem so the item is properly associated
    batch_id = "e2e-seed-batch"
    batch = db.get(Batch, (project_id, batch_id))
    if batch is None:
        from datetime import UTC, datetime

        batch = Batch(
            project_id=project_id,
            id=batch_id,
            status="completed",
            cli_tool="opencode",
            auto_publish=False,
            auto_merge=False,
            max_parallel=1,
        )
        db.add(batch)
        db.flush()

    bi = db.scalar(
        select(BatchItem).where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
        )
    )
    if bi is None:
        from datetime import UTC, datetime
        from orch.db.models import BatchItemStatus

        bi = BatchItem(
            project_id=project_id,
            batch_id=batch_id,
            work_item_id=item_id,
            status=BatchItemStatus.completed,
        )
        db.add(bi)
        db.flush()

    # Upsert WorkflowStep rows for S01 and S02
    # Check by step_number since the unique constraint is on (project_id, work_item_id, step_number)
    existing_steps_by_num: dict[int, WorkflowStep] = {
        ws.step_number: ws
        for ws in db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
        ).all()
    }
    existing_steps = {ws.step_id: ws for ws in existing_steps_by_num.values()}

    if "S01" not in existing_steps and 1 not in existing_steps_by_num:
        ws01 = WorkflowStep(
            project_id=project_id,
            work_item_id=item_id,
            step_id="S01",
            step_number=1,
            agent_label="Database Implementation",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db.add(ws01)
        db.flush()
        existing_steps["S01"] = ws01

    if "S02" not in existing_steps and 2 not in existing_steps_by_num:
        ws02 = WorkflowStep(
            project_id=project_id,
            work_item_id=item_id,
            step_id="S02",
            step_number=2,
            agent_label="QV Migration Check",
            step_type=StepType.quality_validation,
            status=StepStatus.completed,
        )
        db.add(ws02)
        db.flush()
        existing_steps["S02"] = ws02

    # Upsert StepRun for S01 (pi runtime with session_file)
    existing_runs_s01 = list(
        db.scalars(
            select(StepRun).where(StepRun.step_id == existing_steps["S01"].id)
        ).all()
    )

    session_file_path = _find_pi_session_file()
    from datetime import UTC, datetime

    if session_file_path:
        if not existing_runs_s01:
            run01 = StepRun(
                step_id=existing_steps["S01"].id,
                run_number=1,
                status=RunStatus.completed,
                cli_tool="pi",
                session_file=session_file_path,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_secs=120.0,
            )
            db.add(run01)
    else:
        # No pi session found — write a synthetic JSONL fixture to /tmp
        fake_session = (
            '{"type":"session","version":3,"id":"test-fixture","cwd":"/fake"}\n'
            '{"type":"message","id":"m1","message":{"role":"user","content":[{"type":"text","text":"Test prompt"}]}}\n'
            '{"type":"message","id":"m2","message":{"role":"assistant","content":[{"type":"text","text":"Test response for session log viewer"}]}}\n'
        )
        tmp_dir = Path("/tmp/iw-e2e-sessions")
        tmp_dir.mkdir(exist_ok=True)
        session_file_path = str(tmp_dir / "fixture_s01_run1.jsonl")
        Path(session_file_path).write_text(fake_session)

        if not existing_runs_s01:
            run01 = StepRun(
                step_id=existing_steps["S01"].id,
                run_number=1,
                status=RunStatus.completed,
                cli_tool="pi",
                session_file=session_file_path,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_secs=120.0,
            )
            db.add(run01)

    # Upsert StepRun for S02 (claude runtime with log_content)
    existing_runs_s02 = list(
        db.scalars(
            select(StepRun).where(StepRun.step_id == existing_steps["S02"].id)
        ).all()
    )

    if not existing_runs_s02:
        run02 = StepRun(
            step_id=existing_steps["S02"].id,
            run_number=1,
            status=RunStatus.completed,
            cli_tool="claude",
            log_content=(
                "[09:15:23] Starting claude-code session for S02\n"
                "[09:15:24] Loading design document CR-00065_CR_Design.md\n"
                "[09:15:26] Running alembic revision --autogenerate\n"
                "[09:15:30] Running make migration-check\n"
                "[09:15:35] All checks passed — step S02 complete.\n"
            ),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_secs=45.0,
        )
        db.add(run02)

    db.flush()
    print(f"e2e_fixture: seeded session log data for {item_id}")