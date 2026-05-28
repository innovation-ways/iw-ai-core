from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dashboard.app import create_app
from dashboard.dependencies import get_db
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


@pytest.fixture
def client(db_session: Session) -> TestClient:
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


@pytest.fixture
def seeded_scope_blocked_step(db_session: Session) -> tuple[str, str, str]:
    project = Project(
        id="test-modal-i00115",
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()

    item = WorkItem(
        project_id=project.id,
        id="I-00115-MODAL-TEST",
        type=WorkItemType.Feature,
        title="I-00115 modal test",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(item)
    db_session.flush()

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
    db_session.add(step)
    db_session.flush()

    db_session.add(
        StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.failed,
            worktree_path="/tmp/test-worktree",
        )
    )
    db_session.add(
        FixCycle(
            step_id=step.id,
            cycle_number=1,
            status=FixStatus.escalated,
            trigger_type=FixTrigger.quality_validation,
            fix_metadata={"scope_violations": [".gitleaks.toml"]},
        )
    )
    db_session.commit()

    return project.id, item.id, step.step_id


def _modal_html(client: TestClient, seeded_scope_blocked_step: tuple[str, str, str]) -> str:
    project_id, item_id, step_id = seeded_scope_blocked_step
    response = client.get(f"/project/{project_id}/api/item/{item_id}/scope/amend-modal/{step_id}")
    assert response.status_code == 200
    return response.text


def test_i00115_modal_submit_form_wires_cleanup_hook(
    client: TestClient, seeded_scope_blocked_step: tuple[str, str, str]
) -> None:
    html = _modal_html(client, seeded_scope_blocked_step)
    form_match = re.search(r'<form\b[^>]*hx-post="[^"]*scope/amend-and-restart[^"]*"[^>]*>', html)
    assert form_match, "expected amend-and-restart form open tag"
    form_open_tag = form_match.group(0)
    assert form_open_tag.count("scope-amend-modal") == 1
    assert "scope-amend-overlay" in form_open_tag


def test_i00115_modal_close_button_uses_getelementbyid_for_overlay(
    client: TestClient, seeded_scope_blocked_step: tuple[str, str, str]
) -> None:
    html = _modal_html(client, seeded_scope_blocked_step)
    assert "this.closest('#scope-amend-overlay')" not in html


def test_i00115_modal_esc_key_dismisses(
    client: TestClient, seeded_scope_blocked_step: tuple[str, str, str]
) -> None:
    html = _modal_html(client, seeded_scope_blocked_step)
    assert 'event.key === "Escape"' in html or "keyCode === 27" in html
    assert "scope-amend-modal" in html
    assert "scope-amend-overlay" in html
    assert "dismissModal();" in html or "remove()" in html


def test_i00115_modal_backdrop_click_dismisses(
    client: TestClient, seeded_scope_blocked_step: tuple[str, str, str]
) -> None:
    html = _modal_html(client, seeded_scope_blocked_step)
    assert "event.target === overlay" in html
    assert (
        'document.getElementById("scope-amend-overlay")' in html
        or "document.getElementById('scope-amend-overlay')" in html
    )
    assert 'addEventListener("click", onOverlayClick)' in html or "onclick=" in html


def test_i00115_cancel_button_still_works(
    client: TestClient, seeded_scope_blocked_step: tuple[str, str, str]
) -> None:
    html = _modal_html(client, seeded_scope_blocked_step)
    cancel_button_match = re.search(r"<button[^>]*>\s*Cancel\s*</button>", html)
    assert cancel_button_match, "expected cancel button"
    assert 'onclick="window.dismissScopeAmendModal();"' in cancel_button_match.group(0)
    assert html.count("modal.remove();") == 1
    assert "overlay.remove();" in html
