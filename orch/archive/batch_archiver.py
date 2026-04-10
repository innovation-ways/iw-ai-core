"""Batch-level archive orchestrator.

Responsibilities:
  1. Run per-project post_archive_commands (alembic, docker, etc.)
  2. Archive all merged work items in the batch (via archive_work_item)
  3. Transition batch.status → archived
  4. Emit batch_archived (success) or batch_archive_failed (fatal error) SSE event
"""

from __future__ import annotations

import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from orch.archive.archiver import archive_work_item
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
)

logger = logging.getLogger(__name__)


def archive_batch(project_id: str, batch_id: str) -> list[str]:
    """Orchestrate full batch archival. Creates its own DB session (for use in threads).

    Steps:
      1. Run post_archive_commands from project.config (failures are logged, not fatal)
      2. Archive all merged BatchItems via archive_work_item()
      3. Transition batch.status → archived, set batch.archived_at
      4. Emit batch_archived or batch_archive_failed DaemonEvent

    Args:
        project_id: Project identifier.
        batch_id: Batch identifier.

    Returns:
        List of successfully archived work item IDs.
    """
    from orch.db.session import get_session  # noqa: PLC0415

    try:
        return _run_archive(project_id, batch_id)
    except Exception:
        logger.exception(
            "[%s] Fatal error archiving batch %s — emitting batch_archive_failed",
            project_id,
            batch_id,
        )
        # Best-effort: emit failure event even if main session is broken
        try:
            with get_session() as db:
                _emit(
                    db, "batch_archive_failed", project_id, batch_id, "Archive failed (fatal error)"
                )
                db.commit()
        except Exception:
            logger.exception("[%s] Failed to emit batch_archive_failed event", project_id)
        return []


def _run_archive(project_id: str, batch_id: str) -> list[str]:
    """Inner implementation — raises on fatal errors (caller handles)."""
    from orch.db.session import get_session  # noqa: PLC0415

    with get_session() as db:
        batch = db.get(Batch, (project_id, batch_id))
        if batch is None:
            raise ValueError(f"Batch {batch_id} not found in project {project_id}")

        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        repo_root = Path(project.repo_root)
        archive_dir = repo_root / "ai-dev" / "archives"
        post_archive_commands: list[str] = (project.config or {}).get("post_archive_commands", [])

        # --- Step 1: Run post-archive commands ---
        command_errors: list[str] = []
        for cmd in post_archive_commands:
            error = _run_command(cmd, cwd=repo_root, project_id=project_id)
            if error:
                command_errors.append(error)

        # --- Step 2: Archive merged work items ---
        batch_items = (
            db.execute(
                select(BatchItem).where(
                    BatchItem.project_id == project_id,
                    BatchItem.batch_id == batch_id,
                    BatchItem.status == BatchItemStatus.merged,
                )
            )
            .scalars()
            .all()
        )

        archived: list[str] = []
        item_errors: list[str] = []
        for bi in batch_items:
            try:
                archive_work_item(db, project_id, bi.work_item_id, archive_dir)
                archived.append(bi.work_item_id)
            except Exception as exc:
                item_errors.append(f"{bi.work_item_id}: {exc}")
                logger.exception(
                    "[%s] Failed to archive work item %s in batch %s",
                    project_id,
                    bi.work_item_id,
                    batch_id,
                )

        # --- Step 3: Transition batch to archived ---
        now = datetime.now(UTC)
        batch.status = BatchStatus.archived
        batch.archived_at = now

        # --- Step 4: Emit completion event ---
        all_errors = command_errors + item_errors
        if all_errors:
            error_summary = "; ".join(all_errors)
            _emit(
                db,
                "batch_archive_failed",
                project_id,
                batch_id,
                f"Batch {batch_id} archived with errors: {error_summary}",
                {"archived_items": archived, "errors": all_errors},
            )
            logger.warning(
                "[%s] Batch %s archived with %d error(s): %s",
                project_id,
                batch_id,
                len(all_errors),
                error_summary,
            )
        else:
            _emit(
                db,
                "batch_archived",
                project_id,
                batch_id,
                f"Batch {batch_id} archived successfully ({len(archived)} item(s))",
                {"archived_items": archived},
            )
            logger.info(
                "[%s] Batch %s archived successfully (%d item(s))",
                project_id,
                batch_id,
                len(archived),
            )

        db.commit()

    return archived


def _run_command(cmd: str, cwd: Path, project_id: str) -> str | None:
    """Run a shell command. Returns an error string on failure, None on success."""
    logger.info("[%s] Running post-archive command: %s", project_id, cmd)
    try:
        result = subprocess.run(  # noqa: S602
            cmd,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            output = (result.stderr or result.stdout).strip()[:500]
            error = f"'{cmd}' exited {result.returncode}: {output}"
            logger.error("[%s] Post-archive command failed: %s", project_id, error)
            return error
        logger.info("[%s] Post-archive command succeeded: %s", project_id, cmd)
        return None
    except subprocess.TimeoutExpired:
        error = f"'{cmd}' timed out after 300s"
        logger.error("[%s] Post-archive command timed out: %s", project_id, cmd)
        return error
    except Exception as exc:
        error = f"'{cmd}' raised {exc}"
        logger.exception("[%s] Post-archive command raised exception: %s", project_id, cmd)
        return error


def _emit(
    db: Any,
    event_type: str,
    project_id: str,
    batch_id: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent (caller commits)."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=batch_id,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)
