"""End-to-end integration test for restart_setup full flow (AC5).

Sets up a real git repo + worktree, creates a setup-failed BatchItem with
log files on disk, calls POST /project/{project_id}/api/item/{item_id}/restart-setup,
and verifies:
- worktree directory is removed
- log files are unlinked
- StepRun rows are deleted
- WorkflowStep rows are reset
- WorkItem and BatchItem status flipped
- setup_restarted daemon event exists
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
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


# ---------------------------------------------------------------------------
# Git helpers (mirror test_worktree_setup_context_copy.py)
# ---------------------------------------------------------------------------


def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )


def _make_worktree(repo: Path, branch: str, worktree_path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", branch, str(worktree_path), "HEAD"],
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# TestClient fixture (same pattern as dashboard tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Full flow test
# ---------------------------------------------------------------------------


class TestRestartSetupFullFlow:
    """Integration test for the complete restart_setup flow."""

    def test_restart_setup_removes_worktree_and_clears_steps(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Full restart_setup flow: worktree deleted, steps reset, event emitted."""
        item_id = "CR00029-full-flow"
        worktree_branch = f"agent/cr00029-{item_id}"

        # --- Set up real git repo + worktree ---
        main_repo = tmp_path / "main_repo"
        main_repo.mkdir()
        _make_git_repo(main_repo)

        # Create a worktree directory that simulates the failed setup
        worktree_dir = tmp_path / "worktrees" / "CR29-A"
        worktree_dir.parent.mkdir(parents=True, exist_ok=True)
        _make_worktree(main_repo, worktree_branch, worktree_dir)

        # Put a marker file in the worktree to prove it gets deleted
        marker_file = worktree_dir / "setup_marker.txt"
        marker_file.write_text("this should be deleted")
        assert worktree_dir.exists()

        # --- Create DB records ---
        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Full Flow Test",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)

        # Update project to point at our temp repo_root
        test_project.repo_root = str(main_repo)
        db_session.add(test_project)

        batch = Batch(
            id="CR00029-batch-full-flow",
            project_id=test_project.id,
            status=BatchStatus.approved,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id="CR00029-batch-full-flow",
            status=BatchItemStatus.setup_failed,
            notes="Setup failed: worktree already exists",
            worktree_info={"path": str(worktree_dir)},
        )
        db_session.add(batch_item)

        # All steps still pending
        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.pending,
        )
        db_session.add(step)
        db_session.flush()

        # StepRun with log file
        log_file = tmp_path / "step_run_1.log"
        log_file.write_text("setup log output\nfailed at worktree creation\n")
        step_run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.failed,
            worktree_path=str(worktree_dir),
            log_file=str(log_file),
        )
        db_session.add(step_run)
        db_session.flush()
        db_session.commit()

        assert log_file.exists()  # precondition: log file exists on disk

        # --- Call restart_setup ---
        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"

        # --- Verify worktree directory removed ---
        assert not worktree_dir.exists(), f"Worktree dir {worktree_dir} should have been deleted"

        # --- Verify log file unlinked ---
        assert not log_file.exists(), f"Log file {log_file} should have been unlinked"

        # --- Verify StepRun rows deleted ---
        db_session.expire_all()
        runs = list(db_session.scalars(select(StepRun).where(StepRun.step_id == step.id)).all())
        assert len(runs) == 0, f"Expected 0 StepRuns, got {len(runs)}"

        # --- Verify WorkflowStep reset ---
        steps = list(
            db_session.scalars(
                select(WorkflowStep).where(WorkflowStep.work_item_id == item_id)
            ).all()
        )
        assert len(steps) == 1
        assert steps[0].status == StepStatus.pending
        assert steps[0].started_at is None
        assert steps[0].completed_at is None
        assert steps[0].report_file is None

        # --- Verify WorkItem.status = approved ---
        item = db_session.scalar(select(WorkItem).where(WorkItem.id == item_id))
        assert item.status == WorkItemStatus.approved

        # --- Verify BatchItem.status = pending, notes cleared ---
        bi = db_session.scalar(select(BatchItem).where(BatchItem.work_item_id == item_id))
        assert bi.status == BatchItemStatus.pending
        assert bi.notes is None

        # --- Verify setup_restarted daemon event ---
        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "setup_restarted",
                DaemonEvent.entity_id == item_id,
            )
        )
        assert event is not None, "setup_restarted daemon event not found"
        assert event.entity_type == "work_item"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
