"""Tests for GET /project/{project_id}/item/{item_id}/step/{step_id}/session-log (CR-00065 S04)."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture
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
# Seed helpers
# ---------------------------------------------------------------------------


def _make_project(db_session: Session, project_id: str = "proj-1") -> dict:
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


def _make_pi_jsonl(tmp_path: Path, lines: list[dict], suffix: str | None = None) -> str:
    """Write a minimal pi session .jsonl file and return its path.

    Args:
        tmp_path: temp directory to write into.
        lines: list of JSON-serialisable dicts (one per line).
        suffix: optional string appended to filename for disambiguation (e.g. run number).
               Defaults to a UUID so each call gets a unique file.
    """
    if suffix is None:
        import uuid

        suffix = uuid.uuid4().hex[:8]
    session_file = tmp_path / f"session_{suffix}.jsonl"
    session_file.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return str(session_file)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSessionLogEndpoint:
    """CR-00065 S04: GET /project/{id}/api/item/{item_id}/step/{step_id}/session-log."""

    def test_session_log_endpoint_pi_run_200(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ):
        """GET returns 200 with rendered fragment for pi run with session_file."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-pi-log")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S01",
            step_number=1,
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
        )
        db_session.add(step)
        db_session.flush()

        session_file = _make_pi_jsonl(
            tmp_path,
            [
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [
                            {"type": "text", "text": "Hello, I will implement the feature."},
                        ],
                    },
                },
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [
                            {
                                "type": "toolCall",
                                "name": "Bash",
                                "arguments": {"command": "echo hello"},
                            },
                        ],
                    },
                },
            ],
        )

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.running,
            cli_tool="pi",
            session_file=session_file,
            started_at=datetime.now(UTC),
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/session-log",
        )
        assert response.status_code == 200, response.text
        # Fragment must contain the rendered assistant text
        assert "Hello, I will implement the feature." in response.text
        # Fragment must contain the rendered tool call
        assert "Bash" in response.text
        # Fragment must not wrap in base.html
        assert "<html" not in response.text.lower()
        assert "<!doctype" not in response.text.lower()
        # is_live = True (running status)
        assert "every 3s" in response.text, "htmx polling must be present for running step"

    def test_session_log_endpoint_claude_run_200(self, client: TestClient, db_session: Session):
        """GET returns 200 with rendered fragment for claude run with log_content."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-claude-log")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S02",
            step_number=2,
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            cli_tool="claude",
            log_content="[TOOL_CALL] Bash\necho hello\n[TOOL_RESULT] hello\n[ASSISTANT] Done.",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db_session.add(run)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/session-log",
        )
        assert response.status_code == 200, response.text
        # log segment content must be rendered
        assert "Done." in response.text or "hello" in response.text
        # Fragment must not wrap in base.html
        assert "<html" not in response.text.lower()
        assert "<!doctype" not in response.text.lower()

    def test_session_log_endpoint_not_found_404(self, client: TestClient, db_session: Session):
        """GET returns 404 for unknown step_id."""
        seed = _make_project(db_session, "proj-404-log")

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/UNKNOWN-STEP/session-log",
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_session_log_endpoint_no_run_returns_empty(
        self, client: TestClient, db_session: Session
    ):
        """GET with no StepRun rows returns 200 with 'no content' message."""
        from orch.db.models import StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-no-run")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S03",
            step_number=3,
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.pending,
        )
        db_session.add(step)
        db_session.commit()

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/session-log",
        )
        assert response.status_code == 200, response.text
        assert "No log content available yet." in response.text

    def test_session_log_endpoint_latest_run_default(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ):
        """GET without run_number param returns content for highest run_number."""
        from datetime import UTC, datetime

        from orch.db.models import RunStatus, StepRun, StepStatus, StepType, WorkflowStep

        seed = _make_project(db_session, "proj-multi-run")

        step = WorkflowStep(
            project_id=seed["project"].id,
            work_item_id=seed["item"].id,
            step_id="S04",
            step_number=4,
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        session_file_run1 = _make_pi_jsonl(
            tmp_path,
            [
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [{"type": "text", "text": "First attempt text"}],
                    },
                },
            ],
            suffix="run1",
        )
        session_file_run2 = _make_pi_jsonl(
            tmp_path,
            [
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [{"type": "text", "text": "Second attempt text — latest run"}],
                    },
                },
            ],
            suffix="run2",
        )

        run1 = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.failed,
            cli_tool="pi",
            session_file=session_file_run1,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        run2 = StepRun(
            step_id=step.id,
            run_number=2,
            status=RunStatus.completed,
            cli_tool="pi",
            session_file=session_file_run2,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db_session.add(run1)
        db_session.add(run2)
        db_session.commit()

        # No run_number → default to latest (run_number=2)
        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/session-log",
        )
        assert response.status_code == 200, response.text
        assert "Second attempt text — latest run" in response.text
        assert "First attempt text" not in response.text

        # Explicit run_number=1 → run 1 content
        response_run1 = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}/step/{step.step_id}/session-log?run_number=1",
        )
        assert response_run1.status_code == 200, response_run1.text
        assert "First attempt text" in response_run1.text
        assert "Second attempt text" not in response_run1.text
