"""Tests for CR-00036: auto-merge toggle on the batch detail Plan tab.

Verifies via the HTTP endpoint (TestClient + testcontainer DB) that:
- AC11a: toggle is enabled when batch is in planning|approved|paused
- AC11b: toggle is disabled when batch is in executing|completed
- Toggle is pre-checked according to batch.auto_merge
"""

from __future__ import annotations

import os
import re
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
# Helpers
# ---------------------------------------------------------------------------


def _seed_project(db_session: Session, project_id: str = "test-auto-merge-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Auto Merge Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


def _make_batch(
    db_session: Session,
    project_id: str,
    batch_id: str,
    status: BatchStatus,
    auto_merge: bool,
) -> Batch:
    batch = Batch(
        id=batch_id,
        project_id=project_id,
        status=status,
        max_parallel=5,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=auto_merge,
        execution_plan_md="# Plan\nTest plan content",
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def _find_auto_merge_toggle(html: str) -> str | None:
    """Return the HTML of the auto-merge toggle input element, or None if not found."""
    idx = html.find('id="auto-merge-toggle"')
    if idx == -1:
        return None
    start = html.rfind("<", 0, idx)
    end = html.find(">", idx)
    return html[start : end + 1]


def _has_disabled_attr(html: str) -> bool:
    """Return True if the toggle has a real HTML `disabled` boolean attribute.

    Matches `disabled` as a standalone boolean attribute value (not `disabled:` in
    Tailwind class values like `disabled:opacity-50`).
    """
    toggle = _find_auto_merge_toggle(html)
    if toggle is None:
        return False
    # Match `disabled` as a standalone word followed by space, closing slash, or
    # end of attribute string — not `disabled:` (Tailwind) or `disabled=` (not used here).
    # Self-closing tags: `<input ... disabled />` — `disabled` followed by ` /`.
    # Void end: `<input ... disabled>` — `disabled` at end before `>`.
    return bool(re.search(r"\bdisabled\b(?=\s|/|>)", toggle))


def _add_work_item(
    db_session: Session,
    project_id: str,
    batch_id: str,
    work_item_id: str,
    title: str,
) -> None:
    wi = WorkItem(
        id=work_item_id,
        project_id=project_id,
        title=title,
        type=WorkItemType.Feature,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.approved,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(wi)
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=work_item_id,
        status=BatchItemStatus.pending,
        execution_group=0,
    )
    db_session.add(bi)
    db_session.flush()
    db_session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAutoMergeTogglePlanTab:
    """AC11a + AC11b: toggle enabled/disabled based on batch status."""

    @pytest.mark.parametrize("status", ["planning", "approved", "paused"])
    def test_toggle_enabled_and_checked_when_auto_merge_true(
        self, client: TestClient, db_session: Session, status: str
    ) -> None:
        """Toggle is enabled and checked when batch.auto_merge=True and status is editable."""
        project = _seed_project(db_session, f"test-toggle-on-{status}")
        _make_batch(
            db_session, project.id, f"BATCH-ON-{status}", BatchStatus[status], auto_merge=True
        )
        _add_work_item(
            db_session, project.id, f"BATCH-ON-{status}", f"WI-ON-{status}", "Toggle On Item"
        )

        response = client.get(f"/project/{project.id}/batch/BATCH-ON-{status}?tab=plan")
        assert response.status_code == 200, response.text
        html = response.text

        toggle = _find_auto_merge_toggle(html)
        assert toggle is not None, "auto-merge toggle must be present in plan tab"
        assert not _has_disabled_attr(html), f"toggle should NOT be disabled when status={status}"
        assert "checked" in toggle, "toggle should be checked when batch.auto_merge=True"

    @pytest.mark.parametrize("status", ["planning", "approved", "paused"])
    def test_toggle_enabled_and_unchecked_when_auto_merge_false(
        self, client: TestClient, db_session: Session, status: str
    ) -> None:
        """Toggle is enabled but unchecked when batch.auto_merge=False and status is editable."""
        project = _seed_project(db_session, f"test-toggle-off-{status}")
        _make_batch(
            db_session, project.id, f"BATCH-OFF-{status}", BatchStatus[status], auto_merge=False
        )
        _add_work_item(
            db_session, project.id, f"BATCH-OFF-{status}", f"WI-OFF-{status}", "Toggle Off Item"
        )

        response = client.get(f"/project/{project.id}/batch/BATCH-OFF-{status}?tab=plan")
        assert response.status_code == 200, response.text
        html = response.text

        toggle = _find_auto_merge_toggle(html)
        assert toggle is not None
        assert not _has_disabled_attr(html), f"toggle should NOT be disabled when status={status}"
        assert "checked" not in toggle, "toggle should NOT be checked when batch.auto_merge=False"

    @pytest.mark.parametrize("status", ["executing", "completed", "completed_with_errors"])
    def test_toggle_disabled_when_not_editable(
        self, client: TestClient, db_session: Session, status: str
    ) -> None:
        """Toggle is disabled when batch status is executing/completed."""
        project = _seed_project(db_session, f"test-toggle-disabled-{status}")
        _make_batch(
            db_session, project.id, f"BATCH-DIS-{status}", BatchStatus[status], auto_merge=True
        )
        _add_work_item(
            db_session,
            project.id,
            f"BATCH-DIS-{status}",
            f"WI-DIS-{status}",
            "Toggle Disabled Item",
        )

        response = client.get(f"/project/{project.id}/batch/BATCH-DIS-{status}?tab=plan")
        assert response.status_code == 200, response.text
        html = response.text

        toggle = _find_auto_merge_toggle(html)
        assert toggle is not None, "auto-merge toggle must be present"
        assert _has_disabled_attr(html), f"toggle SHOULD be disabled when status={status}"


if __name__ == "__main__":  # pragma: no cover - manual debug
    pytest.main([__file__, "-v"])
