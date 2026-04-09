"""Integration tests for project dashboard, batch, and item detail pages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from collections.abc import Generator


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


def make_project(db: Any, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",  # noqa: S108
        config={},
    )
    db.add(project)
    db.flush()
    return project


def make_item(
    db: Any,
    project_id: str = "test-proj",
    item_id: str = "I-00001",
    title: str = "Test Item",
    status: WorkItemStatus = WorkItemStatus.in_progress,
    design_doc_content: str | None = None,
) -> WorkItem:
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title=title,
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        design_doc_content=design_doc_content,
    )
    db.add(item)
    db.flush()
    return item


def make_step(
    db: Any,
    project_id: str = "test-proj",
    item_id: str = "I-00001",
    step_id: str = "S01",
    step_number: int = 1,
    status: StepStatus = StepStatus.completed,
    report_content: str | None = None,
) -> WorkflowStep:
    step = WorkflowStep(
        project_id=project_id,
        work_item_id=item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label="Backend",
        step_type=StepType.implementation,
        status=status,
        report_content=report_content,
    )
    db.add(step)
    db.flush()
    return step


def make_batch(
    db: Any,
    project_id: str = "test-proj",
    batch_id: str = "BATCH-00001",
    status: BatchStatus = BatchStatus.executing,
) -> Batch:
    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=status,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()
    return batch


def make_batch_item(
    db: Any,
    project_id: str = "test-proj",
    batch_id: str = "BATCH-00001",
    item_id: str = "I-00001",
    status: BatchItemStatus = BatchItemStatus.executing,
) -> BatchItem:
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=item_id,
        execution_group=0,
        status=status,
    )
    db.add(bi)
    db.flush()
    return bi


# ---------------------------------------------------------------------------
# Project Dashboard
# ---------------------------------------------------------------------------


def test_project_dashboard_returns_200(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert "Test Project" in resp.text


def test_project_dashboard_shows_active_batches(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session)
    batch = make_batch(db_session)
    make_batch_item(db_session)

    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert batch.id in resp.text


def test_project_dashboard_404_for_unknown_project(client: TestClient, db_session: Any) -> None:
    resp = client.get("/project/no-such-project/")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Batch List
# ---------------------------------------------------------------------------


def test_batch_list_returns_200(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/batches")
    assert resp.status_code == 200
    assert "Batches" in resp.text


def test_batch_list_shows_batch_rows(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session)
    batch = make_batch(db_session)
    make_batch_item(db_session)

    resp = client.get("/project/test-proj/batches")
    assert resp.status_code == 200
    assert batch.id in resp.text


def test_batch_list_status_filter(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session)
    make_batch(db_session, status=BatchStatus.completed)

    # Filter to executing — should not show the completed batch id in batch rows
    resp = client.get("/project/test-proj/batches?status=executing")
    assert resp.status_code == 200
    # The completed batch should not appear in the table rows
    assert "BATCH-00001" not in resp.text


def test_batch_list_404_for_unknown_project(client: TestClient, db_session: Any) -> None:
    resp = client.get("/project/no-such-project/batches")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Batch Detail
# ---------------------------------------------------------------------------


def test_batch_detail_returns_200(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session)
    batch = make_batch(db_session)
    make_batch_item(db_session)
    make_step(db_session)

    resp = client.get(f"/project/test-proj/batch/{batch.id}")
    assert resp.status_code == 200
    assert batch.id in resp.text


def test_batch_detail_shows_items(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(db_session)
    batch = make_batch(db_session)
    make_batch_item(db_session)

    resp = client.get(f"/project/test-proj/batch/{batch.id}")
    assert resp.status_code == 200
    assert item.id in resp.text


def test_batch_detail_404_for_unknown_batch(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/batch/NO-SUCH-BATCH")
    assert resp.status_code == 404


def test_batch_detail_timeline_tab(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session)
    batch = make_batch(db_session)
    make_batch_item(db_session)

    resp = client.get(f"/project/test-proj/batch/{batch.id}?tab=timeline")
    assert resp.status_code == 200
    assert "Timeline" in resp.text


# ---------------------------------------------------------------------------
# Work Item Detail
# ---------------------------------------------------------------------------


def test_item_detail_returns_200(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(db_session)
    make_step(db_session)

    resp = client.get(f"/project/test-proj/item/{item.id}")
    assert resp.status_code == 200
    assert item.id in resp.text
    assert item.title in resp.text


def test_item_detail_404_for_unknown_item(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/item/NO-SUCH-ITEM")
    assert resp.status_code == 404


def test_item_detail_shows_batch_reference(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(db_session)
    make_step(db_session)
    make_batch(db_session)
    make_batch_item(db_session)

    resp = client.get(f"/project/test-proj/item/{item.id}")
    assert resp.status_code == 200
    assert "BATCH-00001" in resp.text


# ---------------------------------------------------------------------------
# Item tabs
# ---------------------------------------------------------------------------


def test_item_overview_tab_returns_html(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(db_session)
    make_step(db_session)

    resp = client.get(f"/project/test-proj/item/{item.id}/tab/overview")
    assert resp.status_code == 200
    assert "<html" not in resp.text  # fragment, not full page
    assert "S01" in resp.text


def test_item_design_doc_tab_renders_markdown(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(
        db_session,
        design_doc_content="# My Design\n\nThis is **bold** text.\n",
    )

    resp = client.get(f"/project/test-proj/item/{item.id}/tab/design-doc")
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "<h1>" in resp.text
    assert "<strong>bold</strong>" in resp.text


def test_item_design_doc_tab_no_content(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(db_session, design_doc_content=None)

    resp = client.get(f"/project/test-proj/item/{item.id}/tab/design-doc")
    assert resp.status_code == 200
    assert "No design document available" in resp.text


def test_item_reports_tab_shows_step_reports(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(db_session)
    make_step(
        db_session,
        report_content="## Summary\n\nAll checks passed.\n",
    )

    resp = client.get(f"/project/test-proj/item/{item.id}/tab/reports")
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "<h2>" in resp.text
    assert "All checks passed" in resp.text


def test_item_reports_tab_no_reports(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(db_session)
    make_step(db_session, report_content=None)

    resp = client.get(f"/project/test-proj/item/{item.id}/tab/reports")
    assert resp.status_code == 200
    assert "No reports available" in resp.text


def test_item_artifacts_tab_no_artifacts(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(db_session)

    resp = client.get(f"/project/test-proj/item/{item.id}/tab/artifacts")
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "No artifacts available" in resp.text


# ---------------------------------------------------------------------------
# 404 for nonexistent project on all page types
# ---------------------------------------------------------------------------


def test_batch_detail_404_for_unknown_project(client: TestClient, db_session: Any) -> None:
    resp = client.get("/project/ghost/batch/BATCH-X")
    assert resp.status_code == 404


def test_item_detail_404_for_unknown_project(client: TestClient, db_session: Any) -> None:
    resp = client.get("/project/ghost/item/I-00001")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SSE fragment endpoints (Option B live refresh)
# ---------------------------------------------------------------------------


def test_batches_fragment_returns_rows(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session)
    batch = make_batch(db_session)
    make_batch_item(db_session)

    resp = client.get("/project/test-proj/batches/fragment")
    assert resp.status_code == 200
    assert "<html" not in resp.text  # fragment, not full page
    assert batch.id in resp.text
    assert "<tr" in resp.text


def test_batches_fragment_empty(client: TestClient, db_session: Any) -> None:
    make_project(db_session)

    resp = client.get("/project/test-proj/batches/fragment")
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "No batches found" in resp.text


def test_batches_fragment_status_filter(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session)
    make_batch(db_session, status=BatchStatus.completed)

    resp = client.get("/project/test-proj/batches/fragment?status=executing")
    assert resp.status_code == 200
    assert "BATCH-00001" not in resp.text


def test_batches_fragment_404_for_unknown_project(client: TestClient, db_session: Any) -> None:
    resp = client.get("/project/ghost/batches/fragment")
    assert resp.status_code == 404


def test_batch_items_fragment_returns_rows(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(db_session)
    batch = make_batch(db_session)
    make_batch_item(db_session)

    resp = client.get(f"/project/test-proj/batch/{batch.id}/fragment/items")
    assert resp.status_code == 200
    assert "<html" not in resp.text  # fragment, not full page
    assert item.id in resp.text
    assert "<tr" in resp.text


def test_batch_items_fragment_empty(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    batch = make_batch(db_session)

    resp = client.get(f"/project/test-proj/batch/{batch.id}/fragment/items")
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "No items in this batch" in resp.text


def test_batch_items_fragment_404_for_unknown_batch(client: TestClient, db_session: Any) -> None:
    make_project(db_session)

    resp = client.get("/project/test-proj/batch/NO-SUCH/fragment/items")
    assert resp.status_code == 404


def test_batch_items_fragment_404_for_unknown_project(client: TestClient, db_session: Any) -> None:
    resp = client.get("/project/ghost/batch/BATCH-X/fragment/items")
    assert resp.status_code == 404


def test_batches_page_has_sse_trigger(client: TestClient, db_session: Any) -> None:
    """Batches list page must include the SSE trigger div for live refresh."""
    make_project(db_session)

    resp = client.get("/project/test-proj/batches")
    assert resp.status_code == 200
    assert "batches-sse-trigger" in resp.text
    assert "batches/fragment" in resp.text


def test_batch_detail_has_sse_trigger(client: TestClient, db_session: Any) -> None:
    """Batch detail items tab must include the SSE trigger div for live refresh."""
    make_project(db_session)
    make_item(db_session)
    batch = make_batch(db_session)
    make_batch_item(db_session)

    resp = client.get(f"/project/test-proj/batch/{batch.id}?tab=items")
    assert resp.status_code == 200
    assert "batch-items-sse-trigger" in resp.text
    assert "fragment/items" in resp.text


def test_item_detail_has_sse_script(client: TestClient, db_session: Any) -> None:
    """Item detail page must include SSE connection for overview tab live refresh."""
    make_project(db_session)
    item = make_item(db_session)
    make_step(db_session)

    resp = client.get(f"/project/test-proj/item/{item.id}")
    assert resp.status_code == 200
    assert "EventSource" in resp.text
    assert "running-update" in resp.text
    assert "/tab/overview" in resp.text
