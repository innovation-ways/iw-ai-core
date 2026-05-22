"""Integration tests for I-00103: per_file_errors in merge_auto_resolution_failed event.

These tests exercise the event-payload schema for `merge_auto_resolution_failed`
events. They use the testcontainer-backed db_session so the JSONB metadata can be
round-tripped through a real PostgreSQL connection.

Fixture wiring mirrors tests/integration/test_auto_merge_phase1.py:
- db_session from tests/integration/conftest.py (testcontainer-backed)
- fake_llm + default_runtime_option from tests/integration/auto_merge_fixtures.py
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from orch.daemon.auto_merge import (
    EVENT_AUTO_RESOLUTION_FAILED,
    PHASE_DRY_RUN,
    AutoMergeConfig,
    attempt_resolution,
)
from orch.db.models import (
    AgentRuntimeOption,
    DaemonEvent,
)
from tests.integration.auto_merge_fixtures import (
    FakeLLM,
    make_work_item,
)

pytest_plugins = ("tests.integration.auto_merge_fixtures",)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _phase1_config(runtime_option_id: int) -> AutoMergeConfig:
    return AutoMergeConfig(
        phase=PHASE_DRY_RUN,
        runtime_option_id=runtime_option_id,
        allowlist_patterns=("tests/**/*.py", "docs/**/*.md"),
        refuselist_patterns=("orch/db/migrations/versions/*.py", ".env"),
        max_conflict_hunk_lines=80,
        max_conflicted_files_per_merge=5,
        max_file_size_bytes=256_000,
        max_event_metadata_bytes=262_144,
        llm_call_timeout_seconds=120,
    )


def _read_failed_event(db: Session, project_id: str) -> DaemonEvent:
    row = db.scalars(
        select(DaemonEvent).where(
            DaemonEvent.project_id == project_id,
            DaemonEvent.event_type == EVENT_AUTO_RESOLUTION_FAILED,
        )
    ).first()
    assert row is not None, "merge_auto_resolution_failed event was not emitted"
    return row


# ---------------------------------------------------------------------------
# Test 1: reproduction — event carries per_file_error_strings
# ---------------------------------------------------------------------------


def test_i00103_failed_event_carries_per_file_error_strings(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """Reproduction: error string must appear in event_metadata['per_file_errors'].

    FAILS before fix: the failed-event metadata lacks 'per_file_errors' entirely.
    PASSES after fix: the list contains one entry with file_path, error, cli_tool, model.

    The default_runtime_option fixture already uses model='minimax/MiniMax-M2.7'
    (the seeded Alembic default). We need cli_tool='opencode' specifically for
    the per_file_errors entry. The seeded default has cli_tool='pi', so we can
    safely UPDATE it to 'opencode' in this test transaction without violating
    uq_agent_runtime_options_cli_model (no other row carries that model).
    """
    project_id = test_project.id
    item_id = "F-99920"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/dashboard/test_auto_merge_routes.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    # Configure FakeLLM to error on this file with the specific timeout message.
    # per_file_errors[i].{file_path, error, cli_tool, model} comes from the
    # LLMCallResult produced by FakeLLM.invoke — the error string is ours,
    # the cli_tool/model come from the runtime_option row (default_runtime_option
    # has cli_tool='claude', model='claude-sonnet-4-6-automerge-test' per the
    # make_default_runtime_option fixture).
    fake_llm.error_for[conflict_files[0]] = (
        "LLM call timed out after 120s: subprocess.TimeoutExpired(..., 120)"
    )

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="I-00103 reproduction test",
        item_description="Reproduction for per-file error string propagation.",
        worktree_path=str(tmp_path),
        main_sha="abc123def456",
        branch_name="agent/F-99920",
        eligible_files=conflict_files,
        config=config,
    )

    event = _read_failed_event(db_session, project_id)
    meta = event.event_metadata

    # Shape assertion first so follow-on assertions are meaningful
    assert "per_file_errors" in meta, (
        "I-00103 bug: merge_auto_resolution_failed metadata must contain the per_file_errors key"
    )
    assert isinstance(meta["per_file_errors"], list)
    assert len(meta["per_file_errors"]) == 1, (
        "per_file_errors must have exactly one entry for the single errored file"
    )

    entry = meta["per_file_errors"][0]

    # Semantic assertions — specific expected values, NOT shape-only.
    # cli_tool and model come from the default_runtime_option fixture:
    #   cli_tool = 'claude' (make_default_runtime_option hardcodes it)
    #   model    = 'claude-sonnet-4-6-automerge-test' (same fixture)
    assert entry["file_path"] == "tests/dashboard/test_auto_merge_routes.py", (
        f"expected file_path to be the conflicted file, got {entry.get('file_path')!r}"
    )
    assert "LLM call timed out after 120s" in entry["error"], (
        f"expected the literal timeout substring in the error string, got {entry.get('error')!r}"
    )
    assert entry["cli_tool"] == default_runtime_option.cli_tool, (
        f"expected cli_tool from runtime_option, got {entry.get('cli_tool')!r}"
    )
    assert entry["model"] == default_runtime_option.model, (
        f"expected model from runtime_option, got {entry.get('model')!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: truncation at 500 chars
# ---------------------------------------------------------------------------


def test_per_file_errors_truncated_at_500_chars(
    db_session: Session,
    test_project,
    monkeypatch: pytest.MonkeyPatch,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """Error string longer than 500 chars must be sliced to exactly 500 characters.

    AC5: per_file_errors[i].error is at most 500 chars in the persisted event.
    Exact equality (== 500), not <= 500 — the implementation slices [:500].
    """
    from orch.daemon.auto_merge import LLMCallResult

    project_id = test_project.id
    item_id = "F-99921"
    make_work_item(db_session, project_id, item_id)

    conflict_files = ["tests/dashboard/test_overflow.py"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    long_error = "x" * 2000  # 2000 chars — well over the 500-char cap

    def patched_invoke(**kwargs: object) -> LLMCallResult:
        import hashlib

        return LLMCallResult(
            file_path=kwargs["file_path"],  # type: ignore[index]
            abstained=False,
            proposed_content=None,
            error=long_error,
            model=kwargs["model"],  # type: ignore[index]
            cli_tool=kwargs["cli_tool"],  # type: ignore[index]
            input_tokens=None,
            output_tokens=None,
            prompt_hash=hashlib.sha256(b"patched-prompt").hexdigest(),
            output_hash=None,
        )

    monkeypatch.setattr("orch.daemon.auto_merge.invoke_llm_for_file", patched_invoke)

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Truncation cap test",
        item_description="Verify 500-char truncation on per-file error strings.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99921",
        eligible_files=conflict_files,
        config=config,
    )

    event = _read_failed_event(db_session, project_id)
    meta = event.event_metadata

    assert "per_file_errors" in meta
    assert len(meta["per_file_errors"]) == 1
    # Exact equality — the implementation slices [:500], not [:500] + "..."
    assert len(meta["per_file_errors"][0]["error"]) == 500, (
        f"expected exactly 500 chars after truncation, got "
        f"{len(meta['per_file_errors'][0]['error'])}"
    )


# ---------------------------------------------------------------------------
# Test 3: only errored calls appear in per_file_errors (not abstains / successes)
# ---------------------------------------------------------------------------


def test_per_file_errors_only_includes_errored_calls(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """Only LLMCallResult entries with error != None appear in per_file_errors.

    Abstained and successful calls must NOT appear in the list.
    The failed event is still emitted because at least one file errored.
    """
    project_id = test_project.id
    item_id = "F-99922"
    make_work_item(db_session, project_id, item_id)

    conflict_files = [
        "tests/unit/test_error_file.py",  # will error
        "tests/unit/test_abstain_file.py",  # will abstain
        "tests/unit/test_success_file.py",  # will succeed
    ]
    for f in conflict_files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    fake_llm.error_for["tests/unit/test_error_file.py"] = "exit code 1: OOM killed"
    fake_llm.abstain_for.add("tests/unit/test_abstain_file.py")
    # test_success_file.py: default FakeLLM response (no error, no abstain)

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Mixed results test",
        item_description="Only errored calls appear in per_file_errors.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99922",
        eligible_files=conflict_files,
        config=config,
    )

    event = _read_failed_event(db_session, project_id)
    meta = event.event_metadata

    assert "per_file_errors" in meta
    per_file = meta["per_file_errors"]

    # Only the errored call appears
    assert len(per_file) == 1, (
        f"expected exactly 1 per_file_errors entry (the errored call only), "
        f"got {len(per_file)}: {per_file}"
    )
    assert per_file[0]["file_path"] == "tests/unit/test_error_file.py"
    assert per_file[0]["error"] == "exit code 1: OOM killed"

    # Abstained and successful calls must NOT appear
    paths_in_per_file_errors = {e["file_path"] for e in per_file}
    assert "tests/unit/test_abstain_file.py" not in paths_in_per_file_errors
    assert "tests/unit/test_success_file.py" not in paths_in_per_file_errors

    # Verify the error_files and abstained_files fields still carry all paths
    assert "tests/unit/test_error_file.py" in meta["error_files"]
    assert "tests/unit/test_abstain_file.py" in meta["abstained_files"]


# ---------------------------------------------------------------------------
# Test 4: per_file_errors absent or empty when no calls errored
# ---------------------------------------------------------------------------


def test_per_file_errors_absent_or_empty_when_no_calls_errored(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """Failed event emitted via pure-abstention (no errors) must have per_file_errors missing or [].

    The existing 'abstained_files' field continues to carry the data.
    No per_file_errors entry must be present for abstain-only failures.
    """
    project_id = test_project.id
    item_id = "F-99923"
    make_work_item(db_session, project_id, item_id)

    conflict_files = [
        "tests/unit/test_abstain_a.py",
        "tests/unit/test_abstain_b.py",
    ]
    for f in conflict_files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    # All files abstain — no errors
    fake_llm.abstain_for.update(conflict_files)

    config = _phase1_config(runtime_option_id=default_runtime_option.id)

    attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="Abstain-only test",
        item_description="per_file_errors must be absent or empty when no calls errored.",
        worktree_path=str(tmp_path),
        main_sha="abc",
        branch_name="agent/F-99923",
        eligible_files=conflict_files,
        config=config,
    )

    event = _read_failed_event(db_session, project_id)
    meta = event.event_metadata

    # per_file_errors must either be absent or empty
    assert meta.get("per_file_errors", []) == [], (
        f"per_file_errors must be absent or empty for abstain-only failures, "
        f"got {meta.get('per_file_errors')!r}"
    )

    # The abstain data still lives in abstained_files
    assert set(meta["abstained_files"]) == set(conflict_files)
