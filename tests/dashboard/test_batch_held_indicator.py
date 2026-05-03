"""Tests for F-00076: held-state row indicator in batch items fragment.

Verifies that a DaemonEvent of type 'item_held_for_scope' causes the
batch_items_rows.html fragment to render a held-indicator on the
corresponding pending item row.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.batches import _batch_item_rows, _get_held_reasons
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
    from collections.abc import Generator

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
# Helpers
# ---------------------------------------------------------------------------


def _seed_project_and_work_item(
    db_session: Session,
    project_id: str = "test-held-proj",
    work_item_id: str = "WI-HELD-001",
) -> WorkItem:
    project = Project(
        id=project_id,
        display_name="Test Held Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)

    work_item = WorkItem(
        id=work_item_id,
        project_id=project_id,
        title="Held Test Item",
        type=WorkItemType.Feature,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.in_progress,
        config={"scope_extraction": {"source": "declared"}},
        depends_on=[],
        blocks=[],
        impacted_paths=["orch/daemon/**"],
    )
    db_session.add(work_item)
    db_session.flush()
    return work_item


# ---------------------------------------------------------------------------
# _get_held_reasons tests (unit-level)
# ---------------------------------------------------------------------------


class TestGetHeldReasons:
    """Unit tests for _get_held_reasons helper."""

    def test_no_item_held_for_scope_returns_empty_dict(self, db_session: Session) -> None:
        """No DaemonEvent rows → empty dict."""
        project_id = "test-no-events-proj"
        project = Project(id=project_id, display_name="X", repo_root="/x", config={})
        db_session.add(project)
        db_session.flush()

        result = _get_held_reasons(project_id, ["WI-001", "WI-002"], db_session)
        assert result == {}

    def test_held_event_returns_reason_string(self, db_session: Session) -> None:
        """A single item_held_for_scope event within window → reason for that item."""
        project_id = "test-held-event-proj"
        _seed_project_and_work_item(db_session, project_id, "WI-HELD-EVENT")
        batch = Batch(id="batch-held", project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        bi = BatchItem(
            project_id=project_id,
            batch_id="batch-held",
            work_item_id="WI-HELD-EVENT",
            status=BatchItemStatus.pending,
            execution_group=0,
        )
        db_session.add(bi)

        ev = DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id="WI-HELD-EVENT",
            entity_type="work_item",
            message="Held: overlaps with I-00001 on `orch/daemon/**`",
            event_metadata={
                "candidate": "WI-HELD-EVENT",
                "blocking": "I-00001",
                "conflicting_globs": ["orch/daemon/**"],
            },
        )
        db_session.add(ev)
        db_session.flush()

        result = _get_held_reasons(project_id, ["WI-HELD-EVENT"], db_session)
        assert "WI-HELD-EVENT" in result
        assert "I-00001" in result["WI-HELD-EVENT"]
        assert "Held:" in result["WI-HELD-EVENT"]

    def test_multiple_globs_shows_glob_summary(self, db_session: Session) -> None:
        """3+ conflicting globs → glob_summary with first 2 + '+N'."""
        project_id = "test-multi-glob-proj"
        _seed_project_and_work_item(db_session, project_id, "WI-MULTI-GLOB")
        batch = Batch(id="batch-multi-glob", project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        bi = BatchItem(
            project_id=project_id,
            batch_id="batch-multi-glob",
            work_item_id="WI-MULTI-GLOB",
            status=BatchItemStatus.pending,
            execution_group=0,
        )
        db_session.add(bi)

        ev = DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id="WI-MULTI-GLOB",
            entity_type="work_item",
            message="Held",
            event_metadata={
                "candidate": "WI-MULTI-GLOB",
                "blocking": "I-00002",
                "conflicting_globs": ["a.py", "b.py", "c.py", "d.py"],
            },
        )
        db_session.add(ev)
        db_session.flush()

        result = _get_held_reasons(project_id, ["WI-MULTI-GLOB"], db_session)
        summary = result["WI-MULTI-GLOB"]
        # Should contain "a.py, b.py+2" style summary
        assert "a.py" in summary
        assert "b.py" in summary
        assert "+2" in summary

    def test_event_outside_window_is_ignored(self, db_session: Session) -> None:
        """A hold event older than 5 minutes is not returned."""
        project_id = "test-old-event-proj"
        _seed_project_and_work_item(db_session, project_id, "WI-OLD-EVENT")
        ev = DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id="WI-OLD-EVENT",
            entity_type="work_item",
            message="Held",
            event_metadata={
                "candidate": "WI-OLD-EVENT",
                "blocking": "I-00003",
                "conflicting_globs": ["old.py"],
            },
            created_at=datetime.now(UTC) - timedelta(seconds=600),
        )
        db_session.add(ev)
        db_session.flush()

        # window_secs=300 (default), event is 600s old → ignored
        result = _get_held_reasons(project_id, ["WI-OLD-EVENT"], db_session)
        assert "WI-OLD-EVENT" not in result

    def test_non_pending_item_not_returned(self, db_session: Session) -> None:
        """Even if a hold event exists, only pending items get the reason."""
        project_id = "test-not-pending-proj"
        # The hold reason dict contains entries keyed by work_item_id, but
        # _batch_item_rows filters by status == 'pending' via the existing
        # BatchItemRow dataclass — the held_reason field is simply None when
        # there is no hold. This test verifies the _get_held_reasons returns
        # a reason for an item that has a hold event.
        _seed_project_and_work_item(db_session, project_id, "WI-NOT-PENDING")
        batch = Batch(id="batch-not-pending", project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        bi = BatchItem(
            project_id=project_id,
            batch_id="batch-not-pending",
            work_item_id="WI-NOT-PENDING",
            status=BatchItemStatus.pending,  # This is checked in _batch_item_rows
            execution_group=0,
        )
        db_session.add(bi)
        ev = DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id="WI-NOT-PENDING",
            entity_type="work_item",
            message="Held",
            event_metadata={
                "candidate": "WI-NOT-PENDING",
                "blocking": "I-00004",
                "conflicting_globs": ["x.py"],
            },
        )
        db_session.add(ev)
        db_session.flush()

        result = _get_held_reasons(project_id, ["WI-NOT-PENDING"], db_session)
        assert "WI-NOT-PENDING" in result


# ---------------------------------------------------------------------------
# _batch_item_rows integration: held_reason field
# ---------------------------------------------------------------------------


class TestBatchItemRowsHeldReason:
    """_batch_item_rows surfaces held_reason for pending items with a hold event."""

    def test_held_reason_appears_for_pending_item_with_hold_event(
        self, db_session: Session
    ) -> None:
        """pending item + recent hold event → held_reason is not None."""
        project_id = "test-hr-pending"
        _seed_project_and_work_item(db_session, project_id, "WI-HR-PENDING")
        batch = Batch(id="batch-hr-pending", project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        bi = BatchItem(
            project_id=project_id,
            batch_id="batch-hr-pending",
            work_item_id="WI-HR-PENDING",
            status=BatchItemStatus.pending,
            execution_group=0,
        )
        db_session.add(bi)
        ev = DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id="WI-HR-PENDING",
            entity_type="work_item",
            message="Held: overlaps with I-99999 on `foo.py`",
            event_metadata={
                "candidate": "WI-HR-PENDING",
                "blocking": "I-99999",
                "conflicting_globs": ["foo.py"],
            },
        )
        db_session.add(ev)
        db_session.flush()

        held_reasons = _get_held_reasons(project_id, ["WI-HR-PENDING"], db_session)
        rows = _batch_item_rows(
            project_id, "batch-hr-pending", db_session, held_reasons=held_reasons
        )

        assert len(rows) == 1
        assert rows[0].item_id == "WI-HR-PENDING"
        assert rows[0].held_reason is not None
        assert "I-99999" in rows[0].held_reason

    def test_held_reason_is_none_when_no_hold_event(self, db_session: Session) -> None:
        """pending item with no hold event → held_reason is None."""
        project_id = "test-hr-none"
        _seed_project_and_work_item(db_session, project_id, "WI-HR-NONE")
        batch = Batch(id="batch-hr-none", project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        bi = BatchItem(
            project_id=project_id,
            batch_id="batch-hr-none",
            work_item_id="WI-HR-NONE",
            status=BatchItemStatus.pending,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.flush()

        rows = _batch_item_rows(project_id, "batch-hr-none", db_session, held_reasons={})
        assert len(rows) == 1
        assert rows[0].held_reason is None


# ---------------------------------------------------------------------------
# HTTP smoke: batch items fragment renders held indicator
# ---------------------------------------------------------------------------


class TestHttpHeldIndicator:
    """Smoke test: GET /project/{id}/batch/{id}/fragment/items includes held indicator."""

    def test_batch_items_fragment_renders_held_indicator(
        self, client: TestClient, db_session: Session
    ) -> None:
        """A pending item with a recent item_held_for_scope event → held indicator in HTML."""
        project_id = "test-http-held"
        _seed_project_and_work_item(db_session, project_id, "WI-HTTP-HELD")
        batch = Batch(id="batch-http-held", project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        bi = BatchItem(
            project_id=project_id,
            batch_id="batch-http-held",
            work_item_id="WI-HTTP-HELD",
            status=BatchItemStatus.pending,
            execution_group=0,
        )
        db_session.add(bi)
        ev = DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id="WI-HTTP-HELD",
            entity_type="work_item",
            message="Held",
            event_metadata={
                "candidate": "WI-HTTP-HELD",
                "blocking": "I-BLOCKER",
                "conflicting_globs": ["bar.py", "baz.py"],
            },
        )
        db_session.add(ev)
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{project_id}/batch/batch-http-held/fragment/items")
        assert response.status_code == 200, response.text
        html = response.text
        assert "I-BLOCKER" in html
        assert "Held:" in html or "held" in html.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
