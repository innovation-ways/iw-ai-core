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
from orch.config import CORE_ROOT, load_config
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    WorkItem,
)

logger = logging.getLogger(__name__)


def archive_batch(project_id: str, batch_id: str, *, run_post_commands: bool = True) -> list[str]:
    """Orchestrate full batch archival. Creates its own DB session (for use in threads).

    Steps:
      1. Run post_archive_commands from project.config (failures are logged, not fatal)
         — skipped when run_post_commands=False
      2. Archive all merged BatchItems via archive_work_item()
      3. Transition batch.status → archived, set batch.archived_at
      4. Emit batch_archived or batch_archive_failed DaemonEvent

    Args:
        project_id: Project identifier.
        batch_id: Batch identifier.
        run_post_commands: When False, skip post_archive_commands entirely.

    Returns:
        List of successfully archived work item IDs.
    """
    from orch.db.session import get_session  # noqa: PLC0415

    try:
        return _run_archive(project_id, batch_id, run_post_commands=run_post_commands)
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


def _run_archive(project_id: str, batch_id: str, *, run_post_commands: bool = True) -> list[str]:
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
        config = load_config()
        raw_archive_dir = Path(config.archive_dir)
        archive_dir = (
            raw_archive_dir if raw_archive_dir.is_absolute() else CORE_ROOT / raw_archive_dir
        )
        post_archive_commands: list[str] = (project.config or {}).get("post_archive_commands", [])

        # --- Step 1: Run post-archive commands (skipped if run_post_commands=False) ---
        command_errors: list[str] = []
        if run_post_commands:
            for cmd in post_archive_commands:
                error = _run_command(cmd, cwd=repo_root, project_id=project_id)
                if error:
                    command_errors.append(error)
        else:
            logger.info("[%s] Skipping post-archive commands for batch %s", project_id, batch_id)

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
        # Paths to stage in git: deleted item folders + new .tar.zst bundles.
        # We collect them explicitly per item rather than relying on `git add -A`,
        # which would drag any unrelated dirty state in the worktree into the
        # archive commit and trip pre-commit hooks on files the archive never
        # touched (the 2026-05-02 BATCH-00070/71/72 incident).
        paths_to_stage: list[Path] = []
        for bi in batch_items:
            try:
                archive_work_item(db, project_id, bi.work_item_id, archive_dir)
                archived.append(bi.work_item_id)
                paths_to_stage.extend(
                    _archive_paths_for_item(db, project_id, bi.work_item_id, archive_dir)
                )
            except Exception as exc:
                item_errors.append(f"{bi.work_item_id}: {exc}")
                logger.exception(
                    "[%s] Failed to archive work item %s in batch %s",
                    project_id,
                    bi.work_item_id,
                    batch_id,
                )

        # --- Step 2.5: Commit deleted work item folders to git ---
        if archived:
            commit_error = _git_commit_archive(
                repo_root, batch_id, archived, paths_to_stage, project_id
            )
            if commit_error:
                item_errors.append(commit_error)

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


def _archive_paths_for_item(
    db: Any, project_id: str, item_id: str, archive_dir: Path
) -> list[Path]:
    """Return the absolute paths the archive operation touched for one item.

    Includes the deleted active folder (so its deletion can be staged) and the
    newly created .tar.zst bundle. Caller is responsible for filtering out
    paths that fall outside the project's repo_root.
    """
    wi = db.get(WorkItem, (project_id, item_id))
    if wi is None:
        return []

    project = db.get(Project, project_id)
    repo_root = Path(project.repo_root) if project else None
    paths: list[Path] = []

    # The work item folder (now deleted from disk by archive_work_item, but git
    # still tracks it — we need to stage the deletion).
    if wi.design_doc_path and repo_root is not None:
        paths.append((repo_root / wi.design_doc_path).parent)
    elif repo_root is not None:
        paths.append(repo_root / "ai-dev" / "active" / item_id)

    # The newly created archive bundle. wi.archive_path is set by
    # archive_work_item to "<project_id>/<item_id>.tar.zst" (relative to
    # archive_dir). Skip if Tier 2 was disabled (archive_path is None).
    if wi.archive_path:
        paths.append(archive_dir / wi.archive_path)

    return paths


def _git_commit_archive(
    repo_root: Path,
    batch_id: str,
    archived_items: list[str],
    paths_to_stage: list[Path],
    project_id: str,
) -> str | None:
    """Stage explicit archive paths and commit to git. Returns error string or None.

    Restricts staging to paths under repo_root — archive bundles in a central
    archive_dir outside the project repo are skipped (they live in the
    iw-ai-core repo, not the project being archived).
    """
    items_str = ", ".join(archived_items)
    commit_msg = f"Archive {batch_id}: remove {items_str}"
    logger.info("[%s] Committing archive deletions for batch %s", project_id, batch_id)

    repo_root_resolved = repo_root.resolve()
    rel_paths: list[str] = []
    for p in paths_to_stage:
        try:
            rel = p.resolve().relative_to(repo_root_resolved)
        except ValueError:
            # Path is outside repo_root (e.g. central archive_dir). Skip.
            continue
        rel_paths.append(str(rel))

    if not rel_paths:
        logger.info(
            "[%s] No archive paths under repo_root for batch %s — nothing to commit",
            project_id,
            batch_id,
        )
        return None

    try:
        add_result = subprocess.run(  # noqa: S603
            ["git", "add", "--", *rel_paths],  # noqa: S607
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if add_result.returncode != 0:
            output = (add_result.stderr or add_result.stdout).strip()
            error = f"git add failed: {output}"
            logger.error("[%s] %s", project_id, error)
            return error

        commit_result = subprocess.run(  # noqa: S603
            ["git", "commit", "-m", commit_msg],  # noqa: S607
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if commit_result.returncode != 0:
            output = (commit_result.stderr or commit_result.stdout).strip()
            # "nothing to commit" is not an error
            if "nothing to commit" in output:
                logger.info("[%s] Nothing to commit for batch %s archive", project_id, batch_id)
                return None
            error = f"git commit failed: {output}"
            logger.error("[%s] %s", project_id, error)
            return error

        logger.info(
            "[%s] Committed archive deletions for batch %s: %s",
            project_id,
            batch_id,
            items_str,
        )
        return None
    except subprocess.TimeoutExpired:
        error = "git commit timed out after 60s"
        logger.error("[%s] %s", project_id, error)
        return error
    except Exception as exc:
        error = f"git commit raised {exc}"
        logger.exception("[%s] %s", project_id, error)
        return error


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
