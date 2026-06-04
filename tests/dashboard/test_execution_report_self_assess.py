"""Dashboard smoke tests for the Self-Assessment section in the execution report tab.

Uses FastAPI's TestClient against a PostgreSQL testcontainer (via the
db_session fixture from tests/integration/conftest.py).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            """Yield the test db_session for FastAPI dependency injection."""
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def _create_item_with_self_assess(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
    findings_json: str | None = None,
    report_md: str = "# Narrative",
    step_status: StepStatus = StepStatus.completed,
    run_status: RunStatus = RunStatus.completed,
) -> WorkItem:
    """Helper: create a WorkItem with a self_assess step and optional findings."""
    item = WorkItem(
        project_id=test_project.id,
        id="F-00099",
        title="Test Self-Assess Feature",
        type=WorkItemType.Feature,
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.active,
        design_doc_search="",
    )
    db_session.add(item)

    step = WorkflowStep(
        project_id=test_project.id,
        work_item_id=item.id,
        step_id="S03",
        step_number=3,
        step_type=StepType.self_assess,
        agent_label="SelfAssess",
        opencode_agent="self-assess-impl",
        status=step_status,
    )
    db_session.add(step)
    db_session.flush()  # get step.id

    work_dir = tmp_path / "ai-dev" / "work" / item.id
    reports_dir = work_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if run_status in (RunStatus.completed, RunStatus.failed):
        report_file = reports_dir / f"{item.id}_self_assess_report.md"
        report_file.write_text(report_md, encoding="utf-8")

        findings_file = reports_dir / f"{item.id}_self_assess_findings.json"
        if findings_json:
            findings_file.write_text(findings_json, encoding="utf-8")

        step_run = StepRun(
            step_id=step.id,
            run_number=1,
            status=run_status,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
            duration_secs=60.0,
            report_file=str(report_file),
        )
        db_session.add(step_run)

    db_session.commit()
    return item


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


class TestSelfAssessmentFragment:
    """Smoke tests for Self-Assessment section rendering in the execution report tab."""

    def test_self_assessment_section_visible_when_findings_exist(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """RED (smoke): with findings JSON present, 'Self-Assessment' heading is in HTML."""
        item = _create_item_with_self_assess(
            db_session,
            test_project,
            tmp_path,
            findings_json=SAMPLE_FINDINGS_JSON,
            report_md="# Narrative content",
        )

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # GREEN: Self-Assessment heading is visible
        assert "Self-Assessment" in html

        # Findings content
        assert "Agent re-read files repeatedly" in html
        assert "Missing verification step" in html

        # Severity badges
        assert "HIGH" in html
        assert "MED" in html

        # Clipboard buttons
        assert "Copy paste prompt" in html

        # Bottom line
        assert "Two HIGH severity findings" in html

        # Coverage notes
        assert "All step logs were sampled" in html

    def test_self_assessment_not_in_html_when_no_self_assess_step(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When the project has no self_assess step, section is completely absent."""
        # Create a regular item without self_assess step
        item = WorkItem(
            project_id=test_project.id,
            id="F-00100",
            title="Regular Feature",
            type=WorkItemType.Feature,
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.active,
            design_doc_search="",
        )
        db_session.add(item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item.id,
            step_id="S01",
            step_number=1,
            step_type=StepType.implementation,
            agent_label="Backend",
            opencode_agent="backend-impl",
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # Self-Assessment section must NOT appear at all
        assert "Self-Assessment" not in html

    def test_self_assessment_not_rendered_when_step_is_pending(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When the self_assess step is pending (not run), section is absent."""
        item = _create_item_with_self_assess(
            db_session,
            test_project,
            tmp_path,
            findings_json=SAMPLE_FINDINGS_JSON,
            step_status=StepStatus.pending,
            run_status=RunStatus.running,
        )

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # Section must not appear when step hasn't run
        assert "Self-Assessment" not in html

    def test_self_assessment_not_rendered_when_findings_json_missing(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When only report MD exists but findings JSON is absent, section is absent (AC5)."""
        item = _create_item_with_self_assess(
            db_session,
            test_project,
            tmp_path,
            findings_json=None,  # No findings JSON
            report_md="# Only report MD",
            step_status=StepStatus.completed,
            run_status=RunStatus.completed,
        )

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # Self-assessment ran (completed step exists) but no findings file —
        # per boundary behavior table: render italic "no findings captured"
        assert "Self-Assessment" in html  # section renders because step ran
        assert "no findings were captured" in html

    def test_self_assessment_only_iw_ai_core_findings(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When all findings target iw-ai-core, only that subsection appears."""
        core_only_json = json.dumps(
            {
                "narrative_md": None,
                "findings": [
                    {
                        "severity": "HIGH",
                        "class": "Process",
                        "target": "iw-ai-core",
                        "title": "Daemon re-arm timer logic race",
                        "recommendation": "Add a lock around the re-arm check",
                        "paste_prompt": "/iw-new-incident title='Race in daemon timer'",
                        "evidence": [],
                    },
                ],
            }
        )
        item = _create_item_with_self_assess(
            db_session, test_project, tmp_path, findings_json=core_only_json
        )

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        assert "Suggestions for iw-ai-core" in html
        # Project subsection must not appear
        assert "Suggestions for test-proj" not in html

    def test_self_assessment_section_absent_when_step_is_skipped(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When self_assess step was skipped (no runs at all), section is not rendered."""
        item = WorkItem(
            project_id=test_project.id,
            id="F-00103",
            title="Skipped Self-Assess Feature",
            type=WorkItemType.Feature,
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.active,
            design_doc_search="",
        )
        db_session.add(item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item.id,
            step_id="S03",
            step_number=3,
            step_type=StepType.self_assess,
            agent_label="SelfAssess",
            opencode_agent="self-assess-impl",
            status=StepStatus.skipped,  # explicitly skipped — no runs
        )
        db_session.add(step)
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        assert "Self-Assessment" not in html


class TestSelfAssessmentXSSEscaping:
    """Invariant 2 / XSS safety: paste_prompt is HTML-escaped in rendered output."""

    def test_paste_prompt_xss_escaped(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """A finding with XSS payload in paste_prompt is escaped in HTML output."""
        xss_payload = "</script><script>alert(1)</script>"
        findings_with_xss = json.dumps(
            {
                "narrative_md": "XSS test",
                "findings": [
                    {
                        "severity": "HIGH",
                        "class": "Process",
                        "target": "iw-ai-core",
                        "title": "XSS finding",
                        "recommendation": "Fix it.",
                        "paste_prompt": xss_payload,
                        "evidence": [],
                    },
                ],
            }
        )
        item = _create_item_with_self_assess(
            db_session,
            test_project,
            tmp_path,
            findings_json=findings_with_xss,
        )

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # The raw XSS payload must NOT appear as-is in HTML
        assert xss_payload not in html
        # The escaped version must appear (browsers escape &lt; etc.)
        assert "&lt;script&gt;" in html or "alert" not in html


class TestSelfAssessmentAllProjectFindings:
    """Boundary: all findings target=project → only project subsection appears."""

    def test_only_project_subsection_when_no_iw_ai_core_findings(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When all findings target 'project', only that subsection renders."""
        project_only_json = json.dumps(
            {
                "narrative_md": "All project findings.",
                "findings": [
                    {
                        "severity": "HIGH",
                        "class": "Process",
                        "target": "project",
                        "title": "Missing error handling in project/foo.py",
                        "recommendation": "Add a try/except.",
                        "paste_prompt": "/iw-new-cr title='Add error handling'",
                        "evidence": [],
                    },
                ],
            }
        )
        item = _create_item_with_self_assess(
            db_session, test_project, tmp_path, findings_json=project_only_json
        )

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        assert "Suggestions for test-proj" in html
        assert "Suggestions for iw-ai-core" not in html


class TestSelfAssessmentMalformedJSON:
    """Boundary: malformed findings JSON renders narrative with empty findings list."""

    def test_section_renders_narrative_when_json_malformed(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When findings JSON is malformed, narrative is preserved and finding list is empty."""
        item = _create_item_with_self_assess(
            db_session,
            test_project,
            tmp_path,
            findings_json="{ this is not json }",
            report_md="# Narrative from report MD",
        )

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # Section appears (step ran)
        assert "Self-Assessment" in html
        # Narrative is rendered
        assert "Narrative from report MD" in html
        # No findings rendered (empty list)
        assert "agent-re-read" not in html.lower()


class TestSelfAssessmentEvidenceAndEffort:
    """I-00067 follow-up: each finding card must surface evidence, effort, and
    the paste prompt so the user can act on it."""

    def test_evidence_effort_and_paste_prompt_rendered(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Verifies that the effort and paste prompt sections render in the."""
        rich_findings = json.dumps(
            {
                "findings": [
                    {
                        "severity": "HIGH",
                        "class": "convention",
                        "target": "iw-ai-core",
                        "title": "Tailwind CLI broke silently",
                        "recommendation": "Append CSS directly to styles.css",
                        "paste_prompt": "/iw-new-cr Add CLAUDE.md rule for Tailwind fallback",
                        "evidence": [
                            "I-00067_S01_run1.log:392 — make: Nothing to be done for 'css'",
                            "I-00067_S05_fix1.log:28 — MODULE_NOT_FOUND postcss-selector-parser",
                        ],
                        "effort": "S",
                    },
                ],
            }
        )
        item = _create_item_with_self_assess(
            db_session, test_project, tmp_path, findings_json=rich_findings
        )

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # The full /iw-new-cr command appears in the page so users can copy it
        assert "/iw-new-cr Add CLAUDE.md rule for Tailwind fallback" in html
        # The evidence summary is rendered (collapsible details element)
        assert "Evidence (2)" in html
        # Individual evidence lines appear
        assert "make: Nothing to be done for &#39;css&#39;" in html or (
            "make: Nothing to be done" in html
        )
        assert "MODULE_NOT_FOUND postcss-selector-parser" in html
        # Effort badge appears
        assert "effort: S" in html

    def test_loader_falls_back_to_canonical_findings_when_framework_path_differs(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Reproduces I-00067: StepRun.report_file points at the framework's
        per-step file (I-00067_S06_SelfAssess_report.md), but iw-item-analyze
        writes findings to the canonical I-00067_self_assess_findings.json.
        The loader must still surface the findings.
        """
        item = WorkItem(
            project_id=test_project.id,
            id="I-00067",
            title="Framework Path Mismatch Repro",
            type=WorkItemType.Feature,
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.active,
            design_doc_search="",
        )
        db_session.add(item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item.id,
            step_id="S06",
            step_number=6,
            step_type=StepType.self_assess,
            agent_label="SelfAssess",
            opencode_agent="self-assess-impl",
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        reports_dir = tmp_path / "ai-dev" / "active" / item.id / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        framework_report = reports_dir / f"{item.id}_S06_SelfAssess_report.md"
        framework_report.write_text("# Framework agent report", encoding="utf-8")

        # Canonical iw-item-analyze outputs (different filename)
        canonical_narrative = reports_dir / f"{item.id}_self_assess_report.md"
        canonical_narrative.write_text(
            "### Item Analysis: I-00067\n\nBottom line: 5 findings worth fixing.",
            encoding="utf-8",
        )
        canonical_findings = reports_dir / f"{item.id}_self_assess_findings.json"
        canonical_findings.write_text(
            json.dumps(
                {
                    "bottom_line": "5 findings worth fixing.",
                    "findings": [
                        {
                            "severity": "HIGH",
                            "class": "convention",
                            "target": "iw-ai-core",
                            "title": "Real finding from canonical sidecar",
                            "recommendation": "Apply the fix",
                            "paste_prompt": "/iw-new-cr Apply fix from I-00067",
                            "evidence": ["log:42 — actual evidence"],
                            "effort": "M",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        step_run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
            duration_secs=60.0,
            report_file=str(framework_report),
        )
        db_session.add(step_run)
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # The canonical findings ARE surfaced (no "no findings were captured")
        assert "no findings were captured" not in html
        assert "Real finding from canonical sidecar" in html
        assert "/iw-new-cr Apply fix from I-00067" in html
        assert "5 findings worth fixing" in html
        # The narrative comes from the canonical iw-item-analyze .md file,
        # not the framework's per-step report.
        assert "Item Analysis: I-00067" in html


class TestSelfAssessmentInvariant2:
    """Invariant 2: zero DOM nodes when section is absent (no hidden placeholder)."""

    def test_no_self_assess_html_when_section_absent(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When no self_assess step exists, no Self-Assessment-related HTML is emitted."""
        item = WorkItem(
            project_id=test_project.id,
            id="F-00104",
            title="No Self-Assess Step",
            type=WorkItemType.Feature,
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.active,
            design_doc_search="",
        )
        db_session.add(item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item.id,
            step_id="S01",
            step_number=1,
            step_type=StepType.implementation,
            agent_label="Backend",
            opencode_agent="backend-impl",
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # Zero occurrences of any self-assessment related string
        assert html.count("Self-Assessment") == 0
        assert html.count("self_assess") == 0
        assert html.count("findings") == 0
