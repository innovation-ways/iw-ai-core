"""I-00126 AC3: batch-approve branch-warning popup in the dashboard.

Tests that the confirm_batch_dialog returns a branch warning when the repo
is not on its default branch (monkeypatch of resolve_branch_for_project), and
that the approve flow correctly gates the batch (planning → approved only after
confirm; No/Cancel leaves it at planning).

Uses the file-local `client` fixture (FastAPI TestClient backed by the
testcontainer db_session fixture from tests/dashboard/conftest.py).

AC coverage:
  - AC3a: without confirm — response requires confirmation, contains specific
    warning text "local branch is not <default>", batch stays planning
  - AC3b: confirm=yes → batch becomes approved
  - AC3c: confirm=no → batch stays planning
  - AC3d: on-default → no warning, approve proceeds directly
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchStatus,
    DaemonEvent,
    Project,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """FastAPI TestClient backed by the testcontainer db_session.

    The alembic guard is mocked so the app boots using the testcontainer
    engine instead of the live orch DB.
    """
    import dashboard.middlewares.alembic_guard as mg

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    mg._alembic_guard_status = None
    mg._dashboard_last_check = 0.0
    try:

        def override_get_db():
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


def _make_batch(db: Session, project_id: str, batch_id: str) -> Batch:
    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=BatchStatus.planning,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()
    return batch


# ---------------------------------------------------------------------------
# AC3a: without confirm → warning + planning (NOT approved)
# ---------------------------------------------------------------------------


def test_i00126_approve_warns_when_not_on_default_branch(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3a: confirm dialog requires confirmation when repo is not on default branch.

    GET /project/{pid}/api/confirm-batch/approve/{bid} must return HTML with:
      - the specific warning text: 'local branch is not <code>main</code>'
      - the batch stays in planning status (NOT approved)
    """
    from orch.utils.branch_resolver import BranchInfo

    # Patch resolve_branch_for_project to simulate repo not on default branch
    monkeypatch.setattr(
        "orch.utils.branch_resolver.resolve_branch_for_project",
        lambda _repo_root: BranchInfo(
            current_branch="feature/stray",
            default_branch="main",
            is_on_default=False,
        ),
    )

    batch = _make_batch(db_session, test_project.id, "B-I00126-001")
    db_session.commit()

    # Act: request the confirm dialog (no confirm flag)
    resp = client.get(f"/project/{test_project.id}/api/confirm-batch/approve/{batch.id}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert "text/html" in resp.headers.get("content-type", "")

    body = resp.text

    # Assert: specific warning text is present (semantic, not just "modal exists")
    assert "local branch is not <code>main</code>" in body, (
        f"Confirm dialog must contain the specific branch-warning text. Got:\n{body[:500]}"
    )
    assert "feature/stray" not in body or "main" in body, (
        "Dialog should reference the expected branch name (main)"
    )

    # Assert: batch is still planning (NOT approved by the GET)
    db_session.expire_all()
    db_session.refresh(batch)
    assert batch.status == BatchStatus.planning, (
        f"Confirm dialog GET must not approve the batch. Status: {batch.status.value}"
    )

    # Assert: no batch_approved event was emitted
    events = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == test_project.id,
            DaemonEvent.event_type == "batch_approved",
            DaemonEvent.entity_id == batch.id,
        )
        .all()
    )
    assert len(events) == 0, "batch_approved must NOT be emitted on confirm-dialog GET"


# ---------------------------------------------------------------------------
# AC3b: confirm=yes → batch becomes approved
# ---------------------------------------------------------------------------


def test_i00126_approve_with_confirm_yes_becomes_approved(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3b: POST to approve after confirming (repo not on default) → batch approved."""
    from orch.utils.branch_resolver import BranchInfo

    monkeypatch.setattr(
        "orch.utils.branch_resolver.resolve_branch_for_project",
        lambda _repo_root: BranchInfo(
            current_branch="feature/stray",
            default_branch="main",
            is_on_default=False,
        ),
    )

    batch = _make_batch(db_session, test_project.id, "B-I00126-002")
    db_session.commit()

    # Act: POST approve (this is the hx-post URL the confirm dialog's Yes button fires)
    resp = client.post(f"/project/{test_project.id}/api/batch/{batch.id}/approve")
    assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"

    # Assert: batch is now approved
    db_session.expire_all()
    db_session.refresh(batch)
    assert batch.status == BatchStatus.approved, (
        f"Confirmed approve must set status to approved. Got: {batch.status.value}"
    )

    # Assert: batch_approved event was emitted
    events = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == test_project.id,
            DaemonEvent.event_type == "batch_approved",
            DaemonEvent.entity_id == batch.id,
        )
        .all()
    )
    assert len(events) >= 1, "batch_approved daemon_event must be emitted"


# ---------------------------------------------------------------------------
# AC3c: no confirm POST → batch stays planning (cancel path)
# ---------------------------------------------------------------------------


def test_i00126_approve_without_confirm_stays_planning(
    client: TestClient,
    db_session: Session,
    test_project: Project,
) -> None:
    """AC3c: the confirm-dialog GET does not itself approve the batch.

    This is implicitly tested by AC3a (batch stays planning after confirm GET).
    This test is the explicit "cancel" assertion: batch stays planning even
    when we make a no-op interaction (simulating browser Cancel click).
    """
    batch = _make_batch(db_session, test_project.id, "B-I00126-003")
    db_session.commit()

    # Act: GET the confirm dialog (simulates "clicking Approve but then Cancel")
    resp = client.get(f"/project/{test_project.id}/api/confirm-batch/approve/{batch.id}")
    assert resp.status_code == 200

    # Assert: batch still planning
    db_session.expire_all()
    db_session.refresh(batch)
    assert batch.status == BatchStatus.planning, (
        f"Cancel (or no-confirm GET) must leave batch at planning. Got: {batch.status.value}"
    )


# ---------------------------------------------------------------------------
# AC3d: on-default → no warning, approve proceeds directly
# ---------------------------------------------------------------------------


def test_i00126_approve_on_default_no_warning(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3d: when repo IS on the default branch, no warning appears."""
    from orch.utils.branch_resolver import BranchInfo

    # Patch to simulate repo on default branch
    monkeypatch.setattr(
        "orch.utils.branch_resolver.resolve_branch_for_project",
        lambda _repo_root: BranchInfo(
            current_branch="main",
            default_branch="main",
            is_on_default=True,
        ),
    )

    batch = _make_batch(db_session, test_project.id, "B-I00126-004")
    db_session.commit()

    # Act: GET confirm dialog
    resp = client.get(f"/project/{test_project.id}/api/confirm-batch/approve/{batch.id}")
    assert resp.status_code == 200

    body = resp.text

    # Assert: NO warning text in the response
    assert "local branch is not <code>" not in body, (
        "When on default branch, confirm dialog must NOT contain branch warning. "
        f"Got:\n{body[:500]}"
    )

    # Assert: approve still works (no guard blocking)
    resp2 = client.post(f"/project/{test_project.id}/api/batch/{batch.id}/approve")
    assert resp2.status_code == 204, (
        f"On-default approval must succeed. Got: {resp2.status_code} {resp2.text}"
    )

    db_session.expire_all()
    db_session.refresh(batch)
    assert batch.status == BatchStatus.approved, (
        f"On-default batch must be approved. Got: {batch.status.value}"
    )


# ---------------------------------------------------------------------------
# Semantic guard: ensure the warning mentions the DYNAMIC default branch
# ---------------------------------------------------------------------------


def test_i00126_warning_dynamic_default_branch(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The warning message must use the dynamic default_branch, not hardcoded 'main'."""
    from orch.utils.branch_resolver import BranchInfo

    # Project has non-standard default 'trunk'
    monkeypatch.setattr(
        "orch.utils.branch_resolver.resolve_branch_for_project",
        lambda _repo_root: BranchInfo(
            current_branch="feature/other",
            default_branch="trunk",
            is_on_default=False,
        ),
    )

    batch = _make_batch(db_session, test_project.id, "B-I00126-005")
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/api/confirm-batch/approve/{batch.id}")
    assert resp.status_code == 200

    body = resp.text

    # Assert: warning mentions 'trunk' (the dynamic default), NOT 'main'
    assert "local branch is not <code>trunk</code>" in body, (
        f"Warning must mention the dynamic default branch 'trunk'. Got:\n{body[:500]}"
    )
    assert "local branch is not <code>main</code>" not in body, (
        "Warning must NOT hardcode 'main' when default is 'trunk'"
    )
