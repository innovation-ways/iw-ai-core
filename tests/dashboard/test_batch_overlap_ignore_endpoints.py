"""Dashboard endpoint tests for CR-00078: per-batch overlap ignore endpoints.

Uses TestClient + db_session testcontainer to exercise the real FastAPI
handlers in `dashboard/routers/actions.py` and `dashboard/routers/batches.py`
against a real PostgreSQL clone.

Routes under test (prefix /project/{project_id}/api):
  - POST /batch/{batch_id}/overlap/{held_item_id}/ignore
  - POST /batch/{batch_id}/overlap/{held_item_id}/ignore-all
  - GET  /batch/{batch_id}/overlap/{held_item_id}          (overlap_modal in batches.py)
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchOverlapIgnore,
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


def _seed_project(db_session: Session, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="CR-00078 Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


def _seed_overlap_environment(
    db_session: Session,
    project_id: str,
    batch_id: str,
    held_item_id: str,
    blocking_item_id: str,
    conflicting_globs: list[str],
) -> None:
    """Seed project + work items + batch + batch_item + held event."""
    _seed_project(db_session, project_id)

    blocker = WorkItem(
        id=blocking_item_id,
        project_id=project_id,
        title=f"Blocker {blocking_item_id}",
        type=WorkItemType.ChangeRequest,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.in_progress,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=conflicting_globs,
    )
    db_session.add(blocker)

    held = WorkItem(
        id=held_item_id,
        project_id=project_id,
        title=f"Held {held_item_id}",
        type=WorkItemType.ChangeRequest,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.approved,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=conflicting_globs,
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

    db_session.add(
        DaemonEvent(
            project_id=project_id,
            event_type="item_held_for_scope",
            entity_id=held_item_id,
            entity_type="work_item",
            message=f"Held: {held_item_id} overlaps with {blocking_item_id}",
            event_metadata={
                "candidate_item_id": held_item_id,
                "blocking_item_id": blocking_item_id,
                "conflicting_globs": conflicting_globs,
            },
            created_at=datetime.now(UTC),
        )
    )
    db_session.flush()


# ---------------------------------------------------------------------------
# AC1 + AC2: POST /ignore
# ---------------------------------------------------------------------------


class TestIgnoreSingleEndpoint:
    """Tests for POST /batch/{batch_id}/overlap/{held_item_id}/ignore."""

    def test_post_ignore_inserts_row_and_emits_event(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC1: POST /ignore inserts one BatchOverlapIgnore row and emits one event."""
        project_id = "test-proj-ignore"
        batch_id = "BATCH-IGNORE-001"
        held_item_id = "CR-IGNORE-001"
        blocking_item_id = "CR-BLOCK-IGNORE-001"
        conflicting_globs = ["docs/readme.md", "docs/guide.md"]

        _seed_overlap_environment(
            db_session, project_id, batch_id, held_item_id, blocking_item_id, conflicting_globs
        )
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/batch/{batch_id}/overlap/{held_item_id}/ignore",
            data={
                "blocking_item_id": blocking_item_id,
                "file_pattern": "docs/readme.md",
            },
        )
        assert response.status_code == 200, response.text

        # Assert exactly 1 BatchOverlapIgnore row with expected PK
        rows = list(
            db_session.scalars(
                select(BatchOverlapIgnore).where(
                    BatchOverlapIgnore.project_id == project_id,
                    BatchOverlapIgnore.batch_id == batch_id,
                    BatchOverlapIgnore.held_item_id == held_item_id,
                    BatchOverlapIgnore.blocking_item_id == blocking_item_id,
                    BatchOverlapIgnore.file_pattern == "docs/readme.md",
                )
            ).all()
        )
        assert len(rows) == 1, f"Expected 1 BatchOverlapIgnore row, got {len(rows)}"
        assert rows[0].ignored_by == "operator"

        # Assert exactly 1 DaemonEvent with exact event_type
        events = list(
            db_session.scalars(
                select(DaemonEvent).where(
                    DaemonEvent.project_id == project_id,
                    DaemonEvent.event_type == "batch_overlap_ignored_by_operator",
                    DaemonEvent.entity_id == held_item_id,
                )
            ).all()
        )
        assert len(events) == 1, (
            f"Expected 1 batch_overlap_ignored_by_operator event, got {len(events)}"
        )
        # Semantic: event_metadata["file_pattern"] must match
        assert events[0].event_metadata is not None
        assert events[0].event_metadata.get("file_pattern") == "docs/readme.md"
        assert events[0].event_metadata.get("blocking_item_id") == blocking_item_id

    def test_post_ignore_idempotent(self, client: TestClient, db_session: Session) -> None:
        """
        AC2: POST the same ignore twice → 1 row + 2 events (audit preserved).
        """
        project_id = "test-proj-idem"
        batch_id = "BATCH-IDEM-001"
        held_item_id = "CR-IDEM-001"
        blocking_item_id = "CR-BLOCK-IDEM-001"
        conflicting_globs = ["docs/intro.md"]

        _seed_overlap_environment(
            db_session, project_id, batch_id, held_item_id, blocking_item_id, conflicting_globs
        )
        db_session.commit()

        url = f"/project/{project_id}/api/batch/{batch_id}/overlap/{held_item_id}/ignore"
        data = {"blocking_item_id": blocking_item_id, "file_pattern": "docs/intro.md"}

        r1 = client.post(url, data=data)
        assert r1.status_code == 200, r1.text

        r2 = client.post(url, data=data)
        assert r2.status_code == 200, r2.text

        # Exactly 1 BatchOverlapIgnore row (no duplicates)
        count = len(
            list(
                db_session.scalars(
                    select(BatchOverlapIgnore).where(
                        BatchOverlapIgnore.project_id == project_id,
                        BatchOverlapIgnore.batch_id == batch_id,
                        BatchOverlapIgnore.held_item_id == held_item_id,
                        BatchOverlapIgnore.blocking_item_id == blocking_item_id,
                        BatchOverlapIgnore.file_pattern == "docs/intro.md",
                    )
                ).all()
            )
        )
        assert count == 1, f"Expected 1 BatchOverlapIgnore row (idempotent), got {count}"

        # Exactly 2 DaemonEvent rows (audit preserved on second call)
        events = list(
            db_session.scalars(
                select(DaemonEvent).where(
                    DaemonEvent.project_id == project_id,
                    DaemonEvent.event_type == "batch_overlap_ignored_by_operator",
                    DaemonEvent.entity_id == held_item_id,
                )
            ).all()
        )
        assert len(events) == 2, f"Expected 2 events (audit on each call), got {len(events)}"


# ---------------------------------------------------------------------------
# POST /ignore-all endpoint
# ---------------------------------------------------------------------------


class TestIgnoreAllEndpoint:
    """Tests for POST /batch/{batch_id}/overlap/{held_item_id}/ignore-all."""

    def test_post_ignore_all_inserts_n_rows(self, client: TestClient, db_session: Session) -> None:
        """
        AC3: Seed 5 item_held_for_scope events; POST /ignore-all → 5 rows + 1 event.
        """
        project_id = "test-proj-ignore-all"
        batch_id = "BATCH-IGNORE-ALL-001"
        held_item_id = "CR-IGNORE-ALL-001"
        blocking_item_ids = ["CR-B1", "CR-B2"]
        # 5 distinct (blocking_id, file) pairs across 2 blocking items
        event_globs = [
            ("CR-B1", "docs/a.md"),
            ("CR-B1", "docs/b.md"),
            ("CR-B1", "docs/c.md"),
            ("CR-B2", "docs/d.md"),
            ("CR-B2", "docs/e.md"),
        ]

        _seed_project(db_session, project_id)

        # Seed all 5 blocking work items
        for bid in blocking_item_ids:
            wi = WorkItem(
                id=bid,
                project_id=project_id,
                title=f"Blocker {bid}",
                type=WorkItemType.ChangeRequest,
                phase=WorkItemPhase.active,
                status=WorkItemStatus.in_progress,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            )
            db_session.add(wi)

        held = WorkItem(
            id=held_item_id,
            project_id=project_id,
            title=f"Held {held_item_id}",
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

        # Emit 5 item_held_for_scope events
        for bid, glob in event_globs:
            db_session.add(
                DaemonEvent(
                    project_id=project_id,
                    event_type="item_held_for_scope",
                    entity_id=held_item_id,
                    entity_type="work_item",
                    message=f"Held: {held_item_id}",
                    event_metadata={
                        "candidate_item_id": held_item_id,
                        "blocking_item_id": bid,
                        "conflicting_globs": [glob],
                    },
                    created_at=datetime.now(UTC),
                )
            )
        db_session.flush()
        db_session.commit()

        # POST /ignore-all
        response = client.post(
            f"/project/{project_id}/api/batch/{batch_id}/overlap/{held_item_id}/ignore-all",
        )
        assert response.status_code == 200, response.text

        # Assert exactly 5 BatchOverlapIgnore rows
        rows = list(
            db_session.scalars(
                select(BatchOverlapIgnore).where(
                    BatchOverlapIgnore.project_id == project_id,
                    BatchOverlapIgnore.batch_id == batch_id,
                    BatchOverlapIgnore.held_item_id == held_item_id,
                )
            ).all()
        )
        assert len(rows) == 5, f"Expected 5 BatchOverlapIgnore rows, got {len(rows)}"

        # Assert exactly 1 DaemonEvent with exact event_type and count=5
        events = list(
            db_session.scalars(
                select(DaemonEvent).where(
                    DaemonEvent.project_id == project_id,
                    DaemonEvent.event_type == "batch_overlap_ignore_all_by_operator",
                    DaemonEvent.entity_id == held_item_id,
                )
            ).all()
        )
        assert len(events) == 1, (
            f"Expected 1 batch_overlap_ignore_all_by_operator event, got {len(events)}"
        )
        assert events[0].event_metadata is not None
        assert events[0].event_metadata.get("count") == 5, (
            f"Expected count=5 in event_metadata, got {events[0].event_metadata.get('count')}"
        )

    def test_post_ignore_all_idempotent(self, client: TestClient, db_session: Session) -> None:
        """
        Pre-populate 3 of 5 pairs; POST /ignore-all; assert final row count is 5.
        """
        project_id = "test-proj-ia-idem"
        batch_id = "BATCH-IA-IDEM"
        held_item_id = "CR-IA-IDEM"
        event_globs = [
            ("CR-B1", "docs/a.md"),
            ("CR-B1", "docs/b.md"),
            ("CR-B1", "docs/c.md"),
            ("CR-B2", "docs/d.md"),
            ("CR-B2", "docs/e.md"),
        ]

        _seed_project(db_session, project_id)

        for bid in ["CR-B1", "CR-B2"]:
            db_session.add(
                WorkItem(
                    id=bid,
                    project_id=project_id,
                    title=f"Blocker {bid}",
                    type=WorkItemType.ChangeRequest,
                    phase=WorkItemPhase.active,
                    status=WorkItemStatus.in_progress,
                    config={},
                    depends_on=[],
                    blocks=[],
                    impacted_paths=[],
                )
            )
        # Held item must exist in work_items for the batch_items FK
        db_session.add(
            WorkItem(
                id=held_item_id,
                project_id=project_id,
                title=f"Held {held_item_id}",
                type=WorkItemType.ChangeRequest,
                phase=WorkItemPhase.active,
                status=WorkItemStatus.approved,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            )
        )
        db_session.flush()

        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.approved)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=held_item_id,
                status=BatchItemStatus.pending,
                execution_group=0,
            )
        )
        db_session.flush()  # Persist batch_items so FK is visible to pre-ignore rows

        for bid, glob in event_globs:
            db_session.add(
                DaemonEvent(
                    project_id=project_id,
                    event_type="item_held_for_scope",
                    entity_id=held_item_id,
                    entity_type="work_item",
                    message="Held",
                    event_metadata={
                        "candidate_item_id": held_item_id,
                        "blocking_item_id": bid,
                        "conflicting_globs": [glob],
                    },
                    created_at=datetime.now(UTC),
                )
            )

        # Pre-populate 3 ignores — must be added AFTER batch_item is flushed
        pre_ignore_globs = [
            ("CR-B1", "docs/a.md"),
            ("CR-B1", "docs/b.md"),
            ("CR-B1", "docs/c.md"),
        ]
        for bid, glob in pre_ignore_globs:
            db_session.add(
                BatchOverlapIgnore(
                    project_id=project_id,
                    batch_id=batch_id,
                    held_item_id=held_item_id,
                    blocking_item_id=bid,
                    file_pattern=glob,
                    ignored_by="operator",
                )
            )
        db_session.flush()
        db_session.commit()

        # POST /ignore-all
        response = client.post(
            f"/project/{project_id}/api/batch/{batch_id}/overlap/{held_item_id}/ignore-all",
        )
        assert response.status_code == 200, response.text

        # Final row count must be 5 (3 pre-existing + 2 new, no duplicates)
        rows = list(
            db_session.scalars(
                select(BatchOverlapIgnore).where(
                    BatchOverlapIgnore.project_id == project_id,
                    BatchOverlapIgnore.batch_id == batch_id,
                    BatchOverlapIgnore.held_item_id == held_item_id,
                )
            ).all()
        )
        assert len(rows) == 5, f"Expected 5 BatchOverlapIgnore rows (idempotent), got {len(rows)}"


# ---------------------------------------------------------------------------
# GET /overlap/{held_item_id} — modal filters ignored files
# ---------------------------------------------------------------------------


class TestOverlapModalFiltersIgnored:
    """GET /batch/{batch_id}/overlap/{held_item_id} excludes already-ignored files."""

    def test_get_modal_filters_ignored_files(self, client: TestClient, db_session: Session) -> None:
        """Pre-ignore 2 of 5 globs; GET modal; assert those 2 globs are NOT in the response."""
        project_id = "test-proj-modal-filter"
        batch_id = "BATCH-MODAL-FILTER"
        held_item_id = "CR-MODAL-FILTER"
        blocking_item_id = "CR-BLOCK-MODAL"
        all_globs = [
            "docs/file_a.md",
            "docs/file_b.md",
            "docs/file_c.md",
            "docs/file_d.md",
            "docs/file_e.md",
        ]
        ignored_globs = ["docs/file_a.md", "docs/file_c.md"]

        _seed_overlap_environment(
            db_session, project_id, batch_id, held_item_id, blocking_item_id, all_globs
        )
        # Pre-populate ignores for 2 of 5 files
        for glob in ignored_globs:
            db_session.add(
                BatchOverlapIgnore(
                    project_id=project_id,
                    batch_id=batch_id,
                    held_item_id=held_item_id,
                    blocking_item_id=blocking_item_id,
                    file_pattern=glob,
                    ignored_by="operator",
                )
            )
        db_session.commit()

        response = client.get(
            f"/project/{project_id}/batch/{batch_id}/overlap/{held_item_id}",
        )
        assert response.status_code == 200, response.text
        html = response.text

        # The 2 ignored files must NOT appear in the response
        for glob in ignored_globs:
            assert glob not in html, (
                f"Ignored file {glob!r} must NOT appear in modal response (filtered out)"
            )

        # The 3 non-ignored files must appear in the response
        visible_globs = [g for g in all_globs if g not in ignored_globs]
        for glob in visible_globs:
            assert glob in html, f"Non-ignored file {glob!r} must appear in modal response"


# ---------------------------------------------------------------------------
# AC6: Timeline rendering — new event types appear with exact human-readable lines
# ---------------------------------------------------------------------------


class TestTimelineRendering:
    """Seed each of the 3 new event types; verify the exact human-readable lines appear."""

    def test_timeline_renders_new_event_types(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC6: Each new event type renders with the exact line from CR-00078 §5."""
        project_id = "test-timeline-new-types"
        batch_id = "BATCH-TIMELINE"
        held_item_id = "CR-TIMELINE-001"
        blocking_item_id = "CR-BLOCK-TL-001"

        _seed_overlap_environment(
            db_session,
            project_id,
            batch_id,
            held_item_id,
            blocking_item_id,
            ["docs/guide.md", "docs/readme.md"],
        )

        now = datetime.now(UTC)

        # Seed 3 events: one per new type
        event_1 = DaemonEvent(
            project_id=project_id,
            event_type="batch_overlap_ignored_by_operator",
            entity_id=held_item_id,
            entity_type="work_item",
            message=(
                f"Operator ignored overlap on docs/guide.md "
                f"with {blocking_item_id} (held: {held_item_id})"
            ),
            event_metadata={
                "candidate_item_id": held_item_id,
                "blocking_item_id": blocking_item_id,
                "file_pattern": "docs/guide.md",
                "ignored_by": "operator",
            },
            created_at=now,
        )

        event_2 = DaemonEvent(
            project_id=project_id,
            event_type="batch_overlap_ignore_all_by_operator",
            entity_id=held_item_id,
            entity_type="work_item",
            message=f"Operator ignored all 5 remaining overlaps for {held_item_id}",
            event_metadata={
                "candidate_item_id": held_item_id,
                "count": 5,
                "pairs": [
                    {"blocking_item_id": "CR-B1", "file_pattern": "docs/a.md"},
                    {"blocking_item_id": "CR-B1", "file_pattern": "docs/b.md"},
                    {"blocking_item_id": "CR-B1", "file_pattern": "docs/c.md"},
                    {"blocking_item_id": "CR-B2", "file_pattern": "docs/d.md"},
                    {"blocking_item_id": "CR-B2", "file_pattern": "docs/e.md"},
                ],
            },
            created_at=now - timedelta(seconds=1),
        )

        event_3 = DaemonEvent(
            project_id=project_id,
            event_type="batch_overlap_allowed_by_ignore",
            entity_id=held_item_id,
            entity_type="work_item",
            message=f"{held_item_id} launched — ignored overlaps with {blocking_item_id}",
            event_metadata={
                "candidate_item_id": held_item_id,
                "ignored_pairs": [
                    {"blocking_item_id": blocking_item_id, "file_pattern": "docs/readme.md"},
                ],
            },
            created_at=now - timedelta(seconds=2),
        )

        db_session.add_all([event_1, event_2, event_3])
        db_session.flush()
        db_session.commit()

        response = client.get(
            f"/project/{project_id}/batch/{batch_id}?tab=logs",
        )
        assert response.status_code == 200, response.text
        html = response.text

        # Verify the 3 exact human-readable lines from CR-00078 §5 appear in the response
        assert "Operator ignored overlap on docs/guide.md" in html, (
            "batch_overlap_ignored_by_operator must render exact line"
        )
        assert "Operator ignored all 5 remaining overlaps for" in html, (
            "batch_overlap_ignore_all_by_operator must render "
            "'Operator ignored all <N> remaining overlaps for <held_item_id>'"
        )
        assert "launched — ignored overlaps with" in html, (
            "batch_overlap_allowed_by_ignore must render "
            "'<held_item_id> launched — ignored overlaps with <blocking_id_list>'"
        )
