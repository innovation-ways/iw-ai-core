"""F-00090 S03: Dashboard tests for the regression classification form.

Covers AC5 + Boundary rows that flow through the UI.

Container: dashboard tests use FastAPI TestClient with testcontainer-backed
db_session fixture (never the live DB port 5433).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Project,
    RegressionClassification,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Helper: create a minimal project + Incident item in the DB
# ---------------------------------------------------------------------------


def _seed_project_and_items(db_session, *, project_id="F90TEST", item_id="I-99991"):
    """Create a project, a merged Feature F-00001, and an Incident I-99991.

    Returns dict with project, feature (merged), incident objects.
    """
    project = Project(id=project_id, display_name="F-00090 Test Project", repo_root="/tmp/f90test")
    db_session.add(project)
    db_session.flush()

    # A merged feature that can serve as a regression source
    feature = WorkItem(
        project_id=project_id,
        id="F-00001",
        type=WorkItemType.Feature,
        title="F-00001 merged feature",
        status=WorkItemStatus.completed,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
        merge_commit_sha="aaa1111",
    )
    db_session.add(feature)

    # A second merged feature
    feature2 = WorkItem(
        project_id=project_id,
        id="F-00002",
        type=WorkItemType.Feature,
        title="F-00002 second merged feature",
        status=WorkItemStatus.completed,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
        merge_commit_sha="bbb2222",
    )
    db_session.add(feature2)

    # The Incident (not yet classified)
    incident = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.ChangeRequest,  # no Incident enum; I-NNNNN IDs are ChangeRequest
        title="I-99991 regression incident",
        status=WorkItemStatus.completed,  # merged so suggestions can run
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=["src/broken.py"],
        merge_commit_sha="ccc3333",
    )
    db_session.add(incident)
    db_session.commit()
    return {"project": project, "feature": feature, "feature2": feature2, "incident": incident}


# ---------------------------------------------------------------------------
# TDD RED first: tests that MUST fail before the fragment exists
# ---------------------------------------------------------------------------


def test_form_renders_on_incident_detail_page(db_session, client: TestClient):
    """AC5: Incident detail page shows the classification form with all required elements."""
    data = _seed_project_and_items(db_session)
    project_id = data["project"].id
    item_id = data["incident"].id

    # The form must appear on the incident detail page
    response = client.get(f"/project/{project_id}/item/{item_id}")
    assert response.status_code == 200

    # Searchable dropdown of prior merged work items
    assert 'name="introduced_by_work_item_id"' in response.text, (
        "Expected searchable dropdown for introduced_by_work_item_id in response"
    )
    # Free-text commit SHA input
    assert 'name="commit_sha"' in response.text, "Expected commit SHA input field in response"
    # Radio group with three values
    assert 'value="regression"' in response.text, "Expected 'regression' radio button in response"
    assert 'value="pre_existing"' in response.text, (
        "Expected 'pre_existing' radio button in response"
    )
    assert 'value="unknown"' in response.text, "Expected 'unknown' radio button in response"
    # Form htmx target
    assert "regression-classify" in response.text, "Expected htmx form endpoint in response"


def test_form_submit_persists_and_returns_row_fragment(db_session, client: TestClient):
    """AC5 happy path: POST the form and verify values are persisted."""
    data = _seed_project_and_items(db_session)
    project_id = data["project"].id
    item_id = data["incident"].id

    # POST the classification form with valid data
    response = client.post(
        f"/project/{project_id}/item/{item_id}/regression-classify",
        data={
            "introduced_by_work_item_id": "F-00001",
            "commit_sha": "",
            "classification": "regression",
        },
    )
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:500]}"
    )

    # Verify DB was updated
    db_session.expire_all()
    from sqlalchemy import select

    item = db_session.execute(select(WorkItem).where(WorkItem.id == item_id)).scalar_one()

    assert item.introduced_by_work_item_id == "F-00001", (
        f"Expected introduced_by_work_item_id='F-00001', got {item.introduced_by_work_item_id!r}"
    )
    assert item.regression_classification == RegressionClassification.regression, (
        f"Expected regression_classification=regression, got {item.regression_classification!r}"
    )
    assert item.classified_at is not None, "classified_at must be set after POST"
    assert item.classified_by is not None, "classified_by must be set after POST"


def test_form_validation_error_on_unknown_fk(db_session, client: TestClient):
    """Boundary: POST with bogus introduced_by_work_item_id returns 422 + inline error."""
    data = _seed_project_and_items(db_session)
    project_id = data["project"].id
    item_id = data["incident"].id

    response = client.post(
        f"/project/{project_id}/item/{item_id}/regression-classify",
        data={
            "introduced_by_work_item_id": "F-NONEXIST",
            "commit_sha": "",
            "classification": "regression",
        },
    )
    # Service raises ValueError for unknown FK → route returns 422
    assert response.status_code == 422, (
        f"Expected 422 for unknown FK, got {response.status_code}: {response.text[:500]}"
    )
    # The form must be re-rendered with an inline error message
    assert "does not exist" in response.text or "not found" in response.text.lower(), (
        f"Expected inline error for unknown FK in response: {response.text[:500]}"
    )


def test_accept_suggestion_uses_heuristic_auto(db_session, client: TestClient):
    """Boundary: POST with accept_top=1 sets classified_by='heuristic:auto'."""
    data = _seed_project_and_items(db_session)
    project_id = data["project"].id
    item_id = data["incident"].id

    response = client.post(
        f"/project/{project_id}/item/{item_id}/regression-classify",
        data={
            "introduced_by_work_item_id": "F-00001",
            "commit_sha": "",
            "classification": "regression",
            "accept_top": "1",
        },
    )
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:500]}"
    )

    db_session.expire_all()
    from sqlalchemy import select

    item = db_session.execute(select(WorkItem).where(WorkItem.id == item_id)).scalar_one()
    assert item.classified_by == "heuristic:auto", (
        f"Expected classified_by='heuristic:auto', got {item.classified_by!r}"
    )


def test_suggestion_button_hidden_when_no_candidates(db_session, client: TestClient, tmp_path):
    """Boundary: when suggest_introducer returns [], 'Accept suggestion' button is absent."""
    data = _seed_project_and_items(db_session)
    project_id = data["project"].id
    item_id = data["incident"].id

    # Ensure the incident has no merge SHA so suggest_introducer short-circuits to []
    # (Already done by _seed_project_and_items — the incident has merge_commit_sha
    # but in this test the repo doesn't exist so git calls fail, returning [].
    # For a clean test, create a scenario where suggest_introducer returns [].
    # The item has merge_sha but git won't find anything → no candidates.
    response = client.get(f"/project/{project_id}/item/{item_id}")
    assert response.status_code == 200

    # The "Accept suggestion" button must not appear when there are no candidates
    assert "Accept suggestion" not in response.text, (
        "Expected 'Accept suggestion' button to be absent when no heuristic candidates exist"
    )


def test_regression_suggestions_endpoint_returns_list(db_session, client: TestClient, tmp_path):
    """GET regression-suggestions returns the suggestion list fragment."""
    data = _seed_project_and_items(db_session)
    project_id = data["project"].id
    item_id = data["incident"].id

    response = client.get(f"/project/{project_id}/item/{item_id}/regression-suggestions")
    # Must return 200 (even with no git repo — git calls fail, suggestion list is [])
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:500]}"
    )
    # Fragment must be a valid HTML response (not a full page)
    assert "<html" not in response.text.lower() or "<body>" not in response.text.lower(), (
        "Expected an htmx fragment, not a full page"
    )


def test_pre_existing_classification_omits_introduced_by(db_session, client: TestClient):
    """Boundary: classification=pre_existing sets introduced_by_work_item_id=NULL."""
    data = _seed_project_and_items(db_session)
    project_id = data["project"].id
    item_id = data["incident"].id

    response = client.post(
        f"/project/{project_id}/item/{item_id}/regression-classify",
        data={
            "introduced_by_work_item_id": "",
            "commit_sha": "",
            "classification": "pre_existing",
        },
    )
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:500]}"
    )

    db_session.expire_all()
    from sqlalchemy import select

    item = db_session.execute(select(WorkItem).where(WorkItem.id == item_id)).scalar_one()
    assert item.introduced_by_work_item_id is None, (
        f"Expected introduced_by_work_item_id=NULL for pre_existing; "
        f"got {item.introduced_by_work_item_id!r}"
    )
    assert item.regression_classification == RegressionClassification.pre_existing


def test_commit_sha_validated_on_submit(db_session, client: TestClient):
    """Boundary: invalid SHA format returns 422 + inline error."""
    data = _seed_project_and_items(db_session)
    project_id = data["project"].id
    item_id = data["incident"].id

    response = client.post(
        f"/project/{project_id}/item/{item_id}/regression-classify",
        data={
            "introduced_by_work_item_id": "F-00001",
            "commit_sha": "not-a-valid-sha!!",
            "classification": "regression",
        },
    )
    # Server must validate SHA format and return 422
    assert response.status_code == 422, (
        f"Expected 422 for invalid SHA, got {response.status_code}: {response.text[:500]}"
    )
    assert "sha" in response.text.lower() or "commit" in response.text.lower(), (
        f"Expected error message about SHA format, got: {response.text[:500]}"
    )
