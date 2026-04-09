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
    BatchItem,
    BatchItemStatus,
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

    if already_archived or archive_dir is None:
        return

    work_item_dir = repo_root / "ai-dev" / "design" / "active" / item_id
    if not work_item_dir.exists():
        return

    archive_dir = Path(archive_dir)
    dest_dir = archive_dir / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dest_dir / f"{item_id}.tar.zst"

    _compress_to_zstd(work_item_dir, archive_path, arcname=item_id)

    wi.archive_path = f"{project_id}/{item_id}.tar.zst"
    wi.archive_size_bytes = archive_path.stat().st_size
    db.flush()

    # --- Cleanup ---

    if cleanup:
        shutil.rmtree(work_item_dir)


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


def archive_batch(project_id: str, batch_id: str) -> list[str]:
    """Archive all merged items in a batch. Creates its own DB session (for use in threads).

    Args:
        project_id: Project identifier.
        batch_id: Batch identifier.

    Returns:
        List of archived item IDs.
    """
    from orch.db.session import get_session

    archived: list[str] = []
    with get_session() as db:
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
        project = db.get(Project, project_id)
        archive_dir = Path(project.repo_root) / "ai-dev" / "archives" if project else None
        for bi in batch_items:
            try:
                archive_work_item(db, project_id, bi.work_item_id, archive_dir)
                archived.append(bi.work_item_id)
            except Exception:
                pass
        db.commit()
    return archived


def _compress_to_zstd(source_dir: Path, dest_path: Path, arcname: str) -> None:
    """Create a .tar.zst archive from source_dir."""
    cctx = zstd.ZstdCompressor(level=3)
    with (
        dest_path.open("wb") as f_out,
        cctx.stream_writer(f_out) as compressor,
        tarfile.open(fileobj=compressor, mode="w|") as tar,
    ):
        tar.add(source_dir, arcname=arcname)
