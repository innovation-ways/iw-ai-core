"""Integration tests for the backfill regression-classification script (F-00090 AC8).

These tests invoke the script's public ``run()`` function directly, passing the
test's ``db_session`` so the script operates inside the test's per-test
PostgreSQL clone.  This is the same pattern used by the CLI contract tests
(``tests/integration/cli/test_*_contract.py``) — run the entry point
in-process with the test's DB session, not as a subprocess.

AC8 invariant (Invariant 3 from F-00090): the heuristic auto-classifier never
persists a classification without operator action.  These tests verify that
the backfill never writes WorkItem rows.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from orch.db.models import Project, WorkItem, WorkItemType
from scripts import backfill_regression_classification as backfill_mod

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_incidents(db_session: Session, project_id: str) -> list[WorkItem]:
    """Seed 3 Incidents: one classified 'regression', two with NULL classification."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    items = [
        WorkItem(
            project_id=project_id,
            id="I-SEED-001",
            type=WorkItemType.Issue,
            title="Existing regression",
            status="completed",
            phase="done",
            regression_classification="regression",  # already classified — skipped
            classified_by="operator:sergiog",
            classified_at=now,
            created_at=now,
        ),
        WorkItem(
            project_id=project_id,
            id="I-SEED-002",
            type=WorkItemType.Issue,
            title="Unclassified incident 1",
            status="completed",
            phase="done",
            regression_classification=None,
            created_at=now,
        ),
        WorkItem(
            project_id=project_id,
            id="I-SEED-003",
            type=WorkItemType.Issue,
            title="Unclassified incident 2",
            status="completed",
            phase="done",
            regression_classification=None,
            created_at=now,
        ),
    ]
    db_session.add_all(items)
    db_session.flush()
    return items


def _hash_work_items(session: Session, project_id: str) -> str:
    """Return a stable hash of all WorkItem rows for a project (for idempotency checks)."""
    rows = session.execute(
        select(WorkItem.id, WorkItem.regression_classification, WorkItem.classified_at)
        .where(WorkItem.project_id == project_id)
        .order_by(WorkItem.id)
    ).all()
    data = "|".join(f"{r.id}:{r.regression_classification}:{r.classified_at}" for r in rows)
    return hashlib.sha256(data.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_backfill_processes_only_unclassified_incidents(
    db_session: Session,
    test_project: Project,
) -> None:
    """Backfill visits only the NULL-classification rows.

    I-SEED-001 has regression_classification='regression' (already classified);
    the backfill must not visit it.  The summary line returned by run() includes
    'Processed N incidents' where N == count of NULL rows.
    """
    _seed_incidents(db_session, test_project.id)

    processed, had_suggestions, classified = backfill_mod.run(
        test_project.id, db_session=db_session
    )

    # Should see 2 (only the NULL-classification rows), not 3
    assert processed == 2, (
        f"Expected processed=2 (NULL rows only), got {processed}; "
        f"had_suggestions={had_suggestions}, classified={classified}"
    )
    # classified is always 0 — backfill never persists
    assert classified == 0


def test_backfill_persists_no_classifications(
    db_session: Session,
    test_project: Project,
) -> None:
    """Invariant 3: the backfill never writes WorkItem rows.

    Run the full backfill (not --dry-run); re-query all Incidents;
    assert every regression_classification IS NULL and classified_at IS NULL.
    """
    _seed_incidents(db_session, test_project.id)

    processed, had_suggestions, classified = backfill_mod.run(
        test_project.id, db_session=db_session
    )

    # Re-query to see persisted state — no classifications written by the backfill.
    # Note: I-SEED-001 was pre-seeded as classified 'regression'; the backfill's
    # WHERE clause filters it out so it never calls suggest_introducer on it.
    # We verify: (a) no new classifications appear on previously-NULL rows, and
    # (b) the pre-classified row (I-SEED-001) is untouched.
    all_incidents = (
        db_session.execute(
            select(WorkItem)
            .where(
                WorkItem.project_id == test_project.id,
                WorkItem.type == WorkItemType.Issue,
            )
            .order_by(WorkItem.id)
        )
        .scalars()
        .all()
    )

    # The backfill should not have changed any of the previously-NULL rows
    assert all(
        i.regression_classification is None for i in all_incidents if i.id != "I-SEED-001"
    ), "Backfill persisted classifications on previously-NULL rows (Invariant 3 violated)"
    # I-SEED-001 was pre-classified; backfill should not have touched it (it's excluded by WHERE)
    i_seed_001 = next(i for i in all_incidents if i.id == "I-SEED-001")
    assert i_seed_001.regression_classification is not None
    assert i_seed_001.classified_by == "operator:sergiog"
    assert classified == 0


def test_backfill_is_idempotent(
    db_session: Session,
    test_project: Project,
) -> None:
    """Running the backfill twice produces identical counts and no DB writes."""
    _seed_incidents(db_session, test_project.id)

    # Capture row state before first run
    row_hash_before = _hash_work_items(db_session, test_project.id)

    result1 = backfill_mod.run(test_project.id, db_session=db_session)
    row_hash_after1 = _hash_work_items(db_session, test_project.id)

    result2 = backfill_mod.run(test_project.id, db_session=db_session)
    row_hash_after2 = _hash_work_items(db_session, test_project.id)

    # Counts must be identical across runs
    assert result1 == result2, (
        f"Idempotency violated: counts differ between runs\n  Run1: {result1}\n  Run2: {result2}"
    )

    # No DB writes either time
    assert row_hash_before == row_hash_after1 == row_hash_after2, (
        "DB state changed after backfill run"
    )


def test_backfill_handles_zero_incidents(
    db_session: Session,
    test_project: Project,
) -> None:
    """Empty project: processed=0, no DB writes."""
    processed, had_suggestions, classified = backfill_mod.run(
        test_project.id, db_session=db_session
    )

    assert processed == 0, f"Expected processed=0, got {processed}"
    assert had_suggestions == 0
    assert classified == 0
    # No DB writes — empty project has no WorkItem rows, so the hash is
    # SHA256 of an empty string (canonical zero-rows hash).
    row_hash = _hash_work_items(db_session, test_project.id)
    zero_rows_hash = hashlib.sha256(b"").hexdigest()
    assert row_hash == zero_rows_hash
