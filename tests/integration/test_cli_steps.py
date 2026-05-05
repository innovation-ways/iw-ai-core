"""Integration tests for step lifecycle CLI commands against a real PostgreSQL testcontainer."""

import json
from typing import Any

from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import (
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(
    runner: CliRunner,
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
) -> Any:
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def make_item(
    db_session: Any,
    item_id: str = "I-00001",
    status: WorkItemStatus = WorkItemStatus.approved,
) -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Issue,
        title="Test item",
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()
    return item


def make_step(
    db_session: Any,
    item_id: str = "I-00001",
    step_id: str = "S01",
    status: StepStatus = StepStatus.pending,
) -> WorkflowStep:
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=1,
        step_id=step_id,
        agent_label="Backend",
        step_type=StepType.implementation,
        status=status,
    )
    db_session.add(step)
    db_session.flush()
    return step


def make_step_run(
    db_session: Any,
    step: WorkflowStep,
    status: RunStatus = RunStatus.running,
    run_number: int = 1,
) -> StepRun:
    step_run = StepRun(
        step_id=step.id,
        run_number=run_number,
        status=status,
    )
    db_session.add(step_run)
    db_session.flush()
    return step_run


# ---------------------------------------------------------------------------
# step-start
# ---------------------------------------------------------------------------


def test_step_start_pending_to_in_progress(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.pending)

    runner = CliRunner()
    result = invoke(runner, ["step-start", "I-00001", "--step", "S01"], cli_get_session)
    assert result.exit_code == 0, result.output

    db_session.refresh(step)
    assert step.status == StepStatus.in_progress
    assert step.started_at is not None


def test_step_start_json_output(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    make_step(db_session, status=StepStatus.pending)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "step-start", "I-00001", "--step", "S01"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "in_progress"
    assert data["step_id"] == "S01"


def test_step_start_idempotent_when_in_progress(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    """step-start on an already in_progress step is a no-op (idempotent)."""
    make_item(db_session)
    make_step(db_session, status=StepStatus.in_progress)

    runner = CliRunner()
    result = invoke(runner, ["step-start", "I-00001", "--step", "S01"], cli_get_session)
    assert result.exit_code == 0
    assert "already in progress" in result.output


def test_step_start_rejects_completed(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    make_step(db_session, status=StepStatus.completed)

    runner = CliRunner()
    result = invoke(runner, ["step-start", "I-00001", "--step", "S01"], cli_get_session)
    assert result.exit_code == 1


def test_step_start_not_found_exits_1(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)

    runner = CliRunner()
    result = invoke(runner, ["step-start", "I-00001", "--step", "S99"], cli_get_session)
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# step-done
# ---------------------------------------------------------------------------


def test_step_done_in_progress_to_completed(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.in_progress)

    runner = CliRunner()
    result = invoke(runner, ["step-done", "I-00001", "--step", "S01"], cli_get_session)
    assert result.exit_code == 0, result.output

    db_session.refresh(step)
    assert step.status == StepStatus.completed
    assert step.completed_at is not None
    assert step.report_file is None


def test_step_done_with_report_stores_path(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.in_progress)

    runner = CliRunner()
    result = invoke(
        runner,
        ["step-done", "I-00001", "--step", "S01", "--report", "reports/S01-backend.md"],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    db_session.refresh(step)
    assert step.status == StepStatus.completed
    assert step.report_file == "reports/S01-backend.md"


def test_step_done_rejects_non_in_progress(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    make_step(db_session, status=StepStatus.pending)

    runner = CliRunner()
    result = invoke(runner, ["step-done", "I-00001", "--step", "S01"], cli_get_session)
    assert result.exit_code == 1


def test_step_done_with_report_propagates_path_to_step_run(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    """step-done --report mirrors path onto the running StepRun (parity with step-fail).

    Without this, the execution-report view's self-assessment loader cannot
    locate the report (and its findings sidecar) because it reads
    StepRun.report_file, not WorkflowStep.report_file.
    """
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.in_progress)
    step_run = make_step_run(db_session, step, status=RunStatus.running)

    runner = CliRunner()
    result = invoke(
        runner,
        ["step-done", "I-00001", "--step", "S01", "--report", "reports/S01-backend.md"],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    db_session.refresh(step)
    db_session.refresh(step_run)
    assert step.report_file == "reports/S01-backend.md"
    assert step_run.report_file == "reports/S01-backend.md"


# ---------------------------------------------------------------------------
# step-fail
# ---------------------------------------------------------------------------


def test_step_fail_in_progress_to_failed(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.in_progress)

    runner = CliRunner()
    result = invoke(
        runner,
        ["step-fail", "I-00001", "--step", "S01", "--reason", "Compilation error"],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    db_session.refresh(step)
    assert step.status == StepStatus.failed


def test_step_fail_stores_reason_in_step_run(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.in_progress)
    step_run = make_step_run(db_session, step, status=RunStatus.running)

    runner = CliRunner()
    result = invoke(
        runner,
        ["step-fail", "I-00001", "--step", "S01", "--reason", "Out of memory"],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    db_session.refresh(step)
    db_session.refresh(step_run)
    assert step.status == StepStatus.failed
    assert step_run.error_message == "Out of memory"
    assert step_run.status == RunStatus.failed


def test_step_fail_rejects_non_in_progress(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    make_step(db_session, status=StepStatus.pending)

    runner = CliRunner()
    result = invoke(
        runner,
        ["step-fail", "I-00001", "--step", "S01", "--reason", "Something went wrong"],
        cli_get_session,
    )
    assert result.exit_code == 1


def test_step_fail_with_report_stores_path_and_content(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Any,
) -> None:
    """step-fail --report stores both report_file and report_content (mirrors step-done).

    Without this, fix-cycle prompts for browser_verification only see the
    one-line --reason text and apply guesswork patches.
    """
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.in_progress)
    step_run = make_step_run(db_session, step, status=RunStatus.running)

    report_file = tmp_path / "S01_browser_report.md"
    report_file.write_text("# Browser Report\n\n| V1 | FAIL | tab missing |\n")

    runner = CliRunner()
    result = invoke(
        runner,
        [
            "step-fail",
            "I-00001",
            "--step",
            "S01",
            "--reason",
            "V1 failed",
            "--report",
            str(report_file),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    db_session.refresh(step)
    db_session.refresh(step_run)
    assert step.status == StepStatus.failed
    assert step.report_file == str(report_file)
    assert step.report_content is not None
    assert "V1" in step.report_content
    assert step_run.report_file == str(report_file)
    assert step_run.error_message == "V1 failed"


def test_step_fail_without_report_leaves_fields_null(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    """step-fail without --report keeps report_file/report_content as None."""
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.in_progress)

    runner = CliRunner()
    result = invoke(
        runner,
        ["step-fail", "I-00001", "--step", "S01", "--reason", "agent error"],
        cli_get_session,
    )
    assert result.exit_code == 0

    db_session.refresh(step)
    assert step.status == StepStatus.failed
    assert step.report_file is None
    assert step.report_content is None


# ---------------------------------------------------------------------------
# Full lifecycle: start → done
# ---------------------------------------------------------------------------


def test_full_step_lifecycle_start_done(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.pending)

    runner = CliRunner()

    result = invoke(runner, ["step-start", "I-00001", "--step", "S01"], cli_get_session)
    assert result.exit_code == 0

    db_session.refresh(step)
    assert step.status == StepStatus.in_progress

    result = invoke(
        runner,
        ["step-done", "I-00001", "--step", "S01", "--report", "out/report.md"],
        cli_get_session,
    )
    assert result.exit_code == 0

    db_session.refresh(step)
    assert step.status == StepStatus.completed
    assert step.report_file == "out/report.md"


# ---------------------------------------------------------------------------
# Full lifecycle: start → fail
# ---------------------------------------------------------------------------


def test_full_step_lifecycle_start_fail(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session)
    step = make_step(db_session, status=StepStatus.pending)

    runner = CliRunner()

    result = invoke(runner, ["step-start", "I-00001", "--step", "S01"], cli_get_session)
    assert result.exit_code == 0

    result = invoke(
        runner,
        ["step-fail", "I-00001", "--step", "S01", "--reason", "Agent crashed"],
        cli_get_session,
    )
    assert result.exit_code == 0

    db_session.refresh(step)
    assert step.status == StepStatus.failed
