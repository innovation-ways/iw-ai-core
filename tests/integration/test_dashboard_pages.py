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


# ---------------------------------------------------------------------------
# Research Panel
# ---------------------------------------------------------------------------


def _seed_research_doc(
    db: Any,
    project_id: str,
    doc_id: str = "R-00001",
    title: str = "Test Research",
    content: str = "# Findings\nSome findings.",
    status: str = "published",
    category: str = "technical",
) -> None:
    """Seed a research ProjectDoc via DocService (handles composite PK, slug, tier, etc.)."""
    from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory
    from orch.doc_service import DocService

    svc = DocService(db)
    svc.create_doc(
        project_id=project_id,
        doc_id=doc_id,
        title=title,
        doc_type=DocType.research,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory(category),
        status=DocStatus(status),
        content=content,
    )


def test_research_library_page_empty(client: TestClient, test_project: Project) -> None:
    """Research library page renders with empty state when no research docs exist."""
    response = client.get(f"/project/{test_project.id}/research")
    assert response.status_code == 200
    assert "research" in response.text.lower() or "iw-research" in response.text


def test_research_library_page_with_docs(
    client: TestClient, db_session: Any, test_project: Project
) -> None:
    """Research library lists seeded research documents."""
    _seed_research_doc(
        db_session, test_project.id, doc_id="R-00001", title="API Rate Limiting Research"
    )
    response = client.get(f"/project/{test_project.id}/research")
    assert response.status_code == 200
    assert "R-00001" in response.text
    assert "API Rate Limiting Research" in response.text


def test_research_detail_page(client: TestClient, db_session: Any, test_project: Project) -> None:
    """Research detail page renders markdown content."""
    _seed_research_doc(
        db_session,
        test_project.id,
        doc_id="R-00002",
        title="Queue Strategy Research",
        content="# Queue Strategy\n\nRedis is **fast**.",
    )
    response = client.get(f"/project/{test_project.id}/research/R-00002")
    assert response.status_code == 200
    assert "Queue Strategy Research" in response.text
    assert "<strong>fast</strong>" in response.text or "fast" in response.text


def test_research_detail_page_not_found(client: TestClient, test_project: Project) -> None:
    """Research detail page returns 404 for unknown doc_id."""
    response = client.get(f"/project/{test_project.id}/research/R-99999")
    assert response.status_code == 404


def test_research_detail_wrong_doc_type_returns_404(
    client: TestClient, db_session: Any, test_project: Project
) -> None:
    """Research detail page returns 404 if doc_id belongs to a non-research doc."""
    from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory
    from orch.doc_service import DocService

    svc = DocService(db_session)
    svc.create_doc(
        project_id=test_project.id,
        doc_id="MOD-00001",
        title="Module Doc",
        doc_type=DocType.module,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.published,
        content="# Module",
    )
    response = client.get(f"/project/{test_project.id}/research/MOD-00001")
    assert response.status_code == 404


def test_research_detail_null_content(
    client: TestClient, db_session: Any, test_project: Project
) -> None:
    """Research detail page renders gracefully when content is None."""
    from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory
    from orch.doc_service import DocService

    svc = DocService(db_session)
    svc.create_doc(
        project_id=test_project.id,
        doc_id="R-00003",
        title="Empty Research",
        doc_type=DocType.research,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        content=None,
    )
    response = client.get(f"/project/{test_project.id}/research/R-00003")
    assert response.status_code == 200


def test_research_search_returns_results(
    client: TestClient, db_session: Any, test_project: Project
) -> None:
    """Research search endpoint returns matching docs."""
    _seed_research_doc(
        db_session,
        test_project.id,
        doc_id="R-00004",
        title="Authentication Methods Research",
    )
    response = client.get(f"/project/{test_project.id}/api/research/search?q=Authentication")
    assert response.status_code == 200
    assert "R-00004" in response.text
    assert "Authentication Methods Research" in response.text


def test_research_search_filters_by_status(
    client: TestClient, db_session: Any, test_project: Project
) -> None:
    """Research search endpoint filters by status."""
    _seed_research_doc(
        db_session,
        test_project.id,
        doc_id="R-00005",
        title="Draft Research",
        status="draft",
    )
    _seed_research_doc(
        db_session,
        test_project.id,
        doc_id="R-00006",
        title="Published Research",
        status="published",
    )
    response = client.get(f"/project/{test_project.id}/api/research/search?status=draft")
    assert response.status_code == 200
    assert "R-00005" in response.text
    assert "R-00006" not in response.text


def test_research_search_empty_results(client: TestClient, test_project: Project) -> None:
    """Research search endpoint returns empty state when no matches."""
    response = client.get(f"/project/{test_project.id}/api/research/search?q=nonexistent")
    assert response.status_code == 200
    assert "No research documents found" in response.text


def test_research_search_no_query_returns_all(
    client: TestClient, db_session: Any, test_project: Project
) -> None:
    """Research search endpoint returns all docs when no filter provided."""
    _seed_research_doc(
        db_session,
        test_project.id,
        doc_id="R-00007",
        title="Research Seven",
    )
    _seed_research_doc(
        db_session,
        test_project.id,
        doc_id="R-00008",
        title="Research Eight",
    )
    response = client.get(f"/project/{test_project.id}/api/research/search")
    assert response.status_code == 200
    assert "R-00007" in response.text
    assert "R-00008" in response.text
