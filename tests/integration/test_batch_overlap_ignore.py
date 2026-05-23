"""Model-level integration tests for BatchOverlapIgnore (CR-00078).

Uses the testcontainer db_session fixture so tests exercise real PostgreSQL.
The db_session fixture (real PostgreSQL via testcontainers) lives in
tests/integration/conftest.py and is re-exported by tests/dashboard/conftest.py.
These tests intentionally live in tests/integration/ (not tests/unit/) because:
- The unit conftest's db_session is a MagicMock — insufficient for real DB assertions
- Composite PK uniqueness requires the actual PostgreSQL constraint
- server_default on ignored_at must be exercised against the real DB

Each test seeds the required parent rows (Batch, BatchItem, WorkItem for blockers)
first so the FK constraints on batch_overlap_ignore are satisfied.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchOverlapIgnore,
    Project,
    WorkItem,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _seed_batch_and_items(
    db_session: Session,
    project: Project,
    batch_id: str,
    held_item_id: str,
    blocking_item_id: str,
) -> tuple[Batch, BatchItem, WorkItem, WorkItem]:
    """Create Batch + BatchItem + held WorkItem + blocking WorkItem so all FKs satisfied."""
    batch = Batch(
        project_id=project.id,
        id=batch_id,
        status="planning",
    )
    db_session.add(batch)

    # Both held and blocking items must exist in work_items for BatchItem FK
    blocker = WorkItem(
        project_id=project.id,
        id=blocking_item_id,
        type=WorkItemType.ChangeRequest,
        title=f"Blocker item {blocking_item_id}",
        status="in_progress",
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(blocker)

    held = WorkItem(
        project_id=project.id,
        id=held_item_id,
        type=WorkItemType.ChangeRequest,
        title=f"Held item {held_item_id}",
        status="approved",
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(held)
    db_session.flush()

    batch_item = BatchItem(
        project_id=project.id,
        batch_id=batch_id,
        work_item_id=held_item_id,
        status=BatchItemStatus.pending,
        execution_group=0,
    )
    db_session.add(batch_item)
    db_session.flush()
    return batch, batch_item, blocker, held


class TestBatchOverlapIgnoreModel:
    """Model-level tests for BatchOverlapIgnore using real PostgreSQL."""

    def test_insert_and_read(self, db_session: Session, test_project: Project) -> None:
        """Insert one BatchOverlapIgnore row and verify every field round-trips."""
        _seed_batch_and_items(
            db_session,
            test_project,
            batch_id="BATCH-001",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
        )
        row = BatchOverlapIgnore(
            project_id=test_project.id,
            batch_id="BATCH-001",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
            file_pattern="docs/IW_AI_Core_Testing_Strategy.md",
            ignored_by="operator",
            reason="Intentional overlap for testing",
        )
        db_session.add(row)
        db_session.commit()

        fetched = db_session.scalar(
            select(BatchOverlapIgnore).where(
                BatchOverlapIgnore.project_id == test_project.id,
                BatchOverlapIgnore.batch_id == "BATCH-001",
                BatchOverlapIgnore.held_item_id == "CR-00072",
                BatchOverlapIgnore.blocking_item_id == "CR-00057",
                BatchOverlapIgnore.file_pattern == "docs/IW_AI_Core_Testing_Strategy.md",
            )
        )
        assert fetched is not None
        assert fetched.project_id == test_project.id
        assert fetched.batch_id == "BATCH-001"
        assert fetched.held_item_id == "CR-00072"
        assert fetched.blocking_item_id == "CR-00057"
        assert fetched.file_pattern == "docs/IW_AI_Core_Testing_Strategy.md"
        assert fetched.ignored_by == "operator"
        assert fetched.reason == "Intentional overlap for testing"
        # ignored_at is NOT NULL with server_default — DB must have set it
        assert fetched.ignored_at is not None

    def test_composite_pk_uniqueness(self, db_session: Session, test_project: Project) -> None:
        """Two inserts with identical composite PK columns raise IntegrityError."""
        _seed_batch_and_items(
            db_session,
            test_project,
            batch_id="BATCH-002",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
        )
        pk_values = {
            "project_id": test_project.id,
            "batch_id": "BATCH-002",
            "held_item_id": "CR-00072",
            "blocking_item_id": "CR-00057",
            "file_pattern": "orch/daemon/batch_manager.py",
            "ignored_by": "operator",
        }
        row1 = BatchOverlapIgnore(**pk_values)
        db_session.add(row1)
        db_session.flush()  # First insert succeeds

        row2 = BatchOverlapIgnore(**pk_values)
        db_session.add(row2)
        # The exact class must be IntegrityError (not bare Exception)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_default_ignored_at(self, db_session: Session, test_project: Project) -> None:
        """Insert with ignored_at=None (omitted) → DB populates with now()."""
        _seed_batch_and_items(
            db_session,
            test_project,
            batch_id="BATCH-003",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
        )
        row = BatchOverlapIgnore(
            project_id=test_project.id,
            batch_id="BATCH-003",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
            file_pattern="tests/test_example.py",
            ignored_by="operator",
            # ignored_at intentionally omitted — DB should apply server_default
        )
        db_session.add(row)
        db_session.commit()

        fetched = db_session.scalar(
            select(BatchOverlapIgnore).where(BatchOverlapIgnore.batch_id == "BATCH-003")
        )
        assert fetched is not None
        assert fetched.ignored_at is not None
        # Timestamp must be within the last few seconds of insertion
        now = datetime.now(UTC)
        age = (now - fetched.ignored_at).total_seconds()
        assert 0 <= age <= 5, f"ignored_at is {age:.1f}s old, expected <= 5s"

    def test_reason_optional(self, db_session: Session, test_project: Project) -> None:
        """reason is nullable — NULL value is accepted."""
        _seed_batch_and_items(
            db_session,
            test_project,
            batch_id="BATCH-004",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
        )
        row = BatchOverlapIgnore(
            project_id=test_project.id,
            batch_id="BATCH-004",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
            file_pattern="docs/guide.md",
            ignored_by="operator",
            reason=None,  # explicitly null
        )
        db_session.add(row)
        db_session.commit()

        fetched = db_session.scalar(
            select(BatchOverlapIgnore).where(BatchOverlapIgnore.batch_id == "BATCH-004")
        )
        assert fetched is not None
        assert fetched.reason is None

    def test_ignored_by_not_null(self, db_session: Session, test_project: Project) -> None:
        """ignored_by is NOT NULL — empty string is accepted by DB."""
        _seed_batch_and_items(
            db_session,
            test_project,
            batch_id="BATCH-005",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
        )
        row = BatchOverlapIgnore(
            project_id=test_project.id,
            batch_id="BATCH-005",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
            file_pattern="docs/empty.txt",
            ignored_by="",
        )
        db_session.add(row)
        db_session.commit()

        fetched = db_session.scalar(
            select(BatchOverlapIgnore).where(BatchOverlapIgnore.batch_id == "BATCH-005")
        )
        assert fetched is not None
        assert fetched.ignored_by == ""
