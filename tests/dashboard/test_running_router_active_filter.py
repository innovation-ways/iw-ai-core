"""I-00090 — Tests for the active-item filter on /system/running.

The dashboard's `/system/running` page (and `/project/{id}/running`) must only
surface failed/completed step rows for work items that are *currently active*
— i.e. WorkItem.archived_at IS NULL AND WorkItem.status NOT IN (completed,
cancelled). Items in draft/approved/in_progress/paused/failed status DO
surface (item-level `failed` is unresolved).

See ai-dev/active/I-00090/I-00090_Issue_Design.md.
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
from dashboard.routers.running import _query_failed_steps, _query_recent_completions
from orch.db.models import (
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Client fixture (same pattern as tests/dashboard/test_docs_running_jobs.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient that overrides get_db to use the test db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Private seed helpers
# ---------------------------------------------------------------------------


def _make_project(db: Session, pid: str = "p1", display_name: str = "Project One") -> Project:
    """Create and flush a Project row."""
    project = Project(
        id=pid,
        display_name=display_name,
        repo_root=f"/repos/{pid}",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def _make_item(
    db: Session,
    project_id: str,
    item_id: str,
    *,
    status: WorkItemStatus,
    archived_at: datetime | None = None,
    title: str = "Test Work Item",
) -> WorkItem:
    """Create and flush a WorkItem row with the given status/archived state."""
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.ChangeRequest,
        title=title,
        status=status,
        phase=WorkItemPhase.active,
        archived_at=archived_at,
    )
    db.add(item)
    db.flush()
    return item


def _make_step(
    db: Session,
    project_id: str,
    work_item_id: str,
    step_id: str,
    *,
    status: StepStatus,
    step_number: int = 1,
    step_type: StepType = StepType.implementation,
) -> WorkflowStep:
    """Create and flush a WorkflowStep row."""
    step = WorkflowStep(
        project_id=project_id,
        work_item_id=work_item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label="Backend",
        step_type=step_type,
        status=status,
    )
    db.add(step)
    db.flush()
    return step


def _make_run(
    db: Session,
    step_id: int,
    *,
    status: RunStatus,
    completed_at: datetime | None = None,
    run_number: int = 1,
) -> StepRun:
    """Create and flush a StepRun row."""
    run = StepRun(
        step_id=step_id,
        run_number=run_number,
        status=status,
        completed_at=completed_at,
    )
    db.add(run)
    db.flush()
    return run


# ---------------------------------------------------------------------------
# Helper-level tests for _query_failed_steps()
# ---------------------------------------------------------------------------


class TestQueryFailedStepsExcludesCompleted:
    """Reproduction test (RED on pre-S01, GREEN after the active-item predicate).

    AC1: A WorkflowStep whose parent WorkItem.status == completed must NOT
    appear in the Failed/Needs Attention table.
    """

    def test_query_failed_steps_excludes_completed_item(self, db_session: Session) -> None:
        """RED until .where(WorkItem.status.notin_([...])) is added.

        Pre-S01 reasoning: _query_failed_steps() returned rows for ALL
        failed/needs_fix steps regardless of parent item status. With a
        completed parent item, the assertion 'CR-DEAD' not in [r.item_id for r in rows]
        would FAIL because CR-DEAD appears in the unfiltered result set.
        """
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-DEAD", status=WorkItemStatus.completed)
        _make_step(db_session, project.id, item.id, "S01", status=StepStatus.failed)
        db_session.flush()

        rows = _query_failed_steps(db_session)

        assert "CR-DEAD" not in [r.item_id for r in rows], (
            f"completed item should not surface in Failed table; got items: "
            f"{[r.item_id for r in rows]}"
        )


class TestQueryFailedStepsActiveItemsIncluded:
    """AC2: Active items (in_progress / paused / failed / draft / approved) still surface."""

    def test_query_failed_steps_includes_in_progress_item(self, db_session: Session) -> None:
        """An in_progress item with a failed step must appear."""
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-ALIVE", status=WorkItemStatus.in_progress)
        _make_step(db_session, project.id, item.id, "S01", status=StepStatus.failed)
        db_session.flush()

        rows = _query_failed_steps(db_session)
        item_ids = [r.item_id for r in rows]

        assert item_ids == ["CR-ALIVE"], (
            f"in_progress item should be the sole surfaced row; got items: {item_ids}"
        )

    def test_query_failed_steps_includes_paused_item(self, db_session: Session) -> None:
        """A paused item with a failed step must appear."""
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-PAUSED", status=WorkItemStatus.paused)
        _make_step(db_session, project.id, item.id, "S01", status=StepStatus.failed)
        db_session.flush()

        rows = _query_failed_steps(db_session)
        item_ids = [r.item_id for r in rows]

        assert item_ids == ["CR-PAUSED"], (
            f"paused item should be the sole surfaced row; got items: {item_ids}"
        )

    def test_query_failed_steps_includes_failed_item(self, db_session: Session) -> None:
        """An item whose own status=failed (unresolved problem) must still appear."""
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-BROKEN", status=WorkItemStatus.failed)
        _make_step(db_session, project.id, item.id, "S01", status=StepStatus.failed)
        db_session.flush()

        rows = _query_failed_steps(db_session)
        item_ids = [r.item_id for r in rows]

        assert item_ids == ["CR-BROKEN"], (
            f"item-level 'failed' is unresolved and must be the sole surfaced row; "
            f"got items: {item_ids}"
        )

    def test_query_failed_steps_includes_needs_fix_status(self, db_session: Session) -> None:
        """A step with status=needs_fix on an in_progress item must appear.

        Regression guard for the OR in status.in_([failed, needs_fix]).
        """
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-NEEDSFIX", status=WorkItemStatus.in_progress)
        _make_step(db_session, project.id, item.id, "S01", status=StepStatus.needs_fix)
        db_session.flush()

        rows = _query_failed_steps(db_session)
        item_ids = [r.item_id for r in rows]

        assert item_ids == ["CR-NEEDSFIX"], (
            f"needs_fix step on active item should be the sole surfaced row; got items: {item_ids}"
        )


class TestQueryFailedStepsInactiveItemsExcluded:
    """AC1: Inactive items (cancelled / archived) must NOT surface."""

    def test_query_failed_steps_excludes_cancelled_item(self, db_session: Session) -> None:
        """A cancelled item with a failed step must NOT appear."""
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-CANCELLED", status=WorkItemStatus.cancelled)
        _make_step(db_session, project.id, item.id, "S01", status=StepStatus.failed)
        db_session.flush()

        rows = _query_failed_steps(db_session)
        item_ids = [r.item_id for r in rows]

        assert "CR-CANCELLED" not in item_ids, (
            f"cancelled item should not surface; got items: {item_ids}"
        )

    def test_query_failed_steps_excludes_archived_item(self, db_session: Session) -> None:
        """An archived item (any status) with a failed step must NOT appear.

        archived_at set to now() is sufficient — status is irrelevant when
        archived_at IS NOT NULL.
        """
        project = _make_project(db_session, "p1")
        item = _make_item(
            db_session,
            project.id,
            "CR-ARCHIVED",
            status=WorkItemStatus.in_progress,
            archived_at=datetime.now(UTC),
        )
        _make_step(db_session, project.id, item.id, "S01", status=StepStatus.failed)
        db_session.flush()

        rows = _query_failed_steps(db_session)
        item_ids = [r.item_id for r in rows]

        assert "CR-ARCHIVED" not in item_ids, (
            f"archived item should not surface; got items: {item_ids}"
        )


class TestQueryFailedStepsProjectFilter:
    """Regression guard: project_id filter must still isolate projects."""

    def test_query_failed_steps_respects_project_filter(self, db_session: Session) -> None:
        """When project_id is passed, only rows from that project are returned."""
        proj_a = _make_project(db_session, "proj-a", "Project A")
        proj_b = _make_project(db_session, "proj-b", "Project B")

        item_a = _make_item(db_session, proj_a.id, "CR-A-ACTIVE", status=WorkItemStatus.in_progress)
        _make_step(db_session, proj_a.id, item_a.id, "S01", status=StepStatus.failed)

        item_b = _make_item(db_session, proj_b.id, "CR-B-ACTIVE", status=WorkItemStatus.in_progress)
        _make_step(db_session, proj_b.id, item_b.id, "S01", status=StepStatus.failed)
        db_session.flush()

        # Query scoped to project A only
        rows_a = _query_failed_steps(db_session, project_id=proj_a.id)
        item_ids_a = [r.item_id for r in rows_a]

        assert "CR-A-ACTIVE" in item_ids_a, (
            f"project A item should be in project-A-scoped result; got: {item_ids_a}"
        )
        assert "CR-B-ACTIVE" not in item_ids_a, (
            f"project B item must NOT be in project-A-scoped result; got: {item_ids_a}"
        )

        # Query scoped to project B only
        rows_b = _query_failed_steps(db_session, project_id=proj_b.id)
        item_ids_b = [r.item_id for r in rows_b]

        assert "CR-B-ACTIVE" in item_ids_b, (
            f"project B item should be in project-B-scoped result; got: {item_ids_b}"
        )
        assert "CR-A-ACTIVE" not in item_ids_b, (
            f"project A item must NOT be in project-B-scoped result; got: {item_ids_b}"
        )


# ---------------------------------------------------------------------------
# Helper-level tests for _query_recent_completions()
# ---------------------------------------------------------------------------


class TestQueryRecentCompletionsActiveItemsIncluded:
    """AC3: Active items still appear in Recently Completed."""

    def test_query_recent_completions_includes_in_progress_item(self, db_session: Session) -> None:
        """An in_progress item with a recent completed run must appear."""
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-ALIVE", status=WorkItemStatus.in_progress)
        step = _make_step(db_session, project.id, item.id, "S01", status=StepStatus.pending)
        _make_run(
            db_session,
            step.id,
            status=RunStatus.completed,
            completed_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        db_session.flush()

        rows = _query_recent_completions(db_session)
        item_ids = [r.item_id for r in rows]

        assert item_ids == ["CR-ALIVE"], (
            f"in_progress item with recent completion should be the sole surfaced row; "
            f"got items: {item_ids}"
        )

    def test_query_recent_completions_includes_paused_item(self, db_session: Session) -> None:
        """A paused item with a recent completed run must appear."""
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-PAUSED", status=WorkItemStatus.paused)
        step = _make_step(db_session, project.id, item.id, "S01", status=StepStatus.pending)
        _make_run(
            db_session,
            step.id,
            status=RunStatus.completed,
            completed_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        db_session.flush()

        rows = _query_recent_completions(db_session)
        item_ids = [r.item_id for r in rows]

        assert item_ids == ["CR-PAUSED"], (
            f"paused item with recent completion should be the sole surfaced row; "
            f"got items: {item_ids}"
        )

    def test_query_recent_completions_includes_failed_item(self, db_session: Session) -> None:
        """An item whose own status=failed with a recent completed run must appear."""
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-BROKEN", status=WorkItemStatus.failed)
        step = _make_step(db_session, project.id, item.id, "S01", status=StepStatus.pending)
        _make_run(
            db_session,
            step.id,
            status=RunStatus.completed,
            completed_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        db_session.flush()

        rows = _query_recent_completions(db_session)
        item_ids = [r.item_id for r in rows]

        assert item_ids == ["CR-BROKEN"], (
            f"item-level 'failed' is unresolved and must be the sole surfaced row; "
            f"got items: {item_ids}"
        )


class TestQueryRecentCompletionsInactiveItemsExcluded:
    """AC3: Inactive items (completed / cancelled / archived) must NOT surface."""

    def test_query_recent_completions_excludes_completed_item(self, db_session: Session) -> None:
        """RED until the active-item predicate is added to _query_recent_completions.

        Pre-S01 reasoning: _query_recent_completions() returned ALL completed
        runs within the 1-hour window regardless of parent item status.
        Assertion 'CR-DEAD' not in [r.item_id for r in rows] would FAIL
        against pre-S01 code because CR-DEAD's run is within the cutoff and
        the unfiltered query returns it.
        """
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-DEAD", status=WorkItemStatus.completed)
        step = _make_step(db_session, project.id, item.id, "S01", status=StepStatus.pending)
        _make_run(
            db_session,
            step.id,
            status=RunStatus.completed,
            completed_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        db_session.flush()

        rows = _query_recent_completions(db_session)
        item_ids = [r.item_id for r in rows]

        assert "CR-DEAD" not in item_ids, (
            f"completed item should not surface in Recently Completed; got items: {item_ids}"
        )

    def test_query_recent_completions_excludes_cancelled_item(self, db_session: Session) -> None:
        """A cancelled item with a recent completed run must NOT appear."""
        project = _make_project(db_session, "p1")
        item = _make_item(db_session, project.id, "CR-CANCELLED", status=WorkItemStatus.cancelled)
        step = _make_step(db_session, project.id, item.id, "S01", status=StepStatus.pending)
        _make_run(
            db_session,
            step.id,
            status=RunStatus.completed,
            completed_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        db_session.flush()

        rows = _query_recent_completions(db_session)
        item_ids = [r.item_id for r in rows]

        assert "CR-CANCELLED" not in item_ids, (
            f"cancelled item should not surface; got items: {item_ids}"
        )

    def test_query_recent_completions_excludes_archived_item(self, db_session: Session) -> None:
        """An archived item (any status) with a recent completed run must NOT appear."""
        project = _make_project(db_session, "p1")
        item = _make_item(
            db_session,
            project.id,
            "CR-ARCHIVED",
            status=WorkItemStatus.in_progress,
            archived_at=datetime.now(UTC),
        )
        step = _make_step(db_session, project.id, item.id, "S01", status=StepStatus.pending)
        _make_run(
            db_session,
            step.id,
            status=RunStatus.completed,
            completed_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        db_session.flush()

        rows = _query_recent_completions(db_session)
        item_ids = [r.item_id for r in rows]

        assert "CR-ARCHIVED" not in item_ids, (
            f"archived item should not surface; got items: {item_ids}"
        )


# ---------------------------------------------------------------------------
# Route-level smoke tests
# ---------------------------------------------------------------------------


class TestSystemRunningRouteActiveFilter:
    """GET /system/running — active-item filter applied to rendered HTML."""

    def test_system_running_route_renders_active_item_only(
        self, client: TestClient, db_session: Session
    ) -> None:
        """The system-wide page must show I-ALIVE but not I-DEAD.

        Seeds two failed steps in the same project: one on an in_progress item,
        one on a completed item. Asserts the active item appears and the
        completed item does NOT appear in the HTML body.
        """
        project = _make_project(db_session, "sys-proj", "System Test Project")

        # Active item (must appear)
        item_alive = _make_item(
            db_session,
            project.id,
            "I-ALIVE",
            status=WorkItemStatus.in_progress,
        )
        _make_step(db_session, project.id, item_alive.id, "S01", status=StepStatus.failed)

        # Dead item (must NOT appear)
        item_dead = _make_item(
            db_session,
            project.id,
            "I-DEAD",
            status=WorkItemStatus.completed,
        )
        _make_step(db_session, project.id, item_dead.id, "S01", status=StepStatus.failed)
        db_session.flush()

        response = client.get("/system/running")
        assert response.status_code == 200, f"expected 200, got {response.status_code}"

        body = response.text
        assert "I-ALIVE" in body, (
            f"active item I-ALIVE should appear in /system/running; body snippet: {body[:500]}"
        )
        assert "I-DEAD" not in body, (
            f"completed item I-DEAD must NOT appear in /system/running; "
            f"but got body snippet: {body[:500]}"
        )


class TestProjectRunningRouteActiveFilter:
    """GET /project/{id}/running — active-item filter + project scoping."""

    def test_project_running_route_renders_active_item_only(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """The per-project page must show only the active item from that project.

        Seeds:
        - Project A (test_project): I-ALIVE (in_progress) + I-DEAD (completed)
        - Project B: I-B-ACTIVE (in_progress) + I-B-DEAD (completed)

        Asserts the route for Project A:
          - I-ALIVE appears (active, correct project)
          - I-DEAD does NOT appear (completed)
          - I-B-ACTIVE does NOT appear (correct project filter)
          - I-B-DEAD does NOT appear (completed AND wrong project)
        """
        # Project B setup
        proj_b = _make_project(db_session, "proj-b-run", "Project B Run")
        item_b_alive = _make_item(
            db_session,
            proj_b.id,
            "I-B-ALIVE",
            status=WorkItemStatus.in_progress,
        )
        _make_step(db_session, proj_b.id, item_b_alive.id, "S01", status=StepStatus.failed)
        item_b_dead = _make_item(
            db_session,
            proj_b.id,
            "I-B-DEAD",
            status=WorkItemStatus.completed,
        )
        _make_step(db_session, proj_b.id, item_b_dead.id, "S01", status=StepStatus.failed)

        # Project A (test_project) — active item
        item_a_alive = _make_item(
            db_session,
            test_project.id,
            "I-ALIVE",
            status=WorkItemStatus.in_progress,
        )
        _make_step(db_session, test_project.id, item_a_alive.id, "S01", status=StepStatus.failed)

        # Project A — dead item (must NOT appear)
        item_a_dead = _make_item(
            db_session,
            test_project.id,
            "I-A-DEAD",
            status=WorkItemStatus.completed,
        )
        _make_step(db_session, test_project.id, item_a_dead.id, "S01", status=StepStatus.failed)
        db_session.flush()

        response = client.get(f"/project/{test_project.id}/running")
        assert response.status_code == 200, f"expected 200, got {response.status_code}"

        body = response.text
        # Active item from project A — must appear
        assert "I-ALIVE" in body, "active item I-ALIVE should appear in project A's running page"
        # Completed item from project A — must NOT appear
        assert "I-A-DEAD" not in body, (
            "completed item I-A-DEAD must NOT appear in project A's running page"
        )
        # Project B items — must NOT appear (project filter)
        assert "I-B-ALIVE" not in body, (
            "project B item I-B-ALIVE must NOT appear in project A's running page"
        )
        assert "I-B-DEAD" not in body, (
            "project B item I-B-DEAD must NOT appear in project A's running page"
        )
