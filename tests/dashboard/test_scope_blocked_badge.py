"""I-00101: Dashboard tests for scope-blocked badge rendering.

When a WorkflowStep has a latest FixCycle with status=escalated and
fix_metadata.scope_violations non-empty, the item detail page must:
  1. Render a distinct "Scope blocked" badge (not the generic needs_fix pill)
  2. NOT render the generic needs_fix badge class on that row
  3. Show an "Amend scope & restart" modal trigger button
  4. Hide the Restart button (scope-blocked steps are restarted via amend)
  5. Show the Skip button
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    FixCycle,
    FixStatus,
    FixTrigger,
    Project,
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
# TestClient fixture (same pattern as test_cancel_button_visibility.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Provide a TestClient with get_db overridden to the test db_session."""
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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_project(db: Session, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def _seed_scope_blocked_item(
    db: Session,
    project: Project,
    item_id: str = "I-00101-SCOPE-TEST",
    scope_violations: list[str] | None = None,
) -> tuple[WorkItem, WorkflowStep, FixCycle]:
    """Seed a minimal work item with one needs_fix step and one scope-escalated FixCycle."""
    if scope_violations is None:
        scope_violations = [".gitleaks.toml"]

    item = WorkItem(
        project_id=project.id,
        id=item_id,
        type=WorkItemType.Feature,
        title="I-00101 scope blocked test",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db.add(item)
    db.flush()

    step = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        step_id="S01",
        agent_label="test",
        step_type=StepType.quality_validation,
        gate="security-secrets",
        status=StepStatus.needs_fix,
    )
    db.add(step)
    db.flush()

    fix_cycle = FixCycle(
        step_id=step.id,
        cycle_number=1,
        status=FixStatus.escalated,
        trigger_type=FixTrigger.quality_validation,
        fix_metadata={"scope_violations": scope_violations},
    )
    db.add(fix_cycle)
    db.commit()

    return item, step, fix_cycle


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScopeBlockedBadge:
    """AC1: scope-blocked badge appears on steps escalated by scope violations."""

    def test_i00101_scope_blocked_badge_renders_for_escalated_cycle_with_violations(
        self, client: TestClient, db_session: Session
    ) -> None:
        """The item detail page must contain badge-scope-blocked class for a scope-blocked step."""
        project = _seed_project(db_session, "test-scope-badge")
        item, step, _ = _seed_scope_blocked_item(db_session, project)

        # GET the item detail page
        response = client.get(f"/project/{project.id}/item/{item.id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Find the step row for S01
        step_rows = soup.select("table tbody tr")
        s01_row = None
        for row in step_rows:
            if "S01" in row.get_text():
                s01_row = row
                break

        assert s01_row is not None, f"Could not find S01 row in:\n{soup.get_text()[:500]}"

        # CRITICAL: scope-blocked badge must be present
        badge = s01_row.find(
            lambda tag: (
                tag.name in ("span", "div") and "badge-scope-blocked" in tag.get("class", [])
            )
        )
        assert badge is not None, (
            f"Expected badge-scope-blocked on S01 row; HTML snippet:\n{s01_row}"
        )

        # Verify the badge's title/aria-label contains the offending path
        title = badge.get("title") or badge.get("aria-label") or ""
        assert ".gitleaks.toml" in title, (
            f"Badge title must contain the offending path; got {title!r}"
        )

    def test_i00101_scope_blocked_badge_omitted_when_no_violations_on_needs_fix(
        self, client: TestClient, db_session: Session
    ) -> None:
        """needs_fix step with a non-scope escalation (no scope_violations)
        must NOT show scope-blocked badge."""
        project = _seed_project(db_session, "test-no-violations")
        item, step, fix_cycle = _seed_scope_blocked_item(
            db_session,
            project,
            item_id="I-00101-NO-VIOLATIONS",
            scope_violations=None,  # Will use [] from empty fix_metadata
        )

        # Update the fix cycle to have no scope_violations
        fix_cycle.fix_metadata = {}
        db_session.commit()

        response = client.get(f"/project/{project.id}/item/{item.id}")
        assert response.status_code == 200

        html = response.text
        # Attribute-scoped assertion: must appear in a class= attribute context
        assert 'class="badge-scope-blocked"' not in html, (
            "scope-blocked badge must NOT appear when scope_violations is absent"
        )

    def test_i00101_restart_button_hidden_on_scope_blocked_row(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Scope-blocked step rows must NOT render the generic restart_button."""
        project = _seed_project(db_session, "test-no-restart")
        item, step, _ = _seed_scope_blocked_item(db_session, project, "I-00101-NO-RESTART")

        response = client.get(f"/project/{project.id}/item/{item.id}")
        assert response.status_code == 200

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Find S01 row
        step_rows = soup.select("table tbody tr")
        s01_row = None
        for row in step_rows:
            if "S01" in row.get_text():
                s01_row = row
                break

        assert s01_row is not None

        # The S01 row must NOT contain a restart POST URL (hx-post to restart-step)
        # Attribute-scoped: look for hx-post with restart-step
        restart_links = s01_row.select('[hx-post*="restart-step"]')
        assert len(restart_links) == 0, (
            f"Scope-blocked row must NOT have restart-step button; found {restart_links}"
        )

    def test_i00101_amend_modal_trigger_url_is_correct(
        self, client: TestClient, db_session: Session
    ) -> None:
        """The Amend scope button must have the correct hx-get URL to the modal endpoint."""
        project = _seed_project(db_session, "test-amend-url")
        item, step, _ = _seed_scope_blocked_item(db_session, project, "I-00101-AMEND-URL")

        response = client.get(f"/project/{project.id}/item/{item.id}")
        assert response.status_code == 200

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Find the Amend scope button — hx-get attribute-scoped
        amend_buttons = soup.select(
            f'[hx-get*="/project/{project.id}/api/item/{item.id}/scope/amend-modal/S01"]'
        )
        assert len(amend_buttons) >= 1, (
            f"Expected at least one Amend scope button for S01; HTML snippet:\n"
            f"{soup.get_text()[:500]}"
        )

        # Verify it contains the amend scope text
        button_text = amend_buttons[0].get_text(strip=True)
        assert "Amend scope" in button_text, (
            f"Amend button text must contain 'Amend scope'; got {button_text!r}"
        )

    def test_i00101_skip_button_present_on_scope_blocked_row(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Scope-blocked step rows must still show the Skip button."""
        project = _seed_project(db_session, "test-skip-present")
        item, step, _ = _seed_scope_blocked_item(db_session, project, "I-00101-SKIP-PRESENT")

        response = client.get(f"/project/{project.id}/item/{item.id}")
        assert response.status_code == 200

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Find S01 row
        step_rows = soup.select("table tbody tr")
        s01_row = None
        for row in step_rows:
            if "S01" in row.get_text():
                s01_row = row
                break

        assert s01_row is not None

        # Skip button (hx-get to confirm-skip or hx-post skip)
        # Check for skip-related hx-get or form actions
        skip_elements = s01_row.find_all(
            lambda tag: (
                tag.name in ("button", "a")
                and ("skip" in tag.get("hx-post", "") or "skip" in tag.get("hx-get", ""))
            )
        )
        assert len(skip_elements) >= 1, (
            f"Scope-blocked row must still show Skip button; S01 row HTML:\n{s01_row}"
        )
