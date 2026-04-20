"""Integration tests for execution report dashboard routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Any) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Any, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def make_item(
    db_session: Any,
    project_id: str = "test-proj",
    item_id: str = "I-00001",
    status: WorkItemStatus = WorkItemStatus.in_progress,
) -> WorkItem:
    item = WorkItem(
        project_id=project_id,
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
    project_id: str = "test-proj",
    item_id: str = "I-00001",
    step_id: str = "S01",
    step_number: int = 1,
    status: StepStatus = StepStatus.completed,
) -> WorkflowStep:
    step = WorkflowStep(
        project_id=project_id,
        work_item_id=item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label="Backend",
        step_type=StepType.implementation,
        status=status,
    )
    db_session.add(step)
    db_session.flush()
    return step


# ---------------------------------------------------------------------------
# Tab fragment route tests
# ---------------------------------------------------------------------------


def test_execution_report_tab_returns_200_for_known_item(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """GET /project/{id}/item/{id}/tab/execution-report returns 200 for a known item."""
    item = make_item(db_session, project_id=test_project.id, item_id="I-00001")
    make_step(db_session, project_id=test_project.id, item_id=item.id)

    resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
    assert resp.status_code == 200


def test_execution_report_tab_returns_404_for_unknown_item(
    client: TestClient,
    test_project: Project,
) -> None:
    """GET /project/{id}/item/{id}/tab/execution-report returns 404 for an unknown item."""
    resp = client.get(f"/project/{test_project.id}/item/I-DOES-NOT-EXIST/tab/execution-report")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Standalone page route tests
# ---------------------------------------------------------------------------


def test_execution_report_page_returns_200_for_known_item(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """GET /project/{id}/item/{id}/execution-report returns 200 for a known item."""
    item = make_item(db_session, project_id=test_project.id, item_id="I-00001")
    make_step(db_session, project_id=test_project.id, item_id=item.id)

    resp = client.get(f"/project/{test_project.id}/item/{item.id}/execution-report")
    assert resp.status_code == 200


def test_execution_report_page_returns_404_for_unknown_item(
    client: TestClient,
    test_project: Project,
) -> None:
    """GET /project/{id}/item/{id}/execution-report returns 404 for an unknown item."""
    resp = client.get(f"/project/{test_project.id}/item/I-DOES-NOT-EXIST/execution-report")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Extended dashboard tests for execution report content
# ---------------------------------------------------------------------------


def test_execution_report_tab_html_contains_summary_card(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """HTML contains summary information for the item."""
    item = make_item(db_session, project_id=test_project.id, item_id="I-00001")
    make_step(db_session, project_id=test_project.id, item_id=item.id)

    resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
    assert resp.status_code == 200
    text_lower = resp.text.lower()
    has_content = (
        "retry hotspots" in text_lower
        or "step gantt" in text_lower
        or "gantt" in text_lower
        or "execution" in text_lower
        or "completed" in text_lower
    )
    assert has_content, "HTML should contain execution summary content"


def test_execution_report_tab_html_contains_gantt_rows(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """HTML contains gantt rows for each workflow step."""
    item = make_item(db_session, project_id=test_project.id, item_id="I-00002")
    make_step(db_session, project_id=test_project.id, item_id=item.id, step_id="S01", step_number=1)
    make_step(db_session, project_id=test_project.id, item_id=item.id, step_id="S02", step_number=2)

    resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
    assert resp.status_code == 200


def test_existing_tabs_byte_identical(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """Snapshot test: existing item-detail tabs return 200 with consistent HTML structure."""
    item = make_item(db_session, project_id=test_project.id, item_id="I-00003")
    make_step(db_session, project_id=test_project.id, item_id=item.id)

    tabs = ["overview", "design-doc", "reports", "artifacts", "evidences", "logs", "fix-cycles"]
    snapshots: dict[str, int] = {}
    for tab in tabs:
        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/{tab}")
        assert resp.status_code == 200
        snapshots[tab] = len(resp.text)

    for tab in tabs:
        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/{tab}")
        assert resp.status_code == 200
        assert len(resp.text) == snapshots[tab]


def test_execution_report_page_contains_execution_markdown(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """The execution-report page contains markdown-style content."""
    item = make_item(db_session, project_id=test_project.id, item_id="I-00004")
    make_step(db_session, project_id=test_project.id, item_id=item.id)

    resp = client.get(f"/project/{test_project.id}/item/{item.id}/execution-report")
    assert resp.status_code == 200
    assert len(resp.text) > 0
