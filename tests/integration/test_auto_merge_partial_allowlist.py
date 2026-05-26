"""Integration tests for CR-00088 — partial-allowlist semantics in Phase 1 dry-run.

Reproduces the CR-00084 conflict shape end-to-end:
  - 3 conflicted files: docs/architecture/foo.md (allowlisted), Makefile, pyproject.toml
  - Default AutoMergeConfig (relies on executor/auto_merge.toml defaults)
  - Phase = 1 (dry-run); LLM stubbed so no real API calls

Assertions:
  - EVENT_AUTO_RESOLUTION_ATTEMPTED has allowlisted_files=[docs/architecture/foo.md]
    and deferred_files=[Makefile, pyproject.toml]
  - EVENT_AUTO_RESOLVED has docs/architecture/foo.md in proposed_files
    but Makefile and pyproject.toml are absent
  - Phase-1 invariant: worktree byte-identical before and after
  - Work item ends in status=failed (Phase-1 behaviour unchanged)

AC5 from CR-00088_CR_Design.md.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from orch.daemon.auto_merge import (
    EVENT_AUTO_RESOLUTION_ATTEMPTED,
    EVENT_AUTO_RESOLVED,
    PHASE_DRY_RUN,
    AutoMergeConfig,
    attempt_resolution,
    classify_conflicts,
)
from orch.db.models import DaemonEvent, WorkItem
from tests.integration.auto_merge_fixtures import (
    FakeLLM,
    make_work_item,
)

# Register auto_merge_fixtures so its fixtures are discoverable without explicit import.
pytest_plugins = ("tests.integration.auto_merge_fixtures",)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
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


def _latest_event(db: Session, project_id: str, item_id: str, event_type: str) -> DaemonEvent:
    """Return the most recent event of the given type for this item."""
    events = _events_of_type(db, project_id, event_type)
    assert len(events) >= 1, f"Expected at least one {event_type} event for item {item_id}"
    return max(events, key=lambda e: e.id)


def _hash_worktree_tree(worktree_path: Path) -> str:
    """Return a content-addressed hash of every regular file under worktree_path.

    Walks the directory tree (not git-tracked files) and computes a single
    SHA-256 aggregating every file's content hash.  This is stable across
    process IDs and timestamps — only file content matters, not git state.
    Used to assert Phase-1 invariant: the worktree's on-disk content is
    byte-identical before and after attempt_resolution().
    """
    per_file_hashes: list[str] = []
    for abs_path in sorted(worktree_path.rglob("*"), key=lambda p: str(p)):
        if not abs_path.is_file():
            continue
        try:
            content = abs_path.read_bytes()
        except OSError:
            content = b""
        per_file_hashes.append(hashlib.sha256(content).hexdigest())

    return hashlib.sha256("".join(per_file_hashes).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Test: CR-00084 conflict shape — event metadata partitions correctly
# ---------------------------------------------------------------------------


def test_cr00084_shape_partitions_event_metadata(
    db_session: Session,
    test_project,
    fake_llm: FakeLLM,
    default_runtime_option,
    tmp_path: Path,
) -> None:
    """AC5: CR-00084 shape → phase-1 dry-run partitions event metadata correctly.

    Conflict shape (CR-00088_CR_Design.md):
      - docs/architecture/foo.md  ← matches docs/**/*.md allowlist pattern
      - Makefile                    ← NOT allowlisted, NOT refused
      - pyproject.toml              ← NOT allowlisted, NOT refused

    Default config (AutoMergeConfig.defaults()):
      - phase = PHASE_DRY_RUN (1)
      - allowlist = ("tests/**/*.py", "docs/**/*.md", "ai-dev/active/**/reports/**", ...)
      - refuselist = migrations, .env, .gitleaks.toml, uv.lock, ...

    Note: fnmatch treats '**' as two consecutive '*' wildcards, so
    "docs/**/*.md" requires a '/' after the '**' segment.  A path like
    "docs/architecture/foo.md" matches (two directory components), while
    "docs/foo.md" does NOT (only one component).  Mirror the pattern used
    in test_auto_merge_refuse_list.py::test_allowlisted_docs_pass_classification.

    Asserts:
      1. classify_conflicts: eligible=[docs/architecture/foo.md],
         deferred=[Makefile, pyproject.toml], skipped_reason=None
      2. EVENT_AUTO_RESOLUTION_ATTEMPTED.metadata.allowlisted_files == ["docs/architecture/foo.md"]
      3. EVENT_AUTO_RESOLUTION_ATTEMPTED.metadata.deferred_files == ["Makefile", "pyproject.toml"]
      4. EVENT_AUTO_RESOLVED.metadata contains docs/architecture/foo.md in proposed_files
      5. Makefile and pyproject.toml are NOT in proposed_files
      6. EVENT_AUTO_RESOLVED.metadata.deferred_files == ["Makefile", "pyproject.toml"]
      7. Phase-1 invariant: worktree content hash unchanged before/after
      8. Work item status == "failed" (Phase-1 behaviour unchanged)
    """
    project_id = test_project.id
    item_id = "CR-00084-SIM"
    make_work_item(db_session, project_id, item_id, title="CR-00084 shape simulation")

    conflict_files = [
        "docs/architecture/foo.md",  # matches docs/**/*.md allowlist pattern
        "Makefile",
        "pyproject.toml",
    ]

    # Write conflict-marker content for every file (classify_conflicts reads files)
    for rel_path in conflict_files:
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<<<<<<< HEAD\nversion from main\n=======\nversion from branch\n>>>>>>> branch\n"
        )

    config = AutoMergeConfig.defaults()
    # Phase 0 defaults to SKIPPED; set phase=1 (dry-run) for the CR-00084 shape test
    object.__setattr__(config, "phase", PHASE_DRY_RUN)

    # 1. Classify: confirm partition at the classification level
    classification = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=conflict_files,
        config=config,
    )
    assert classification.skipped_reason is None, (
        f"Expected skipped_reason=None (partial allowlist), got {classification.skipped_reason!r}"
    )
    assert classification.eligible_files == ("docs/architecture/foo.md",), (
        f"Expected eligible=[docs/architecture/foo.md], got {classification.eligible_files}"
    )
    assert classification.deferred_files == ("Makefile", "pyproject.toml"), (
        f"Expected deferred=[Makefile, pyproject.toml], got {classification.deferred_files}"
    )

    # Snapshot worktree BEFORE the call
    pre_hash = _hash_worktree_tree(tmp_path)

    # 2. Full attempt_resolution path (Phase 1 dry-run)
    result = attempt_resolution(
        db=db_session,
        project_id=project_id,
        item_id=item_id,
        item_title="CR-00084 shape simulation",
        item_description="Simulated CR-00084 conflict shape with partial allowlist.",
        worktree_path=str(tmp_path),
        main_sha="abc123def456",
        branch_name="agent/CR-00084-SIM",
        eligible_files=list(classification.eligible_files),
        deferred_files=list(classification.deferred_files),
        config=config,
    )

    # Phase 1 always returns success=False
    assert result.success is False, "Phase 1 must never return success=True"
    assert result.phase == PHASE_DRY_RUN

    # FakeLLM should have been called exactly once (for docs/architecture/foo.md)
    assert len(fake_llm.calls) == 1, (
        f"Expected 1 LLM call (for docs/architecture/foo.md), got {len(fake_llm.calls)}: "
        f"{[c.file_path for c in fake_llm.calls]}"
    )
    assert fake_llm.calls[0].file_path == "docs/architecture/foo.md"

    # 3. EVENT_AUTO_RESOLUTION_ATTEMPTED
    attempted = _latest_event(db_session, project_id, item_id, EVENT_AUTO_RESOLUTION_ATTEMPTED)
    assert attempted.event_metadata["allowlisted_files"] == ["docs/architecture/foo.md"], (
        f"Expected allowlisted_files=[docs/architecture/foo.md], "
        f"got {attempted.event_metadata.get('allowlisted_files')}"
    )
    assert attempted.event_metadata["deferred_files"] == ["Makefile", "pyproject.toml"], (
        f"Expected deferred_files=[Makefile, pyproject.toml], "
        f"got {attempted.event_metadata.get('deferred_files')}"
    )
    assert attempted.event_metadata["phase"] == PHASE_DRY_RUN, (
        f"Expected phase=1, got {attempted.event_metadata.get('phase')}"
    )
    assert attempted.event_metadata["policy_decision"] == "allowlist"

    # 4. EVENT_AUTO_RESOLVED
    resolved = _latest_event(db_session, project_id, item_id, EVENT_AUTO_RESOLVED)
    # Check proposed_files (primary key) or resolved_files (fallback)
    proposed: list[str] = resolved.event_metadata.get("proposed_files", [])
    if not proposed:
        proposed = resolved.event_metadata.get("resolved_files", [])

    assert "docs/architecture/foo.md" in proposed, (
        f"Expected docs/architecture/foo.md in proposed_files, got {proposed}"
    )
    # Non-allowlisted files must NOT be in the LLM output
    assert "Makefile" not in proposed, (
        f"Makefile must NOT be proposed (not allowlisted) — got {proposed}"
    )
    assert "pyproject.toml" not in proposed, (
        f"pyproject.toml must NOT be proposed (not allowlisted) — got {proposed}"
    )
    assert resolved.event_metadata["deferred_files"] == ["Makefile", "pyproject.toml"], (
        f"Expected deferred_files=[Makefile, pyproject.toml] in resolved event, "
        f"got {resolved.event_metadata.get('deferred_files')}"
    )
    assert resolved.event_metadata["phase"] == PHASE_DRY_RUN

    # 5. Phase-1 invariant: worktree untouched
    post_hash = _hash_worktree_tree(tmp_path)
    assert post_hash == pre_hash, (
        f"Phase 1 dry-run must not mutate the worktree. Pre-hash={pre_hash}, post-hash={post_hash}"
    )

    # NOTE: Work item status transitions (e.g. approved → failed) are the
    # responsibility of merge_queue.py after it processes attempt_resolution()'s
    # return value.  attempt_resolution() only emits DaemonEvents and returns
    # an AutoMergeResult; it does not write back to the WorkItem row.
