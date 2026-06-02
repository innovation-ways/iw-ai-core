"""Dashboard integration test: POST /batch/create-from-selection renders max_parallel correctly.

AC3: A batch created via the dashboard endpoint must have its execution_plan_md
contain the **exact** Batch.max_parallel value (5), not a hardcoded literal.

RED evidence (pre-fix):
- Pre-fix `dashboard/routers/actions.py:_build_plan` passes literal 4 to
  `generate_execution_plan_md`, `generate_drawio`, and `generate_png`.
  The resulting markdown reads "**Max Parallel**: 4" regardless of
  `Batch.max_parallel` (which is always 5 in the create endpoint).
  → `assert "**Max Parallel**: 5" in batch.execution_plan_md` FAILS.
  After S01 fix: `_build_plan` passes `batch.max_parallel` → assertion passes.

The create-from-selection endpoint hardcodes `max_parallel=5` and exposes no
form field to change it, so value=5 is the only value that can appear through
the dashboard. Value variation is covered by the unit test
`test_execution_plan_md_renders_given_max_parallel`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired to the testcontainer db_session.

    Mirrors the pattern used by tests/integration/test_dashboard_actions.py.
    """
    import os

    import dashboard.middlewares.alembic_guard as mg

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    mg._alembic_guard_status = None
    mg._dashboard_last_check = 0.0
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


def test_create_batch_plan_reads_max_parallel(
    client: TestClient,
    db_session: Session,
    test_project: Project,
) -> None:
    """AC3: execution_plan_md must contain the Batch.max_parallel value (5).

    The endpoint creates the batch with max_parallel=5 (hardcoded, no form field).
    Before the fix: _build_plan passes literal 4 → markdown says
    "**Max Parallel**: 4".
    After the fix: _build_plan passes batch.max_parallel (5) → markdown says
    "**Max Parallel**: 5".
    """
    project_id = test_project.id

    # Two approved WorkItems with NON-overlapping impacted_paths.
    # Non-overlapping isolates the max_parallel bug from the overlap-detection bug.
    item_a = WorkItem(
        project_id=project_id,
        id="I-00104-A",
        type=WorkItemType.Issue,
        title="Item A — foo scope",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=["foo/a.py"],
    )
    item_b = WorkItem(
        project_id=project_id,
        id="I-00104-B",
        type=WorkItemType.Issue,
        title="Item B — bar scope",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=["bar/b.py"],
    )
    db_session.add(item_a)
    db_session.add(item_b)
    db_session.commit()

    response = client.post(
        f"/project/{project_id}/api/batch/create-from-selection",
        data={"item_ids": ["I-00104-A", "I-00104-B"]},
    )

    assert response.status_code == 204, f"expected 204; got {response.status_code}: {response.text}"

    batch = db_session.scalars(select(Batch).where(Batch.project_id == project_id)).one()

    assert batch.status == BatchStatus.planning
    assert batch.max_parallel == 5

    # AC3 assertion — exact value match
    plan_md = batch.execution_plan_md or ""
    assert "**Max Parallel**: 5" in plan_md, (
        "expected **Max Parallel**: 5 in execution_plan_md; got the actual value from the markdown"
    )
    # Defend against a future regression that re-introduces the literal 4
    assert "**Max Parallel**: 4" not in plan_md
