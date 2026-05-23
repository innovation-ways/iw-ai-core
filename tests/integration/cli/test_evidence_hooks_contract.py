"""Contract tests for evidence-ingestion hooks across the CLI.

Covers the `ingest_phase_from_disk` calls that fire on:
- `approve` → EvidencePhase.pre (orch/cli/item_commands.py)
- `step-done` (browser_verification) → EvidencePhase.post (orch/cli/step_commands.py)

These tests run `iw` as a real subprocess, so they seed the database on the
per-test `db_engine` clone (committed) rather than through `db_session`. They
deliberately do NOT take the `test_project` fixture: that fixture inserts the
`test-proj` row inside the still-open `db_session` transaction, and seeding the
same project id here on a separate connection would block forever on the
duplicate primary key. Never the live DB — always the testcontainer clone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from orch.db.models import (
    EvidencePhase,
    Project,
    WorkItem,
    WorkItemEvidence,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess

# The `iw` subprocess is driven through the `iw_subprocess` fixture from
# tests/integration/cli/conftest.py — it builds the env that points the CLI at
# the per-test clone and satisfies the live-DB guard.


# ---------------------------------------------------------------------------
# approve hook — EvidencePhase.pre
# ---------------------------------------------------------------------------


def test_approve_hook_ingests_pre_phase_evidences(
    db_engine: object,
    pg_container: object,
    tmp_path: Path,
    iw_subprocess: Callable[..., CompletedProcess[str]],
) -> None:
    """Approve ingests files from ai-dev/active/<id>/evidences/pre/ as EvidencePhase.pre."""
    project_id = "test-proj"
    item_id = "F-00010"

    pre_dir = tmp_path / "ai-dev" / "active" / item_id / "evidences" / "pre"
    pre_dir.mkdir(parents=True)
    (pre_dir / "pre-evidence.md").write_text("# Pre-approval evidence")

    sm = sessionmaker(bind=db_engine)

    with sm() as session:
        session.add(Project(id=project_id, display_name="Test", repo_root=str(tmp_path), config={}))
        session.flush()
        session.add(
            WorkItem(
                project_id=project_id,
                id=item_id,
                type=WorkItemType.Feature,
                title=f"Test {item_id}",
                status=WorkItemStatus.draft,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            )
        )
        session.commit()

    result = iw_subprocess(["approve", item_id], project_id, tmp_path)
    assert result.returncode == 0, f"approve failed: {result.stderr}"

    with sm() as session:
        ev = session.execute(
            select(WorkItemEvidence).where(
                WorkItemEvidence.project_id == project_id,
                WorkItemEvidence.work_item_id == item_id,
                WorkItemEvidence.phase == EvidencePhase.pre,
            )
        ).scalar_one_or_none()
        assert ev is not None, "pre-phase evidence was not ingested"
        assert ev.filename == "pre-evidence.md"
        assert b"Pre-approval" in ev.content


def test_approve_hook_no_pre_directory_no_error(
    db_engine: object,
    pg_container: object,
    tmp_path: Path,
    iw_subprocess: Callable[..., CompletedProcess[str]],
) -> None:
    """Approve succeeds even when ai-dev/active/<id>/evidences/pre/ does not exist."""
    project_id = "test-proj"
    item_id = "F-00011"

    # Deliberately do NOT create the evidences/pre directory

    sm = sessionmaker(bind=db_engine)

    with sm() as session:
        session.add(Project(id=project_id, display_name="Test", repo_root=str(tmp_path), config={}))
        session.flush()
        session.add(
            WorkItem(
                project_id=project_id,
                id=item_id,
                type=WorkItemType.Feature,
                title=f"Test {item_id}",
                status=WorkItemStatus.draft,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            )
        )
        session.commit()

    result = iw_subprocess(["approve", item_id], project_id, tmp_path)
    assert result.returncode == 0, f"approve should succeed without pre dir: {result.stderr}"

    with sm() as session:
        count = session.execute(
            select(WorkItemEvidence).where(
                WorkItemEvidence.project_id == project_id,
                WorkItemEvidence.work_item_id == item_id,
                WorkItemEvidence.phase == EvidencePhase.pre,
            )
        ).scalar_one_or_none()
        assert count is None, "no pre evidence should exist when dir is absent"


# ---------------------------------------------------------------------------
# step-done hook — EvidencePhase.post (browser_verification)
# ---------------------------------------------------------------------------


def test_step_done_hook_ingests_post_phase_evidences_browser_verification(
    db_engine: object,
    pg_container: object,
    tmp_path: Path,
    iw_subprocess: Callable[..., CompletedProcess[str]],
) -> None:
    """step-done on browser_verification ingests evidences/post/ files as EvidencePhase.post."""
    project_id = "test-proj"
    item_id = "F-00012"

    post_dir = tmp_path / "ai-dev" / "active" / item_id / "evidences" / "post"
    post_dir.mkdir(parents=True)
    (post_dir / "post-screenshot.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    )
    (post_dir / "post-results.json").write_text('{"passed": true}')

    sm = sessionmaker(bind=db_engine)

    from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

    with sm() as session:
        session.add(Project(id=project_id, display_name="Test", repo_root=str(tmp_path), config={}))
        session.flush()
        session.add(
            WorkItem(
                project_id=project_id,
                id=item_id,
                type=WorkItemType.Feature,
                title=f"Test {item_id}",
                status=WorkItemStatus.in_progress,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            )
        )
        session.flush()
        step = WorkflowStep(
            project_id=project_id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.browser_verification,
            status=StepStatus.in_progress,
        )
        session.add(step)
        session.flush()
        step_pk = step.id
        session.add(
            StepRun(
                step_id=step_pk,
                run_number=1,
                status=RunStatus.running,
                worktree_path=str(tmp_path),
            )
        )
        session.commit()

    result = iw_subprocess(
        ["step-done", item_id, "--step", "S01"],
        project_id,
        tmp_path,
    )
    assert result.returncode == 0, (
        f"step-done on browser_verification step failed:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    with sm() as session:
        evs = (
            session.execute(
                select(WorkItemEvidence)
                .where(
                    WorkItemEvidence.project_id == project_id,
                    WorkItemEvidence.work_item_id == item_id,
                    WorkItemEvidence.phase == EvidencePhase.post,
                )
                .order_by(WorkItemEvidence.filename)
            )
            .scalars()
            .all()
        )
        assert len(evs) == 2, (
            f"Expected 2 post-evidence files, got {len(evs)}: {[e.filename for e in evs]}"
        )
        filenames = {ev.filename for ev in evs}
        assert filenames == {"post-results.json", "post-screenshot.png"}


def test_step_done_hook_non_browser_step_no_post_evidence(
    db_engine: object,
    pg_container: object,
    tmp_path: Path,
    iw_subprocess: Callable[..., CompletedProcess[str]],
) -> None:
    """step-done on a non-browser_verification step does NOT trigger post evidence ingestion."""
    project_id = "test-proj"
    item_id = "F-00013"

    post_dir = tmp_path / "ai-dev" / "active" / item_id / "evidences" / "post"
    post_dir.mkdir(parents=True)
    (post_dir / "stray-file.txt").write_text("should not be ingested")

    sm = sessionmaker(bind=db_engine)

    from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

    with sm() as session:
        session.add(Project(id=project_id, display_name="Test", repo_root=str(tmp_path), config={}))
        session.flush()
        session.add(
            WorkItem(
                project_id=project_id,
                id=item_id,
                type=WorkItemType.Feature,
                title=f"Test {item_id}",
                status=WorkItemStatus.in_progress,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            )
        )
        session.flush()
        step = WorkflowStep(
            project_id=project_id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,  # non-browser step
            status=StepStatus.in_progress,
        )
        session.add(step)
        session.flush()
        session.add(
            StepRun(
                step_id=step.id,
                run_number=1,
                status=RunStatus.running,
                worktree_path=str(tmp_path),
            )
        )
        session.commit()

    result = iw_subprocess(
        ["step-done", item_id, "--step", "S01"],
        project_id,
        tmp_path,
    )
    assert result.returncode == 0, f"step-done failed: {result.stderr}"

    with sm() as session:
        evs = (
            session.execute(
                select(WorkItemEvidence).where(
                    WorkItemEvidence.project_id == project_id,
                    WorkItemEvidence.work_item_id == item_id,
                    WorkItemEvidence.phase == EvidencePhase.post,
                )
            )
            .scalars()
            .all()
        )
        assert len(evs) == 0, (
            "post evidence should NOT be ingested for non-browser_verification steps"
        )
