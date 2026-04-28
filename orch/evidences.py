"""Evidence ingestion pipeline for work item evidence files.

Ingests files from ai-dev/active/<id>/evidences/{pre,post}/ into the
work_item_evidences table via upsert (ON CONFLICT DO UPDATE).
"""

from __future__ import annotations

import mimetypes
import os
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import Insert

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import EvidencePhase, WorkItemEvidence

mimetypes.add_type("application/yaml", ".yaml")
mimetypes.add_type("application/yaml", ".yml")


def _is_real_file(entry: os.DirEntry[Any]) -> bool:
    try:
        return entry.is_file(follow_symlinks=False)
    except TypeError:
        return stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode)


class EvidenceTooLargeError(Exception):
    """Raised when an evidence file exceeds the configured size limit."""

    def __init__(self, filename: str, size: int, max_bytes: int) -> None:
        super().__init__(
            f"Evidence file '{filename}' is {size} bytes, exceeds max {max_bytes} bytes "
            f"(configure via IW_CORE_EVIDENCE_MAX_BYTES)"
        )
        self.filename = filename
        self.size = size
        self.max_bytes = max_bytes


def _default_max_bytes() -> int:
    """Read IW_CORE_EVIDENCE_MAX_BYTES from config; default 5 MiB."""
    raw = os.environ.get("IW_CORE_EVIDENCE_MAX_BYTES", "")
    if not raw:
        return 5 * 1024 * 1024
    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            "IW_CORE_EVIDENCE_MAX_BYTES must be an integer; check your .env file"
        ) from None


def ingest_phase_from_disk(
    session: Session,
    project_id: str,
    work_item_id: str,
    phase: EvidencePhase,
    root: Path,
    step_id: str | None = None,
    max_bytes: int | None = None,
) -> int:
    """Ingest all regular files from the evidence phase directory into the DB.

    Upserts by (project_id, work_item_id, phase, filename). Does not commit;
    the caller's session owns the transaction boundary.

    Returns the number of rows upserted (inserts + updates).

    Raises EvidenceTooLargeError if any file exceeds max_bytes.
    """
    if max_bytes is None:
        max_bytes = _default_max_bytes()

    phase_dir = root / "ai-dev" / "active" / work_item_id / "evidences" / phase.value
    if not phase_dir.is_dir():
        return 0

    count = 0
    with os.scandir(phase_dir) as entries:
        for entry in entries:
            if not _is_real_file(entry):
                continue

            with Path(entry.path).open("rb") as f:
                content = f.read()
            size = len(content)
            if size > max_bytes:
                raise EvidenceTooLargeError(entry.name, size, max_bytes)

            content_type = mimetypes.guess_type(entry.name)[0] or "application/octet-stream"

            stmt = Insert(WorkItemEvidence).values(
                project_id=project_id,
                work_item_id=work_item_id,
                phase=phase,
                filename=entry.name,
                content=content,
                size_bytes=size,
                content_type=content_type,
                captured_at=func.now(),
                step_id=step_id,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=(
                    "project_id",
                    "work_item_id",
                    "phase",
                    "filename",
                ),
                set_={
                    "content": stmt.excluded.content,
                    "size_bytes": stmt.excluded.size_bytes,
                    "content_type": stmt.excluded.content_type,
                    "captured_at": stmt.excluded.captured_at,
                    "step_id": stmt.excluded.step_id,
                },
            )
            session.execute(stmt)
            count += 1

    return count
