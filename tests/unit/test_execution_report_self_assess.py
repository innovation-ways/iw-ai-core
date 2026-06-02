"""Unit tests for self_assessment data loading in execution reports.

Uses mocked DB sessions (no testcontainers) following the existing pattern in
tests/unit/test_execution_report_assembly.py.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from orch.self_assess import SelfAssessmentData

# Import the functions under test
from orch.daemon.execution_report import (
    _load_self_assessment,
    assemble_execution_report,
)
from orch.db.models import (
    RunStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)
from orch.self_assess import SelfAssessmentData

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def make_mock_work_item(
    work_item_id: str = "F-00055",
    project_id: str = "test-proj",
    status: WorkItemStatus = WorkItemStatus.completed,
    title: str = "Test Feature",
) -> WorkItem:
    """Return make mock work item."""
    item = MagicMock(spec=WorkItem)
    item.project_id = project_id
    item.id = work_item_id
    item.title = title
    item.type = WorkItemType.Feature
    item.status = status
    item.phase = WorkItemPhase.active
    return item


def make_mock_workflow_step(
    step_id: str = "S01",
    step_number: int = 1,
    step_type: StepType = StepType.self_assess,
    step_label: str | None = "SelfAssess",
    agent_label: str = "SelfAssess",
) -> WorkflowStep:
    """Return make mock workflow step."""
    step = MagicMock(spec=WorkflowStep)
    step.id = 1
    step.step_id = step_id
    step.step_number = step_number
    step.step_type = step_type
    step.step_label = step_label
    step.agent_label = agent_label
    step.opencode_agent = "self-assess-impl"
    return step


def make_mock_step_run(
    step_db_id: int,
    run_number: int = 1,
    status: RunStatus = RunStatus.completed,
    report_file: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> MagicMock:
    """Return make mock step run."""
    run = MagicMock()
    run.step_id = step_db_id
    run.run_number = run_number
    run.status = status
    run.report_file = report_file
    run.started_at = started_at
    run.completed_at = completed_at
    run.error_message = None
    run.duration_secs = 30.0
    return run


# ---------------------------------------------------------------------------
# Tests for _load_self_assessment
# ---------------------------------------------------------------------------

SAMPLE_FINDINGS_JSON = json.dumps(
    {
        "narrative_md": "# Self-Assessment Narrative\n\nThis item had process issues.",
        "bottom_line": "The step completed with some areas for improvement.",
        "coverage_notes": "All step logs were read in full.",
        "findings": [
            {
                "severity": "HIGH",
                "class": "Process",
                "target": "iw-ai-core",
                "title": "Agent re-reads the same files repeatedly",
                "recommendation": "Add a log-summarisation step to reduce redundant I/O",
                "paste_prompt": "/iw-new-incident title='Agent re-reads same files'",
                "evidence": [],
                "effort": "medium",
            },
            {
                "severity": "MED",
                "class": "Process",
                "target": "project",
                "title": "Manifest did not include a verification step",
                "recommendation": "Add a qv-gate step to catch regressions earlier",
                "paste_prompt": "/iw-new-cr title='Add verification step to manifest'",
                "evidence": [],
                "effort": "low",
            },
            {
                "severity": "LOW",
                "class": "Process",
                "target": "iw-ai-core",
                "title": "Step timing telemetry is incomplete",
                "recommendation": "Emit a completed_at timestamp for every step run",
                "paste_prompt": "/iw-new-incident title='Step timing gaps'",
                "evidence": [],
            },
        ],
    }
)


class TestLoadSelfAssessment:
    """Tests for _load_self_assessment using mocked sessions and tmp_path."""

    def test_no_self_assess_step_returns_none(self, tmp_path: Path) -> None:
        """When no self_assess step exists, _load_self_assessment returns None."""
        steps = [make_mock_workflow_step(step_type=StepType.implementation)]
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = _load_self_assessment(mock_session, steps, "test-proj", "F-00055")
        assert result is None

    def test_self_assess_step_with_no_runs_returns_none(self) -> None:
        """A self_assess step with no StepRun rows returns None."""
        steps = [make_mock_workflow_step(step_type=StepType.self_assess)]
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = _load_self_assessment(mock_session, steps, "test-proj", "F-00055")
        assert result is None

    def test_self_assess_run_with_no_report_file_returns_none(self) -> None:
        """A self_assess step run with null report_file returns None."""
        steps = [make_mock_workflow_step(step_type=StepType.self_assess)]
        mock_run = make_mock_step_run(step_db_id=1, report_file=None)
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_run

        result = _load_self_assessment(mock_session, steps, "test-proj", "F-00055")
        assert result is None

    def test_self_assess_run_with_pending_status_returns_none(self) -> None:
        """A self_assess step run with pending/running status returns None."""
        steps = [make_mock_workflow_step(step_type=StepType.self_assess)]
        mock_run = make_mock_step_run(
            step_db_id=1,
            status=RunStatus.running,
            report_file="/some/path.md",
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_run

        result = _load_self_assessment(mock_session, steps, "test-proj", "F-00055")
        assert result is None

    def test_findings_json_parsed_correctly(self, tmp_path: Path) -> None:
        """With a valid findings JSON on disk, findings are parsed and returned."""
        # Create the sidecar files
        report_file = tmp_path / "F-00055_self_assess_report.md"
        report_file.write_text("# Narrative content", encoding="utf-8")
        findings_file = tmp_path / "F-00055_self_assess_findings.json"
        findings_file.write_text(SAMPLE_FINDINGS_JSON, encoding="utf-8")

        steps = [make_mock_workflow_step(step_type=StepType.self_assess)]
        mock_run = make_mock_step_run(
            step_db_id=1,
            status=RunStatus.completed,
            report_file=str(report_file),
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_run

        result = _load_self_assessment(mock_session, steps, "test-proj", "F-00055")

        assert result is not None
        assert isinstance(result, SelfAssessmentData)
        assert len(result.findings) == 3
        assert result.narrative_md is not None
        assert result.bottom_line is not None
        assert result.coverage_notes is not None

        # Verify sorting: HIGH → MED → LOW
        severities = [f.severity for f in result.findings]
        assert severities == ["HIGH", "MED", "LOW"]

    def test_findings_json_missing_returns_empty_findings_with_narrative(
        self, tmp_path: Path
    ) -> None:
        """When findings JSON is absent but report file exists, narrative is preserved."""
        report_file = tmp_path / "F-00055_self_assess_report.md"
        report_file.write_text("# Only narrative here", encoding="utf-8")

        steps = [make_mock_workflow_step(step_type=StepType.self_assess)]
        mock_run = make_mock_step_run(
            step_db_id=1,
            status=RunStatus.completed,
            report_file=str(report_file),
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_run

        result = _load_self_assessment(mock_session, steps, "test-proj", "F-00055")

        assert result is not None
        assert result.narrative_md == "# Only narrative here"
        assert result.findings == []

    def test_malformed_findings_json_returns_empty_findings_with_narrative(
        self, tmp_path: Path
    ) -> None:
        """When findings JSON is malformed, narrative is preserved with empty findings list."""
        report_file = tmp_path / "F-00055_self_assess_report.md"
        report_file.write_text("# Narrative", encoding="utf-8")
        findings_file = tmp_path / "F-00055_self_assess_findings.json"
        findings_file.write_text("{ this is not json }", encoding="utf-8")

        steps = [make_mock_workflow_step(step_type=StepType.self_assess)]
        mock_run = make_mock_step_run(
            step_db_id=1,
            status=RunStatus.completed,
            report_file=str(report_file),
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_run

        result = _load_self_assessment(mock_session, steps, "test-proj", "F-00055")

        assert result is not None
        assert result.narrative_md == "# Narrative"
        assert result.findings == []

    def test_disk_narrative_used_when_findings_json_omits_narrative_md(
        self, tmp_path: Path
    ) -> None:
        """The iw-item-analyze skill writes the narrative to the .md file and omits
        narrative_md from the JSON. The loader must still surface the disk narrative.
        """
        report_file = tmp_path / "I-00066_self_assess_report.md"
        report_file.write_text("# Item Analysis: I-00066\n\nClean run.", encoding="utf-8")
        findings_file = tmp_path / "I-00066_self_assess_findings.json"
        findings_file.write_text(
            json.dumps(
                {
                    "item_id": "I-00066",
                    "bottom_line": "Item ran cleanly.",
                    "coverage_notes": "DB UP.",
                    "findings": [],
                }
            ),
            encoding="utf-8",
        )

        steps = [make_mock_workflow_step(step_type=StepType.self_assess)]
        mock_run = make_mock_step_run(
            step_db_id=1,
            status=RunStatus.completed,
            report_file=str(report_file),
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_run

        result = _load_self_assessment(mock_session, steps, "test-proj", "I-00066")

        assert result is not None
        assert result.bottom_line == "Item ran cleanly."
        assert result.findings == []
        assert result.narrative_md == "# Item Analysis: I-00066\n\nClean run."

    def test_report_file_not_on_disk_still_parses_findings(self, tmp_path: Path) -> None:
        """When the report file is missing but findings JSON exists, findings are still parsed."""
        # Create the findings file at the path that findings_path_for derives
        # from the report_file (F-00055_report.md -> F-00055_findings.json)
        report_file = tmp_path / "F-00055_report.md"  # derives to F-00055_findings.json
        findings_file = tmp_path / "F-00055_findings.json"
        findings_file.write_text(SAMPLE_FINDINGS_JSON, encoding="utf-8")
        # report_file itself does NOT exist

        steps = [make_mock_workflow_step(step_type=StepType.self_assess)]
        mock_run = make_mock_step_run(
            step_db_id=1,
            status=RunStatus.completed,
            report_file=str(report_file),
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_run

        result = _load_self_assessment(mock_session, steps, "test-proj", "F-00055")

        assert result is not None
        # Findings should still be parsed since findings JSON exists
        assert len(result.findings) == 3

    def test_canonical_sidecar_used_when_framework_path_differs(self, tmp_path: Path) -> None:
        """Real-world I-00067 case: report_file follows the framework's per-step
        naming (``<ID>_S<NN>_<AgentName>_report.md``), but iw-item-analyze writes
        its findings to the canonical ``<ID>_self_assess_findings.json``. The
        loader must locate the canonical sidecar even though
        ``findings_path_for(report_file)`` derives a different path that does
        not exist.
        """
        # Framework per-step report (what StepRun.report_file actually points to)
        framework_report = tmp_path / "I-00067_S06_SelfAssess_report.md"
        framework_report.write_text("# Framework agent report", encoding="utf-8")
        # findings_path_for would derive I-00067_S06_SelfAssess_findings.json — DOESN'T exist.

        # Canonical iw-item-analyze outputs (sibling files in the same dir).
        # Real iw-item-analyze omits narrative_md from the JSON — it lives
        # in the sibling .md file. Use the same shape here.
        canonical_narrative = tmp_path / "I-00067_self_assess_report.md"
        canonical_narrative.write_text(
            "### Item Analysis: I-00067\n\nBottom line: real narrative here.",
            encoding="utf-8",
        )
        canonical_findings = tmp_path / "I-00067_self_assess_findings.json"
        canonical_findings.write_text(
            json.dumps(
                {
                    "bottom_line": "real narrative here.",
                    "findings": json.loads(SAMPLE_FINDINGS_JSON)["findings"],
                }
            ),
            encoding="utf-8",
        )

        steps = [make_mock_workflow_step(step_type=StepType.self_assess)]
        mock_run = make_mock_step_run(
            step_db_id=1,
            status=RunStatus.completed,
            report_file=str(framework_report),
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_run

        result = _load_self_assessment(mock_session, steps, "test-proj", "I-00067")

        assert result is not None
        # Findings come from the canonical sidecar
        assert len(result.findings) == 3
        # Narrative comes from the canonical narrative file (preferred over framework report)
        assert result.narrative_md is not None
        assert "real narrative here" in result.narrative_md
        assert "Framework agent report" not in result.narrative_md


class TestAssembleExecutionReportWithSelfAssessment:
    """Integration of self_assessment into assemble_execution_report via RED-GREEN cycle."""

    def test_assemble_with_self_assess_step_and_findings(self, tmp_path: Path) -> None:
        """RED: assemble_execution_report should populate self_assessment when findings exist."""
        item = make_mock_work_item(status=WorkItemStatus.completed)
        step = make_mock_workflow_step(step_id="S03", step_number=3, step_type=StepType.self_assess)

        report_file = tmp_path / "F-00055_self_assess_report.md"
        report_file.write_text("# Step narrative", encoding="utf-8")
        findings_file = tmp_path / "F-00055_self_assess_findings.json"
        findings_file.write_text(SAMPLE_FINDINGS_JSON, encoding="utf-8")

        mock_run = make_mock_step_run(
            step_db_id=step.id,
            status=RunStatus.completed,
            report_file=str(report_file),
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
        )

        mock_session = MagicMock()
        mock_session.get.return_value = item

        # Mock execute for steps query, step_runs query, fix_cycles query, and latest_run
        mock_steps_result = MagicMock()
        mock_steps_result.scalars.return_value.all.return_value = [step]
        mock_runs_result = MagicMock()
        mock_runs_result.scalars.return_value.all.return_value = [mock_run]
        mock_cycles_result = MagicMock()
        mock_cycles_result.scalars.return_value.all.return_value = []
        mock_latest_run_result = MagicMock()
        mock_latest_run_result.scalar_one_or_none.return_value = mock_run

        mock_session.execute.side_effect = [
            mock_steps_result,  # steps query
            mock_runs_result,  # step_runs query
            mock_cycles_result,  # fix_cycles query
            mock_latest_run_result,  # latest run for self_assess
        ]

        data = assemble_execution_report(mock_session, "test-proj", "F-00055")

        # GREEN: verify self_assessment is populated
        assert data.self_assessment is not None
        assert len(data.self_assessment.findings) == 3
        assert data.self_assessment.narrative_md is not None

    def test_assemble_without_self_assess_step(self) -> None:
        """No self_assess step: self_assessment must be None (no crash)."""
        item = make_mock_work_item(status=WorkItemStatus.completed)
        step = make_mock_workflow_step(
            step_id="S01", step_number=1, step_type=StepType.implementation
        )

        mock_session = MagicMock()
        mock_session.get.return_value = item
        mock_steps_result = MagicMock()
        mock_steps_result.scalars.return_value.all.return_value = [step]
        mock_runs_result = MagicMock()
        mock_runs_result.scalars.return_value.all.return_value = []
        mock_cycles_result = MagicMock()
        mock_cycles_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [
            mock_steps_result,
            mock_runs_result,
            mock_cycles_result,
        ]

        data = assemble_execution_report(mock_session, "test-proj", "F-00055")

        # REFACTOR: self_assessment is None when there's no self_assess step
        assert data.self_assessment is None

    def test_assemble_self_assess_step_skipped(self) -> None:
        """A self_assess step with no runs (skipped): self_assessment is None."""
        item = make_mock_work_item(status=WorkItemStatus.completed)
        step = make_mock_workflow_step(step_id="S03", step_number=3, step_type=StepType.self_assess)

        mock_session = MagicMock()
        mock_session.get.return_value = item
        mock_steps_result = MagicMock()
        mock_steps_result.scalars.return_value.all.return_value = [step]
        mock_runs_result = MagicMock()
        mock_runs_result.scalars.return_value.all.return_value = []
        mock_cycles_result = MagicMock()
        mock_cycles_result.scalars.return_value.all.return_value = []
        mock_latest_run_result = MagicMock()
        mock_latest_run_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [
            mock_steps_result,
            mock_runs_result,
            mock_cycles_result,
            mock_latest_run_result,
        ]

        data = assemble_execution_report(mock_session, "test-proj", "F-00055")

        assert data.self_assessment is None

    def test_assemble_self_assess_failed_step_still_renders(self, tmp_path: Path) -> None:
        """A self_assess step that failed still populates self_assessment (soft-step)."""
        item = make_mock_work_item(status=WorkItemStatus.completed)
        step = make_mock_workflow_step(step_id="S03", step_number=3, step_type=StepType.self_assess)

        report_file = tmp_path / "F-00055_self_assess_report.md"
        report_file.write_text("# Failed run narrative", encoding="utf-8")
        findings_file = tmp_path / "F-00055_self_assess_findings.json"
        findings_file.write_text(SAMPLE_FINDINGS_JSON, encoding="utf-8")

        mock_run = make_mock_step_run(
            step_db_id=step.id,
            status=RunStatus.failed,  # step failed but item still proceeds
            report_file=str(report_file),
        )
        mock_session = MagicMock()
        mock_session.get.return_value = item
        mock_steps_result = MagicMock()
        mock_steps_result.scalars.return_value.all.return_value = [step]
        mock_runs_result = MagicMock()
        mock_runs_result.scalars.return_value.all.return_value = [mock_run]
        mock_cycles_result = MagicMock()
        mock_cycles_result.scalars.return_value.all.return_value = []
        mock_latest_run_result = MagicMock()
        mock_latest_run_result.scalar_one_or_none.return_value = mock_run

        mock_session.execute.side_effect = [
            mock_steps_result,
            mock_runs_result,
            mock_cycles_result,
            mock_latest_run_result,
        ]

        data = assemble_execution_report(mock_session, "test-proj", "F-00055")

        # Even with failed status, self_assessment should be populated
        assert data.self_assessment is not None
        assert len(data.self_assessment.findings) == 3
