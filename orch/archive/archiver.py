"""Two-tier archive system: Tier 1 (DB content storage) + Tier 2 (zstd compression)."""

from __future__ import annotations

import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import zstandard as zstd
from sqlalchemy import select

from orch.db.models import (
    Project,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def archive_work_item(
    db: Session,
    project_id: str,
    item_id: str,
    archive_dir: Path | str | None,
    cleanup: bool = True,
) -> None:
    """Archive a single work item: Tier 1 (DB) + Tier 2 (.tar.zst).

    Idempotent: if already archived (archived_at is set), refreshes Tier 1 content
    but skips Tier 2 compression (archive already exists).

    Args:
        db: Active SQLAlchemy session (caller manages transaction/commit).
        project_id: Project identifier.
        item_id: Work item identifier.
        archive_dir: Directory to store .tar.zst archives. If None, Tier 2 is skipped.
        cleanup: If True, delete the source folder from the project repo after archiving.

    Raises:
        ValueError: If the work item or project is not found.
    """
    wi = db.get(WorkItem, (project_id, item_id))
    if wi is None:
        raise ValueError(f"Work item {item_id} not found in project {project_id}")

    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    repo_root = Path(project.repo_root)
    already_archived = wi.archived_at is not None

    # --- Tier 1: Store searchable content in DB ---

    if wi.design_doc_path:
        doc_path = repo_root / wi.design_doc_path
        if doc_path.exists():
            wi.design_doc_content = doc_path.read_text(encoding="utf-8")

    steps = (
        db.execute(
            select(WorkflowStep).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
        )
        .scalars()
        .all()
    )
    for step in steps:
        if step.report_file:
            report_path = repo_root / step.report_file
            if report_path.exists():
                step.report_content = report_path.read_text(encoding="utf-8")

    wi.phase = WorkItemPhase.done
    if not already_archived:
        wi.archived_at = datetime.now(UTC)
    db.flush()

    # --- Tier 2: Compress to archive ---

    # Skip if archive file already exists or no archive dir configured
    if archive_dir is None or wi.archive_path is not None:
        return

    # A work item occupies two on-disk trees, both compressed into the bundle
    # and removed from the repo on cleanup:
    #   <active>/         — design doc, prompts, manifest (parent of design_doc_path)
    #   ai-dev/work/<id>/ — step reports, logs, fix prompts, self-assessment output
    # The work tree is captured even when self_assess wrote uncommitted files
    # into it post-merge, so nothing is lost when the folder is removed.
    if wi.design_doc_path:
        active_dir = (repo_root / wi.design_doc_path).parent
        if not active_dir.exists():
            # design_doc_path may be stale; fall back to conventional location
            active_dir = repo_root / "ai-dev" / "active" / item_id
    else:
        active_dir = repo_root / "ai-dev" / "active" / item_id
    work_dir = repo_root / "ai-dev" / "work" / item_id

    members: list[tuple[Path, str]] = []
    if active_dir.exists():
        members.append((active_dir, item_id))
    if work_dir.exists():
        members.append((work_dir, f"{item_id}/work"))
    if not members:
        return

    archive_dir = Path(archive_dir)
    dest_dir = archive_dir / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dest_dir / f"{item_id}.tar.zst"

    _compress_to_zstd(members, archive_path)

    wi.archive_path = f"{project_id}/{item_id}.tar.zst"
    wi.archive_size_bytes = archive_path.stat().st_size
    db.flush()

    # --- Cleanup ---

    if cleanup:
        for src, _ in members:
            shutil.rmtree(src)


def archive_all_completed(
    db: Session,
    project_id: str,
    archive_dir: Path | str | None,
) -> list[str]:
    """Archive all completed, unarchived items for a project.

    Args:
        db: Active SQLAlchemy session (caller manages transaction/commit).
        project_id: Project identifier.
        archive_dir: Directory to store .tar.zst archives. If None, Tier 2 is skipped.

    Returns:
        List of archived item IDs.
    """
    items = (
        db.execute(
            select(WorkItem).where(
                WorkItem.project_id == project_id,
                WorkItem.status == WorkItemStatus.completed,
                WorkItem.archived_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    archived: list[str] = []
    for wi in items:
        archive_work_item(db, project_id, wi.id, archive_dir)
        archived.append(wi.id)
    return archived


def _compress_to_zstd(members: list[tuple[Path, str]], dest_path: Path) -> None:
    """Create a .tar.zst archive containing each (source_dir, arcname) member."""
    cctx = zstd.ZstdCompressor(level=3)
    with (
        dest_path.open("wb") as f_out,
        cctx.stream_writer(f_out) as compressor,
        tarfile.open(fileobj=compressor, mode="w|") as tar,
    ):
        for source_dir, arcname in members:
            tar.add(source_dir, arcname=arcname)
