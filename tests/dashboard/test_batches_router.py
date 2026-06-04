"""Tests for CR-00058 S03: scope status pill (held + policy_allowed) in batches router.

Verifies that _get_scope_statuses returns the correct record shape for both
event types and that held takes precedence over policy_allowed when both exist
within the window.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.batches import (
    _batch_item_rows,
    _get_scope_statuses,
)
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


def _seed_project(
    db_session: Session,
    project_id: str = "test-scope-proj",
) -> Project:
    project = Project(
        id=project_id,
        display_name="Test Scope Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


def _seed_work_item(
    db_session: Session,
    project_id: str,
    work_item_id: str,
    title: str = "Test Item",
) -> WorkItem:
    work_item = WorkItem(
        id=work_item_id,
        project_id=project_id,
        title=title,
        type=WorkItemType.Feature,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.in_progress,
        config={"scope_extraction": {"source": "declared"}},
        depends_on=[],
        blocks=[],
        impacted_paths=["src/**/*.py"],
    )
    db_session.add(work_item)
    db_session.flush()
    return work_item


def _seed_batch_and_items(
    db_session: Session,
    project_id: str,
    batch_id: str,
    work_item_ids: list[str],
    status: BatchItemStatus = BatchItemStatus.pending,
) -> None:
    batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
    db_session.add(batch)
    for _idx, wi_id in enumerate(work_item_ids):
        bi = BatchItem(
            project_id=project_id,
            batch_id=batch_id,
            work_item_id=wi_id,
            status=status,
            execution_group=0,
        )
        db_session.add(bi)
    db_session.flush()


# ---------------------------------------------------------------------------
# _get_scope_statuses unit tests
# ---------------------------------------------------------------------------


class TestGetScopeStatuses:
    """Unit tests for _get_scope_statuses helper."""

    def test_no_events_returns_empty_dict(self, db_session: Session) -> None:
        """No DaemonEvent rows → empty dict."""
        project_id = "test-no-events-scope"
        _seed_project(db_session, project_id)

        result = _get_scope_statuses(project_id, ["WI-001", "WI-002"], db_session)
        assert result == {}

    def test_policy_allowed_event_returns_policy_allowed_status(self, db_session: Session) -> None:
        """An item with only item_overlap_allowed_by_policy event → status='policy_allowed'."""
        project_id = "test-policy-allowed"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-POLICY-ALLOWED")
        _seed_batch_and_items(db_session, project_id, "batch-policy-allowed", ["WI-POLICY-ALLOWED"])

        ev = DaemonEvent(
            project_id=project_id,
            event_type="item_overlap_allowed_by_policy",
            entity_id="WI-POLICY-ALLOWED",
            entity_type="work_item",
            message="Allowed by policy",
            event_metadata={
                "candidate": "WI-POLICY-ALLOWED",
                "in_flight_item_ids": ["I-BLOCKER-1", "I-BLOCKER-2"],
                "matched_allow_patterns": ["tests/**", "docs/**"],
                "dropped_block_globs": ["tests/**/*.py"],
            },
        )
        db_session.add(ev)
        db_session.flush()

        result = _get_scope_statuses(project_id, ["WI-POLICY-ALLOWED"], db_session)

        assert "WI-POLICY-ALLOWED" in result
        record = result["WI-POLICY-ALLOWED"]
        assert record.status == "policy_allowed"
        assert record.matched_allow_patterns == ["tests/**", "docs/**"]
        assert record.blocking_item_ids == ["I-BLOCKER-1", "I-BLOCKER-2"]
        assert record.matched_globs == ["tests/**/*.py"]

    def test_held_event_returns_held_status(self, db_session: Session) -> None:
        """An item with only item_held_for_scope event → status='held'."""
        project_id = "test-held-scope"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-HELD-SCOPE")
        _seed_batch_and_items(db_session, project_id, "batch-held-scope", ["WI-HELD-SCOPE"])

        ev = DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id="WI-HELD-SCOPE",
            entity_type="work_item",
            message="Held: overlaps with I-HELD-BLOCKER on `src/**/*.py`",
            event_metadata={
                "candidate": "WI-HELD-SCOPE",
                "blocking_item_id": "I-HELD-BLOCKER",
                "conflicting_globs": ["src/**/*.py"],
            },
        )
        db_session.add(ev)
        db_session.flush()

        result = _get_scope_statuses(project_id, ["WI-HELD-SCOPE"], db_session)

        assert "WI-HELD-SCOPE" in result
        record = result["WI-HELD-SCOPE"]
        assert record.status == "held"
        assert record.blocking_item_ids == ["I-HELD-BLOCKER"]
        assert record.matched_globs == ["src/**/*.py"]

    def test_both_events_held_precedence(self, db_session: Session) -> None:
        """An item with both event types within window → status='held' (held takes precedence)."""
        project_id = "test-both-events"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-BOTH-EVENTS")
        _seed_batch_and_items(db_session, project_id, "batch-both-events", ["WI-BOTH-EVENTS"])

        # Add held event
        held_ev = DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id="WI-BOTH-EVENTS",
            entity_type="work_item",
            message="Held",
            event_metadata={
                "candidate": "WI-BOTH-EVENTS",
                "blocking_item_id": "I-HELD-BLOCKER",
                "conflicting_globs": ["src/main.py"],
            },
        )
        db_session.add(held_ev)

        # Add policy_allowed event
        policy_ev = DaemonEvent(
            project_id=project_id,
            event_type="item_overlap_allowed_by_policy",
            entity_id="WI-BOTH-EVENTS",
            entity_type="work_item",
            message="Allowed by policy",
            event_metadata={
                "candidate": "WI-BOTH-EVENTS",
                "in_flight_item_ids": ["I-POLICY-BLOCKER"],
                "matched_allow_patterns": ["tests/**"],
                "dropped_block_globs": ["tests/**/*.py"],
            },
        )
        db_session.add(policy_ev)
        db_session.flush()

        result = _get_scope_statuses(project_id, ["WI-BOTH-EVENTS"], db_session)

        assert "WI-BOTH-EVENTS" in result
        record = result["WI-BOTH-EVENTS"]
        assert record.status == "held", (
            f"Expected 'held' when both event types exist, got {record.status!r}"
        )
        assert record.blocking_item_ids == ["I-HELD-BLOCKER"]

    def test_old_event_outside_window_is_ignored(self, db_session: Session) -> None:
        """An event older than window_secs is not returned."""
        project_id = "test-old-scope-event"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-OLD-SCOPE")
        _seed_batch_and_items(db_session, project_id, "batch-old-scope", ["WI-OLD-SCOPE"])

        ev = DaemonEvent(
            project_id=project_id,
            event_type="item_overlap_allowed_by_policy",
            entity_id="WI-OLD-SCOPE",
            entity_type="work_item",
            message="Allowed by policy",
            event_metadata={
                "candidate": "WI-OLD-SCOPE",
                "in_flight_item_ids": ["I-OLD-BLOCKER"],
                "matched_allow_patterns": ["tests/**"],
                "dropped_block_globs": [],
            },
            created_at=datetime.now(UTC) - timedelta(seconds=600),
        )
        db_session.add(ev)
        db_session.flush()

        # window_secs=300 (default), event is 600s old → ignored
        result = _get_scope_statuses(project_id, ["WI-OLD-SCOPE"], db_session)
        assert "WI-OLD-SCOPE" not in result

    def test_multiple_items_each_get_correct_status(self, db_session: Session) -> None:
        """Multiple items with different event types → correct status per item."""
        project_id = "test-multi-item-scope"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-ITEM-HELD")
        _seed_work_item(db_session, project_id, "WI-ITEM-ALLOWED")
        _seed_batch_and_items(
            db_session,
            project_id,
            "batch-multi-item",
            ["WI-ITEM-HELD", "WI-ITEM-ALLOWED"],
        )

        # Held item
        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_held_for_scope",
                entity_id="WI-ITEM-HELD",
                entity_type="work_item",
                message="Held",
                event_metadata={
                    "candidate": "WI-ITEM-HELD",
                    "blocking_item_id": "I-HELD",
                    "conflicting_globs": ["src/a.py"],
                },
            )
        )
        # Policy allowed item
        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_overlap_allowed_by_policy",
                entity_id="WI-ITEM-ALLOWED",
                entity_type="work_item",
                message="Allowed",
                event_metadata={
                    "candidate": "WI-ITEM-ALLOWED",
                    "in_flight_item_ids": ["I-ALLOWED-BLOCKER"],
                    "matched_allow_patterns": ["tests/**"],
                    "dropped_block_globs": [],
                },
            )
        )
        db_session.flush()

        result = _get_scope_statuses(project_id, ["WI-ITEM-HELD", "WI-ITEM-ALLOWED"], db_session)

        assert result["WI-ITEM-HELD"].status == "held"
        assert result["WI-ITEM-ALLOWED"].status == "policy_allowed"


class TestGetScopeStatusesSqlRoundTrip:
    """Assert that _get_scope_statuses uses a single combined query."""

    def test_combined_query_single_round_trip(self, db_session: Session) -> None:
        """SQLAlchemy event listener confirms only one query for both event types."""
        project_id = "test-sql-round-trip"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-SQL-1")
        _seed_work_item(db_session, project_id, "WI-SQL-2")
        _seed_batch_and_items(db_session, project_id, "batch-sql", ["WI-SQL-1", "WI-SQL-2"])

        # Held for WI-SQL-1
        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_held_for_scope",
                entity_id="WI-SQL-1",
                entity_type="work_item",
                message="Held",
                event_metadata={
                    "candidate": "WI-SQL-1",
                    "blocking_item_id": "I-SQL-BLOCKER",
                    "conflicting_globs": ["src/x.py"],
                },
            )
        )
        # Policy allowed for WI-SQL-2
        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_overlap_allowed_by_policy",
                entity_id="WI-SQL-2",
                entity_type="work_item",
                message="Allowed",
                event_metadata={
                    "candidate": "WI-SQL-2",
                    "in_flight_item_ids": ["I-SQL-BLOCKER-2"],
                    "matched_allow_patterns": ["tests/**"],
                    "dropped_block_globs": [],
                },
            )
        )
        db_session.flush()

        # Track number of SELECT queries executed during _get_scope_statuses
        queries: list[str] = []

        def _track(conn: object, cursor: object, statement: str, *args: object) -> None:
            if statement.strip().upper().startswith("SELECT"):
                queries.append(statement)

        engine = db_session.get_bind()
        event.listen(engine, "before_cursor_execute", _track)

        try:
            result = _get_scope_statuses(project_id, ["WI-SQL-1", "WI-SQL-2"], db_session)
        finally:
            event.remove(engine, "before_cursor_execute", _track)

        # Should have exactly one SELECT (combined query for both event types)
        select_queries = [q for q in queries if "SELECT" in q.upper()]
        assert len(select_queries) == 1, (
            f"Expected 1 combined SELECT, got {len(select_queries)}. Queries: {select_queries}"
        )

        # Verify correct results
        assert result["WI-SQL-1"].status == "held"
        assert result["WI-SQL-2"].status == "policy_allowed"


# ---------------------------------------------------------------------------
# _batch_item_rows integration: scope_status field
# ---------------------------------------------------------------------------


class TestBatchItemRowsScopeStatus:
    """_batch_item_rows surfaces scope_status for pending items with events."""

    def test_scope_status_held_for_pending_item_with_held_event(self, db_session: Session) -> None:
        """Pending item + recent held event → scope_status.status == 'held'."""
        project_id = "test-br-held"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-BR-HELD")
        _seed_batch_and_items(db_session, project_id, "batch-br-held", ["WI-BR-HELD"])

        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_held_for_scope",
                entity_id="WI-BR-HELD",
                entity_type="work_item",
                message="Held",
                event_metadata={
                    "candidate": "WI-BR-HELD",
                    "blocking_item_id": "I-BR-BLOCKER",
                    "conflicting_globs": ["src/main.py"],
                },
            )
        )
        db_session.flush()

        scope_statuses = _get_scope_statuses(project_id, ["WI-BR-HELD"], db_session)
        rows = _batch_item_rows(
            project_id, "batch-br-held", db_session, scope_statuses=scope_statuses
        )

        assert len(rows) == 1
        assert rows[0].item_id == "WI-BR-HELD"
        assert rows[0].scope_status is not None
        assert rows[0].scope_status.status == "held"

    def test_scope_status_policy_allowed_for_item_with_policy_event(
        self, db_session: Session
    ) -> None:
        """Pending item + policy_allowed event → scope_status.status == 'policy_allowed'."""
        project_id = "test-br-policy"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-BR-POLICY")
        _seed_batch_and_items(db_session, project_id, "batch-br-policy", ["WI-BR-POLICY"])

        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_overlap_allowed_by_policy",
                entity_id="WI-BR-POLICY",
                entity_type="work_item",
                message="Allowed by policy",
                event_metadata={
                    "candidate": "WI-BR-POLICY",
                    "in_flight_item_ids": ["I-BR-POLICY-BLOCKER"],
                    "matched_allow_patterns": ["tests/**", "docs/**"],
                    "dropped_block_globs": ["tests/**/*.py"],
                },
            )
        )
        db_session.flush()

        scope_statuses = _get_scope_statuses(project_id, ["WI-BR-POLICY"], db_session)
        rows = _batch_item_rows(
            project_id, "batch-br-policy", db_session, scope_statuses=scope_statuses
        )

        assert len(rows) == 1
        assert rows[0].item_id == "WI-BR-POLICY"
        assert rows[0].scope_status is not None
        assert rows[0].scope_status.status == "policy_allowed"
        assert rows[0].scope_status.matched_allow_patterns == ["tests/**", "docs/**"]

    def test_scope_status_none_when_no_events(self, db_session: Session) -> None:
        """Item with no events → scope_status is None."""
        project_id = "test-br-none"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-BR-NONE")
        _seed_batch_and_items(db_session, project_id, "batch-br-none", ["WI-BR-NONE"])

        scope_statuses = _get_scope_statuses(project_id, ["WI-BR-NONE"], db_session)
        rows = _batch_item_rows(
            project_id, "batch-br-none", db_session, scope_statuses=scope_statuses
        )

        assert len(rows) == 1
        assert rows[0].item_id == "WI-BR-NONE"
        assert rows[0].scope_status is None


# ---------------------------------------------------------------------------
# HTTP smoke: fragment renders policy_allowed pill
# ---------------------------------------------------------------------------


class TestHttpPolicyAllowedPill:
    """Smoke test: GET /project/{id}/batch/{id}/fragment/items includes policy_allowed pill."""

    def test_fragment_renders_policy_allowed_pill(
        self, client: TestClient, db_session: Session
    ) -> None:
        """A pending item with item_overlap_allowed_by_policy event → info-tone pill in HTML."""
        project_id = "test-http-policy"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-HTTP-POLICY")
        _seed_batch_and_items(db_session, project_id, "batch-http-policy", ["WI-HTTP-POLICY"])

        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_overlap_allowed_by_policy",
                entity_id="WI-HTTP-POLICY",
                entity_type="work_item",
                message="Allowed",
                event_metadata={
                    "candidate": "WI-HTTP-POLICY",
                    "in_flight_item_ids": ["I-HTTP-BLOCKER"],
                    "matched_allow_patterns": ["tests/**"],
                    "dropped_block_globs": ["tests/**/*.py"],
                },
            )
        )
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{project_id}/batch/batch-http-policy/fragment/items")
        assert response.status_code == 200, response.text
        html = response.text
        # The template must render a pill with the policy_allowed pattern
        assert "tests/**" in html
        assert "policy" in html.lower() or "allowed" in html.lower()

    def test_fragment_renders_held_pill_when_both_events_exist(
        self, client: TestClient, db_session: Session
    ) -> None:
        """An item with both held and policy_allowed events → renders held pill (precedence)."""
        project_id = "test-http-both"
        _seed_project(db_session, project_id)
        _seed_work_item(db_session, project_id, "WI-HTTP-BOTH")
        _seed_batch_and_items(db_session, project_id, "batch-http-both", ["WI-HTTP-BOTH"])

        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_held_for_scope",
                entity_id="WI-HTTP-BOTH",
                entity_type="work_item",
                message="Held",
                event_metadata={
                    "candidate": "WI-HTTP-BOTH",
                    "blocking_item_id": "I-HTTP-HELD-BLOCKER",
                    "conflicting_globs": ["src/main.py"],
                },
            )
        )
        db_session.add(
            DaemonEvent(
                project_id=project_id,
                event_type="item_overlap_allowed_by_policy",
                entity_id="WI-HTTP-BOTH",
                entity_type="work_item",
                message="Allowed",
                event_metadata={
                    "candidate": "WI-HTTP-BOTH",
                    "in_flight_item_ids": ["I-HTTP-POLICY-BLOCKER"],
                    "matched_allow_patterns": ["tests/**"],
                    "dropped_block_globs": [],
                },
            )
        )
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{project_id}/batch/batch-http-both/fragment/items")
        assert response.status_code == 200, response.text
        html = response.text
        # Held pill must be shown (precedence), not policy_allowed
        assert "I-HTTP-HELD-BLOCKER" in html
        assert "Held:" in html or "held" in html.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
