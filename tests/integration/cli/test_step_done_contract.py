"""Contract tests for `iw step-done` against a real PostgreSQL testcontainer.

Tests the full contract: exit codes, stdout shape, DB row effects, and
evidence-ingestion hooks triggered by browser_verification steps.

All tests use the testcontainer db_session fixture — never the live DB.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from orch.cli.main import cli
from orch.db.models import (
    EvidencePhase,
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemEvidence,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from subprocess import CompletedProcess

    from sqlalchemy.orm import Session

    from orch.db.models import Project as ProjectModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(
    runner: CliRunner,
    args: list[str],
    get_session: object,
    project_id: str = "test-proj",
) -> pytest.ClickResult:
    """Invoke the CLI with a pre-injected session factory."""
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def seed_item_with_step(
    db_session: Session,
    project_id: str,
    item_id: str,
    step_id: str = "S01",
    step_type: StepType = StepType.implementation,
    step_status: StepStatus = StepStatus.pending,
    item_status: WorkItemStatus = WorkItemStatus.approved,
) -> int:
    """Seed a work item + step in the given state. Returns step PK."""
    # Idempotent: skip if project already exists (e.g. from test_project fixture)
    existing = db_session.get(Project, project_id)
    if not existing:
        db_session.add(
            Project(id=project_id, display_name="Test", repo_root="/repos/test", config={})
        )
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title=f"Test {item_id}",
        status=item_status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(item)
    db_session.flush()

    step = WorkflowStep(
        project_id=project_id,
        work_item_id=item_id,
        step_number=1,
        step_id=step_id,
        agent_label="Backend",
        step_type=step_type,
        status=step_status,
        started_at=None,
        completed_at=None,
    )
    db_session.add(step)
    db_session.flush()
    return step.id


def seed_in_progress_step(
    db_session: Session,
    project_id: str,
    item_id: str,
    step_id: str = "S01",
    step_type: StepType = StepType.implementation,
) -> int:
    """Seed a work item + step in in_progress state with a running StepRun. Returns step PK."""
    step_pk = seed_item_with_step(
        db_session,
        project_id,
        item_id,
        step_id,
        step_type=step_type,
        step_status=StepStatus.in_progress,
        item_status=WorkItemStatus.in_progress,
    )
    run = StepRun(
        step_id=step_pk,
        run_number=1,
        status=RunStatus.running,
        worktree_path="/tmp/test-worktree",
    )
    db_session.add(run)
    db_session.flush()
    return step_pk


def _step_status_in_db(
    db_session: Session, project_id: str, item_id: str, step_id: str
) -> str | None:
    step = db_session.execute(
        select(WorkflowStep).where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == step_id,
        )
    ).scalar_one_or_none()
    return step.status.value if step else None


def _latest_step_run_status(
    db_session: Session, project_id: str, item_id: str, step_id: str
) -> str | None:
    step = db_session.execute(
        select(WorkflowStep).where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == step_id,
        )
    ).scalar_one_or_none()
    if step is None:
        return None
    run = db_session.execute(
        select(StepRun)
        .where(StepRun.step_id == step.id)
        .order_by(StepRun.run_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    return run.status.value if run else None


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


def test_step_done_success_in_progress_to_completed(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: marking a step in_progress → completed transitions the step row."""
    item_id = "F-00001"
    seed_in_progress_step(db_session, test_project.id, item_id)

    runner = CliRunner()
    result = invoke(runner, ["step-done", item_id, "--step", "S01"], cli_get_session)

    assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.output}"

    # DB effect: step status
    assert _step_status_in_db(db_session, test_project.id, item_id, "S01") == "completed"

    # DB effect: latest StepRun status
    assert _latest_step_run_status(db_session, test_project.id, item_id, "S01") == "completed"


def test_step_done_with_report_path_stores_report_file(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """Exit 0 with --report: report_file is stored on the step row."""
    item_id = "F-00002"
    seed_in_progress_step(db_session, test_project.id, item_id)

    report = tmp_path / "report.md"
    report.write_text("# Step Report\n\nDone.")

    runner = CliRunner()
    result = invoke(
        runner,
        ["step-done", item_id, "--step", "S01", "--report", str(report)],
        cli_get_session,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"

    step = db_session.execute(
        select(WorkflowStep).where(
            WorkflowStep.project_id == test_project.id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == "S01",
        )
    ).scalar_one()
    assert step.report_file == str(report)
    assert step.report_content is not None
    assert "Step Report" in step.report_content


def test_step_done_json_output_shape(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0 with --json: stdout is valid JSON matching the documented shape."""
    item_id = "F-00003"
    seed_in_progress_step(db_session, test_project.id, item_id)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "--json", "step-done", item_id, "--step", "S01"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert "step_id" in data
    assert "status" in data
    assert data["step_id"] == "S01"
    assert data["status"] == "completed"


def test_step_done_idempotent_second_call_on_completed_step(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Marking an already-completed step as done: exit 1 with an error message."""
    item_id = "F-00004"
    seed_in_progress_step(db_session, test_project.id, item_id)

    runner = CliRunner()
    first = invoke(runner, ["step-done", item_id, "--step", "S01"], cli_get_session)
    assert first.exit_code == 0, f"First call failed: {first.stderr}"

    second = invoke(runner, ["step-done", item_id, "--step", "S01"], cli_get_session)
    assert second.exit_code == 1, f"Second call should error: {second.stderr}"
    assert "completed" in (second.stderr or "").lower()


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_step_done_unknown_item_exit_1(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 1 + clear stderr: item not found."""
    runner = CliRunner()
    result = invoke(runner, ["step-done", "I-DOES-NOT-EXIST", "--step", "S01"], cli_get_session)
    assert result.exit_code == 1
    assert "not found" in (result.stderr or "").lower()


def test_step_done_nonexistent_step_exit_1(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 1 + clear stderr: step does not exist on the item."""
    item_id = "F-00005"
    seed_in_progress_step(db_session, test_project.id, item_id)

    runner = CliRunner()
    result = invoke(runner, ["step-done", item_id, "--step", "S99"], cli_get_session)
    assert result.exit_code == 1
    assert "not found" in (result.stderr or "").lower()


def test_step_done_missing_report_path_stores_reference_without_content(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: a non-existent --report path is non-fatal.

    The path reference is still recorded on the step row, but report_content
    stays unset because the best-effort file read is skipped when the file is
    absent (orch/cli/step_commands.py — `if full_path.exists()`).
    """
    item_id = "F-00006"
    seed_in_progress_step(db_session, test_project.id, item_id)

    runner = CliRunner()
    result = invoke(
        runner,
        ["step-done", item_id, "--step", "S01", "--report", "does-not-exist.md"],
        cli_get_session,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.output}"

    step = db_session.execute(
        select(WorkflowStep).where(
            WorkflowStep.project_id == test_project.id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == "S01",
        )
    ).scalar_one()
    assert step.status.value == "completed"
    assert step.report_file == "does-not-exist.md"
    assert step.report_content is None


def test_step_done_approve_pending_step_exit_1(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 1 + clear stderr: cannot mark a pending step as done."""
    item_id = "F-00007"
    seed_item_with_step(db_session, test_project.id, item_id, step_status=StepStatus.pending)

    runner = CliRunner()
    result = invoke(runner, ["step-done", item_id, "--step", "S01"], cli_get_session)
    assert result.exit_code == 1, f"Should error on pending step: {result.stderr}"


# ---------------------------------------------------------------------------
# Browser-verification evidence-ingestion hook
# ---------------------------------------------------------------------------


def test_step_done_browser_verification_ingests_post_evidences(
    db_engine: object,
    pg_container: object,
    tmp_path: Path,
    iw_subprocess: Callable[..., CompletedProcess[str]],
) -> None:
    """Exit 0 on browser_verification step: evidence files from ai-dev/active/<id>/evidences/post/
    are ingested into work_item_evidences table (EvidencePhase.post).

    This test runs the CLI as a subprocess to exercise the full evidence pipeline
    (ingest_phase_from_disk called inside step_done for browser_verification steps).

    Deliberately does NOT take the ``test_project`` fixture — that fixture inserts
    ``test-proj`` inside the still-open ``db_session`` transaction, and this test
    re-seeds the same project id on a separate ``db_engine`` connection; the
    duplicate primary key would block forever on the unresolved transaction.
    """
    project_id = "test-proj"
    item_id = "F-00008"

    # Build a minimal evidence directory tree
    active_dir = tmp_path / "ai-dev" / "active" / item_id / "evidences" / "post"
    active_dir.mkdir(parents=True)

    # Write a test evidence file
    evidence_file = active_dir / "test-screenshot.png"
    evidence_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01")

    # Seed DB via engine
    from sqlalchemy.orm import sessionmaker as _sm

    sm = _sm(bind=db_engine)

    with sm() as session:
        session.add(Project(id=project_id, display_name="Test", repo_root=str(tmp_path), config={}))
        session.flush()
        item = WorkItem(
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
        session.add(item)
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
        run = StepRun(
            step_id=step_pk, run_number=1, status=RunStatus.running, worktree_path=str(tmp_path)
        )
        session.add(run)
        session.commit()

    result = iw_subprocess(["step-done", item_id, "--step", "S01"], project_id, tmp_path)

    assert result.returncode == 0, (
        f"step-done on browser_verification step failed:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Verify evidence was ingested
    with sm() as session:
        ev = session.execute(
            select(WorkItemEvidence).where(
                WorkItemEvidence.project_id == project_id,
                WorkItemEvidence.work_item_id == item_id,
                WorkItemEvidence.phase == EvidencePhase.post,
            )
        ).scalar_one_or_none()
        assert ev is not None, "post-phase evidence was not ingested"
        assert ev.filename == "test-screenshot.png"
        assert ev.size_bytes > 0
