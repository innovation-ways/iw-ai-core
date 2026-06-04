"""Integration tests for dashboard fragment endpoints against a real PostgreSQL testcontainer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
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
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Any, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


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
    status: StepStatus = StepStatus.in_progress,
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


def make_batch(
    db_session: Any,
    project_id: str = "test-proj",
    batch_id: str = "B-001",
    status: BatchStatus = BatchStatus.planning,
) -> Batch:
    batch = Batch(
        id=batch_id,
        project_id=project_id,
        status=status,
        max_parallel=2,
        cli_tool="claude",
        auto_publish=False,
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def make_batch_item(
    db_session: Any,
    project_id: str = "test-proj",
    batch_id: str = "B-001",
    item_id: str = "I-00001",
    execution_group: int = 1,
    status: BatchItemStatus = BatchItemStatus.pending,
) -> BatchItem:
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=item_id,
        execution_group=execution_group,
        status=status,
    )
    db_session.add(bi)
    db_session.flush()
    return bi


# ---------------------------------------------------------------------------
# Batch header fragment tests
# ---------------------------------------------------------------------------


def test_batch_header_fragment_returns_200(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """GET /project/{id}/batch/{bid}/fragment/header returns 200."""
    batch = make_batch(db_session, project_id=test_project.id)
    resp = client.get(f"/project/{test_project.id}/batch/{batch.id}/fragment/header")
    assert resp.status_code == 200
    assert "planning" in resp.text.lower()  # status badge shows


def test_batch_header_fragment_reflects_status_change(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """Fragment should show updated status after DB change."""
    batch = make_batch(db_session, project_id=test_project.id, status=BatchStatus.planning)

    # First request shows planning
    resp1 = client.get(f"/project/{test_project.id}/batch/{batch.id}/fragment/header")
    assert resp1.status_code == 200

    # Change status
    batch.status = BatchStatus.approved
    db_session.flush()

    # Second request should show approved
    resp2 = client.get(f"/project/{test_project.id}/batch/{batch.id}/fragment/header")
    assert resp2.status_code == 200
    assert "approved" in resp2.text.lower()


def test_batch_header_fragment_404_for_missing_batch(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """Fragment should 404 for nonexistent batch."""
    resp = client.get(f"/project/{test_project.id}/batch/NONEXIST/fragment/header")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Item header fragment tests
# ---------------------------------------------------------------------------


def test_item_header_fragment_returns_200(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """GET /project/{id}/item/{iid}/fragment/header returns 200."""
    item = make_item(db_session, project_id=test_project.id)
    resp = client.get(f"/project/{test_project.id}/item/{item.id}/fragment/header")
    assert resp.status_code == 200


def test_item_header_fragment_reflects_status_change(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """Fragment should show updated status after DB change."""
    item = make_item(db_session, project_id=test_project.id, status=WorkItemStatus.draft)

    resp1 = client.get(f"/project/{test_project.id}/item/{item.id}/fragment/header")
    assert resp1.status_code == 200
    assert "draft" in resp1.text.lower()

    item.status = WorkItemStatus.approved
    db_session.flush()

    resp2 = client.get(f"/project/{test_project.id}/item/{item.id}/fragment/header")
    assert resp2.status_code == 200
    assert "approved" in resp2.text.lower()


def test_item_header_fragment_404_for_missing_item(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """Fragment should 404 for nonexistent item."""
    resp = client.get(f"/project/{test_project.id}/item/NONEXIST/fragment/header")
    assert resp.status_code == 404


def test_item_header_fragment_includes_metrics(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """Fragment should render metric cards (steps completed, fix cycles)."""
    item = make_item(db_session, project_id=test_project.id)
    make_step(
        db_session,
        project_id=test_project.id,
        step_id="S01",
        step_number=1,
        status=StepStatus.completed,
    )
    make_step(
        db_session,
        project_id=test_project.id,
        step_id="S02",
        step_number=2,
        status=StepStatus.pending,
    )

    resp = client.get(f"/project/{test_project.id}/item/{item.id}/fragment/header")
    assert resp.status_code == 200
    # Should contain "Steps" metric card.
    # _get_steps adds 2 synthetic steps (S00 setup + MERGE), so total is 4 (2 real + 2 synthetic).
    # 1 real step is completed, so the card shows "1/4".
    assert "Steps" in resp.text
    assert "1/4" in resp.text
