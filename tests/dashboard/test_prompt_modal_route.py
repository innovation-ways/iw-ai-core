"""Tests for the /item/{item_id}/step/{step_id}/prompt-modal route (CR-00056 S06)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """FastAPI TestClient backed by the testcontainer db_session."""
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
# Seed helpers
# ---------------------------------------------------------------------------


def _make_project(db_session: Session, project_id: str = "proj-1") -> dict:
    """Create minimal project + item + batch + batch_item rows. Returns dict of rows."""
    from orch.db.models import Batch, BatchItem, Project, WorkItem

    project = Project(
        id=project_id,
        display_name=f"Test Project {project_id}",
        repo_root="/tmp/repo",
        config={},
    )
    db_session.add(project)
    db_session.flush()  # ensure PK is visible for FK constraints

    item = WorkItem(
        project_id=project_id,
        id="CR-00001",
        type="Feature",
        status="approved",
        title="Test Item",
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(item)
    db_session.flush()  # ensure PK visible for workflow_steps FK

    batch = Batch(project_id=project_id, id="batch-1", status="approved")
    db_session.add(batch)
    db_session.flush()

    bi = BatchItem(
        project_id=project_id,
        batch_id="batch-1",
        work_item_id="CR-00001",
        status="completed",
    )
    db_session.add(bi)
    db_session.commit()

    return {"project": project, "item": item, "batch": batch, "batch_item": bi}


class TestPromptModalRoute:
    """CR-00056 S06/S11: prompt-modal route tests."""

    def test_returns_200_with_initial_prompt_section(self, client: TestClient, db_session: Session):
        """AC5 happy path: route returns 200 with a single Initial Prompt section."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-ac5-1")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S02",
            step_number=2,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
            prompt_file="prompts/S02.md",
        )
        db_session.add(step)
        db_session.flush()

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="The initial prompt for S02",
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 200, response.text
        # AC5: modal body contains the full prompt text
        assert "The initial prompt for S02" in response.text
        # Modal has the correct a11y attributes
        assert 'role="dialog"' in response.text
        assert 'aria-modal="true"' in response.text
        assert 'aria-labelledby="prompt-modal-title"' in response.text
        # Fragment does NOT extend base.html
        assert "<html" not in response.text.lower()
        assert "<!doctype" not in response.text.lower()

    def test_returns_200_with_initial_and_fix_sections(
        self, client: TestClient, db_session: Session
    ):
        """AC7: step with two runs (initial + fix-cycle) shows both labelled sections in order."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-ac7-1")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S03",
            step_number=3,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        # Run 1: initial prompt
        run1 = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="Base prompt for S03.",
            fix_prompt_text=None,
        )
        db_session.add(run1)

        # Run 2: fix-cycle retry (run_number=2 → cycle 1)
        run2 = StepRun(
            step_id=step.id,
            run_number=2,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text=None,
            fix_prompt_text="Fix prompt for S03 cycle 1.",
        )
        db_session.add(run2)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 200, response.text
        # Both sections present
        assert "Base prompt for S03." in response.text
        assert "Fix prompt for S03 cycle 1." in response.text
        # AC7: fix prompt labelled with cycle number
        assert "Fix Prompt (cycle 1)" in response.text
        # Initial prompt labelled
        assert "Initial Prompt" in response.text
        # Order: Initial before Fix (chronological)
        init_pos = response.text.index("Initial Prompt")
        fix_pos = response.text.index("Fix Prompt (cycle 1)")
        assert init_pos < fix_pos, "Initial Prompt must appear before Fix Prompt"

    def test_returns_404_when_step_belongs_to_other_project(
        self, client: TestClient, db_session: Session
    ):
        """AC9: step from a different project → 404 (not 403, not 500)."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        # Two projects, each with an item
        _make_project(db_session, "proj-ac9-a")
        seed2 = _make_project(db_session, "proj-ac9-b")

        # Step in proj-ac9-b
        step = WorkflowStep(
            project_id="proj-ac9-b",
            work_item_id=seed2["item"].id,
            step_id="S04",
            step_number=4,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="Prompt for S04 in project B",
        )
        db_session.add(run)
        db_session.commit()

        # Request from project A for step S04 (which is in project B) → 404
        response = client.get(
            f"/project/proj-ac9-a/item/{seed2['item'].id}/step/S04/prompt-modal",
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_returns_404_when_item_id_mismatch(self, client: TestClient, db_session: Session):
        """Same project, different item — step exists under one item but requested for another."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-ac9-mismatch")

        # Two items in the same project
        from orch.db.models import WorkItem

        item2 = WorkItem(
            project_id="proj-ac9-mismatch",
            id="CR-99999",
            type="Feature",
            status="approved",
            title="Second Item",
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        db_session.add(item2)
        db_session.flush()

        # Step attached to item2 (CR-99999)
        step = WorkflowStep(
            project_id="proj-ac9-mismatch",
            work_item_id="CR-99999",
            step_id="S02",
            step_number=2,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="Prompt for S02 on CR-99999",
        )
        db_session.add(run)
        db_session.commit()

        # Request with item_id CR-00001 but step_id S02 belongs to CR-99999 → 404
        response = client.get(
            f"/project/proj-ac9-mismatch/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_returns_404_when_step_has_no_prompt_text(
        self, client: TestClient, db_session: Session
    ):
        """Returns 404 when no run has any prompt content set."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-no-prompt")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S05",
            step_number=5,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        # Run with NULL prompts (pre-CR-00056 historical row)
        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text=None,
            fix_prompt_text=None,
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_fragment_has_aria_modal_dialog(self, client: TestClient, db_session: Session):
        """Modal markup has correct role='dialog', aria-modal='true', aria-labelledby."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-a11y")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S06",
            step_number=6,
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
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="Prompt for a11y test",
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 200, response.text
        body = response.text
        assert 'role="dialog"' in body, "Missing role='dialog'"
        assert 'aria-modal="true"' in body, "Missing aria-modal='true'"
        assert 'aria-labelledby="prompt-modal-title"' in body, (
            "Missing aria-labelledby='prompt-modal-title'"
        )

    def test_fragment_does_not_extend_base_html(self, client: TestClient, db_session: Session):
        """htmx fragment response must NOT contain <html> or <!DOCTYPE — it is a partial."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-frag")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S07",
            step_number=7,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="Fragment test content",
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 200, response.text
        body_lower = response.text.lower()
        assert "<html" not in body_lower, "Fragment must not contain <html>"
        assert "<!doctype" not in body_lower, "Fragment must not contain <!doctype>"

    def test_prompt_text_is_html_escaped(self, client: TestClient, db_session: Session):
        """Prompt content with <script> tags is HTML-escaped in the response body.

        Verifies that when the DB contains a literal <script> tag, the template
        renders it as &lt;script&gt; (HTML-escaped) inside the <pre> element.
        The modal initialization script at the bottom of the fragment is NOT XSS
        — we only check the actual prompt content in the <pre> element.
        """
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-xss")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S08",
            step_number=8,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        xss_payload = "<script>alert(1)</script>"
        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text=xss_payload,
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 200, response.text

        # Check the raw pre element HTML (not the decoded text, since BeautifulSoup
        # decodes HTML entities when calling get_text()). The pre element's raw HTML
        # content (between the tags) should have the escaped form.
        import re

        # Find the pre element and check its raw HTML content
        pre_pattern = re.compile(
            r'<pre\s+class="prompt-modal-pre"\s+[^>]*data-prompt-section-body="0"[^>]*>(.*?)</pre>',
            re.DOTALL,
        )
        pre_match = pre_pattern.search(response.text)
        assert pre_match is not None, (
            f"Could not find pre element with data-prompt-section-body='0' in response. "
            f"Response snippet: {response.text[:500]!r}"
        )

        pre_raw_html = pre_match.group(1)
        # The escaped form must appear in the raw HTML
        assert "&lt;script&gt;" in pre_raw_html, (
            f"Expected &lt;script&gt; in raw pre HTML. Pre HTML: {pre_raw_html!r}"
        )
        # The raw (unescaped) form must NOT appear in the pre HTML content
        assert xss_payload not in pre_raw_html, (
            f"Unescaped XSS payload found in pre HTML: {pre_raw_html!r}"
        )

    # ---------------------------------------------------------------------------
    # S06 tests (existing — kept, renamed to reflect original coverage)
    # ---------------------------------------------------------------------------

    def test_returns_200_with_prompt_text(self, client: TestClient, db_session: Session):
        """Route returns 200 with prompt modal fragment when step has prompt_text."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-pm-1")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S01",
            step_number=1,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
            prompt_file="prompts/S01.md",
        )
        db_session.add(step)
        db_session.flush()

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="Initial prompt text for S01",
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 200, response.text
        assert "Initial prompt text" in response.text

    def test_404_unknown_item(self, client: TestClient, db_session: Session):
        """Returns 404 when work item does not exist."""
        _make_project(db_session, "proj-pm-2")

        response = client.get(
            "/project/proj-pm-2/item/UNKNOWN-CR/step/S01/prompt-modal",
        )
        assert response.status_code == 404

    def test_404_unknown_step(self, client: TestClient, db_session: Session):
        """Returns 404 when step_id is not part of the item."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-pm-3")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S01",
            step_number=1,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="Initial prompt",
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/UNKNOWN-STEP/prompt-modal",
        )
        assert response.status_code == 404

    def test_404_no_prompt_text(self, client: TestClient, db_session: Session):
        """Returns 404 when no run has prompt_text or fix_prompt_text."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-pm-4")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S01",
            step_number=1,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        # Run with no prompt_text
        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text=None,
            fix_prompt_text=None,
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 404

    def test_fix_prompt_text_sections(self, client: TestClient, db_session: Session):
        """Fix prompts are rendered as separate 'Fix Prompt (cycle N)' sections."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-pm-5")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S01",
            step_number=1,
            agent_label="Code",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        # Run 1: initial prompt
        run1 = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="Initial prompt",
            fix_prompt_text=None,
        )
        db_session.add(run1)

        # Run 2: fix prompt (first retry)
        run2 = StepRun(
            step_id=step.id,
            run_number=2,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text=None,
            fix_prompt_text="Fix prompt for cycle 1",
        )
        db_session.add(run2)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/prompt-modal",
        )
        assert response.status_code == 200
        assert "Initial prompt" in response.text
        assert "Fix Prompt (cycle 1)" in response.text
        assert "Fix prompt for cycle 1" in response.text


class TestStepDetailHasPrompt:
    """CR-00056 S06: has_prompt field on StepDetail dataclass."""

    def test_synthetic_step_returns_404(self, client: TestClient, db_session: Session):
        """Synthetic steps (S00/MERGE) have no WorkflowStep row — returns 404."""
        seed = _make_project(db_session, "proj-synth")

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/S00/prompt-modal",
        )
        assert response.status_code == 404

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/MERGE/prompt-modal",
        )
        assert response.status_code == 404
