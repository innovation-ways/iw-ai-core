"""Integration tests for execution report auto-generation with real DB.

Uses testcontainers PostgreSQL to test assemble_execution_report and
write_execution_report with seeded data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from orch.daemon.execution_report import (
    assemble_execution_report,
    render_execution_report_markdown,
)
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
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestExecutionReportAutoGeneration:
    """Integration tests for report auto-generation using seeded DB data."""

    @pytest.fixture
    def db_session_with_schema(self, db_session: Session) -> Session:
        return db_session

    def _seed_work_item(
        self, session: Session, project_id: str
    ) -> tuple[WorkItem, list[WorkflowStep], list[StepRun]]:
        item = WorkItem(
            project_id=project_id,
            id="F-00056",
            type=WorkItemType.Feature,
            title="Test Feature for Auto-Generation",
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.done,
            config={},
            depends_on=[],
            blocks=[],
        )
        session.add(item)
        session.flush()

        steps = []
        all_runs = []

        step1 = WorkflowStep(
            project_id=project_id,
            work_item_id="F-00056",
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        session.add(step1)
        session.flush()
        steps.append(step1)

        step2 = WorkflowStep(
            project_id=project_id,
            work_item_id="F-00056",
            step_number=2,
            step_id="S02",
            agent_label="Tests",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        session.add(step2)
        session.flush()
        steps.append(step2)

        step3 = WorkflowStep(
            project_id=project_id,
            work_item_id="F-00056",
            step_number=3,
            step_id="S03",
            agent_label="Code Review",
            step_type=StepType.code_review,
            status=StepStatus.completed,
        )
        session.add(step3)
        session.flush()
        steps.append(step3)

        for run_num in [1, 2, 3]:
            run = StepRun(
                step_id=step1.id,
                run_number=run_num,
                status=RunStatus.completed if run_num == 3 else RunStatus.failed,
                started_at=datetime(2025, 1, 1, 10 + run_num - 1, 0, 0, tzinfo=UTC),
                completed_at=datetime(2025, 1, 1, 10 + run_num - 1, 5, 0, tzinfo=UTC),
                duration_secs=300.0,
            )
            session.add(run)
            all_runs.append(run)

        for run_num in [1, 2]:
            run = StepRun(
                step_id=step2.id,
                run_number=run_num,
                status=RunStatus.completed if run_num == 2 else RunStatus.failed,
                started_at=datetime(2025, 1, 1, 11, run_num * 5, 0, tzinfo=UTC),
                completed_at=datetime(2025, 1, 1, 11, run_num * 5 + 5, 0, tzinfo=UTC),
                duration_secs=300.0,
            )
            session.add(run)
            all_runs.append(run)

        run = StepRun(
            step_id=step3.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 12, 10, 0, tzinfo=UTC),
            duration_secs=600.0,
        )
        session.add(run)
        all_runs.append(run)

        session.flush()
        return item, steps, all_runs

    def _seed_fix_cycles(self, session: Session, steps: list[WorkflowStep]) -> None:
        step1, step2, _ = steps[0], steps[1], steps[2]

        cycle1 = FixCycle(
            step_id=step1.id,
            cycle_number=1,
            trigger_type=FixTrigger.code_review,
            status=FixStatus.completed,
            fix_summary="- Fixed SQL injection in user query\n- Added parameterized queries",
            trigger_report="/path/to/trigger1.md",
            fix_report="/path/to/fix1.md",
            started_at=datetime(2025, 1, 1, 10, 10, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 20, 0, tzinfo=UTC),
        )
        session.add(cycle1)

        cycle2 = FixCycle(
            step_id=step1.id,
            cycle_number=2,
            trigger_type=FixTrigger.code_review,
            status=FixStatus.completed,
            fix_summary="- Improved error handling",
            trigger_report="/path/to/trigger2.md",
            fix_report="/path/to/fix2.md",
            started_at=datetime(2025, 1, 1, 10, 25, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC),
        )
        session.add(cycle2)

        cycle3 = FixCycle(
            step_id=step2.id,
            cycle_number=1,
            trigger_type=FixTrigger.code_review,
            status=FixStatus.completed,
            fix_summary=None,
            trigger_report="/path/to/trigger3.md",
            fix_report=None,
            started_at=datetime(2025, 1, 1, 11, 15, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 11, 25, 0, tzinfo=UTC),
        )
        session.add(cycle3)

        session.flush()

    def test_assemble_execution_report_with_seeded_data(
        self, db_session: Session, test_project: Project
    ) -> None:
        item, steps, _ = self._seed_work_item(db_session, test_project.id)
        self._seed_fix_cycles(db_session, steps)

        data = assemble_execution_report(db_session, test_project.id, "F-00056")

        assert data.work_item_id == "F-00056"
        assert data.verdict == "completed"
        assert len(data.steps) == 3

        step_ids = [s.step_id for s in data.steps]
        assert "S01" in step_ids
        assert "S02" in step_ids
        assert "S03" in step_ids

        hotspot_steps = [s.step_id for s in data.steps if s.is_hotspot]
        assert "S01" in hotspot_steps
        assert "S02" in hotspot_steps

    def test_assemble_execution_report_hotspot_detection(
        self, db_session: Session, test_project: Project
    ) -> None:
        item, steps, _ = self._seed_work_item(db_session, test_project.id)
        self._seed_fix_cycles(db_session, steps)

        data = assemble_execution_report(db_session, test_project.id, "F-00056")

        hotspots_by_step = {h.step_id: h for h in data.hotspots}
        assert "S01" in hotspots_by_step
        assert "S02" in hotspots_by_step
        assert hotspots_by_step["S01"].retry_count == 3
        assert hotspots_by_step["S02"].retry_count == 2

    def test_render_markdown_with_seeded_data(
        self, db_session: Session, test_project: Project
    ) -> None:
        item, steps, _ = self._seed_work_item(db_session, test_project.id)
        self._seed_fix_cycles(db_session, steps)

        data = assemble_execution_report(db_session, test_project.id, "F-00056")
        md = render_execution_report_markdown(data)

        assert "# Execution Report: F-00056" in md
        assert "## Retry Hotspots" in md
        assert "## Step Timeline" in md
        assert "## Fix Cycles" in md
        assert "---" in md

    def test_null_fix_summary_renders_placeholder(
        self, db_session: Session, test_project: Project
    ) -> None:
        item, steps, _ = self._seed_work_item(db_session, test_project.id)
        self._seed_fix_cycles(db_session, steps)

        data = assemble_execution_report(db_session, test_project.id, "F-00056")
        md = render_execution_report_markdown(data)

        assert "> _no fix summary captured (pre-F-00056)_" in md

    def test_multi_line_fix_summary_renders_blockquote(
        self, db_session: Session, test_project: Project
    ) -> None:
        item, steps, _ = self._seed_work_item(db_session, test_project.id)
        self._seed_fix_cycles(db_session, steps)

        data = assemble_execution_report(db_session, test_project.id, "F-00056")
        md = render_execution_report_markdown(data)

        assert "> - Fixed SQL injection in user query" in md
        assert "> - Added parameterized queries" in md

    def test_hotspots_sorted_by_retry_count_desc(
        self, db_session: Session, test_project: Project
    ) -> None:
        item, steps, _ = self._seed_work_item(db_session, test_project.id)
        self._seed_fix_cycles(db_session, steps)

        data = assemble_execution_report(db_session, test_project.id, "F-00056")

        assert len(data.hotspots) == 2
        assert data.hotspots[0].retry_count >= data.hotspots[1].retry_count

    def test_write_execution_report_creates_file(
        self, db_session: Session, test_project: Project, tmp_path: pytest.TempPathFactory
    ) -> None:
        item, steps, _ = self._seed_work_item(db_session, test_project.id)
        self._seed_fix_cycles(db_session, steps)

        active_dir = tmp_path / "ai-dev" / "active" / "F-00056"
        active_dir.mkdir(parents=True, exist_ok=True)

        project = db_session.get(Project, test_project.id)
        original_repo_root = project.repo_root
        project.repo_root = str(tmp_path)

        try:
            data = assemble_execution_report(db_session, test_project.id, "F-00056")
            md = render_execution_report_markdown(data)

            report_file = active_dir / "F-00056_execution_report.md"
            report_file.write_text(md, encoding="utf-8")

            assert report_file.exists()
            content = report_file.read_text(encoding="utf-8")
            assert len(content) > 0
            assert "# Execution Report: F-00056" in content
        finally:
            project.repo_root = original_repo_root

    def test_zero_step_runs_item_not_started_verdict(
        self, db_session: Session, test_project: Project
    ) -> None:
        item = WorkItem(
            project_id=test_project.id,
            id="F-00057",
            type=WorkItemType.Feature,
            title="Empty Feature",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        db_session.flush()

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id="F-00057",
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.pending,
        )
        db_session.add(step)
        db_session.flush()

        data = assemble_execution_report(db_session, test_project.id, "F-00057")
        assert data.verdict == "not_started"
        assert data.steps[0].runs == []

    def test_assemble_unknown_item_raises_value_error(
        self, db_session: Session, test_project: Project
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            assemble_execution_report(db_session, test_project.id, "F-DOES-NOT-EXIST")

    def test_report_file_path_resolution_active_dir(
        self, db_session: Session, test_project: Project, tmp_path: pytest.TempPathFactory
    ) -> None:
        active_dir = tmp_path / "ai-dev" / "active" / "F-00058"
        active_dir.mkdir(parents=True, exist_ok=True)

        project = db_session.get(Project, test_project.id)
        original_repo_root = project.repo_root
        project.repo_root = str(tmp_path)

        try:
            item = WorkItem(
                project_id=test_project.id,
                id="F-00058",
                type=WorkItemType.Feature,
                title="Test Path Resolution",
                status=WorkItemStatus.completed,
                phase=WorkItemPhase.done,
                config={},
                depends_on=[],
                blocks=[],
            )
            db_session.add(item)
            db_session.flush()

            step = WorkflowStep(
                project_id=test_project.id,
                work_item_id="F-00058",
                step_number=1,
                step_id="S01",
                agent_label="Backend",
                step_type=StepType.implementation,
                status=StepStatus.completed,
            )
            db_session.add(step)
            db_session.flush()

            run = StepRun(
                step_id=step.id,
                run_number=1,
                status=RunStatus.completed,
                started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
                completed_at=datetime(2025, 1, 1, 10, 5, 0, tzinfo=UTC),
                duration_secs=300.0,
            )
            db_session.add(run)
            db_session.flush()

            data = assemble_execution_report(db_session, test_project.id, "F-00058")
            md = render_execution_report_markdown(data)
            report_file = active_dir / "F-00058_execution_report.md"
            report_file.write_text(md, encoding="utf-8")

            assert report_file.exists()
        finally:
            project.repo_root = original_repo_root
