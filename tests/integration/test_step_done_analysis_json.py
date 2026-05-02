"""Integration tests for `iw step-done --analysis-json` flag handling.

AC7: the flag is accepted for self_assess steps and rejected for other
step types; same-parent-dir validation is enforced.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click
from click.testing import CliRunner

from orch.cli.step_commands import step_done
from orch.db.models import (
    Project,
    RunStatus,
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
# Helpers
# ---------------------------------------------------------------------------


def make_work_item(db: Session, item_id: str = "F-00001") -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Feature,
        title="Test Item",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


def make_step(
    db: Session,
    item_id: str,
    step_id: str,
    step_type: StepType,
    status: StepStatus = StepStatus.in_progress,
) -> WorkflowStep:
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_id=step_id,
        step_number=int(step_id[1:]),
        agent_label="TestAgent",
        step_type=step_type,
        status=status,
    )
    db.add(step)
    db.flush()
    return step


def make_step_run(db: Session, step: WorkflowStep) -> None:
    from orch.db.models import StepRun

    step_run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.running,
    )
    db.add(step_run)
    db.flush()


def _make_get_session(db: Session):
    """Return a get_session factory for the CLI context."""
    from contextlib import contextmanager

    @contextmanager
    def _get_session():
        yield db

    return _get_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStepDoneAnalysisJsonFlag:
    """AC7: --analysis-json flag validation on `iw step-done`."""

    def test_flag_accepted_for_self_assess(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """--analysis-json is accepted when step_type is self_assess."""
        item = make_work_item(db_session, "F-00001")
        step = make_step(
            db_session,
            "F-00001",
            "S02",
            step_type=StepType.self_assess,
            status=StepStatus.in_progress,
        )
        make_step_run(db_session, step)

        # Create the sidecar files
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        report_file = reports_dir / "F-00001_self_assess_report.md"
        report_file.write_text("# Narrative", encoding="utf-8")
        findings_file = reports_dir / "F-00001_self_assess_findings.json"
        findings_file.write_text('{"findings":[]}', encoding="utf-8")

        runner = CliRunner()

        @click.command("step-done")
        @click.pass_context
        def cmd(
            ctx,
            item_id=item.id,
            step_id="S02",
            report=str(report_file),
            analysis_json=str(findings_file),
        ):
            ctx.obj = {
                "get_session": _make_get_session(db_session),
                "json": False,
                "project_id": test_project.id,
            }
            return step_done.callback(
                item_id=item_id,
                step_id=step_id,
                report_path=report,
                analysis_json_path=analysis_json,
            )

        result = runner.invoke(cmd, standalone_mode=False)
        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

    def test_flag_rejected_for_implementation_step(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """--analysis-json raises UsageError when step_type is not self_assess."""
        item = make_work_item(db_session, "F-00001")
        step = make_step(
            db_session,
            "F-00001",
            "S01",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
        )
        make_step_run(db_session, step)

        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        report_file = reports_dir / "F-00001_report.md"
        report_file.write_text("# Report", encoding="utf-8")
        findings_file = reports_dir / "F-00001_findings.json"
        findings_file.write_text('{"findings":[]}', encoding="utf-8")

        runner = CliRunner()

        @click.command("step-done")
        @click.pass_context
        def cmd(
            ctx,
            item_id=item.id,
            step_id="S01",
            report=str(report_file),
            analysis_json=str(findings_file),
        ):
            ctx.obj = {
                "get_session": _make_get_session(db_session),
                "json": False,
                "project_id": test_project.id,
            }
            return step_done.callback(
                item_id=item_id,
                step_id=step_id,
                report_path=report,
                analysis_json_path=analysis_json,
            )

        result = runner.invoke(cmd, standalone_mode=False)
        assert result.exit_code != 0, (
            f"Expected non-zero exit for implementation step, got {result.exit_code}"
        )

    def test_flag_rejected_for_code_review_step(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """--analysis-json is rejected for code_review step_type."""
        item = make_work_item(db_session, "F-00001")
        step = make_step(
            db_session,
            "F-00001",
            "S03",
            step_type=StepType.code_review,
            status=StepStatus.in_progress,
        )
        make_step_run(db_session, step)

        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        report_file = reports_dir / "F-00001_report.md"
        findings_file = reports_dir / "F-00001_findings.json"
        findings_file.write_text('{"findings":[]}', encoding="utf-8")

        runner = CliRunner()

        @click.command("step-done")
        @click.pass_context
        def cmd(
            ctx,
            item_id=item.id,
            step_id="S03",
            report=str(report_file),
            analysis_json=str(findings_file),
        ):
            ctx.obj = {
                "get_session": _make_get_session(db_session),
                "json": False,
                "project_id": test_project.id,
            }
            return step_done.callback(
                item_id=item_id,
                step_id=step_id,
                report_path=report,
                analysis_json_path=analysis_json,
            )

        result = runner.invoke(cmd, standalone_mode=False)
        assert result.exit_code != 0

    def test_analysis_json_requires_report_flag(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """--analysis-json without --report raises UsageError."""
        item = make_work_item(db_session, "F-00001")
        step = make_step(
            db_session,
            "F-00001",
            "S02",
            step_type=StepType.self_assess,
            status=StepStatus.in_progress,
        )
        make_step_run(db_session, step)

        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        findings_file = reports_dir / "F-00001_self_assess_findings.json"
        findings_file.write_text('{"findings":[]}', encoding="utf-8")

        runner = CliRunner()

        @click.command("step-done")
        @click.pass_context
        def cmd(ctx, item_id=item.id, step_id="S02", analysis_json=str(findings_file)):
            ctx.obj = {
                "get_session": _make_get_session(db_session),
                "json": False,
                "project_id": test_project.id,
            }
            return step_done.callback(
                item_id=item_id,
                step_id=step_id,
                report_path=None,
                analysis_json_path=analysis_json,
            )

        result = runner.invoke(cmd, standalone_mode=False)
        assert result.exit_code != 0

    def test_analysis_json_must_be_same_directory_as_report(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """--analysis-json in different directory raises UsageError."""
        item = make_work_item(db_session, "F-00001")
        step = make_step(
            db_session,
            "F-00001",
            "S02",
            step_type=StepType.self_assess,
            status=StepStatus.in_progress,
        )
        make_step_run(db_session, step)

        dir_a = tmp_path / "dir_a"
        dir_b = tmp_path / "dir_b"
        dir_a.mkdir()
        dir_b.mkdir()
        report_file = dir_a / "F-00001_self_assess_report.md"
        report_file.write_text("# Narrative", encoding="utf-8")
        findings_file = dir_b / "F-00001_self_assess_findings.json"
        findings_file.write_text('{"findings":[]}', encoding="utf-8")

        runner = CliRunner()

        @click.command("step-done")
        @click.pass_context
        def cmd(
            ctx,
            item_id=item.id,
            step_id="S02",
            report=str(report_file),
            analysis_json=str(findings_file),
        ):
            ctx.obj = {
                "get_session": _make_get_session(db_session),
                "json": False,
                "project_id": test_project.id,
            }
            return step_done.callback(
                item_id=item_id,
                step_id=step_id,
                report_path=report,
                analysis_json_path=analysis_json,
            )

        result = runner.invoke(cmd, standalone_mode=False)
        assert result.exit_code != 0, (
            f"Expected non-zero exit, got {result.exit_code}: {result.output}"
        )
