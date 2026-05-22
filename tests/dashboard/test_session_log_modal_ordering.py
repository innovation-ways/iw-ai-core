"""Dashboard reproduction + regression tests for I-00106.

Tests that the Agent Session Log modal renders the newest agent turn FIRST.

Reference pattern: tests/dashboard/test_items_session_log.py (same route, same DB setup).
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture (copied verbatim from test_items_session_log.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """FastAPI TestClient backed by the testcontainer db_session.

    The override MUST be a generator function (uses ``yield``), not a plain
    callable that returns the session directly.  SQLAlchemy Session objects
    are iterable, so FastAPI would consume ``db_session.__next__()`` as the
    yielded value on the first request and ``next(db_session)`` → ``StopIteration``
    on the second request — causing subsequent requests in the same test
    to receive ``None`` as the session, which results in stale / wrong-row
    query results due to SQLAlchemy's identity-map caching.
    """
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers (copied verbatim from test_items_session_log.py)
# ---------------------------------------------------------------------------


def _make_project(db_session: Session, project_id: str = "proj-1") -> dict[str, object]:
    """Create minimal project + item + batch + batch_item rows. Returns dict of rows."""
    from orch.db.models import Batch, BatchItem, Project, WorkItem

    project = Project(
        id=project_id,
        display_name=f"Test Project {project_id}",
        repo_root="/tmp/repo",
        config={},
    )
    db_session.add(project)
    db_session.flush()

    item = WorkItem(
        project_id=project_id,
        id="CR-00001",
        type="Feature",
        status="approved",
        title="Test Item",
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(item)
    db_session.flush()

    batch = Batch(project_id=project_id, id="batch-1", status="approved")
    db_session.add(batch)
    db_session.flush()

    bi = BatchItem(
        project_id=project_id,
        batch_id="batch-1",
        work_item_id="CR-00001",
        status="completed",
    )
    db_session.add(bi)
    db_session.commit()

    return {"project": project, "item": item, "batch": batch, "batch_item": bi}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSessionLogModalOrdering:
    """I-00106: Agent Session Log modal must render newest turn FIRST."""

    def test_i00106_session_log_modal_renders_newest_turn_first(
        self, client: TestClient, db_session: Session
    ):
        """Reproduction test: the modal must render the newest agent turn ABOVE
        the oldest turn.

        Fails before the fix: read_session_content() returns chronological
        segments oldest-first, so OLDEST_TURN_MARKER appears before
        NEWEST_TURN_MARKER in the rendered HTML.

        Fails before the fix (RED):
            assert html.index("NEWEST_TURN_MARKER") < html.index("OLDEST_TURN_MARKER")
            → AssertionError: index 8423 not less than 412

        Passes after the fix: group_into_turns_newest_first() reverses the
        list of turns so the newest turn (with NEWEST_TURN_MARKER) renders first.
        """
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-i00106")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S05",
            step_number=5,
            agent_label="Tests",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
        )
        db_session.add(step)
        db_session.flush()

        # Build log_content as a pi JSONL session string.
        # read_session_content() parses log_content line-by-line when there is no
        # session_file (pi-without-session-file fallback).
        #
        # Turn boundary rule: a turn terminates on an `assistant` segment NOT
        # immediately followed by another `assistant`.  We need two turns, so
        # insert a non-assistant segment (thinking) between the two assistant
        # messages.
        #
        # Turn 1 (oldest): thinking + assistant "OLDEST_TURN_MARKER" → terminated
        # Turn 2 (newest): thinking + assistant "NEWEST_TURN_MARKER" → terminated
        log_content = (
            "\n".join(
                json.dumps(line)
                for line in [
                    {
                        "type": "message",
                        "message": {
                            "role": "assistant",
                            "stopReason": None,
                            "content": [
                                {"type": "thinking", "thinking": "Old reasoning"},
                                {"type": "text", "text": "OLDEST_TURN_MARKER"},
                            ],
                        },
                    },
                    {
                        "type": "thinking",
                        "text": "New reasoning block",
                    },
                    {
                        "type": "message",
                        "message": {
                            "role": "assistant",
                            "stopReason": None,
                            "content": [{"type": "text", "text": "NEWEST_TURN_MARKER"}],
                        },
                    },
                ]
            )
            + "\n"
        )

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.running,
            cli_tool="pi",
            session_file=None,  # trigger log_content fallback path
            log_content=log_content,
            started_at=datetime.now(UTC),
        )
        db_session.add(run)
        db_session.commit()

        resp = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/session-log",
        )
        assert resp.status_code == 200, resp.text
        html = resp.text

        # Both markers must be present in the response
        assert "NEWEST_TURN_MARKER" in html, "Newest turn marker not found in HTML"
        assert "OLDEST_TURN_MARKER" in html, "Oldest turn marker not found in HTML"

        # Semantic ordering assertion — specific markers, not shape
        assert html.index("NEWEST_TURN_MARKER") < html.index("OLDEST_TURN_MARKER"), (
            "I-00106 bug: newest turn must render above the oldest turn. "
            f"Found NEWEST at index {html.index('NEWEST_TURN_MARKER')} and "
            f"OLDEST at index {html.index('OLDEST_TURN_MARKER')}."
        )

    def test_session_log_modal_empty_state_still_renders(
        self, client: TestClient, db_session: Session
    ):
        """AC5: A step run with no readable session content renders the existing
        empty-state message without a template exception.

        This test guards the {% if turns %} / {% else %} branch in the fragment.
        With turns=[], the else branch must render "No log content available yet."
        """
        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-i00106-empty")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S05-empty",
            step_number=1,
            agent_label="Tests",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
        )
        db_session.add(step)
        db_session.flush()

        # StepRun with no session_file and no log_content → read_session_content
        # returns [] → group_into_turns_newest_first([]) returns [] → turns=[]
        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.running,
            cli_tool="pi",
            session_file=None,
            log_content=None,
            started_at=None,
        )
        db_session.add(run)
        db_session.commit()

        resp = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/session-log",
        )
        assert resp.status_code == 200, resp.text
        # AC5: existing empty-state copy must still be present
        assert "No log content available" in resp.text, (
            "Empty-state message must be present for step runs with no session content"
        )
        # No template exception means no Jinja2 error text leaked into the response
        assert "Jinja2" not in resp.text, "Template exception occurred for empty state"
        assert "Template" not in resp.text, "Template exception occurred for empty state"
