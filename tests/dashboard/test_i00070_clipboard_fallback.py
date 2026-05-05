"""I-00070 clipboard fallback — server-side fragment test.

RED: this test FAILS on the buggy template (inline navigator.clipboard call)
and PASSES once the button is rewired through the new shared helper.

Uses FastAPI's TestClient against a PostgreSQL testcontainer (via the
db_session fixture from tests/integration/conftest.py).
"""

from __future__ import annotations

import json
import os
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
            started_at=None,
            completed_at=None,
            duration_secs=60.0,
            report_file=str(report_file),
        )
        db_session.add(step_run)

    db_session.commit()
    return item


SAMPLE_FINDINGS_JSON = json.dumps(
    {
        "narrative_md": "# Self-Assessment Narrative",
        "bottom_line": "One HIGH severity finding requires attention.",
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
        ],
    }
)


class TestI00070ClipboardFallback:
    """AC4: server-side assertion that inline clipboard calls are eliminated."""

    def test_i00070_self_assess_button_does_not_use_inline_clipboard_writetext(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """RED: this test FAILS on the buggy template and PASSES once fixed.

        The fragment must NOT contain a direct call to navigator.clipboard.writeText
        in any inline onclick — that pattern fails silently outside secure contexts
        (plain HTTP on a non-localhost hostname like iw-dev-01).

        The button must instead be wired through the shared window.iwClipboard.copy
        helper so the fallback textarea path is used when navigator.clipboard is
        unavailable.
        """
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

        # The raw clipboard API call must NOT appear in any onclick handler.
        # This is the root cause of the bug on non-localhost HTTP access.
        assert "navigator.clipboard.writeText" not in html, (
            "Inline navigator.clipboard.writeText call still present — "
            "button will silently fail on http://iw-dev-01:9900 (non-secure context)"
        )

        # The button must be wired through the shared helper instead.
        assert "iwClipboard.copy" in html, (
            "Button is not wired through window.iwClipboard.copy — "
            "clipboard fallback will not be available in non-secure contexts"
        )

        # The paste_prompt data attribute is present (so the helper has something to copy).
        assert "data-paste-prompt=" in html

    def test_i00070_copy_button_feedback_strings_in_html(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Verify the helper's success/failure feedback labels are present in the page.

        The helper sets button text to 'Copied' on success. Since we cannot easily
        test the full client-side flow without a browser, we at least verify the
        page loads without errors and the clipboard button is present.
        """
        item = _create_item_with_self_assess(
            db_session,
            test_project,
            tmp_path,
            findings_json=SAMPLE_FINDINGS_JSON,
        )

        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # Button with the paste_prompt data attribute must be present
        assert 'data-paste-prompt="' in html
        # The onclick must reference the shared helper (not navigator.clipboard directly)
        assert "iwClipboard.copy" in html
