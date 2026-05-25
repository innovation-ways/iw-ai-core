"""Scope amendment helpers for I-00101.

When a fix-cycle agent edits a file outside ``scope.allowed_paths``, the daemon
marks the cycle ``escalated`` and the step ``needs_fix``. The operator can then
either AMEND the manifest (add the offending paths to ``allowed_paths``) or
REVERT the agent's edits and re-queue the step.

These helpers are pure I/O against the worktree + parent manifest files and a
read-only DB query. The dashboard endpoint in ``actions.py`` composes them
with the side-effect-bearing DB writes (event emit + StepRun row + step-status
flip).
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from orch.db.models import FixCycle, FixStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AmendResult:
    """Result of an amend operation."""

    paths_added: list[str]  # what we actually appended (deduped against existing)
    manifests_updated: list[Path]  # which files we wrote (worktree always; parent if found)


@dataclass(frozen=True)
class RevertResult:
    """Result of a revert operation."""

    reverted: list[str]  # paths git successfully checked out
    failed: list[str]  # paths where `git checkout` failed (report under each path's stderr)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def amend_allowed_paths(
    worktree_path: Path,
    item_id: str,
    paths_to_add: list[str],
) -> AmendResult:
    """Append ``paths_to_add`` to ``scope.allowed_paths`` in BOTH manifests.

    Targets:
      - ``<worktree_path>/ai-dev/active/<item_id>/workflow-manifest.json`` (always)
      - ``<parent_repo>/ai-dev/active/<item_id>/workflow-manifest.json`` (when found)

    The parent repo path is computed by reading the worktree's ``.git`` file
    (it's a pointer-file for git worktrees: ``gitdir: /path/to/parent/.git/worktrees/<name>``)
    and walking up to the parent repo root. If the parent manifest cannot be
    located, write only the worktree copy and include a note in the result's
    ``manifests_updated`` list (worktree only).

    De-duplicate against existing entries before appending. Pretty-print with
    2-space indentation to match the existing file style. Preserve the
    ``_note`` field and all other top-level keys verbatim.
    """
    paths_added: list[str] = []
    manifests_updated: list[Path] = []

    # Worktree manifest (canonical)
    worktree_manifest = worktree_path / "ai-dev" / "active" / item_id / "workflow-manifest.json"
    if worktree_manifest.exists():
        manifest_data = json.loads(worktree_manifest.read_text())
        existing = list((manifest_data.get("scope") or {}).get("allowed_paths") or [])
        for path in paths_to_add:
            if path not in existing:
                existing.append(path)
                paths_added.append(path)
        scope = manifest_data.get("scope") or {}
        scope["allowed_paths"] = existing
        manifest_data["scope"] = scope
        worktree_manifest.write_text(json.dumps(manifest_data, indent=2, sort_keys=False) + "\n")
        manifests_updated.append(worktree_manifest)
        logger.info(
            "amend_allowed_paths: added %d path(s) to worktree manifest %s",
            len(paths_added),
            worktree_manifest,
        )
    else:
        logger.warning(
            "amend_allowed_paths: worktree manifest not found at %s",
            worktree_manifest,
        )

    # Parent manifest (design-time copy) — find parent repo root from .git pointer
    parent_manifest_path = _resolve_parent_manifest(worktree_path, item_id)
    if parent_manifest_path is not None:
        if parent_manifest_path.exists():
            parent_data = json.loads(parent_manifest_path.read_text())
            existing_parent = list((parent_data.get("scope") or {}).get("allowed_paths") or [])
            for path in paths_to_add:
                if path not in existing_parent:
                    existing_parent.append(path)
            scope_parent = parent_data.get("scope") or {}
            scope_parent["allowed_paths"] = existing_parent
            parent_data["scope"] = scope_parent
            parent_manifest_path.write_text(
                json.dumps(parent_data, indent=2, sort_keys=False) + "\n"
            )
            manifests_updated.append(parent_manifest_path)
            logger.info(
                "amend_allowed_paths: added %d path(s) to parent manifest %s",
                len(paths_added),
                parent_manifest_path,
            )
        else:
            logger.warning(
                "amend_allowed_paths: parent manifest not found at %s",
                parent_manifest_path,
            )
    else:
        logger.info(
            "amend_allowed_paths: could not resolve parent repo for worktree %s "
            "— skipping parent manifest update",
            worktree_path,
        )

    return AmendResult(paths_added=paths_added, manifests_updated=manifests_updated)


def revert_paths_in_worktree(
    worktree_path: Path,
    paths_to_revert: list[str],
) -> RevertResult:
    """Run ``git -C <worktree_path> checkout -- <path>`` for each path.

    Use ``subprocess.run`` with ``cwd`` NOT set (rely on ``-C``); never spawn a
    shell. Capture stderr per-path. Return both the successful and failed
    paths so the caller can emit a partial-success event.
    """
    reverted: list[str] = []
    failed: list[str] = []

    for path in paths_to_revert:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(worktree_path), "checkout", "--", path],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,  # caller decides what to do on failure
        )
        if result.returncode == 0:
            reverted.append(path)
        else:
            failed.append(path)
            logger.warning(
                "revert_paths_in_worktree: git checkout failed for %s in %s: %s",
                path,
                worktree_path,
                result.stderr.strip(),
            )

    return RevertResult(reverted=reverted, failed=failed)


def latest_scope_violation(db: Session, step_id: int) -> list[str] | None:
    """Return ``scope_violations`` from the LATEST FixCycle on the step, or None.

    ``LATEST`` means ``ORDER BY cycle_number DESC LIMIT 1``. Returns None when:
      - the step has no fix cycles, OR
      - the latest cycle is not status=escalated, OR
      - the latest cycle has no ``scope_violations`` key in ``fix_metadata``, OR
      - ``scope_violations`` is an empty list.
    """
    cycle = (
        db.query(FixCycle)
        .filter(FixCycle.step_id == step_id)
        .order_by(FixCycle.cycle_number.desc())
        .first()
    )
    if cycle is None:
        return None
    if cycle.status != FixStatus.escalated:
        return None
    meta = cycle.fix_metadata or {}
    violations = meta.get("scope_violations")
    if not isinstance(violations, list) or len(violations) == 0:
        return None
    return violations


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def should_auto_amend(
    violations: list[str],
    allow_patterns: list[str],
    max_paths: int | None,
) -> bool:
    """Return True when an auto-amend should fire for these violations.

    Returns True only when ALL of:
      1. allow_patterns is non-empty (feature off when empty);
      2. violations is non-empty (nothing to amend means nothing to do);
      3. max_paths is None OR len(violations) <= max_paths;
      4. EVERY violation in ``violations`` matches at least one pattern in
         ``allow_patterns`` via ``scope_match`` from ``orch.daemon.fix_cycle``
         — the SAME matcher the violation detector itself uses, so the two
         layers cannot disagree on pattern semantics.

    Gracefully returns False for non-list inputs without raising.
    """
    # Pure-helper hygiene: reject bad input shapes
    if not isinstance(violations, list) or not isinstance(allow_patterns, list):
        return False

    if not allow_patterns:
        return False
    if not violations:
        return False
    if max_paths is not None and len(violations) > max_paths:
        return False

    # Import here to avoid any module-level import cycle (deferred import).
    # scope_amendment does not import from fix_cycle at module load time;
    # fix_cycle only imports scope_amendment inside _complete_fix_cycle
    # (at function-call time, not module-load time), so this deferred
    # import is safe and creates no cycle.
    from orch.daemon.fix_cycle import scope_match  # noqa: PLC0415

    return all(
        any(scope_match(violation, pattern) for pattern in allow_patterns)
        for violation in violations
    )


def _resolve_parent_manifest(worktree_path: Path, item_id: str) -> Path | None:
    """Resolve the parent repo's manifest path from the worktree's .git pointer.

    Returns None if the .git file is absent or the parent manifest can't be found.
    """
    git_file = worktree_path / ".git"
    if not git_file.exists():
        return None

    # .git in a worktree is a pointer file: "gitdir: /path/to/parent/.git/worktrees/<name>"
    try:
        content = git_file.read_text().strip()
    except OSError:
        return None

    if not content.startswith("gitdir:"):
        # Not a worktree pointer — might be a real .git directory (not common in our setup)
        return None

    # Extract the parent .git directory from the pointer
    gitdir_path = content[len("gitdir:") :].strip()
    # gitdir is /path/to/parent/.git/worktrees/<name>; parent repo root is /path/to/parent/
    parent_git_dir = Path(gitdir_path)
    if not parent_git_dir.exists():
        return None
    # worktrees/<name> → .git → worktrees → parent_repo_root  (3 traversals)
    parent_repo_root = parent_git_dir.parent.parent.parent
    parent_manifest = parent_repo_root / "ai-dev" / "active" / item_id / "workflow-manifest.json"
    return parent_manifest if parent_manifest.exists() else None
