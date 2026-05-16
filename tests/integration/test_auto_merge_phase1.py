"""Integration tests for F-00084 auto_merge Phase 0 and Phase 1.

Covers AC1, AC2, AC4, AC5, AC6 and key Invariants (3, 5, 8).
All tests use the testcontainer Postgres fixture; no real LLM calls.

The FakeLLM fixture (from auto_merge_fixtures) replaces invoke_llm_for_file
at the Python boundary — no subprocess is spawned for LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from orch.daemon import auto_merge as am
from orch.daemon.auto_merge import (
    EVENT_AUTO_RESOLUTION_ATTEMPTED,
    EVENT_AUTO_RESOLUTION_FAILED,
    EVENT_AUTO_RESOLUTION_SKIPPED,
    EVENT_AUTO_RESOLVED,
    PHASE_DISABLED,
    PHASE_DRY_RUN,
    AutoMergeConfig,
    attempt_resolution,
    classify_conflicts,
)
from orch.db.models import (
    AgentRuntimeOption,
    DaemonEvent,
)
from tests.integration.auto_merge_fixtures import (
    FakeLLM,
    make_default_runtime_option,
    make_work_item,
)

# Register auto_merge_fixtures as a pytest plugin so its fixtures are
# discoverable in this module without re-importing them by name (avoids F811).
pytest_plugins = ("tests.integration.auto_merge_fixtures",)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helper: build an AutoMergeConfig for tests
# ---------------------------------------------------------------------------


def _phase0_config(**overrides) -> AutoMergeConfig:
    defaults: dict = {
        "phase": PHASE_DISABLED,
        "runtime_option_id": None,
        "allowlist_patterns": ("tests/**/*.py", "docs/**/*.md"),
        "refuselist_patterns": ("orch/db/migrations/versions/*.py", ".env"),
        "max_conflict_hunk_lines": 80,
        "max_conflicted_files_per_merge": 5,
        "max_file_size_bytes": 256_000,
        "max_event_metadata_bytes": 262_144,
        "llm_call_timeout_seconds": 120,
    }
    defaults.update(overrides)
    return AutoMergeConfig(**defaults)


def _phase1_config(**overrides) -> AutoMergeConfig:
    return _phase0_config(phase=PHASE_DRY_RUN, **overrides)


# ---------------------------------------------------------------------------
# Helper: query DaemonEvent rows by type
# ---------------------------------------------------------------------------


def _events_of_type(db: Session, project_id: str, event_type: str) -> list[DaemonEvent]:
    return list(
        db.scalars(
            select(DaemonEvent).where(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type == event_type,
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# AC1: I-00085 shape — 3 test files, comment-drift conflict, phase=1
# ---------------------------------------------------------------------------


def test_ac1_i00085_shape_phase1_dry_run(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """AC1: 3 test-file conflict (I-00085 shape) → dry-run capture with phase=1.

    Asserts:
    - merge_auto_resolution_attempted event with 3 conflict_files
    - FakeLLM was called 3 times (one per file)
    - merge_auto_resolved event with proposed_content in metadata
    - attempt_resolution returns success=False (Phase 1 never applies)
    """
    project_id = test_project.id
    item_id = "F-99901"
    make_work_item(db_session, project_id, item_id, title="I-00085 shape test")

    conflict_files = [
        "tests/unit/test_runtime_options_a.py",
        "tests/unit/test_runtime_options_b.py",
        "tests/unit/test_runtime_options_c.py",
    ]

    # Create the actual files in tmp_path (classify_conflicts reads them)
    for f in conflict_files:
        path = tmp_path / f
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<<<<<<< HEAD\ncount = 42  # updated by I-00084\n=======\ncount = 42\n>>>>>>> branch\n"
        )

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    # Classify first (simulates merge_queue.py's classify call)
    classification = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=conflict_files,
        config=config,
    )
    assert classification.skipped_reason is None
    assert set(classification.eligible_files) == set(conflict_files)

    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="I-00085 shape test",
        item_description="Test feature matching I-00085 conflict shape.",
        worktree_path=str(tmp_path),
        main_sha="abc123def456",
        branch_name="agent/F-99901-test",
        eligible_files=conflict_files,
        config=config,
    )

    # AC1: Phase 1 always returns success=False
    assert result.success is False
    assert result.phase == PHASE_DRY_RUN

    # FakeLLM called once per file
    assert len(fake_llm.calls) == 3
    called_files = {c.file_path for c in fake_llm.calls}
    assert called_files == set(conflict_files)

    # merge_auto_resolution_attempted event
    attempted = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_ATTEMPTED)
    assert len(attempted) == 1
    meta = attempted[0].event_metadata
    assert meta["conflict_files"] == conflict_files
    assert meta["phase"] == PHASE_DRY_RUN
    assert meta["policy_decision"] == "allowlist"
    assert meta["runtime_option_id"] == default_runtime_option.id

    # merge_auto_resolved event
    resolved = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLVED)
    assert len(resolved) == 1
    resolved_meta = resolved[0].event_metadata
    assert "per_file" in resolved_meta
    assert len(resolved_meta["per_file"]) == 3
    # Every per_file entry has proposed_content and prompt_hash
    for entry in resolved_meta["per_file"]:
        assert "file_path" in entry
        assert "proposed_content" in entry
        assert "prompt_hash" in entry


def test_ac1_resolution_attempted_event_structure(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """AC1 detail: merge_auto_resolution_attempted event metadata keys match spec."""
    project_id = test_project.id
    item_id = "F-99902"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_something.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Test",
        item_description="Desc",
        worktree_path=str(tmp_path),
        main_sha="deadbeef",
        branch_name="agent/F-99902",
        eligible_files=conflict_files,
        config=config,
    )

    attempted = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_ATTEMPTED)
    assert len(attempted) == 1
    meta = attempted[0].event_metadata

    # Spec-required keys
    assert "conflict_files" in meta
    assert "phase" in meta
    assert "policy_decision" in meta
    assert "runtime_option_id" in meta
    assert meta["policy_decision"] == "allowlist"
    assert meta["runtime_option_id"] == default_runtime_option.id


# ---------------------------------------------------------------------------
# AC2: I-00086 shape — prompt contains three-way content and commit logs
# ---------------------------------------------------------------------------


def test_ac2_i00086_shape_prompt_contains_three_way_content(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """AC2: I-00086 shape — invoke_llm_for_file called once per eligible file.

    fake_llm replaces invoke_llm_for_file at the Python boundary, so we verify
    that attempt_resolution dispatches to the LLM exactly once per eligible file
    with the correct file_path. build_resolution_prompt content coverage lives in
    tests/unit/test_auto_merge_prompt.py — calling build_resolution_prompt here
    would be unreachable because fake_llm replaces the whole invoke_llm_for_file.
    """
    project_id = test_project.id
    item_id = "F-99903"
    make_work_item(db_session, project_id, item_id, title="I-00086 shape test")

    conflict_files = [
        "tests/integration/test_agent_runtime_opts.py",
        "tests/integration/test_phase2_apply.py",
        "tests/integration/test_overrides.py",
    ]

    for f in conflict_files:
        path = tmp_path / f
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<<<<<<< HEAD\n"
            "PREV_REVISION = 'abc123'\n"
            "assert count == db_session.query(Model).count()\n"
            "=======\n"
            "PREV_REVISION = 'def456'\n"
            "assert count == 42\n"
            ">>>>>>> branch\n"
        )

    config = _phase1_config(
        runtime_option_id=default_runtime_option.id,
        allowlist_patterns=("tests/**/*.py",),
    )

    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="I-00086 shape test",
        item_description="Hardcoded vs dynamic assertion divergence.",
        worktree_path=str(tmp_path),
        main_sha="cafebabe1234",
        branch_name="agent/F-99903-i00086-shape",
        eligible_files=conflict_files,
        config=config,
    )

    # One LLM call dispatched per eligible file (covering AC2's "three files")
    assert len(fake_llm.calls) == 3
    called_files = {c.file_path for c in fake_llm.calls}
    assert called_files == set(conflict_files)

    # All calls use the configured runtime option's model
    for call in fake_llm.calls:
        assert call.model == default_runtime_option.model
        assert call.cli_tool == default_runtime_option.cli_tool

    # Phase 1: always success=False (dry-run)
    assert result.success is False


# ---------------------------------------------------------------------------
# AC4: Operator UX unchanged — LLM abstains, merge_conflict still fires
# ---------------------------------------------------------------------------


def test_ac4_operator_ux_unchanged_on_abstain(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """AC4: LLM abstains for one file → merge_auto_resolution_failed event.

    attempt_resolution returns success=False regardless. The merge path in
    merge_queue.py always fires merge_conflict afterwards (separately).
    """
    project_id = test_project.id
    item_id = "F-99904"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_ux.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    # Configure LLM to abstain for this file
    fake_llm.abstain_for.add("tests/unit/test_ux.py")

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="UX test",
        item_description="Operator UX unchanged test.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99904",
        eligible_files=conflict_files,
        config=config,
    )

    # success=False because LLM abstained
    assert result.success is False
    assert len(result.abstained_files) == 1
    assert "tests/unit/test_ux.py" in result.abstained_files

    # merge_auto_resolution_failed event emitted
    failed = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_FAILED)
    assert len(failed) == 1
    meta = failed[0].event_metadata
    assert "tests/unit/test_ux.py" in meta["abstained_files"]

    # No merge_auto_resolved event (abstain path)
    resolved = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLVED)
    assert len(resolved) == 0


def test_ac4_operator_ux_unchanged_on_llm_error(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """AC4: LLM error → merge_auto_resolution_failed event; result.success=False."""
    project_id = test_project.id
    item_id = "F-99905"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_error.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    fake_llm.error_for["tests/unit/test_error.py"] = "exit code 1: command not found"

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Error test",
        item_description="LLM error path test.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99905",
        eligible_files=conflict_files,
        config=config,
    )

    assert result.success is False
    assert len(result.error_files) == 1

    failed_events = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_FAILED)
    assert len(failed_events) == 1
    meta = failed_events[0].event_metadata
    assert "tests/unit/test_error.py" in meta["error_files"]


# ---------------------------------------------------------------------------
# AC5: Phase 0 (disabled) — no LLM call, skipped event emitted
# ---------------------------------------------------------------------------


def test_ac5_phase0_default_no_llm_call(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """AC5: phase=0 → merge_auto_resolution_skipped with reason=phase_0; zero LLM calls.

    This test verifies Invariant 2: no LLM tokens ever consumed when phase=0.
    """
    project_id = test_project.id
    item_id = "F-99906"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_phase0.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    config = _phase0_config()

    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Phase 0 test",
        item_description="Phase 0 short-circuit test.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99906",
        eligible_files=conflict_files,
        config=config,
    )

    # Phase 0 returns success=False immediately
    assert result.success is False
    assert result.phase == PHASE_DISABLED

    # ZERO LLM calls (Invariant 2)
    assert len(fake_llm.calls) == 0

    # merge_auto_resolution_skipped event with reason=phase_0
    skipped = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_SKIPPED)
    assert len(skipped) == 1
    meta = skipped[0].event_metadata
    assert meta["reason"] == "phase_0"
    assert conflict_files[0] in meta["eligible_files"]

    # No attempted/resolved/failed events
    assert len(_events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_ATTEMPTED)) == 0
    assert len(_events_of_type(db_session, project_id, EVENT_AUTO_RESOLVED)) == 0
    assert len(_events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_FAILED)) == 0


def test_ac5_phase0_short_circuit_invariant_2(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5 / Invariant 2: confirm test would fail if Phase-0 short-circuit were removed.

    RED evidence technique: we verify the test catches a broken Phase-0 by
    temporarily making the config look like Phase-1 and asserting the fake_llm
    IS called. This proves the AC5 test above would correctly fail if the
    short-circuit were absent.
    """
    project_id = test_project.id
    item_id = "F-99907"

    # Need a runtime option for Phase 1 to work
    option = make_default_runtime_option(db_session, option_id=9991)
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_invariant2.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    # With phase=1 config (violating the Phase-0 default contract), LLM IS called
    phase1_config = _phase1_config(runtime_option_id=option.id)

    attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Invariant 2 check",
        item_description="Proves phase=0 short-circuit is load-bearing.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99907",
        eligible_files=conflict_files,
        config=phase1_config,
    )

    # With phase=1, the LLM IS invoked — so the AC5 assertion (calls==0) would fail
    assert len(fake_llm.calls) == 1, (
        "Phase-1 config should invoke the LLM; if zero calls, the short-circuit is broken"
    )


# ---------------------------------------------------------------------------
# AC6: Hot-reload — config change without daemon restart
# ---------------------------------------------------------------------------


def test_ac6_sighup_reloads_config(tmp_path: Path) -> None:
    """AC6: reload_config() picks up phase changes from a TOML file.

    This tests the hot-reload surface: reload_config() reads the TOML and
    updates the module-level cache. The daemon's SIGHUP handler calls this.
    """
    toml_file = tmp_path / "auto_merge.toml"
    toml_file.write_text("phase = 0\n")

    config0 = am.reload_config(str(toml_file))
    assert config0.phase == PHASE_DISABLED

    # Operator edits the file to phase=1 (simulates editing then SIGHUP)
    toml_file.write_text("phase = 1\n")

    config1 = am.reload_config(str(toml_file))
    assert config1.phase == PHASE_DRY_RUN

    # The cached config was updated
    assert am._cached_config is not None
    assert am._cached_config.phase == PHASE_DRY_RUN


def test_ac6_reload_config_missing_file_returns_defaults(tmp_path: Path) -> None:
    """AC6: reload_config() with missing file returns phase=0 defaults."""
    missing_path = str(tmp_path / "nonexistent.toml")

    config = am.reload_config(missing_path)
    assert config.phase == PHASE_DISABLED


# ---------------------------------------------------------------------------
# Invariant 3: Phase 1 NEVER modifies the git index
# ---------------------------------------------------------------------------


def test_invariant3_phase1_never_modifies_worktree(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """Invariant 3: git state (HEAD + status) is byte-identical before and after Phase 1.

    Phase 1 invokes the LLM (mocked) but MUST NOT call git add or git rebase --continue.
    """
    import subprocess

    # Build a real git repo so we can snapshot git state
    repo = tmp_path / "worktree"
    repo.mkdir()

    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
        "HOME": str(tmp_path),
    }
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=repo, capture_output=True, env=env, check=True
    )
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, env=env, check=True)

    test_file = repo / "tests" / "test_invariant3.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("value = 0\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, env=env, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=repo, capture_output=True, env=env, check=True
    )

    # Write a conflict-marker file (as if rebase left it unresolved)
    test_file.write_text("<<<<<<< HEAD\nvalue = 1\n=======\nvalue = 2\n>>>>>>> branch\n")

    # Snapshot git state BEFORE
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, env=env
    ).stdout.strip()
    status_before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, env=env
    ).stdout

    project_id = test_project.id
    item_id = "F-99908"
    make_work_item(db_session, project_id, item_id)

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Invariant 3 test",
        item_description="Verify git state is not modified by Phase 1.",
        worktree_path=str(repo),
        main_sha="abc",
        branch_name="agent/F-99908",
        eligible_files=["tests/test_invariant3.py"],
        config=config,
    )

    # Snapshot git state AFTER
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, env=env
    ).stdout.strip()
    status_after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, env=env
    ).stdout

    # Both must be identical (Invariant 3)
    assert head_before == head_after, "Phase 1 must not change HEAD"
    assert status_before == status_after, "Phase 1 must not change git index/status"


# ---------------------------------------------------------------------------
# Invariant 5: event metadata is bounded (≤ 256 KB)
# ---------------------------------------------------------------------------


def test_invariant5_oversized_metadata_is_truncated(
    db_session: Session,
    test_project,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant 5: when LLM returns 1 MB per file, event metadata stays ≤ 256 KB."""
    import hashlib

    project_id = test_project.id
    item_id = "F-99909"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_huge_a.py", "tests/unit/test_huge_b.py"]
    for f in conflict_files:
        path = tmp_path / f
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    # Fake LLM that returns 1 MB of content per file
    huge_content = "x" * (1024 * 1024)  # 1 MB

    def huge_llm_invoke(**kwargs):
        prompt_hash = hashlib.sha256(f"huge-{kwargs['file_path']}".encode()).hexdigest()
        output_hash = hashlib.sha256(huge_content.encode()).hexdigest()
        from orch.daemon.auto_merge import LLMCallResult

        return LLMCallResult(
            file_path=kwargs["file_path"],
            abstained=False,
            proposed_content=huge_content,
            error=None,
            model=kwargs["model"],
            cli_tool=kwargs["cli_tool"],
            input_tokens=None,
            output_tokens=None,
            prompt_hash=prompt_hash,
            output_hash=output_hash,
        )

    monkeypatch.setattr("orch.daemon.auto_merge.invoke_llm_for_file", huge_llm_invoke)

    config = _phase1_config(
        runtime_option_id=default_runtime_option.id,
        max_event_metadata_bytes=262_144,  # 256 KB
    )

    attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Huge content test",
        item_description="Invariant 5: metadata size cap.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99909",
        eligible_files=conflict_files,
        config=config,
    )

    resolved = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLVED)
    assert len(resolved) == 1

    # Verify the stored metadata is within the 256 KB cap
    stored_metadata = resolved[0].event_metadata
    serialized = json.dumps(stored_metadata).encode()
    assert len(serialized) <= 262_144, f"Event metadata exceeds 256 KB: {len(serialized)} bytes"


# ---------------------------------------------------------------------------
# Invariant 8: failed LLM call leaves worktree clean
# ---------------------------------------------------------------------------


def test_invariant8_failed_llm_leaves_worktree_clean(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """Invariant 8: after a failed LLM call, the worktree status is unchanged.

    A failed LLM invocation (via FakeLLM.error_for) must not leave
    partial writes in the worktree.
    """
    project_id = test_project.id
    item_id = "F-99910"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_inv8.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    conflict_content = "<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n"
    path.write_text(conflict_content)

    # LLM errors out on this file
    fake_llm.error_for["tests/unit/test_inv8.py"] = "subprocess error: exit 1"

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    content_before = path.read_text()

    attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Invariant 8 test",
        item_description="Worktree must not be modified on LLM failure.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99910",
        eligible_files=conflict_files,
        config=config,
    )

    # File content must be identical (no partial write)
    content_after = path.read_text()
    assert content_before == content_after, (
        "Phase 1 LLM error path must not modify the file content"
    )

    # merge_auto_resolution_failed event
    failed = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_FAILED)
    assert len(failed) == 1


# ---------------------------------------------------------------------------
# Boundary: runtime_option_id points to nonexistent row
# ---------------------------------------------------------------------------


def test_boundary_runtime_option_id_missing(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """Boundary: nonexistent runtime_option_id AND no global default → failed event, zero LLM calls.

    The Alembic migrations seed a global default AgentRuntimeOption row.  We
    disable it within the rolled-back test transaction so _resolve_runtime_option
    returns None, triggering the runtime_option_missing failure path.
    """
    # Remove default status from all seeded rows so the fallback query returns None.
    # We set is_default=False (not enabled=False) to avoid the
    # ck_agent_runtime_options_default_must_be_enabled DB constraint.
    db_session.query(AgentRuntimeOption).filter(AgentRuntimeOption.is_default.is_(True)).update(
        {"is_default": False}
    )
    db_session.flush()

    project_id = test_project.id
    item_id = "F-99911"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_runtime_missing.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    # Point to a nonexistent runtime_option_id with no default fallback
    config = _phase1_config(runtime_option_id=99999)

    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Missing runtime option test",
        item_description="No runtime option available.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99911",
        eligible_files=conflict_files,
        config=config,
    )

    # No default runtime option exists → merge_auto_resolution_failed
    assert result.success is False

    failed_events = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_FAILED)
    # No LLM calls — can't call without any runtime option
    assert len(fake_llm.calls) == 0
    assert len(failed_events) == 1
    assert failed_events[0].event_metadata.get("reason") == "runtime_option_missing"


def test_boundary_runtime_option_falls_back_to_default(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """Boundary: invalid runtime_option_id falls back to the Alembic-seeded global default.

    _resolve_runtime_option falls through to is_default=True when the explicit
    runtime_option_id row is missing.  The Alembic migration seeds exactly one
    such row; we query it here so the assertion is stable regardless of which
    model the seed uses.
    """
    # Find the Alembic-seeded global default (created by migrations, not a fixture).
    seeded_default = (
        db_session.query(AgentRuntimeOption)
        .filter(AgentRuntimeOption.is_default.is_(True), AgentRuntimeOption.enabled.is_(True))
        .first()
    )
    assert seeded_default is not None, "Alembic seed must create at least one default row"

    project_id = test_project.id
    item_id = "F-99912"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_fallback.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    # Point to nonexistent ID — the seeded default provides the fallback
    config = _phase1_config(runtime_option_id=88888)

    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Fallback test",
        item_description="Falls back to default runtime option.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99912",
        eligible_files=conflict_files,
        config=config,
    )

    # Falls back to the seeded default — LLM IS called with the seeded model
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0].model == seeded_default.model
    assert result.success is False


# ---------------------------------------------------------------------------
# Boundary: malformed AUTO_RESOLVE_REQUESTED marker
# ---------------------------------------------------------------------------


def test_boundary_malformed_marker_parse_auto_resolve(tmp_path: Path) -> None:
    """Boundary: malformed JSON in AUTO_RESOLVE_REQUESTED → parse returns None."""
    from orch.daemon.auto_merge import parse_auto_resolve_marker

    output = "AUTO_RESOLVE_REQUESTED={this is not json\n"
    result = parse_auto_resolve_marker(output)
    assert result is None


def test_boundary_missing_marker_parse_auto_resolve(tmp_path: Path) -> None:
    """Boundary: no marker in output → parse returns None."""
    from orch.daemon.auto_merge import parse_auto_resolve_marker

    output = "[worktree_commit] INFO: rebase conflict\n[worktree_commit] ERROR: abort\n"
    result = parse_auto_resolve_marker(output)
    assert result is None


# ---------------------------------------------------------------------------
# Boundary: phase >= 2 raises ValueError
# ---------------------------------------------------------------------------


def test_boundary_phase2_reserved_raises_value_error(
    db_session: Session,
    test_project,
    tmp_path: Path,
) -> None:
    """Boundary: attempt_resolution with phase=2 raises ValueError immediately."""
    project_id = test_project.id
    item_id = "F-99913"
    make_work_item(db_session, project_id, item_id)

    config = _phase0_config(phase=2)

    with pytest.raises(ValueError, match="reserved"):
        attempt_resolution(
            db=db_session,
            project_id=project_id,
            item_id=item_id,
            item_title="Reserved phase test",
            item_description="Phase 2 is reserved.",
            worktree_path=str(tmp_path),
            main_sha="abc",
            branch_name="agent/F-99913",
            eligible_files=["tests/test_something.py"],
            config=config,
        )


# ---------------------------------------------------------------------------
# Multiple files: mixed success and abstain
# ---------------------------------------------------------------------------


def test_mixed_resolved_and_abstained_files(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """Mixed: some files resolved, one abstained → failed event (not resolved)."""
    project_id = test_project.id
    item_id = "F-99914"
    make_work_item(db_session, project_id, item_id)

    conflict_files = [
        "tests/unit/test_resolved.py",
        "tests/unit/test_abstained.py",
    ]
    for f in conflict_files:
        path = tmp_path / f
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    fake_llm.abstain_for.add("tests/unit/test_abstained.py")

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Mixed abstain test",
        item_description="One file resolved, one abstained.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99914",
        eligible_files=conflict_files,
        config=config,
    )

    assert result.success is False
    assert len(result.abstained_files) == 1
    assert "tests/unit/test_abstained.py" in result.abstained_files

    # merge_auto_resolution_failed because of abstain
    failed = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_FAILED)
    assert len(failed) == 1
    meta = failed[0].event_metadata
    assert "tests/unit/test_abstained.py" in meta["abstained_files"]
    assert "tests/unit/test_resolved.py" in meta["proposed_files"]

    # No merge_auto_resolved event when any file fails
    resolved = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLVED)
    assert len(resolved) == 0


# ---------------------------------------------------------------------------
# Invariant 1: No LLM token for refuse-listed file (via attempt_resolution path)
# ---------------------------------------------------------------------------


def test_invariant1_no_llm_call_for_phase0_eligible_files(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """Invariant 1+2: Phase 0 never calls LLM regardless of eligible file list.

    Even if the file passed classification, phase=0 short-circuits before
    any LLM invocation.
    """
    project_id = test_project.id
    item_id = "F-99915"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/unit/test_inv1.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    config = _phase0_config()  # phase=0

    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Invariant 1 test",
        item_description="No LLM in phase 0.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99915",
        eligible_files=conflict_files,
        config=config,
    )

    assert len(fake_llm.calls) == 0  # Invariant 1+2
    assert result.success is False
    assert result.phase == PHASE_DISABLED
