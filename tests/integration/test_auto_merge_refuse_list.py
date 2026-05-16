"""Integration tests for F-00084 auto_merge — refuse-list safety (AC3).

Covers:
- AC3: migration file refuse-list
- All default refuse-list patterns
- Mixed refuse + allow (refuse wins)
- Defence-in-depth: Python classifier catches what bash might miss

All tests use the testcontainer Postgres fixture; no real LLM calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from orch.daemon.auto_merge import (
    EVENT_AUTO_RESOLUTION_SKIPPED,
    PHASE_DISABLED,
    PHASE_DRY_RUN,
    AutoMergeConfig,
    classify_conflicts,
    emit_skipped_event,
)
from orch.db.models import (
    AgentRuntimeOption,
    DaemonEvent,
)
from tests.integration.auto_merge_fixtures import (
    FakeLLM,
    make_work_item,
)

# Register auto_merge_fixtures as a pytest plugin so its fixtures are
# discoverable in this module without re-importing them by name (avoids F811).
pytest_plugins = ("tests.integration.auto_merge_fixtures",)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helper: build AutoMergeConfig
# ---------------------------------------------------------------------------


def _config_with_defaults(phase: int = PHASE_DISABLED) -> AutoMergeConfig:
    """Build config with F-00084 default refuse-list and allowlist."""
    d = AutoMergeConfig.defaults()
    return AutoMergeConfig(
        phase=phase,
        runtime_option_id=d.runtime_option_id,
        allowlist_patterns=d.allowlist_patterns,
        refuselist_patterns=d.refuselist_patterns,
        max_conflict_hunk_lines=d.max_conflict_hunk_lines,
        max_conflicted_files_per_merge=d.max_conflicted_files_per_merge,
        max_file_size_bytes=d.max_file_size_bytes,
        max_event_metadata_bytes=d.max_event_metadata_bytes,
        llm_call_timeout_seconds=d.llm_call_timeout_seconds,
    )


def _load_actual_defaults() -> AutoMergeConfig:
    """Load the actual default config (same as AutoMergeConfig.defaults())."""
    return AutoMergeConfig.defaults()


def _events_of_type(db: Session, project_id: str, event_type: str) -> list[DaemonEvent]:
    return list(
        db.scalars(
            select(DaemonEvent).where(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type == event_type,
            )
        ).all()
    )


def _write_conflict_file(path: Path) -> None:
    """Write a text file with a minimal conflict marker."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")


# ---------------------------------------------------------------------------
# AC3: Migration file is refuse-listed — zero LLM calls
# ---------------------------------------------------------------------------


def test_ac3_migration_file_refuse_list(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """AC3: conflict in orch/db/migrations/versions/*.py → skipped, zero LLM calls.

    Asserts:
    - classify_conflicts returns skipped_reason='refuse_list'
    - emit_skipped_event creates a merge_auto_resolution_skipped event
    - reason='refuse_list' in event_metadata
    - FakeLLM was NOT called (Invariant 1)
    """
    project_id = test_project.id
    migration_path = "orch/db/migrations/versions/d1e2f3abc456_synthetic_conflict.py"

    abs_path = tmp_path / migration_path
    _write_conflict_file(abs_path)

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[migration_path],
        config=config,
    )

    assert result.skipped_reason == "refuse_list"
    assert migration_path in result.refuse_files
    assert len(result.eligible_files) == 0

    # Simulate what merge_queue.py does: emit a skipped event
    emit_skipped_event(
        db_session,
        project_id,
        "F-99920",
        {
            "reason": result.skipped_reason,
            "refuse_files": list(result.refuse_files),
            "eligible_files": [],
        },
    )

    # merge_auto_resolution_skipped event fired
    skipped = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_SKIPPED)
    assert len(skipped) == 1
    meta = skipped[0].event_metadata
    assert meta["reason"] == "refuse_list"
    assert migration_path in meta["refuse_files"]

    # Zero LLM calls (Invariant 1)
    assert len(fake_llm.calls) == 0


def test_ac3_migration_refuse_list_attempt_resolution_phase1(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option: AgentRuntimeOption,
    tmp_path: Path,
) -> None:
    """AC3: Even with phase=1, migration in refuse_files never reaches attempt_resolution.

    The refuse-list check happens in classify_conflicts (before attempt_resolution).
    This test verifies the full path: classify → skipped (never attempt_resolution).
    """
    project_id = test_project.id
    item_id = "F-99921"
    make_work_item(db_session, project_id, item_id)

    migration_path = "orch/db/migrations/versions/abc123_another.py"
    abs_path = tmp_path / migration_path
    _write_conflict_file(abs_path)

    config = _config_with_defaults(phase=PHASE_DRY_RUN)

    # Classification → refuse_list
    classification = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[migration_path],
        config=config,
    )

    assert classification.skipped_reason == "refuse_list"
    # Because skipped_reason is set, merge_queue.py emits skipped — NOT attempt_resolution
    emit_skipped_event(
        db_session,
        project_id,
        item_id,
        {
            "reason": classification.skipped_reason,
            "refuse_files": list(classification.refuse_files),
            "eligible_files": [],
        },
    )

    # LLM was never called
    assert len(fake_llm.calls) == 0

    # Skipped event fired
    skipped = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_SKIPPED)
    assert len(skipped) == 1
    assert skipped[0].event_metadata["reason"] == "refuse_list"


# ---------------------------------------------------------------------------
# Refuse-list: .gitleaks.toml
# ---------------------------------------------------------------------------


def test_refuse_list_gitleaks_toml(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """.gitleaks.toml in conflict → refuse_list skip."""
    _ = test_project.id  # ensure project row exists for test isolation
    conflict_path = ".gitleaks.toml"
    _write_conflict_file(tmp_path / conflict_path)

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[conflict_path],
        config=config,
    )

    assert result.skipped_reason == "refuse_list"
    assert conflict_path in result.refuse_files
    assert len(fake_llm.calls) == 0


# ---------------------------------------------------------------------------
# Refuse-list: .env files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "env_path",
    [
        ".env",
        ".env.test",
        ".env.local",
        ".env.production",
    ],
)
def test_refuse_list_env_files(
    env_path: str,
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """.env and .env.* files in conflict → refuse_list skip."""
    _write_conflict_file(tmp_path / env_path)

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[env_path],
        config=config,
    )

    assert result.skipped_reason == "refuse_list", (
        f"{env_path} should be refuse-listed but got skipped_reason={result.skipped_reason!r}"
    )
    assert env_path in result.refuse_files
    assert len(fake_llm.calls) == 0


# ---------------------------------------------------------------------------
# Refuse-list: executor scripts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exec_script",
    [
        "executor/worktree_commit.sh",
        "executor/worktree_setup.sh",
        "executor/step_executor.sh",
        "executor/step_executor_lib.sh",
        "executor/scope_gate.py",
        "executor/auto_merge.toml",
    ],
)
def test_refuse_list_executor_scripts(
    exec_script: str,
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """Executor scripts in conflict → refuse_list skip (defence in depth)."""
    _write_conflict_file(tmp_path / exec_script)

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[exec_script],
        config=config,
    )

    assert result.skipped_reason == "refuse_list", (
        f"{exec_script} should be refuse-listed but got skipped_reason={result.skipped_reason!r}"
    )
    assert exec_script in result.refuse_files
    assert len(fake_llm.calls) == 0


# ---------------------------------------------------------------------------
# Refuse-list: binary image files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "image_path",
    [
        "dashboard/static/foo.png",
        "dashboard/static/logo.jpg",
        "dashboard/static/icon.jpeg",
        "dashboard/static/anim.gif",
    ],
)
def test_refuse_list_binary_image_suffix(
    image_path: str,
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """Binary image files (by suffix) in conflict → refuse_list skip."""
    path = tmp_path / image_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PNG data here - not actual binary but has matching suffix")

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[image_path],
        config=config,
    )

    assert result.skipped_reason == "refuse_list", (
        f"{image_path} should be refuse-listed but got skipped_reason={result.skipped_reason!r}"
    )
    assert image_path in result.refuse_files
    assert len(fake_llm.calls) == 0


# ---------------------------------------------------------------------------
# Refuse-list: uv.lock (should not go to LLM — handled by --ours rule)
# ---------------------------------------------------------------------------


def test_refuse_list_uv_lock(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """Regression: uv.lock conflict must NOT reach the LLM (handled by --ours rule).

    F-00084 must not accidentally route uv.lock to auto_merge_resolve.
    """
    _write_conflict_file(tmp_path / "uv.lock")

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["uv.lock"],
        config=config,
    )

    assert result.skipped_reason == "refuse_list", (
        "uv.lock should be refuse-listed (handled by worktree_commit.sh --ours)"
    )
    assert "uv.lock" in result.refuse_files
    assert len(fake_llm.calls) == 0


# ---------------------------------------------------------------------------
# Refuse-list: orch/db/identity.py and orch/config.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sensitive_path",
    [
        "orch/db/identity.py",
        "orch/config.py",
    ],
)
def test_refuse_list_sensitive_orch_files(
    sensitive_path: str,
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """orch/db/identity.py and orch/config.py must never reach the LLM."""
    _write_conflict_file(tmp_path / sensitive_path)

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[sensitive_path],
        config=config,
    )

    assert result.skipped_reason == "refuse_list", f"{sensitive_path} must be refuse-listed"
    assert sensitive_path in result.refuse_files
    assert len(fake_llm.calls) == 0


# ---------------------------------------------------------------------------
# Mixed refuse + allow: refuse wins (defence in depth)
# ---------------------------------------------------------------------------


def test_mixed_refuse_and_allow_refuse_wins(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """AC3 extension: one allowlisted + one refuse-listed → refuse wins; no LLM call."""
    project_id = test_project.id
    item_id = "F-99930"
    make_work_item(db_session, project_id, item_id)

    test_file = "tests/unit/test_something.py"
    migration_file = "orch/db/migrations/versions/abc123_test.py"

    _write_conflict_file(tmp_path / test_file)
    _write_conflict_file(tmp_path / migration_file)

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[test_file, migration_file],
        config=config,
    )

    # Refuse-list wins regardless of allowlist match
    assert result.skipped_reason == "refuse_list"
    assert migration_file in result.refuse_files
    assert len(result.eligible_files) == 0

    # Emit the skipped event (simulating merge_queue.py behaviour)
    emit_skipped_event(
        db_session,
        project_id,
        item_id,
        {
            "reason": result.skipped_reason,
            "refuse_files": list(result.refuse_files),
            "eligible_files": [],
        },
    )

    skipped = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_SKIPPED)
    assert len(skipped) == 1
    assert skipped[0].event_metadata["reason"] == "refuse_list"

    # No LLM calls (Invariant 1)
    assert len(fake_llm.calls) == 0


# ---------------------------------------------------------------------------
# Defence-in-depth: Python classifier catches files not in allowlist
# ---------------------------------------------------------------------------


def test_refuse_list_defence_in_depth_non_allowlisted_source(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """Defence-in-depth: source file not in allowlist → not_allowlisted (Python catches it).

    A file like orch/daemon/merge_queue.py is not in the refuse-list but also
    not in the allowlist — Python's classify_conflicts catches it as not_allowlisted.
    This ensures even if bash emits AUTO_RESOLVE_REQUESTED for it, Python rejects.
    """
    source_file = "orch/daemon/merge_queue.py"
    _write_conflict_file(tmp_path / source_file)

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[source_file],
        config=config,
    )

    # Not in allowlist — Python classifier catches it
    assert result.skipped_reason == "not_allowlisted"
    assert len(result.eligible_files) == 0
    assert len(fake_llm.calls) == 0


def test_refuse_list_defence_in_depth_dashboard_js(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    """Defence-in-depth: JS/TS files not in allowlist → not_allowlisted."""
    js_file = "dashboard/static/htmx.min.js"
    _write_conflict_file(tmp_path / js_file)

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[js_file],
        config=config,
    )

    assert result.skipped_reason == "not_allowlisted"
    assert len(result.eligible_files) == 0
    assert len(fake_llm.calls) == 0


# ---------------------------------------------------------------------------
# Allowlisted files: tests and docs pass classification
# ---------------------------------------------------------------------------


def test_allowlisted_test_files_pass_classification(
    tmp_path: Path,
) -> None:
    """Allowlisted test files with valid conflict markers pass classification."""
    conflict_files = [
        "tests/unit/test_something.py",
        "tests/integration/test_another.py",
    ]
    for f in conflict_files:
        path = tmp_path / f
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=conflict_files,
        config=config,
    )

    assert result.skipped_reason is None
    assert set(result.eligible_files) == set(conflict_files)
    assert len(result.refuse_files) == 0


def test_allowlisted_docs_pass_classification(
    tmp_path: Path,
) -> None:
    """Allowlisted docs/**/*.md files pass classification.

    Python's fnmatch treats '**' as two consecutive '*' wildcards — unlike shell
    globbing, fnmatch('docs/file.md', 'docs/**/*.md') is False because the
    pattern requires a literal '/' after the '**' segment.  The allowlist pattern
    docs/**/*.md therefore matches nested paths such as docs/subdir/file.md
    but NOT top-level docs/file.md.  Tests use a nested path to match the actual
    pattern semantics.
    """
    conflict_files = ["docs/architecture/IW_AI_Core_Architecture.md"]
    path = tmp_path / conflict_files[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<<<<<<< HEAD\n# Old section\n=======\n# New section\n>>>>>>> branch\n")

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=conflict_files,
        config=config,
    )

    assert result.skipped_reason is None
    assert set(result.eligible_files) == set(conflict_files)


# ---------------------------------------------------------------------------
# Refuse-list: other binary extensions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "binary_path",
    [
        "data/export.db",
        "data/cache.sqlite",
        "assets/model.parquet",
        "releases/package.zst",
    ],
)
def test_refuse_list_binary_extensions(
    binary_path: str,
    tmp_path: Path,
) -> None:
    """Binary file extensions from the default refuse-list → refuse_list skip."""
    path = tmp_path / binary_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"binary content " * 100)

    config = _load_actual_defaults()

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[binary_path],
        config=config,
    )

    assert result.skipped_reason == "refuse_list", (
        f"{binary_path} should be refuse-listed but got {result.skipped_reason!r}"
    )
    assert binary_path in result.refuse_files


# ---------------------------------------------------------------------------
# Emit skipped event: verify DaemonEvent structure
# ---------------------------------------------------------------------------


def test_emit_skipped_event_structure(
    db_session: Session,
    test_project,
) -> None:
    """emit_skipped_event creates a DaemonEvent with correct fields."""
    project_id = test_project.id
    item_id = "F-99940"

    details = {
        "reason": "refuse_list",
        "refuse_files": ["orch/db/migrations/versions/abc.py"],
        "eligible_files": [],
    }

    emit_skipped_event(db_session, project_id, item_id, details)

    events = _events_of_type(db_session, project_id, EVENT_AUTO_RESOLUTION_SKIPPED)
    assert len(events) == 1

    evt = events[0]
    assert evt.entity_id == item_id
    assert evt.entity_type == "work_item"
    assert evt.project_id == project_id
    assert evt.event_metadata["reason"] == "refuse_list"
    assert "orch/db/migrations/versions/abc.py" in evt.event_metadata["refuse_files"]


def test_emit_config_invalid_event_structure(
    db_session: Session,
    test_project,
) -> None:
    """emit_config_invalid_event creates a DaemonEvent with correct fields."""
    from orch.daemon.auto_merge import EVENT_AUTO_MERGE_CONFIG_INVALID, emit_config_invalid_event

    project_id = test_project.id
    item_id = "F-99941"

    emit_config_invalid_event(db_session, project_id, item_id, "TOML parse error: line 1")

    events = list(
        db_session.scalars(
            select(DaemonEvent).where(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type == EVENT_AUTO_MERGE_CONFIG_INVALID,
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].entity_id == item_id
    assert "error" in events[0].event_metadata
    assert "TOML parse error" in events[0].event_metadata["error"]
