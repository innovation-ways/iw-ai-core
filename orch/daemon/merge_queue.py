"""Merge queue — sequential squash-merges of completed batch items.

Called every poll cycle for each project. Merges one item at a time
(the oldest completed item) to keep git history linear and conflict-free.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orch.db.models import BatchItem, BatchItemStatus, DaemonEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig
    from orch.daemon.project_registry import ProjectConfig

logger = logging.getLogger(__name__)

# Executor scripts: iw-ai-core/executor/
_EXECUTOR_DIR = Path(__file__).resolve().parent.parent.parent / "executor"


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
        batch_item.status = BatchItemStatus.failed
        batch_item.notes = "No worktree path recorded — cannot merge"
        db.commit()
        logger.error("[%s] Cannot merge %s: no worktree path", project_id, item_id)
        return

    batch_item.status = BatchItemStatus.merging
    db.commit()
    _emit_event(db, project_id, "merge_started", item_id, f"Merging {item_id} from {worktree_path}")
    logger.info("[%s] Merging %s (worktree: %s)", project_id, item_id, worktree_path)

    try:
        cmd = [
            "bash",
            str(_EXECUTOR_DIR / "worktree_commit.sh"),
            item_id,
            project_config.working_dir,
        ]  # noqa: S607
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)  # noqa: S603
        if result.returncode != 0:
            raise MergeError(result.stderr.strip() or f"exit code {result.returncode}")

        batch_item.status = BatchItemStatus.merged
        batch_item.merged_at = datetime.now(UTC)
        batch_item.merge_info = {"stdout": result.stdout[:1000]}
        db.commit()
        _emit_event(db, project_id, "item_merged", item_id, f"Merged {item_id} successfully")
        logger.info("[%s] Merged %s", project_id, item_id)

        _cleanup_worktree(item_id, worktree_path, project_config.working_dir)

        project = db.get(Project, project_id)
        if project is not None:
            trigger_doc_regeneration_on_merge(db, batch_item, project)

    except (MergeError, subprocess.TimeoutExpired) as e:
        batch_item.status = BatchItemStatus.failed
        batch_item.notes = f"Merge failed: {e}"
        db.commit()
        _emit_event(db, project_id, "merge_conflict", item_id, str(e))
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
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent (caller commits)."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)
