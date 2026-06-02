"""Dashboard integration tests for the overlap modal endpoint (CR-00077 S05).

Uses TestClient + db_session testcontainer to exercise the real FastAPI
handlers in `dashboard/routers/batches.py` against a real PostgreSQL clone.

Route under test:
  GET /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}

AC coverage:
  AC1  — happy path: 200, grouped sections rendered, all globs present, links present
  AC2  — grouped by blocking item (two sections from two distinct blocking_item_ids)
  AC3  — AC5: 404 when no recent DaemonEvent exists
  AC4  — AC5: 404 when event is outside the 300-second window
  AC6  — read-only: no form, hx-post, hx-delete in response
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired to the testcontainer db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Session, None, None]:
            """Yield the test db_session for FastAPI dependency injection."""
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
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_project(db_session: Session, project_id: str = "p1") -> Project:
    project = Project(
        id=project_id,
        display_name="CR-00077 Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


def _seed_overlap_two_blocking_items(
    db_session: Session,
    project_id: str,
    batch_id: str,
    held_item_id: str,
    blocking_item_1: str,
    blocking_item_2: str,
    globs_1: list[str],
    globs_2: list[str],
) -> None:
    """Seed project + held item + two blocking items + batch + batch_item + two events.

    Produces two DaemonEvent rows with distinct blocker_item_ids so the modal
    renders two grouped sections.
    """
    _seed_project(db_session, project_id)

    wi_blocker_1 = WorkItem(
        id=blocking_item_1,
        project_id=project_id,
        title="First Blocker — Data-Layer Test Module",
        type=WorkItemType.ChangeRequest,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.in_progress,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=globs_1,
    )
    wi_blocker_2 = WorkItem(
        id=blocking_item_2,
        project_id=project_id,
        title="Second Blocker — Scope Amendment Work",
        type=WorkItemType.ChangeRequest,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.in_progress,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=globs_2,
    )
    held = WorkItem(
        id=held_item_id,
        project_id=project_id,
        title="Held Item for Overlap Test",
        type=WorkItemType.ChangeRequest,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.approved,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=globs_1 + globs_2,
    )
    db_session.add_all([wi_blocker_1, wi_blocker_2, held])
    db_session.flush()

    batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.approved)
    db_session.add(batch)

    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=held_item_id,
        status=BatchItemStatus.pending,
        execution_group=0,
    )
    db_session.add(bi)

    now = datetime.now(UTC)
    db_session.add(
        DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id=held_item_id,
            entity_type="work_item",
            message=f"{held_item_id} overlaps with {blocking_item_1}",
            event_metadata={
                "blocking_item_id": blocking_item_1,
                "conflicting_globs": globs_1,
            },
            created_at=now,
        )
    )
    db_session.add(
        DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id=held_item_id,
            entity_type="work_item",
            message=f"{held_item_id} overlaps with {blocking_item_2}",
            event_metadata={
                "blocking_item_id": blocking_item_2,
                "conflicting_globs": globs_2,
            },
            created_at=now - timedelta(seconds=10),
        )
    )
    db_session.flush()


def _seed_empty(db_session: Session, project_id: str, batch_id: str, held_item_id: str) -> None:
    """Seed project + batch + batch_item but NO DaemonEvent rows."""
    _seed_project(db_session, project_id)

    held = WorkItem(
        id=held_item_id,
        project_id=project_id,
        title="Held Without Events",
        type=WorkItemType.ChangeRequest,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.approved,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(held)
    db_session.flush()

    batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.approved)
    db_session.add(batch)

    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=held_item_id,
        status=BatchItemStatus.pending,
        execution_group=0,
    )
    db_session.add(bi)
    db_session.flush()


# ---------------------------------------------------------------------------
# AC1 + AC2: Happy path — grouped sections rendered (200)
# ---------------------------------------------------------------------------


class TestOverlapModalHappyPath:
    """AC1, AC2, AC3, AC6: happy path with two blocking items."""

    def test_status_200_with_two_blocking_items(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC1/AC2/AC3/AC6: modal returns 200 with both blocking items and their globs rendered."""
        project_id = "p1"
        batch_id = "BATCH-99001"
        held_item_id = "CR-99001"
        blocking_1 = "CR-99002"
        blocking_2 = "CR-99003"
        globs_1 = ["docs/Foo.md", "skills/x/**", "ai-dev/work/Y.md"]
        globs_2 = ["orch/hot.py", "dashboard/cold.py"]

        _seed_overlap_two_blocking_items(
            db_session,
            project_id,
            batch_id,
            held_item_id,
            blocking_1,
            blocking_2,
            globs_1,
            globs_2,
        )
        db_session.commit()

        url = f"/project/{project_id}/batch/{batch_id}/overlap/{held_item_id}"
        response = client.get(url)

        assert response.status_code == 200, response.text
        body = response.text

        # AC1: body contains both blocking_item_ids
        assert blocking_1 in body, f"Expected {blocking_1!r} in response body"
        assert blocking_2 in body, f"Expected {blocking_2!r} in response body"

        # AC1: body contains EVERY glob from EVERY seeded event
        for glob in globs_1:
            assert glob in body, f"Expected glob {glob!r} from blocking_1 in response body"
        for glob in globs_2:
            assert glob in body, f"Expected glob {glob!r} from blocking_2 in response body"

        # AC1: section header links to the blocking item's detail page
        assert f"/project/{project_id}/item/{blocking_1}" in body
        assert f"/project/{project_id}/item/{blocking_2}" in body

        # AC1: modal title
        assert f"Overlap details — {held_item_id}" in body

        # AC3: response is a fragment — no <html> or <body>
        assert "<html" not in body.lower(), "Response must be a fragment, not a full page"
        assert "<body" not in body.lower(), "Response must be a fragment, not a full page"

        # AC6: read-only — no form, hx-post, hx-delete
        assert "<form" not in body.lower(), "Modal must not contain form elements (read-only)"
        assert "hx-post" not in body.lower(), "Modal must not contain hx-post actions (read-only)"
        assert "hx-delete" not in body.lower(), (
            "Modal must not contain hx-delete actions (read-only)"
        )


# ---------------------------------------------------------------------------
# AC5: 404 — no recent event
# ---------------------------------------------------------------------------


class TestOverlapModalNoEvent:
    """AC5: 404 when no item_held_for_scope DaemonEvent exists."""

    def test_status_404_no_event(self, client: TestClient, db_session: Session) -> None:
        """AC5: returns 404 with empty-state message when no held event exists for the item."""
        project_id = "p1"
        batch_id = "BATCH-99001"
        held_item_id = "CR-99001"

        _seed_empty(db_session, project_id, batch_id, held_item_id)
        db_session.commit()

        url = f"/project/{project_id}/batch/{batch_id}/overlap/{held_item_id}"
        response = client.get(url)

        assert response.status_code == 404, response.text
        body = response.text

        # AC5: empty-state message present
        assert "No overlap details available" in body, (
            "Expected 'No overlap details available' in 404 body"
        )

        # AC5: still a fragment
        assert "<html" not in body.lower(), "404 response must be a fragment"
        assert "<body" not in body.lower(), "404 response must be a fragment"


# ---------------------------------------------------------------------------
# AC4: 404 — event outside the 300-second window
# ---------------------------------------------------------------------------


class TestOverlapModalWindowCutoff:
    """AC4: event with created_at older than 300 s → 404 (window cutoff regression guard)."""

    def test_status_404_event_outside_window(self, client: TestClient, db_session: Session) -> None:
        """AC4: returns 404 when the most recent held event is older than the 300-second window."""
        project_id = "p1"
        batch_id = "BATCH-99001"
        held_item_id = "CR-99001"
        blocking_item_id = "CR-99002"
        globs = ["old/file.py"]

        _seed_project(db_session, project_id)

        wi_blocker = WorkItem(
            id=blocking_item_id,
            project_id=project_id,
            title="Old Blocker",
            type=WorkItemType.ChangeRequest,
            phase=WorkItemPhase.active,
            status=WorkItemStatus.in_progress,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=globs,
        )
        held = WorkItem(
            id=held_item_id,
            project_id=project_id,
            title="Held Item",
            type=WorkItemType.ChangeRequest,
            phase=WorkItemPhase.active,
            status=WorkItemStatus.approved,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=globs,
        )
        db_session.add_all([wi_blocker, held])
        db_session.flush()

        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.approved)
        db_session.add(batch)

        bi = BatchItem(
            project_id=project_id,
            batch_id=batch_id,
            work_item_id=held_item_id,
            status=BatchItemStatus.pending,
            execution_group=0,
        )
        db_session.add(bi)

        # Event created 301 seconds ago — outside the 300-second window
        stale_time = datetime.now(UTC) - timedelta(seconds=301)
        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_held_for_scope",
                entity_id=held_item_id,
                entity_type="work_item",
                message=f"{held_item_id} overlaps with {blocking_item_id}",
                event_metadata={
                    "blocking_item_id": blocking_item_id,
                    "conflicting_globs": globs,
                },
                created_at=stale_time,
            )
        )
        db_session.flush()

        url = f"/project/{project_id}/batch/{batch_id}/overlap/{held_item_id}"
        response = client.get(url)

        assert response.status_code == 404, response.text
        body = response.text

        # AC4: empty-state message present even though an event exists but is stale
        assert "No overlap details available" in body, (
            "Expected 'No overlap details available' for event outside 300 s window"
        )
        assert "<html" not in body.lower()
        assert "<body" not in body.lower()
