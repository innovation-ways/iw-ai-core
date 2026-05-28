"""Scope enforcement tests for the fix-cycle pipeline.

I-00082: Fix-cycle agent has no allowed_paths enforcement.

These tests verify that when a fix-cycle agent edits files outside
workflow-manifest.json:scope.allowed_paths, the cycle is escalated
rather than allowed to continue.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from orch.db.models import (
    FixStatus,
)


def test_i00082_fix_cycle_escalates_on_out_of_scope_edit(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the fix-cycle agent edits a file outside allowed_paths,
    FixCycle.status is set to FixStatus.escalated and the agent's edits
    are preserved verbatim.

    This test should FAIL before the fix and PASS after.
    """
    from orch.daemon.fix_cycle import run_fix_cycle

    # Arrange: a fake worktree with a manifest declaring a tight allowed_paths
    # and a fake LLM agent that will write to a file outside that list.
    manifest_path = tmp_path / "workflow-manifest.json"
    manifest_path.write_text('{"scope": {"allowed_paths": ["allowed.py"]}, "steps": []}')
    (tmp_path / "allowed.py").write_text("# in scope\n")
    (tmp_path / "out_of_scope.py").write_text("# pre-existing\n")

    # Initialise git repo so git diff / ls-files work

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    def fake_agent_run(prompt: str, cwd: pathlib.Path) -> dict:  # type: ignore[type-arg]
        # Simulate the agent making an out-of-scope edit
        (cwd / "out_of_scope.py").write_text("# agent-edited\n")
        return {"completion_status": "complete"}

    monkeypatch.setattr("orch.daemon.fix_cycle.run_llm_agent", fake_agent_run)

    # Act
    cycle = run_fix_cycle(
        worktree_path=tmp_path,
        item_id="I-99001",
        step_id="S01",
        cycle_number=1,
        gate_failure="lint failed",
    )

    # Assert — semantic, not shape
    assert cycle.status == FixStatus.escalated, (
        f"expected FixStatus.escalated, got {cycle.status!r} — fix-cycle let "
        "the agent edit a file outside allowed_paths"
    )
    assert "out_of_scope.py" in cycle.fix_metadata["scope_violations"]
    assert (tmp_path / "out_of_scope.py").read_text() == "# agent-edited\n", (
        "agent's out-of-scope edit must be preserved verbatim — operator "
        "decides whether to amend allowed_paths or revert"
    )


def _setup_git_worktree(tmp_path: pathlib.Path, files: dict) -> None:
    """Initialise a minimal git repo with the given files committed.

    ``files`` is a mapping of relative path string → file content.
    All files are written, added, and committed in a single initial commit.
    """

    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


def test_i00082_operator_pre_edit_outside_scope_is_preserved(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Operator carry-over edits to files outside allowed_paths are NOT
    flagged as scope violations by the post-cycle reconciliation logic.

    AC3: The pre-cycle snapshot captures the operator's uncommitted edits
    so they are excluded from ``agent_touched = post_cycle - pre_cycle``.
    The cycle must complete normally (FixStatus.completed) and the
    operator's file must remain intact.

    Mirrors the CR-00053/S15 revert-mode incident where the fix-cycle agent
    silently reverted an operator carry-over fix on an out-of-scope file.
    """
    from orch.daemon.fix_cycle import run_fix_cycle

    # Arrange: worktree with a committed operator file outside allowed_paths.
    _setup_git_worktree(
        tmp_path,
        {
            "workflow-manifest.json": '{"scope": {"allowed_paths": ["allowed.py"]}, "steps": []}',
            "allowed.py": "# in scope\n",
            "operator_file.py": "# original operator content\n",
        },
    )

    # Operator modifies the out-of-scope file WITHOUT committing (uncommitted carry-over).
    (tmp_path / "operator_file.py").write_text("# operator carry-over edit\n")

    def fake_agent_run_in_scope(prompt: str, cwd: pathlib.Path) -> dict:  # type: ignore[type-arg]
        # Agent correctly edits only the in-scope file; does NOT touch operator_file.py
        (cwd / "allowed.py").write_text("# fixed by agent\n")
        return {"completion_status": "complete"}

    monkeypatch.setattr("orch.daemon.fix_cycle.run_llm_agent", fake_agent_run_in_scope)

    # Act
    cycle = run_fix_cycle(
        worktree_path=tmp_path,
        item_id="I-99002",
        step_id="S01",
        cycle_number=1,
        gate_failure="lint failed",
    )

    # Assert — semantic, not shape
    assert cycle.status == FixStatus.completed, (
        f"expected FixStatus.completed, got {cycle.status!r} — operator's "
        "pre-cycle edit to an out-of-scope file must not trigger escalation; "
        "only the agent's NEW edits are violations"
    )
    assert cycle.fix_metadata.get("scope_violations", []) == [], (
        "scope_violations must be empty — operator_file.py was already "
        "in pre_cycle_paths, so it is not attributed to the agent"
    )
    assert (tmp_path / "operator_file.py").read_text() == "# operator carry-over edit\n", (
        "post-cycle reconciliation must NOT revert the operator's edit"
    )


def test_i00082_in_scope_fix_cycle_completes_normally(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy-path regression: when the agent edits only files inside
    allowed_paths the cycle finishes with FixStatus.completed and no
    scope_violation_escalation is produced.

    AC4: The step should advance normally; no DaemonEvent of type
    scope_violation_escalation is emitted for this cycle.
    """
    from orch.daemon.fix_cycle import run_fix_cycle

    # Arrange: worktree with two in-scope files and a strict manifest.
    _setup_git_worktree(
        tmp_path,
        {
            "workflow-manifest.json": (
                '{"scope": {"allowed_paths": ["src/module.py", "src/helper.py"]}, "steps": []}'
            ),
            "src/module.py": "def broken(): pass\n",
            "src/helper.py": "# helper\n",
        },
    )

    def fake_agent_run_happy_path(prompt: str, cwd: pathlib.Path) -> dict:  # type: ignore[type-arg]
        # Agent fixes only in-scope files — exactly what is expected
        (cwd / "src" / "module.py").write_text("def fixed(): return True\n")
        return {"completion_status": "complete"}

    monkeypatch.setattr("orch.daemon.fix_cycle.run_llm_agent", fake_agent_run_happy_path)

    # Act
    cycle = run_fix_cycle(
        worktree_path=tmp_path,
        item_id="I-99003",
        step_id="S01",
        cycle_number=1,
        gate_failure="mypy: module.py:1 error",
    )

    # Assert — semantic, not shape
    assert cycle.status == FixStatus.completed, (
        f"expected FixStatus.completed, got {cycle.status!r} — in-scope edits "
        "must not trigger escalation (happy-path regression)"
    )
    assert cycle.fix_metadata.get("scope_violations", []) == [], (
        "no scope violations expected when the agent stays inside allowed_paths"
    )
    # Verify no scope_violations key with content was set (belt-and-suspenders)
    assert (
        "scope_violations" not in cycle.fix_metadata or cycle.fix_metadata["scope_violations"] == []
    ), "fix_metadata must not contain non-empty scope_violations on a clean cycle"


def test_i00082_load_allowed_paths_ignores_corrupt_manifest(tmp_path: pathlib.Path) -> None:
    """_load_allowed_paths must return [] when the manifest exists but contains invalid JSON.

    Covers the OSError/JSONDecodeError handler so the daemon never crashes on
    a corrupt or partially-written manifest file.
    """
    from orch.daemon.fix_cycle import _load_allowed_paths

    # Write a corrupt manifest at the fallback (root-level) path
    (tmp_path / "workflow-manifest.json").write_text("{not valid json}")

    result = _load_allowed_paths(tmp_path, "I-99005")

    assert result == [], "expected empty list for corrupt manifest, got {result!r}"


def test_i00082_run_fix_cycle_no_scope_is_legacy_mode(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When scope.allowed_paths is absent, the cycle completes without violations.

    Legacy items (no allowed_paths in manifest) must not be affected by scope
    enforcement — the reconciliation is skipped and the cycle always completes
    normally even when the agent edits arbitrary files.
    """
    from orch.daemon.fix_cycle import run_fix_cycle

    _setup_git_worktree(
        tmp_path,
        {
            "workflow-manifest.json": '{"steps": []}',
            "main.py": "x = 1\n",
        },
    )

    def fake_agent_no_scope(prompt: str, cwd: pathlib.Path) -> dict:  # type: ignore[type-arg]
        # Agent edits a file — but no scope is declared so it should not matter
        (cwd / "main.py").write_text("x = 2\n")
        return {"completion_status": "complete"}

    monkeypatch.setattr("orch.daemon.fix_cycle.run_llm_agent", fake_agent_no_scope)

    cycle = run_fix_cycle(
        worktree_path=tmp_path,
        item_id="I-99006",
        step_id="S01",
        cycle_number=1,
        gate_failure="some error",
    )

    assert cycle.status == FixStatus.completed, (
        f"expected FixStatus.completed in legacy mode, got {cycle.status!r}"
    )
    assert cycle.fix_metadata.get("scope_violations", []) == []


def test_i00082_complete_fix_cycle_escalates_scope_violation(
    tmp_path: pathlib.Path,
    db_session: object,
    test_project: object,
) -> None:
    """_complete_fix_cycle detects out-of-scope agent edits and sets FixStatus.escalated.

    This exercises the DB-backed scope reconciliation path that reads pre_cycle_paths
    from fix_metadata and compares with the current git state.
    """
    from datetime import UTC, datetime

    from orch.daemon.fix_cycle import _complete_fix_cycle
    from orch.db.models import (
        DaemonEvent,
        FixCycle,
        FixTrigger,
        StepStatus,
        StepType,
        WorkflowStep,
        WorkItem,
        WorkItemPhase,
        WorkItemStatus,
        WorkItemType,
    )

    # Create DB rows
    item = WorkItem(
        project_id="test-proj",
        id="CR-99001",
        type=WorkItemType.ChangeRequest,
        title="Scope violation test",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)  # type: ignore[attr-defined]
    db_session.flush()  # type: ignore[attr-defined]

    step = WorkflowStep(
        project_id="test-proj",
        work_item_id="CR-99001",
        step_number=1,
        step_id="S01",
        agent_label="QV",
        step_type=StepType.quality_validation,
        status=StepStatus.needs_fix,
    )
    db_session.add(step)  # type: ignore[attr-defined]
    db_session.flush()  # type: ignore[attr-defined]

    # Build a git worktree: manifest with tight allowed_paths, initial commit clean
    _setup_git_worktree(
        tmp_path,
        {
            "ai-dev/active/CR-99001/workflow-manifest.json": (
                '{"scope": {"allowed_paths": ["allowed.py"]}, "steps": []}'
            ),
            "allowed.py": "# in scope\n",
        },
    )
    # Simulate the agent creating an out-of-scope file (untracked after agent ran)
    (tmp_path / "out_of_scope.py").write_text("# agent created\n")

    fc = FixCycle(
        step_id=step.id,
        cycle_number=1,
        trigger_type=FixTrigger.quality_validation,
        status=FixStatus.in_progress,
        fix_metadata={
            "worktree_path": str(tmp_path),
            "pre_cycle_paths": [],  # nothing was modified before agent ran
        },
    )
    db_session.add(fc)  # type: ignore[attr-defined]
    db_session.flush()  # type: ignore[attr-defined]

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))

    db_session.refresh(fc)  # type: ignore[attr-defined]
    assert fc.status == FixStatus.escalated, (
        f"expected FixStatus.escalated after out-of-scope edit, got {fc.status!r}"
    )
    assert "out_of_scope.py" in fc.fix_metadata["scope_violations"], (
        "out_of_scope.py must appear in fix_metadata['scope_violations']"
    )

    # A scope_violation_escalation DaemonEvent must have been emitted
    events = (
        db_session.query(DaemonEvent)  # type: ignore[attr-defined]
        .filter_by(project_id="test-proj", event_type="scope_violation_escalation")
        .all()
    )
    assert len(events) == 1, "expected exactly one scope_violation_escalation event"
    assert "out_of_scope.py" in str(events[0].event_metadata)


def test_i00082_complete_fix_cycle_reconciliation_exception_is_tolerated(
    tmp_path: pathlib.Path,
    db_session: object,
    test_project: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When _captured_paths raises during scope reconciliation the exception is logged
    and the cycle still completes normally — violations default to empty.

    This prevents a git-command failure (e.g. corrupt repo) from permanently
    blocking the fix-cycle machinery.
    """
    from datetime import UTC, datetime

    import orch.daemon.fix_cycle as fc_module
    from orch.daemon.fix_cycle import _complete_fix_cycle
    from orch.db.models import (
        FixCycle,
        FixTrigger,
        StepStatus,
        StepType,
        WorkflowStep,
        WorkItem,
        WorkItemPhase,
        WorkItemStatus,
        WorkItemType,
    )

    # Create DB rows
    item = WorkItem(
        project_id="test-proj",
        id="CR-99002",
        type=WorkItemType.ChangeRequest,
        title="Exception tolerance test",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)  # type: ignore[attr-defined]
    db_session.flush()  # type: ignore[attr-defined]

    step = WorkflowStep(
        project_id="test-proj",
        work_item_id="CR-99002",
        step_number=1,
        step_id="S01",
        agent_label="QV",
        step_type=StepType.quality_validation,
        status=StepStatus.needs_fix,
    )
    db_session.add(step)  # type: ignore[attr-defined]
    db_session.flush()  # type: ignore[attr-defined]

    # Manifest must exist so _load_allowed_paths returns non-empty allowed_paths
    # (otherwise the reconciliation block is skipped entirely)
    manifest_dir = tmp_path / "ai-dev" / "active" / "CR-99002"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "workflow-manifest.json").write_text(
        '{"scope": {"allowed_paths": ["allowed.py"]}, "steps": []}'
    )

    # _captured_paths raises — simulates a git failure (e.g. corrupt repo)
    monkeypatch.setattr(
        fc_module, "_captured_paths", lambda _p: (_ for _ in ()).throw(RuntimeError("git error"))
    )  # type: ignore[arg-type]

    fc = FixCycle(
        step_id=step.id,
        cycle_number=1,
        trigger_type=FixTrigger.quality_validation,
        status=FixStatus.in_progress,
        fix_metadata={
            "worktree_path": str(tmp_path),
            "pre_cycle_paths": [],
        },
    )
    db_session.add(fc)  # type: ignore[attr-defined]
    db_session.flush()  # type: ignore[attr-defined]

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))

    # The normal-completion path does not call db.commit() internally (only the
    # violations branch does). Flush pending changes so refresh reads the updated state.
    db_session.flush()  # type: ignore[attr-defined]
    db_session.refresh(fc)  # type: ignore[attr-defined]
    assert fc.status == FixStatus.completed, (
        f"expected FixStatus.completed when reconciliation throws, got {fc.status!r}; "
        "exception must be swallowed and the cycle must proceed normally"
    )
