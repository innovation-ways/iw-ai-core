"""Merge queue — sequential squash-merges of completed batch items.

Called every poll cycle for each project. Merges one item at a time
(the oldest completed item) to keep git history linear and conflict-free.

Migration pipeline integration (CR-00017):
- Before any merge cycle: check is_merge_queue_frozen() — if frozen, skip entirely.
- Before squash-merge: run_pre_merge_dry_run() (Phase 1) — on fail, mark MIGRATION_INVALID.
- After squash-merge: run_post_merge_apply() (Phase 2) — on fail, run_rollback() (Phase 3).
"""

from __future__ import annotations

import json as _json
import logging
import os
import re
import subprocess
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orch.daemon import worktree_compose
from orch.daemon.migration_pipeline import (
    is_merge_queue_frozen,
    run_post_merge_apply,
    run_pre_merge_dry_run,
    run_rollback,
)
from orch.daemon.migration_rebase import run_pre_merge_rebase
from orch.db.models import BatchItem, BatchItemStatus, DaemonEvent, WorkItem, WorkItemStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig
    from orch.daemon.project_registry import ProjectConfig

logger = logging.getLogger(__name__)

# Executor scripts: iw-ai-core/executor/
_EXECUTOR_DIR = Path(__file__).resolve().parent.parent.parent / "executor"

# Maximum bytes kept in merge_info["stdout"] for audit log
_MERGE_INFO_STDOUT_LIMIT = 8000

# F-00076: capture conflict file list emitted by worktree_commit.sh after
# auto-resolving rebase conflicts.
_CONFLICT_MARKER_RE = re.compile(
    r"^\[worktree_commit\] CONFLICT_FILES (\[.*\])$",
    re.MULTILINE,
)


class MergeError(RuntimeError):
    """Raised when worktree_commit.sh exits non-zero."""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def process_merge_queue(
    db: Session,
    project_id: str,
    project_config: ProjectConfig,
    config: DaemonConfig,  # noqa: ARG001  (reserved for future throttling)
) -> None:
    """Merge the oldest completed batch item, if no merge is already in progress."""
    if is_merge_queue_frozen(db):
        logger.debug("[%s] Merge queue is frozen — skipping this cycle", project_id)
        _emit_event(
            db,
            project_id,
            "merge_queue_frozen_skipped",
            None,
            None,
            "Merge queue is frozen — no merges processed",
        )
        db.commit()
        return

    # One merge at a time: bail if another is already running
    merging = (
        db.query(BatchItem)
        .filter(
            BatchItem.project_id == project_id,
            BatchItem.status == BatchItemStatus.merging,
        )
        .first()
    )
    if merging:
        logger.debug(
            "[%s] Merge already in progress (batch_item %d) — waiting", project_id, merging.id
        )
        return

    # Find oldest completed item (ordered by started_at so first-in first-out)
    ready = (
        db.query(BatchItem)
        .filter(
            BatchItem.project_id == project_id,
            BatchItem.status == BatchItemStatus.completed,
        )
        .order_by(BatchItem.started_at)
        .first()
    )
    if ready is None:
        return

    _merge_item(db, ready, project_id, project_config)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _revert_work_item(db: Session, project_id: str, item_id: str) -> None:
    """Revert WorkItem.status to failed and clear completed_at after a merge failure.

    Only touches the WorkItem if its current status is completed — guards against
    double-application and preserves any status already set by other code paths.
    """
    work_item = db.query(WorkItem).filter_by(project_id=project_id, id=item_id).one_or_none()
    if work_item is not None and work_item.status == WorkItemStatus.completed:
        work_item.status = WorkItemStatus.failed
        work_item.completed_at = None


def _merge_item(
    db: Session,
    batch_item: BatchItem,
    project_id: str,
    project_config: ProjectConfig,
) -> None:
    """Squash-merge a completed item's branch to main via worktree_commit.sh."""
    from orch.daemon.batch_merge_hooks import trigger_doc_regeneration_on_merge
    from orch.db.models import Project

    item_id = batch_item.work_item_id
    worktree_path = (batch_item.worktree_info or {}).get("path")

    if not worktree_path:
        # CR-00028: intentionally produce `failed` here (not `merge_failed`).
        # This branch indicates a data-integrity issue — no worktree was ever
        # recorded for this batch item. Keeping it as `failed` ensures the
        # cascade fires so the batch is correctly marked with a hard failure.
        batch_item.status = BatchItemStatus.failed
        batch_item.notes = "No worktree path recorded — cannot merge"
        db.commit()
        logger.error("[%s] Cannot merge %s: no worktree path", project_id, item_id)
        return

    batch_item.status = BatchItemStatus.merging
    db.commit()
    _emit_event(
        db,
        project_id,
        "merge_started",
        item_id,
        "work_item",
        f"Merging {item_id} from {worktree_path}",
    )
    logger.info("[%s] Merging %s (worktree: %s)", project_id, item_id, worktree_path)

    if batch_item.batch_id is not None:
        rebase_result = run_pre_merge_rebase(
            batch_item.batch_id, worktree_path, project_config.working_dir
        )
        if not rebase_result.success:
            batch_item.status = BatchItemStatus.migration_rebase_failed
            batch_item.notes = f"Pre-merge rebase failed: {rebase_result.error_message}"
            # C4: revert WorkItem so it is not orphaned as completed
            _revert_work_item(db, project_id, item_id)
            db.commit()
            compose_path = (
                Path(batch_item.worktree_compose_path) if batch_item.worktree_compose_path else None
            )
            worktree_compose.down(str(batch_item.id), compose_path)
            _emit_event(
                db,
                project_id,
                "migration_pipeline",
                item_id,
                "work_item",
                f"Pre-merge rebase failed: {rebase_result.error_message}",
                {
                    "phase": "rebase",
                    "success": False,
                    "batch_id": batch_item.batch_id,
                    "worktree_base_sha": rebase_result.worktree_base_sha,
                    "current_main_sha": rebase_result.current_main_sha,
                },
            )
            logger.warning(
                "[%s] Pre-merge rebase failed for %s (batch %s): %s",
                project_id,
                item_id,
                batch_item.batch_id,
                rebase_result.error_message,
            )
            return

    # Phase 1: dry-run migration against testcontainer
    if batch_item.batch_id is not None:
        dry_result = run_pre_merge_dry_run(batch_item.batch_id, worktree_path=worktree_path)
        if not dry_result.success:
            batch_item.status = BatchItemStatus.migration_invalid
            batch_item.notes = f"Phase 1 dry-run failed: {dry_result.message}"
            # C4: revert WorkItem so it is not orphaned as completed
            _revert_work_item(db, project_id, item_id)
            db.commit()
            compose_path = (
                Path(batch_item.worktree_compose_path) if batch_item.worktree_compose_path else None
            )
            worktree_compose.down(str(batch_item.id), compose_path)
            _emit_event(
                db,
                project_id,
                "migration_pipeline",
                item_id,
                "work_item",
                f"Phase 1 dry-run failed: {dry_result.message}",
                {"phase": "dry_run", "success": False, "batch_id": batch_item.batch_id},
            )
            logger.warning(
                "[%s] Phase 1 dry-run failed for %s — batch item %s marked MIGRATION_INVALID",
                project_id,
                item_id,
                batch_item.batch_id,
            )
            return

    result: subprocess.CompletedProcess[str] | None = None
    conflict_files: list[str] = []  # defined before try so except block can reference
    try:
        cmd = [
            "bash",
            str(_EXECUTOR_DIR / "worktree_commit.sh"),
            item_id,
            project_config.working_dir,
        ]  # noqa: S607
        # Pass scope-gate toggle via env. Default off — projects opt in via
        # .iw-orch.json {"scope_gate_enabled": true}. See ProjectConfig.
        merge_env = {
            **os.environ,
            "IW_SCOPE_GATE_ENABLED": "true" if project_config.scope_gate_enabled else "false",
        }
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, timeout=120, env=merge_env
        )
        if result.returncode != 0:
            raise MergeError(result.stderr.strip() or f"exit code {result.returncode}")

        batch_item.status = BatchItemStatus.merged
        batch_item.merged_at = datetime.now(UTC)
        # M2: keep up to 8000 chars; flag when output was truncated
        stdout = result.stdout
        # F-00076: parse CONFLICT_FILES marker from worktree_commit.sh output
        m = _CONFLICT_MARKER_RE.search(stdout)
        if m:
            with suppress(_json.JSONDecodeError):
                conflict_files = _json.loads(m.group(1))
        batch_item.merge_info = {
            "stdout": stdout[:_MERGE_INFO_STDOUT_LIMIT],
            "stdout_truncated": len(stdout) > _MERGE_INFO_STDOUT_LIMIT,
            "conflict_files": conflict_files,
        }
        db.commit()
        _emit_event(
            db, project_id, "item_merged", item_id, "work_item", f"Merged {item_id} successfully"
        )
        logger.info("[%s] Merged %s", project_id, item_id)

        worktree_compose.down(
            str(batch_item.id),
            Path(batch_item.worktree_compose_path) if batch_item.worktree_compose_path else None,
        )
        _cleanup_worktree(item_id, worktree_path, project_config.working_dir)

        project = db.get(Project, project_id)
        if project is not None:
            trigger_doc_regeneration_on_merge(db, batch_item, project)

        # I-00063: Commit the orchestration session before Phase 2 to release
        # AccessShareLocks acquired by the reads above. Phase 2's ALTER TABLE
        # requires AccessExclusiveLock and would self-deadlock against our own
        # idle-in-transaction session.
        #
        # We commit but do NOT close: the caller (process_merge_queue → batch
        # manager) owns the session lifecycle via its own context manager, and
        # downstream tests pass in a long-lived fixture session that they
        # continue to use after _merge_item returns.
        #
        # We also capture batch_item.batch_id into a local primitive BEFORE
        # the commit. After commit the ORM object's attributes are expired
        # (default expire_on_commit=True), so accessing batch_item.batch_id
        # would trigger a refresh — opening a new transaction and re-acquiring
        # the share lock we just released. The whole point of the commit is
        # to NOT hold any locks during run_post_merge_apply().
        batch_id_for_apply = batch_item.batch_id
        db.commit()

        # Phase 2: apply migrations to live DB
        if batch_id_for_apply is not None:
            apply_result = run_post_merge_apply(batch_id_for_apply)
            if not apply_result.success:
                logger.warning(
                    "[%s] Phase 2 apply failed for batch %s — running rollback",
                    project_id,
                    batch_id_for_apply,
                )
                rollback_result = run_rollback(batch_id_for_apply)
                _emit_event(
                    db,
                    project_id,
                    "migration_pipeline",
                    item_id,
                    "work_item",
                    f"Phase 2 apply failed, rollback result: {rollback_result.message}",
                    {
                        "phase": "rollback",
                        "success": rollback_result.success,
                        "batch_id": batch_id_for_apply,
                        "frozen": rollback_result.frozen,
                    },
                )
                db.commit()
                if rollback_result.frozen:
                    logger.error(
                        "[%s] Merge queue FROZEN after rollback failure for batch %s",
                        project_id,
                        batch_id_for_apply,
                    )

    except (MergeError, subprocess.TimeoutExpired) as e:
        # CR-00028: use merge_failed so the cascade is NOT triggered.
        # Dependents in later execution groups stay pending — the operator
        # can retry via restart-merge or abandon via abandon-merge.
        batch_item.status = BatchItemStatus.merge_failed
        batch_item.notes = f"Merge failed: {e}"
        # C4: revert WorkItem so it is not orphaned as completed
        _revert_work_item(db, project_id, item_id)
        # F-00076: parse CONFLICT_FILES marker even on failure (it may have
        # been emitted before the failure, e.g. from a partial --continue).
        if result is not None:
            output = result.stdout + result.stderr
            m = _CONFLICT_MARKER_RE.search(output)
            if m:
                with suppress(_json.JSONDecodeError):
                    conflict_files = _json.loads(m.group(1))
        batch_item.merge_info = {
            "conflict_files": conflict_files,
        }
        db.commit()
        worktree_compose.down(
            str(batch_item.id),
            Path(batch_item.worktree_compose_path) if batch_item.worktree_compose_path else None,
        )
        _emit_event(db, project_id, "merge_conflict", item_id, "work_item", str(e))
        logger.error("[%s] Merge failed for %s: %s", project_id, item_id, e)


def _cleanup_worktree(item_id: str, worktree_path: str, repo_root: str) -> None:
    """Remove the git worktree and prune the reference."""
    try:
        subprocess.run(  # noqa: S603, S607
            ["git", "worktree", "remove", "--force", worktree_path],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            timeout=30,
        )
        logger.info("Cleaned up worktree %s for %s", worktree_path, item_id)
    except Exception:
        logger.warning("Failed to clean up worktree %s for %s", worktree_path, item_id)


def _emit_event(
    db: Session,
    project_id: str,
    event_type: str,
    entity_id: str | None,
    entity_type: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent (caller commits)."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        entity_type=entity_type,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)
