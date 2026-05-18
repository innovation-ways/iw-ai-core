"""I-00101: Integration tests for scope-amend and scope-revert endpoints.

Tests the two new POST endpoints in dashboard/routers/actions.py:
  - POST /item/{item_id}/scope/amend-and-restart/{step_id}
  - POST /item/{item_id}/scope/revert-and-restart/{step_id}

And the GET modal endpoint:
  - GET /item/{item_id}/scope/amend-modal/{step_id}

Full end-to-end: seed DB state → HTTP POST → assert manifest writes,
event emission, step restart, new StepRun row. NOT mocked.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    DaemonEvent,
    FixCycle,
    FixStatus,
    FixTrigger,
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
# TestClient fixture (same pattern as test_cancel_button_visibility.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
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
# Fake worktree helpers
# ---------------------------------------------------------------------------


def _make_fake_worktree(
    tmp_path: Path,
    item_id: str,
    *,
    allowed_paths: list[str] | None = None,
    parent_repo: bool = True,
) -> tuple[Path, Path]:
    """Build a fake worktree + optional parent repo.

    Returns (worktree_path, parent_manifest_path)."""
    if allowed_paths is None:
        allowed_paths = ["src/"]

    wt = tmp_path / "worktrees" / item_id
    wt.mkdir(parents=True, exist_ok=True)

    manifest_data = {
        "id": item_id,
        "type": "Feature",
        "title": f"Test item {item_id}",
        "scope": {"allowed_paths": allowed_paths},
        "steps": [{"step_id": "S01", "status": "pending"}],
    }
    manifest_dir = wt / "ai-dev" / "active" / item_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "workflow-manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n")

    parent_manifest_path = Path()
    if parent_repo:
        parent_repo_root = tmp_path / "parent_repos" / item_id
        parent_repo_root.mkdir(parents=True, exist_ok=True)
        # Make it look like a real git repo
        (parent_repo_root / ".git").mkdir()
        # Create the gitdir directory — the path that .git file's "gitdir:" points to
        gitdir = parent_repo_root / ".git" / "worktrees" / item_id
        gitdir.mkdir(parents=True, exist_ok=True)
        git_pointer = wt / ".git"
        git_pointer.write_text(f"gitdir: {gitdir}\n")

        parent_manifest_dir = parent_repo_root / "ai-dev" / "active" / item_id
        parent_manifest_dir.mkdir(parents=True, exist_ok=True)
        parent_manifest_path = parent_manifest_dir / "workflow-manifest.json"
        parent_manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n")

    return wt, parent_manifest_path


def _init_git_repo(wt: Path, filename: str, content: str) -> Path:
    """Initialize a real git repo in wt, commit a file, return the file path."""
    subprocess.run(["git", "init", str(wt)], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(wt), "config", "user.email", "test@test.com"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(wt), "config", "user.name", "Test"],
        capture_output=True,
        check=True,
    )
    file_path = wt / filename
    file_path.write_text(content)
    subprocess.run(["git", "-C", str(wt), "add", "."], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(wt), "commit", "-m", f"add {filename}"],
        capture_output=True,
        check=True,
    )
    return file_path


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_project(db: Session, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def _seed_scope_blocked_step(
    db: Session,
    project: Project,
    item_id: str,
    worktree_path: Path | None,
    scope_violations: list[str] | None = None,
) -> tuple[WorkItem, WorkflowStep]:
    """Create a work item with one needs_fix step and a scope-escalated FixCycle."""
    if scope_violations is None:
        scope_violations = [".gitleaks.toml"]

    item = WorkItem(
        project_id=project.id,
        id=item_id,
        type=WorkItemType.Feature,
        title=f"I-00101 test {item_id}",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db.add(item)
    db.flush()

    step = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        step_id="S01",
        agent_label="test",
        step_type=StepType.quality_validation,
        gate="security-secrets",
        status=StepStatus.needs_fix,
    )
    db.add(step)
    db.flush()

    # StepRun needed for _get_last_run in the endpoint
    from orch.db.models import StepRun

    last_run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.failed,
        worktree_path=str(worktree_path) if worktree_path else None,
    )
    db.add(last_run)

    fix_cycle = FixCycle(
        step_id=step.id,
        cycle_number=1,
        status=FixStatus.escalated,
        trigger_type=FixTrigger.quality_validation,
        fix_metadata={"scope_violations": scope_violations},
    )
    db.add(fix_cycle)
    db.commit()

    return item, step


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScopeAmendAndRestartEndpoint:
    """AC2: amend scope & restart action succeeds end-to-end."""

    def test_i00101_amend_writes_both_manifests_and_emits_event_and_restarts_step(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """POST to amend endpoint must write both manifests, emit event,
        flip step to pending, create new StepRun."""
        project = _seed_project(db_session, "test-amend-endpoint")
        item_id = "I-00101-AMEND-E2E"
        wt, parent_manifest_path = _make_fake_worktree(tmp_path, item_id)

        item, step = _seed_scope_blocked_step(
            db_session, project, item_id, wt, scope_violations=[".gitleaks.toml"]
        )

        # Record pre-state
        pre_step_run_count = db_session.query(StepRun).filter(StepRun.step_id == step.id).count()

        # POST to amend endpoint
        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/scope/amend-and-restart/S01",
            data={"paths": [".gitleaks.toml"]},
        )
        # The endpoint returns 204 No Content (HX-Trigger header, no body)
        assert response.status_code == 204, (
            f"Expected 204, got {response.status_code}: {response.text}"
        )

        db_session.expire_all()

        # (a) worktree manifest updated
        wt_manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        wt_data = json.loads(wt_manifest_path.read_text())
        assert ".gitleaks.toml" in wt_data["scope"]["allowed_paths"], (
            "Worktree manifest must contain .gitleaks.toml; "
            f"got {wt_data['scope']['allowed_paths']}"
        )

        # (b) parent manifest updated
        assert parent_manifest_path.exists(), "Parent manifest must exist"
        parent_data = json.loads(parent_manifest_path.read_text())
        assert ".gitleaks.toml" in parent_data["scope"]["allowed_paths"], (
            "Parent manifest must contain .gitleaks.toml; "
            f"got {parent_data['scope']['allowed_paths']}"
        )

        # (c) exactly one new daemon_event with type scope_amended_by_operator
        new_events = (
            db_session.query(DaemonEvent)
            .filter(DaemonEvent.entity_id == item.id)
            .filter(DaemonEvent.event_type == "scope_amended_by_operator")
            .all()
        )
        assert len(new_events) == 1, (
            f"Expected 1 scope_amended_by_operator event; got {len(new_events)}"
        )
        evt = new_events[0]
        assert evt.event_metadata.get("added_paths") == [".gitleaks.toml"], (
            f"Event metadata.added_paths must be ['.gitleaks.toml']; got {evt.event_metadata}"
        )
        assert evt.event_metadata.get("step_id") == "S01", (
            f"Event metadata.step_id must be 'S01'; got {evt.event_metadata}"
        )

        # (d) step status is now pending
        db_session.expire_all()
        step_refresh = db_session.get(WorkflowStep, step.id)
        assert step_refresh is not None, "Step must exist after amend"
        assert step_refresh.status == StepStatus.pending, (
            f"Step must be pending; got {step_refresh.status}"
        )
        assert step_refresh.started_at is None, "started_at must be cleared"
        assert step_refresh.completed_at is None, "completed_at must be cleared"

        # (e) item status back to in_progress
        db_session.expire_all()
        item_refresh = db_session.get(WorkItem, (project.id, item.id))
        assert item_refresh is not None, "Item must exist after amend"
        assert item_refresh.status == WorkItemStatus.in_progress, (
            f"Item must be in_progress; got {item_refresh.status}"
        )

        # (f) exactly one new step_run created
        new_run_count = db_session.query(StepRun).filter(StepRun.step_id == step.id).count()
        assert new_run_count == pre_step_run_count + 1, (
            f"Expected {pre_step_run_count + 1} step_runs; got {new_run_count}"
        )
        latest_run = (
            db_session.query(StepRun)
            .filter(StepRun.step_id == step.id)
            .order_by(StepRun.run_number.desc())
            .first()
        )
        assert latest_run is not None, "A new StepRun must have been created"
        assert latest_run.run_number == 2, (
            f"New run must be run_number=2; got {latest_run.run_number}"
        )
        assert latest_run.status == RunStatus.pending, (
            f"New run must be pending; got {latest_run.status}"
        )

    def test_i00101_revert_runs_git_checkout_and_emits_event_and_restarts(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """POST to revert endpoint must run git checkout -- <path>,
        NOT amend manifest, emit event, restart step."""
        project = _seed_project(db_session, "test-revert-endpoint")
        item_id = "I-00101-REVERT-E2E"
        wt, _ = _make_fake_worktree(tmp_path, item_id, allowed_paths=["src/"])

        # _make_fake_worktree left a .git file that blocks `git init`.
        # Remove it and set up a real git repo in the worktree directory.
        (wt / ".git").unlink()

        # Initialize real git repo with a committed file
        file_path = _init_git_repo(wt, "out-of-scope.txt", "safe-content")

        # Mutate the file (simulate agent's out-of-scope edit)
        file_path.write_text("out-of-scope-edit")
        assert file_path.read_text() == "out-of-scope-edit"

        item, step = _seed_scope_blocked_step(
            db_session, project, item_id, wt, scope_violations=["out-of-scope.txt"]
        )

        # POST to revert endpoint
        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/scope/revert-and-restart/S01",
        )
        assert response.status_code == 204, (
            f"Expected 204, got {response.status_code}: {response.text}"
        )

        db_session.expire_all()

        # (a) file content restored to HEAD
        assert file_path.read_text() == "safe-content", (
            f"File must be restored to HEAD; got {file_path.read_text()!r}"
        )

        # (b) worktree manifest UNCHANGED (revert does NOT amend)
        wt_manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        manifest_data = json.loads(wt_manifest_path.read_text())
        assert "out-of-scope.txt" not in manifest_data["scope"]["allowed_paths"], (
            "Revert must NOT amend the manifest"
        )

        # (c) one scope_reverted_by_operator event
        new_events = (
            db_session.query(DaemonEvent)
            .filter(DaemonEvent.entity_id == item.id)
            .filter(DaemonEvent.event_type == "scope_reverted_by_operator")
            .all()
        )
        assert len(new_events) == 1, (
            f"Expected 1 scope_reverted_by_operator event; got {len(new_events)}"
        )
        evt = new_events[0]
        assert "out-of-scope.txt" in evt.event_metadata.get("reverted_paths", []), (
            f"Event metadata.reverted_paths must contain 'out-of-scope.txt'; "
            f"got {evt.event_metadata}"
        )

        # (d) step restarted to pending + new StepRun
        db_session.expire_all()
        step_refresh = db_session.get(WorkflowStep, step.id)
        assert step_refresh is not None, "Step must exist after revert"
        assert step_refresh.status == StepStatus.pending

        from orch.db.models import StepRun

        latest_run = (
            db_session.query(StepRun)
            .filter(StepRun.step_id == step.id)
            .order_by(StepRun.run_number.desc())
            .first()
        )
        assert latest_run is not None, "A new StepRun must have been created after revert"
        assert latest_run.run_number == 2, (
            f"New run must be run_number=2; got {latest_run.run_number}"
        )
        assert latest_run.status == RunStatus.pending

    def test_i00101_amend_endpoint_returns_422_on_non_scope_blocked_step(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """POST to amend endpoint on a needs_fix step with no scope violations must return 422."""
        project = _seed_project(db_session, "test-422-non-scope")
        item_id = "I-00101-422-NON-SCOPE"

        # Create worktree with no parent
        wt, _ = _make_fake_worktree(tmp_path, item_id, parent_repo=False)
        item, step = _seed_scope_blocked_step(
            db_session,
            project,
            item_id,
            wt,
            scope_violations=None,  # no scope violations
        )

        # Update fix cycle to have empty scope_violations
        fc = db_session.query(FixCycle).filter(FixCycle.step_id == step.id).first()
        assert fc is not None, "FixCycle must exist"
        fc.fix_metadata = {}
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/scope/amend-and-restart/S01",
            data={"paths": [".gitleaks.toml"]},
        )

        assert response.status_code == 422, (
            f"Expected 422 for non-scope-blocked step; got {response.status_code}"
        )

        # Manifest must be unchanged
        wt_manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        data = json.loads(wt_manifest_path.read_text())
        assert data["scope"]["allowed_paths"] == ["src/"], (
            f"Manifest must not be changed; got {data['scope']['allowed_paths']}"
        )

        # No new daemon_events for this item
        no_new_events = (
            db_session.query(DaemonEvent)
            .filter(DaemonEvent.entity_id == item.id)
            .filter(DaemonEvent.event_type == "scope_amended_by_operator")
            .all()
        )
        assert len(no_new_events) == 0, (
            "No scope_amended_by_operator event should be emitted on 422"
        )

        # No new step_runs
        from orch.db.models import StepRun

        run_count = db_session.query(StepRun).filter(StepRun.step_id == step.id).count()
        assert run_count == 1, f"Only the original step_run should exist; got {run_count}"

    def test_i00101_amend_endpoint_rejects_paths_not_in_violation_set(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """POST with paths outside scope_violations must return 422."""
        project = _seed_project(db_session, "test-422-bad-path")
        item_id = "I-00101-422-BAD-PATH"
        wt, _ = _make_fake_worktree(tmp_path, item_id)

        item, step = _seed_scope_blocked_step(
            db_session,
            project,
            item_id,
            wt,
            scope_violations=[".gitleaks.toml"],
        )

        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/scope/amend-and-restart/S01",
            data={"paths": ["something/else.py"]},  # not in violations
        )

        assert response.status_code == 422, (
            f"Expected 422 for path not in violation set; got {response.status_code}"
        )
        assert (
            "something/else.py" in response.text or "not in violation set" in response.text.lower()
        ), f"Error message must mention the bad path; got {response.text[:200]}"

        # Manifest unchanged
        wt_manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        data = json.loads(wt_manifest_path.read_text())
        assert "something/else.py" not in data["scope"]["allowed_paths"]

    def test_i00101_amend_is_idempotent_at_the_endpoint_level(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """POST twice with the same path: both return 200; path appears
        exactly once; two events + two new runs."""
        project = _seed_project(db_session, "test-idempotent-endpoint")
        item_id = "I-00101-IDEMPOTENT-EP"
        wt, _ = _make_fake_worktree(tmp_path, item_id)

        item, step = _seed_scope_blocked_step(
            db_session,
            project,
            item_id,
            wt,
            scope_violations=[".gitleaks.toml"],
        )

        db_session.expire_all()

        # First POST
        r1 = client.post(
            f"/project/{project.id}/api/item/{item.id}/scope/amend-and-restart/S01",
            data={"paths": [".gitleaks.toml"]},
        )
        assert r1.status_code == 204, f"First request must succeed; got {r1.status_code}: {r1.text}"

        db_session.expire_all()

        # Second POST with same path
        r2 = client.post(
            f"/project/{project.id}/api/item/{item.id}/scope/amend-and-restart/S01",
            data={"paths": [".gitleaks.toml"]},
        )
        assert r2.status_code == 204, (
            f"Second request must succeed; got {r2.status_code}: {r2.text}"
        )

        db_session.expire_all()

        # Path appears exactly once in manifest
        wt_manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        data = json.loads(wt_manifest_path.read_text())
        allowed = data["scope"]["allowed_paths"]
        assert allowed.count(".gitleaks.toml") == 1, f"Path must appear exactly once; got {allowed}"

        # Two events emitted (each operator action is auditable)
        events = (
            db_session.query(DaemonEvent)
            .filter(DaemonEvent.entity_id == item.id)
            .filter(DaemonEvent.event_type == "scope_amended_by_operator")
            .all()
        )
        assert len(events) == 2, f"Expected 2 events; got {len(events)}"

        # Two new step_runs created (run_number 2 and 3)
        from orch.db.models import StepRun

        runs = (
            db_session.query(StepRun)
            .filter(StepRun.step_id == step.id)
            .order_by(StepRun.run_number)
            .all()
        )
        run_numbers = [r.run_number for r in runs]
        assert run_numbers == [1, 2, 3], f"Expected run_numbers [1, 2, 3]; got {run_numbers}"

    def test_i00101_amend_modal_get_returns_correct_html(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """GET /item/{item_id}/scope/amend-modal/{step_id} must return the modal fragment."""
        project = _seed_project(db_session, "test-modal-get")
        item_id = "I-00101-MODAL-GET"
        wt, _ = _make_fake_worktree(tmp_path, item_id)

        item, step = _seed_scope_blocked_step(
            db_session,
            project,
            item_id,
            wt,
            scope_violations=[".gitleaks.toml"],
        )

        response = client.get(f"/project/{project.id}/api/item/{item.id}/scope/amend-modal/S01")

        assert response.status_code == 200, (
            f"Expected 200; got {response.status_code}: {response.text}"
        )
        html = response.text

        # Must contain the modal structure
        assert "scope-amend-modal" in html or "activity-modal" in html, (
            f"Response must be a modal fragment; got {html[:300]}"
        )
        # Must contain the offending path in checkboxes
        assert ".gitleaks.toml" in html, (
            f"Modal must contain the offending path as checkbox; got {html[:500]}"
        )
