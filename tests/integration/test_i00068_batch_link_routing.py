"""Regression tests for I-00068 — Recent Activity batch link routing.

Bug: batch_archived events were routing to /item/ instead of /batch/.
Fix S01 (backend): _emit() now sets entity_type="batch" for batch events.
Fix S03 (frontend): dashboard.html checks entity_type=="batch" first,
                    then falls back to entity_id.startswith("BATCH-").

Tests verify SPECIFIC VALUES (not just shapes) to prevent silent regressions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.archive.batch_archiver import _emit
from orch.db.models import DaemonEvent, Project

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
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def make_daemon_event(
    db: Any,
    project_id: str = "test-proj",
    event_type: str = "batch.started",
    entity_id: str | None = "BATCH-00001",
    entity_type: str | None = "batch",
    message: str | None = "Batch started",
) -> DaemonEvent:
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        entity_type=entity_type,
        message=message,
    )
    db.add(event)
    db.flush()
    return event


# ---------------------------------------------------------------------------
# Backend tests
# ---------------------------------------------------------------------------


def test_batch_archiver_emit_writes_entity_type_batch(db_session: Any) -> None:
    """_emit() for a batch_archived event sets entity_type='batch'.

    This test would FAIL on main (pre-fix _emit does not set entity_type).
    After S01, _emit accepts entity_type kwarg and writes it to the row.
    """
    _emit(
        db_session,
        event_type="batch_archived",
        project_id="test-proj",
        batch_id="BATCH-99099",
        message="Batch BATCH-99099 archived successfully",
        entity_type="batch",
    )
    db_session.commit()

    row = db_session.scalars(
        select(DaemonEvent).where(DaemonEvent.entity_id == "BATCH-99099")
    ).one()

    assert row.entity_type == "batch", f"expected entity_type='batch', got {row.entity_type!r}"
    assert row.entity_id == "BATCH-99099"
    assert row.event_type == "batch_archived"


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------


def test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_batch(
    client: TestClient, db_session: Any
) -> None:
    """When entity_type='batch', the Recent Activity link goes to /batch/.

    This already worked pre-fix (explicit entity_type branch existed).
    Regression-prevention test to lock in the explicit-branch behaviour.
    """
    make_project(db_session)
    make_daemon_event(
        db_session,
        event_type="batch_archived",
        entity_id="BATCH-99099",
        entity_type="batch",
        message="Batch archived",
    )

    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert 'href="/project/test-proj/batch/BATCH-99099"' in resp.text
    assert 'href="/project/test-proj/item/BATCH-99099"' not in resp.text


def test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_none(
    client: TestClient, db_session: Any
) -> None:
    """When entity_type=None but entity_id starts with 'BATCH-', link goes to /batch/.

    This test would FAIL on main (pre-fix template falls through to /item/).
    After S03, the template's BATCH- prefix check handles this case.
    """
    make_project(db_session)
    make_daemon_event(
        db_session,
        event_type="batch_archived",
        entity_id="BATCH-99099",
        entity_type=None,
        message="Batch archived",
    )

    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert 'href="/project/test-proj/batch/BATCH-99099"' in resp.text
    assert 'href="/project/test-proj/item/BATCH-99099"' not in resp.text


def test_dashboard_falls_back_to_item_for_non_batch_id_with_no_entity_type(
    client: TestClient, db_session: Any
) -> None:
    """A work-item ID (I-99099) with entity_type=None routes to /item/.

    Guards against accidentally over-matching 'BATCH-' prefix logic.
    """
    make_project(db_session)
    make_daemon_event(
        db_session,
        event_type="step.completed",
        entity_id="I-99099",
        entity_type=None,
        message="Step completed",
    )

    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert 'href="/project/test-proj/item/I-99099"' in resp.text
    assert 'href="/project/test-proj/batch/I-99099"' not in resp.text


def test_dashboard_falls_back_to_item_for_lowercase_batch_prefix(
    client: TestClient, db_session: Any
) -> None:
    """entity_id='batch-99099' (lowercase) with entity_type=None routes to /item/.

    Locks in case-sensitivity: the prefix check is 'BATCH-', not 'batch-'.
    """
    make_project(db_session)
    make_daemon_event(
        db_session,
        event_type="batch_archived",
        entity_id="batch-99099",
        entity_type=None,
        message="Batch archived",
    )

    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert 'href="/project/test-proj/item/batch-99099"' in resp.text
    assert 'href="/project/test-proj/batch/batch-99099"' not in resp.text


def test_dashboard_does_not_match_batchfoo_prefix_without_dash(
    client: TestClient, db_session: Any
) -> None:
    """entity_id='BATCHFOO' (no dash) with entity_type=None routes to /item/.

    Locks in the trailing-dash requirement of the startswith('BATCH-') check.
    """
    make_project(db_session)
    make_daemon_event(
        db_session,
        event_type="batch_archived",
        entity_id="BATCHFOO",
        entity_type=None,
        message="Batch archived",
    )

    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert 'href="/project/test-proj/item/BATCHFOO"' in resp.text
    assert 'href="/project/test-proj/batch/BATCHFOO"' not in resp.text


def test_dashboard_existing_entity_type_branches_unchanged(
    client: TestClient, db_session: Any
) -> None:
    """Explicit entity_type branches (batch, doc_job, work_item) are unchanged.

    Ensures no regression on the existing explicit branches.
    """
    make_project(db_session)
    make_daemon_event(
        db_session,
        event_type="batch_archived",
        entity_id="BATCH-90001",
        entity_type="batch",
        message="Batch archived",
    )
    make_daemon_event(
        db_session,
        event_type="doc_job.started",
        entity_id="DOCJOB-90001",
        entity_type="doc_job",
        message="Doc job started",
    )
    make_daemon_event(
        db_session,
        event_type="work_item.started",
        entity_id="I-90001",
        entity_type="work_item",
        message="Work item started",
    )

    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert 'href="/project/test-proj/batch/BATCH-90001"' in resp.text
    assert 'href="/project/test-proj/jobs/doc/DOCJOB-90001"' in resp.text
    assert 'href="/project/test-proj/item/I-90001"' in resp.text


# ---------------------------------------------------------------------------
# End-to-end test
# ---------------------------------------------------------------------------


def test_archived_batch_event_renders_correct_dashboard_link(
    client: TestClient, db_session: Any
) -> None:
    """End-to-end: _emit for batch_archived → DaemonEvent row → dashboard /batch/ link.

    Exercises the full regression scenario from the bug report.
    """
    make_project(db_session)

    # Call _emit directly as S01 fix does — sets entity_type="batch"
    _emit(
        db_session,
        event_type="batch_archived",
        project_id="test-proj",
        batch_id="BATCH-99999",
        message="Batch BATCH-99999 archived successfully",
        entity_type="batch",
    )
    db_session.commit()

    # Verify the row in the DB
    row = db_session.scalars(
        select(DaemonEvent).where(DaemonEvent.entity_id == "BATCH-99999")
    ).one()
    assert row.entity_type == "batch"
    assert row.event_type == "batch_archived"

    # Verify the dashboard renders the correct /batch/ link
    resp = client.get("/project/test-proj/")
    assert resp.status_code == 200
    assert 'href="/project/test-proj/batch/BATCH-99999"' in resp.text
    assert 'href="/project/test-proj/item/BATCH-99999"' not in resp.text
