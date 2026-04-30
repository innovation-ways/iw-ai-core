"""Integration tests for queue, history, search, system status, and all-active pages."""

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
    status: WorkItemStatus = WorkItemStatus.draft,
    phase: WorkItemPhase = WorkItemPhase.active,
    design_doc_content: str | None = None,
    completed_at: Any = None,
) -> WorkItem:
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title=title,
        status=status,
        phase=phase,
        config={},
        depends_on=[],
        blocks=[],
        design_doc_content=design_doc_content,
        completed_at=completed_at,
    )
    db.add(item)
    db.flush()
    return item


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
# Queue page
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_queue_returns_200(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/queue")
    assert resp.status_code == 200
    assert "Queue" in resp.text


def test_queue_shows_approved_items_with_checkboxes(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session, item_id="I-00001", status=WorkItemStatus.approved)
    make_item(db_session, item_id="I-00002", status=WorkItemStatus.approved, title="Another item")

    resp = client.get("/project/test-proj/queue")
    assert resp.status_code == 200
    assert "I-00001" in resp.text
    assert "I-00002" in resp.text
    # Should have checkboxes for the approved items
    assert 'type="checkbox"' in resp.text
    assert 'name="item_ids"' in resp.text


def test_queue_shows_draft_items(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session, item_id="I-00003", status=WorkItemStatus.draft, title="Draft item")

    resp = client.get("/project/test-proj/queue")
    assert resp.status_code == 200
    assert "I-00003" in resp.text
    assert "Draft item" in resp.text


def test_queue_draft_has_approve_button(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session, item_id="I-00004", status=WorkItemStatus.draft)

    resp = client.get("/project/test-proj/queue")
    assert resp.status_code == 200
    assert "Approve" in resp.text


def test_queue_empty_state(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/queue")
    assert resp.status_code == 200
    assert "No approved items" in resp.text


def test_queue_404_for_unknown_project(client: TestClient, db_session: Any) -> None:
    resp = client.get("/project/ghost/queue")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# History page
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_history_returns_200(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/history")
    assert resp.status_code == 200
    assert "History" in resp.text


def test_history_shows_completed_items(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(
        db_session,
        item_id="I-00001",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
        title="Completed work",
    )

    resp = client.get("/project/test-proj/history")
    assert resp.status_code == 200
    assert item.id in resp.text
    assert "Completed work" in resp.text


def test_history_shows_failed_items(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(
        db_session,
        item_id="I-00002",
        status=WorkItemStatus.failed,
        title="Failed work",
    )

    resp = client.get("/project/test-proj/history")
    assert resp.status_code == 200
    assert item.id in resp.text


def test_history_returns_paginated_items(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    # Insert 25 completed items — page 1 returns first 20 (server-side pagination)
    for i in range(1, 26):
        make_item(
            db_session,
            item_id=f"I-{i:05d}",
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.done,
            title=f"Item {i}",
        )

    resp = client.get("/project/test-proj/history")
    assert resp.status_code == 200
    # Total count should reflect all 25 items
    assert "25 items" in resp.text
    # Page 1 shows 20 items (default page size)
    assert "I-00025" in resp.text  # most recent (created last, sorted desc by default)


def test_history_type_filter(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(db_session, item_id="I-00001", status=WorkItemStatus.completed, title="Issue item")
    feature = WorkItem(
        project_id="test-proj",
        id="F-00001",
        type=WorkItemType.Feature,
        title="Feature item",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(feature)
    db_session.flush()

    resp = client.get("/project/test-proj/history?type=Feature")
    assert resp.status_code == 200
    assert "F-00001" in resp.text
    assert "I-00001" not in resp.text


def test_history_status_filter(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(
        db_session,
        item_id="I-00001",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
        title="Completed item",
    )
    make_item(
        db_session,
        item_id="I-00002",
        status=WorkItemStatus.failed,
        title="Failed item",
    )

    resp = client.get("/project/test-proj/history?status=completed")
    assert resp.status_code == 200
    assert "I-00001" in resp.text
    assert "I-00002" not in resp.text


def test_history_date_from_filter(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(
        db_session,
        item_id="I-00001",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
    )

    # Filter with a future date — should return no items
    resp = client.get("/project/test-proj/history?date_from=2099-01-01")
    assert resp.status_code == 200
    assert "0 items" in resp.text


def test_history_date_to_filter(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(
        db_session,
        item_id="I-00001",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
    )

    # Filter with a past date — should return no items
    resp = client.get("/project/test-proj/history?date_to=2000-01-01")
    assert resp.status_code == 200
    assert "0 items" in resp.text


def test_history_empty_state(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/history")
    assert resp.status_code == 200
    assert "No history found" in resp.text
    assert "0 items" in resp.text


def test_history_empty_state_with_filter(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/history?type=Feature")
    assert resp.status_code == 200
    assert "for the selected filters" in resp.text


def test_history_table_has_sortable_columns(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(
        db_session,
        item_id="I-00001",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
    )

    resp = client.get("/project/test-proj/history")
    assert resp.status_code == 200
    # Table has id attribute for JS sorting
    assert 'id="history-table"' in resp.text
    # All sortable column headers present with data-sort-key
    for key in ("id", "type", "title", "status", "created", "duration"):
        assert f'data-sort-key="{key}"' in resp.text
    # Sort JS function is present
    assert "sortTable" in resp.text


def test_history_rows_have_sort_data_attributes(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(
        db_session,
        item_id="I-00001",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
        title="Test sort attrs",
    )

    resp = client.get("/project/test-proj/history")
    assert resp.status_code == 200
    assert 'data-sort-id="I-00001"' in resp.text
    assert 'data-sort-type="Issue"' in resp.text
    assert 'data-sort-title="Test sort attrs"' in resp.text
    assert 'data-sort-status="completed"' in resp.text
    assert "data-sort-created=" in resp.text
    assert "data-sort-duration=" in resp.text


def test_history_duration_display(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    from datetime import UTC, datetime, timedelta

    now = datetime.now(tz=UTC)
    make_item(
        db_session,
        item_id="I-00001",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
        completed_at=now + timedelta(minutes=5, seconds=30),
    )

    resp = client.get("/project/test-proj/history")
    assert resp.status_code == 200
    # Duration should be formatted (not raw seconds)
    assert "5m30s" in resp.text


def test_history_clear_link_shown_with_filters(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/history?type=Issue")
    assert resp.status_code == 200
    assert 'href="?"' in resp.text
    assert "Clear" in resp.text


def test_history_no_clear_link_without_filters(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/project/test-proj/history")
    assert resp.status_code == 200
    assert "Clear" not in resp.text


def test_history_404_for_unknown_project(client: TestClient, db_session: Any) -> None:
    resp = client.get("/project/ghost/history")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Search endpoint (htmx fragment)
# ---------------------------------------------------------------------------


def test_search_returns_empty_for_blank_query(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/api/search?q=")
    assert resp.status_code == 200
    # Blank query should return empty content (no results block)
    assert "result" not in resp.text.lower() or resp.text.strip() == ""


def test_search_returns_relevant_results(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    # Insert item with FTS-indexed content
    item = make_item(
        db_session,
        item_id="I-00001",
        title="Template rendering timeout",
        design_doc_content="WeasyPrint times out when rendering large templates.",
    )

    resp = client.get("/api/search?q=rendering")
    assert resp.status_code == 200
    assert "I-00001" in resp.text
    assert item.title in resp.text


def test_search_no_results_shows_empty_state(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(
        db_session,
        item_id="I-00001",
        title="Completely unrelated",
        design_doc_content="Nothing matching here.",
    )

    resp = client.get("/api/search?q=xylophone")
    assert resp.status_code == 200
    assert "No results" in resp.text


def test_search_project_filter(client: TestClient, db_session: Any) -> None:
    make_project(db_session, project_id="proj-a")
    proj_b = Project(
        id="proj-b",
        display_name="Project B",
        repo_root="/repos/b",  # noqa: S108
        config={},
    )
    db_session.add(proj_b)
    db_session.flush()

    make_item(
        db_session,
        project_id="proj-a",
        item_id="I-00001",
        title="Timeout in alpha",
        design_doc_content="rendering timeout alpha",
    )
    item_b = WorkItem(
        project_id="proj-b",
        id="I-00001",
        type=WorkItemType.Issue,
        title="Timeout in beta",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
        config={},
        depends_on=[],
        blocks=[],
        design_doc_content="rendering timeout beta",
    )
    db_session.add(item_b)
    db_session.flush()

    resp = client.get("/api/search?q=timeout&project=proj-a")
    assert resp.status_code == 200
    assert "Timeout in alpha" in resp.text
    assert "Timeout in beta" not in resp.text


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------


def test_system_status_returns_200(client: TestClient, db_session: Any) -> None:
    resp = client.get("/system/status")
    assert resp.status_code == 200
    assert "System Status" in resp.text


def test_system_status_shows_projects(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/system/status")
    assert resp.status_code == 200
    assert "Test Project" in resp.text


def test_system_status_shows_daemon_panel(client: TestClient, db_session: Any) -> None:
    resp = client.get("/system/status")
    assert resp.status_code == 200
    assert "Daemon" in resp.text


def test_system_status_shows_llm_quota_panel(client: TestClient, db_session: Any) -> None:
    resp = client.get("/system/status")
    assert resp.status_code == 200
    assert "LLM Quota" in resp.text


# ---------------------------------------------------------------------------
# All active work
# ---------------------------------------------------------------------------


def test_all_active_returns_200(client: TestClient, db_session: Any) -> None:
    resp = client.get("/system/all-active")
    assert resp.status_code == 200
    assert "All Active Work" in resp.text


def test_all_active_shows_in_progress_items(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    item = make_item(
        db_session,
        item_id="I-00001",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        title="In-progress work",
    )

    resp = client.get("/system/all-active")
    assert resp.status_code == 200
    assert item.id in resp.text
    assert "In-progress work" in resp.text


def test_all_active_excludes_completed_items(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    make_item(
        db_session,
        item_id="I-00001",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
        title="Done work",
    )

    resp = client.get("/system/all-active")
    assert resp.status_code == 200
    assert "I-00001" not in resp.text


def test_all_active_empty_state(client: TestClient, db_session: Any) -> None:
    resp = client.get("/system/all-active")
    assert resp.status_code == 200
    assert "No active work items" in resp.text


# ---------------------------------------------------------------------------
# System config
# ---------------------------------------------------------------------------


def test_system_config_returns_200(client: TestClient, db_session: Any) -> None:
    resp = client.get("/system/config")
    assert resp.status_code == 200
    assert "Configuration" in resp.text


def test_system_config_shows_project_configs(client: TestClient, db_session: Any) -> None:
    make_project(db_session)
    resp = client.get("/system/config")
    assert resp.status_code == 200
    assert "Test Project" in resp.text
