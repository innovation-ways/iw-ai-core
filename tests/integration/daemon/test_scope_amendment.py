"""I-00101: Unit tests for scope_amendment helpers.

Tests three public callables from orch.daemon.scope_amendment:
  - amend_allowed_paths(worktree_path, item_id, paths_to_add) -> AmendResult
  - revert_paths_in_worktree(worktree_path, paths_to_revert) -> RevertResult
  - latest_scope_violation(db, step_id) -> list[str] | None
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orch.daemon.scope_amendment import (
    amend_allowed_paths,
    latest_scope_violation,
    revert_paths_in_worktree,
)
from orch.db.models import (
    FixCycle,
    FixStatus,
    FixTrigger,
    Project,
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
# Manifest helpers
# ---------------------------------------------------------------------------


def _minimal_manifest(
    item_id: str,
    *,
    allowed_paths: list[str] | None = None,
    extra_keys: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal workflow-manifest.json dict for scope amendment tests.

    Args:
        item_id: Work item ID used as the manifest ``id`` field.
        allowed_paths: Optional initial ``scope.allowed_paths`` list.
        extra_keys: Optional additional top-level keys to merge into the manifest.

    Returns:
        A dict suitable for JSON serialisation as ``workflow-manifest.json``.
    """
    manifest = {
        "id": item_id,
        "type": "Feature",
        "title": f"Test item {item_id}",
        "_note": "Auto-generated test manifest",
        "scope": {
            "allowed_paths": allowed_paths or [],
        },
        "steps": [],
    }
    if extra_keys:
        manifest.update(extra_keys)
    return manifest


def _write_manifest(path: Path, data: dict[str, Any]) -> None:
    """Write a manifest dict as JSON to the given path, creating parent directories as needed.

    Args:
        path: Filesystem path where the JSON file will be written.
        data: Dictionary to serialise as the manifest content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# amend_allowed_paths tests
# ---------------------------------------------------------------------------


class TestAmendAllowedPaths:
    """File-I/O tests for the two-manifest amend helper."""

    def test_i00101_amend_writes_both_manifests(self, tmp_path: Path) -> None:
        """amend_allowed_paths must write both worktree and parent manifests."""
        item_id = "I-00101-TEST-AMEND-BOTH"

        # Worktree at tmp_path/.worktrees/<item_id> with a proper .git pointer file
        wt = tmp_path / ".worktrees" / item_id
        wt.mkdir(parents=True, exist_ok=True)
        worktree_manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        _write_manifest(
            worktree_manifest_path,
            _minimal_manifest(item_id, allowed_paths=["src/"]),
        )

        # Parent repo at tmp_path/parent_repo
        # _resolve_parent_manifest reads .git, strips "gitdir:", navigates up from the
        # gitdir path to find the parent repo root. The gitdir path must be
        # <parent_repo>/.git/worktrees/<item_id> so that navigating up:
        #   .parent.parent.parent  →  <parent_repo>/.git  →  <parent_repo>
        parent_repo = tmp_path / "parent_repo"
        parent_repo.mkdir(parents=True, exist_ok=True)
        (parent_repo / ".git").mkdir()

        # Create the gitdir directory (what the .git file's gitdir: path points to)
        gitdir = parent_repo / ".git" / "worktrees" / item_id
        gitdir.mkdir(parents=True, exist_ok=True)

        # Point worktree .git at the gitdir directory
        git_pointer = wt / ".git"
        git_pointer.write_text(f"gitdir: {gitdir}\n")

        # Parent manifest at parent_repo/ai-dev/active/<item_id>/workflow-manifest.json
        parent_manifest_path = (
            parent_repo / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        )
        _write_manifest(
            parent_manifest_path,
            _minimal_manifest(item_id, allowed_paths=["src/"]),
        )

        result = amend_allowed_paths(wt, item_id, [".gitleaks.toml"])

        # Worktree check
        wt_data = json.loads(worktree_manifest_path.read_text())
        assert ".gitleaks.toml" in wt_data["scope"]["allowed_paths"], (
            f"Worktree manifest must contain '.gitleaks.toml' in allowed_paths; "
            f"got {wt_data['scope']['allowed_paths']}"
        )
        # Parent check
        parent_data = json.loads(parent_manifest_path.read_text())
        assert ".gitleaks.toml" in parent_data["scope"]["allowed_paths"], (
            f"Parent manifest must contain '.gitleaks.toml' in allowed_paths; "
            f"got {parent_data['scope']['allowed_paths']}"
        )
        # Result dataclass
        assert ".gitleaks.toml" in result.paths_added
        assert len(result.manifests_updated) == 2

    def test_i00101_amend_is_idempotent_on_duplicate_paths(self, tmp_path: Path) -> None:
        """Calling amend twice with the same path must not duplicate it."""
        item_id = "I-00101-IDEMPOTENT"
        wt = tmp_path / ".worktrees" / item_id
        wt.mkdir(parents=True, exist_ok=True)
        manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        _write_manifest(manifest_path, _minimal_manifest(item_id, allowed_paths=[]))

        # First call
        result1 = amend_allowed_paths(wt, item_id, [".gitleaks.toml"])
        assert result1.paths_added == [".gitleaks.toml"]

        # Second call with same path
        result2 = amend_allowed_paths(wt, item_id, [".gitleaks.toml"])
        assert result2.paths_added == [], "Second call must not re-add already-present path"

        # Manifest must have exactly one occurrence
        data = json.loads(manifest_path.read_text())
        allowed = data["scope"]["allowed_paths"]
        assert allowed.count(".gitleaks.toml") == 1, f"Path must appear exactly once, got {allowed}"

    def test_i00101_amend_preserves_existing_keys_and_note(self, tmp_path: Path) -> None:
        """Amend must not mutate keys other than scope.allowed_paths."""
        item_id = "I-00101-PRESERVE"
        wt = tmp_path / ".worktrees" / item_id
        wt.mkdir(parents=True, exist_ok=True)
        manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"

        original = _minimal_manifest(
            item_id,
            allowed_paths=["src/"],
            extra_keys={
                "_note": "Original note text — do not lose",
                "custom_top_level_key": "custom_value",
                "steps": [{"step_id": "S01", "status": "pending"}],
            },
        )
        _write_manifest(manifest_path, original)

        amend_allowed_paths(wt, item_id, [".gitleaks.toml"])

        updated = json.loads(manifest_path.read_text())

        # Check _note is byte-identical
        assert updated["_note"] == "Original note text — do not lose", "_note must not be modified"
        # Check other top-level keys preserved
        assert updated["id"] == item_id
        assert updated["type"] == "Feature"
        assert updated["custom_top_level_key"] == "custom_value"
        assert updated["steps"] == [{"step_id": "S01", "status": "pending"}]
        # Check scope is present
        assert "scope" in updated
        assert ".gitleaks.toml" in updated["scope"]["allowed_paths"]

    def test_i00101_amend_handles_missing_parent_manifest_gracefully(self, tmp_path: Path) -> None:
        """When parent repo has no manifest, only worktree is updated (no exception)."""
        item_id = "I-00101-NO-PARENT"
        wt = tmp_path / ".worktrees" / item_id
        wt.mkdir(parents=True, exist_ok=True)
        worktree_manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        _write_manifest(
            worktree_manifest_path,
            _minimal_manifest(item_id, allowed_paths=["src/"]),
        )

        # Worktree .git pointer points to a gitdir that exists (in a parent repo
        # that has no manifest at the expected path)
        parent_repo = tmp_path / "parent_repo_no_manifest"
        parent_repo.mkdir(parents=True, exist_ok=True)
        (parent_repo / ".git").mkdir()
        gitdir = parent_repo / ".git" / "worktrees" / item_id
        gitdir.mkdir(parents=True, exist_ok=True)
        git_pointer = wt / ".git"
        git_pointer.write_text(f"gitdir: {gitdir}\n")

        # Must not raise
        result = amend_allowed_paths(wt, item_id, [".gitleaks.toml"])

        # Worktree must still be updated
        wt_data = json.loads(worktree_manifest_path.read_text())
        assert ".gitleaks.toml" in wt_data["scope"]["allowed_paths"]
        # Result must list only the worktree manifest
        assert len(result.manifests_updated) == 1
        assert result.manifests_updated[0] == worktree_manifest_path

    def test_i00101_amend_handles_missing_git_pointer_gracefully(self, tmp_path: Path) -> None:
        """When .git pointer is absent, only worktree manifest is updated."""
        item_id = "I-00101-NO-GIT-POINTER"
        wt = tmp_path / ".worktrees" / item_id
        wt.mkdir(parents=True, exist_ok=True)
        manifest_path = wt / "ai-dev" / "active" / item_id / "workflow-manifest.json"
        _write_manifest(manifest_path, _minimal_manifest(item_id, allowed_paths=[]))

        # No .git file at all
        result = amend_allowed_paths(wt, item_id, [".gitleaks.toml"])

        wt_data = json.loads(manifest_path.read_text())
        assert ".gitleaks.toml" in wt_data["scope"]["allowed_paths"]
        assert len(result.manifests_updated) == 1


# ---------------------------------------------------------------------------
# revert_paths_in_worktree tests
# ---------------------------------------------------------------------------


class TestRevertPathsInWorktree:
    """Git-checkout tests for the revert helper."""

    def test_i00101_revert_runs_git_checkout_for_each_path(self, tmp_path: Path) -> None:
        """revert must restore file to HEAD content and report it in reverted."""
        # Set up a real git repo
        wt = tmp_path / "worktree_for_revert"
        wt.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init", str(wt)], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(wt), "config", "user.email", "test@example.com"],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(wt), "config", "user.name", "Test"],
            capture_output=True,
            check=True,
        )

        # Create and commit a file
        file_path = wt / "safe-content.txt"
        file_path.write_text("safe-content")
        subprocess.run(["git", "-C", str(wt), "add", "."], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(wt), "commit", "-m", "initial"],
            capture_output=True,
            check=True,
        )

        # Mutate the file (simulate out-of-scope edit)
        file_path.write_text("out-of-scope-edit")

        result = revert_paths_in_worktree(wt, ["safe-content.txt"])

        # File must be restored to HEAD content
        assert file_path.read_text() == "safe-content", (
            f"File must be restored to HEAD; got {file_path.read_text()!r}"
        )
        # Reverted list must contain the path
        assert "safe-content.txt" in result.reverted, (
            f"Path must be in reverted; got {result.reverted}"
        )
        assert result.failed == []

    def test_i00101_revert_records_failure_when_path_not_in_repo(self, tmp_path: Path) -> None:
        """revert with an untracked path must report it in failed, not raise."""
        wt = tmp_path / "worktree_for_revert_fail"
        wt.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init", str(wt)], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(wt), "config", "user.email", "test@example.com"],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(wt), "config", "user.name", "Test"],
            capture_output=True,
            check=True,
        )

        # Commit something so git repo is valid
        dummy = wt / "dummy.txt"
        dummy.write_text("dummy")
        subprocess.run(["git", "-C", str(wt), "add", "."], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(wt), "commit", "-m", "init"],
            capture_output=True,
            check=True,
        )

        result = revert_paths_in_worktree(wt, ["nonexistent-file.xyz"])

        assert "nonexistent-file.xyz" in result.failed, (
            f"Untracked path must be in failed; got {result.failed}"
        )
        assert "nonexistent-file.xyz" not in result.reverted

    def test_i00101_revert_multiple_paths_mixed_success_and_failure(self, tmp_path: Path) -> None:
        """Revert with one tracked + one untracked path: succeed on tracked, fail on untracked."""
        wt = tmp_path / "worktree_mixed"
        wt.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init", str(wt)], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(wt), "config", "user.email", "test@example.com"],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(wt), "config", "user.name", "Test"],
            capture_output=True,
            check=True,
        )

        tracked = wt / "tracked.txt"
        tracked.write_text("original")
        subprocess.run(
            ["git", "-C", str(wt), "add", "tracked.txt"], capture_output=True, check=True
        )
        subprocess.run(
            ["git", "-C", str(wt), "commit", "-m", "add tracked"], capture_output=True, check=True
        )

        result = revert_paths_in_worktree(wt, ["tracked.txt", "not-in-repo.txt"])

        assert "tracked.txt" in result.reverted
        assert "not-in-repo.txt" in result.failed
        assert result.failed != result.reverted


# ---------------------------------------------------------------------------
# latest_scope_violation tests (require db_session via testcontainer)
# ---------------------------------------------------------------------------


class TestLatestScopeViolation:
    """DB-backed tests for latest_scope_violation using testcontainer db_session."""

    def _make_project(self, db: Session, project_id: str) -> Project:
        """Create a Project row for tests."""
        project = Project(
            id=project_id,
            display_name=f"Test Project {project_id}",
            repo_root="/repos/test",
            config={},
        )
        db.add(project)
        db.flush()
        return project

    def test_i00101_latest_scope_violation_returns_latest_cycle_violations(
        self, db_session: Session
    ) -> None:
        """Must return scope_violations from the LATEST cycle (cycle_number DESC).

        If the function returned the older cycle's violations ([a]) instead of
        the newer one's ([b, c]), the test would fail — proving "latest" semantics.
        """
        project = self._make_project(db_session, "test-proj-latest")
        item = WorkItem(
            project_id=project.id,
            id="I-00101-LATEST",
            type=WorkItemType.Feature,
            title="I-00101 latest test",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        db_session.add(item)
        step = WorkflowStep(
            project_id=project.id,
            work_item_id="I-00101-LATEST",
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.quality_validation,
            status=StepStatus.needs_fix,
        )
        db_session.add(step)
        db_session.flush()

        # Older cycle
        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=1,
                status=FixStatus.escalated,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={"scope_violations": ["a"]},
            )
        )
        # Latest cycle
        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=2,
                status=FixStatus.escalated,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={"scope_violations": ["b", "c"]},
            )
        )
        db_session.commit()

        result = latest_scope_violation(db_session, step.id)

        assert result == ["b", "c"], (
            f"Must return latest cycle's violations ['b', 'c']; got {result!r}. "
            "If result is ['a'], the function is not ordering by cycle_number DESC."
        )

    def test_i00101_latest_scope_violation_returns_None_for_no_scope_cycle(  # noqa: N802
        self, db_session: Session
    ) -> None:
        """Step with no fix cycles at all must return None."""
        project = self._make_project(db_session, "test-proj-none")
        item = WorkItem(
            project_id=project.id,
            id="I-00101-NO-CYCLE",
            type=WorkItemType.Feature,
            title="I-00101 no cycle test",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        db_session.add(item)
        step = WorkflowStep(
            project_id=project.id,
            work_item_id="I-00101-NO-CYCLE",
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.quality_validation,
            status=StepStatus.needs_fix,
        )
        db_session.add(step)
        db_session.flush()
        db_session.commit()

        result = latest_scope_violation(db_session, step.id)

        assert result is None, f"Expected None for step with no cycles; got {result!r}"

    def test_i00101_latest_scope_violation_returns_None_for_empty_scope_violations(  # noqa: N802
        self, db_session: Session
    ) -> None:
        """Latest cycle with status=escalated but empty scope_violations list must return None.

        An empty list is falsy — the dashboard uses truthiness to decide whether
        to render the badge. None must be returned so the badge is not rendered.
        """
        project = self._make_project(db_session, "test-proj-empty-vlist")
        item = WorkItem(
            project_id=project.id,
            id="I-00101-EMPTY-VLIST",
            type=WorkItemType.Feature,
            title="I-00101 empty vlist test",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        db_session.add(item)
        step = WorkflowStep(
            project_id=project.id,
            work_item_id="I-00101-EMPTY-VLIST",
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.quality_validation,
            status=StepStatus.needs_fix,
        )
        db_session.add(step)
        db_session.flush()

        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=1,
                status=FixStatus.escalated,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={"scope_violations": []},  # empty list
            )
        )
        db_session.commit()

        result = latest_scope_violation(db_session, step.id)

        assert result is None, (
            f"Empty list must return None (falsy check in dashboard); got {result!r}"
        )

    def test_i00101_latest_scope_violation_returns_None_for_non_escalated_status(  # noqa: N802
        self, db_session: Session
    ) -> None:
        """Latest cycle is status=failed (not escalated) -> must return None."""
        project = self._make_project(db_session, "test-proj-non-escalated")
        item = WorkItem(
            project_id=project.id,
            id="I-00101-NON-ESCALATED",
            type=WorkItemType.Feature,
            title="I-00101 non-escalated test",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        db_session.add(item)
        step = WorkflowStep(
            project_id=project.id,
            work_item_id="I-00101-NON-ESCALATED",
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.quality_validation,
            status=StepStatus.failed,
        )
        db_session.add(step)
        db_session.flush()

        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=1,
                status=FixStatus.failed,  # not escalated
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={"scope_violations": ["something.toml"]},
            )
        )
        db_session.commit()

        result = latest_scope_violation(db_session, step.id)

        assert result is None, f"status=failed (not escalated) must return None; got {result!r}"


# ---------------------------------------------------------------------------
# should_auto_amend tests  (CR-00087 S02)
# ---------------------------------------------------------------------------


class TestShouldAutoAmend:
    """Unit tests for should_auto_amend — pure logic, no I/O, no DB."""

    def test_should_auto_amend_returns_false_when_allow_patterns_empty(self) -> None:
        """Feature is off when allow_patterns is empty."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["tests/unit/test_foo.py"],
                allow_patterns=[],
                max_paths=None,
            )
            is False
        )

    def test_should_auto_amend_returns_false_when_violations_empty(self) -> None:
        """Nothing to amend means nothing to do."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=[],
                allow_patterns=["tests/**"],
                max_paths=None,
            )
            is False
        )

    def test_should_auto_amend_returns_true_for_single_matching_violation(self) -> None:
        """Single violation that matches the allow-pattern -> True."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["tests/unit/test_foo.py"],
                allow_patterns=["tests/**"],
                max_paths=None,
            )
            is True
        )

    def test_should_auto_amend_returns_true_when_all_violations_match(self) -> None:
        """Every violation matches at least one allow-pattern -> True."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["tests/unit/test_foo.py", "docs/notes.md"],
                allow_patterns=["tests/**", "**/*.md"],
                max_paths=10,
            )
            is True
        )

    def test_should_auto_amend_returns_false_when_any_violation_not_matched(self) -> None:
        """Partial match — one violation falls outside allow-patterns -> False."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["tests/unit/test_foo.py", "orch/daemon/fix_cycle.py"],
                allow_patterns=["tests/**"],
                max_paths=10,
            )
            is False
        )

    def test_should_auto_amend_returns_false_when_exceeds_max_paths(self) -> None:
        """Count exceeds max_paths cap -> False."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["tests/a.py", "tests/b.py", "tests/c.py", "tests/d.py"],
                allow_patterns=["tests/**"],
                max_paths=3,
            )
            is False
        )

    def test_should_auto_amend_returns_true_when_at_max_paths(self) -> None:
        """At-cap is allowed (violations <= max_paths)."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["tests/a.py"],
                allow_patterns=["tests/**"],
                max_paths=1,
            )
            is True
        )

    def test_should_auto_amend_returns_true_for_docs_directory_glob(self) -> None:
        """dir/** glob covers the directory itself and all paths under it."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["docs/sub/notes.md"],
                allow_patterns=["docs/**"],
                max_paths=None,
            )
            is True
        )

    def test_should_auto_amend_returns_true_for_dashboard_glob(self) -> None:
        """dashboard/** matches any path under dashboard/."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["dashboard/static/chat.js"],
                allow_patterns=["dashboard/**"],
                max_paths=None,
            )
            is True
        )

    def test_should_auto_amend_returns_false_when_max_paths_zero(self) -> None:
        """max_paths=0 is a valid cap that no violation list can satisfy."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["tests/a.py"],
                allow_patterns=["tests/**"],
                max_paths=0,
            )
            is False
        )

    def test_should_auto_amend_returns_false_gracefully_for_non_list_violations(self) -> None:
        """Non-list violations input must not raise — return False."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations="tests/a.py",  # type: ignore[arg-type]
                allow_patterns=["tests/**"],
                max_paths=None,
            )
            is False
        )

    def test_should_auto_amend_returns_false_gracefully_for_non_list_allow_patterns(self) -> None:
        """Non-list allow_patterns input must not raise — return False."""
        from orch.daemon.scope_amendment import should_auto_amend

        assert (
            should_auto_amend(
                violations=["tests/a.py"],
                allow_patterns="tests/**",  # type: ignore[arg-type]
                max_paths=None,
            )
            is False
        )

    def test_should_auto_amend_matches_violation_detector_by_construction(self) -> None:
        """Guard against future matcher drift (CR-00087 AC3).

        For every (violation, pattern) pair used across the test matrix above,
        should_auto_amend and scope_match must agree.  If someone refactors
        scope_match in the future, this test will catch any divergence from the
        auto-amend filter.
        """
        from orch.daemon.fix_cycle import scope_match
        from orch.daemon.scope_amendment import should_auto_amend

        # Pairs from the full test matrix above
        pairs: list[tuple[str, str]] = [
            ("tests/unit/test_foo.py", "tests/**"),
            ("tests/unit/test_foo.py", "tests/**"),
            ("tests/unit/test_foo.py", "**/*.md"),
            ("docs/notes.md", "tests/**"),
            ("docs/notes.md", "**/*.md"),
            ("orch/daemon/fix_cycle.py", "tests/**"),
            ("docs/sub/notes.md", "docs/**"),
            ("dashboard/static/chat.js", "dashboard/**"),
            ("tests/a.py", "tests/**"),
            ("tests/a.py", "tests/**"),
        ]

        for violation, pattern in pairs:
            auto_result = should_auto_amend([violation], [pattern], None)
            matcher_result = scope_match(violation, pattern)
            assert auto_result is matcher_result, (
                f"Mismatch for violation={violation!r}, pattern={pattern!r}: "
                f"should_auto_amend={auto_result}, scope_match={matcher_result}. "
                "Auto-amend filter and violation detector must always agree."
            )
