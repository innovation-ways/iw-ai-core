"""Fixture: failed DocGenerationJob for iw-ai-core:diagram-architecture.

Seeds a single failed DocGenerationJob with the exact error message that
results from a missing editorial guide snapshot.  The job is recent (within
the ~10-minute window that docs_running_jobs considers "recently failed").

Also seeds the corresponding ProjectDoc since the base E2E seed does not
include diagram-architecture.

Idempotent: re-running the seed is a no-op.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    DocGenerationJob,
    EditorialCategory,
    JobStatus,
    ProjectDoc,
)


def seed(db: Session) -> None:
    """Insert (or skip) diagram-architecture ProjectDoc + failed DocGenerationJob."""
    project_id = "iw-ai-core"
    doc_id = "diagram-architecture"
    full_doc_id = f"{project_id}:{doc_id}"
    job_id = "00000000-0000-0000-0000-000000000077"

    # --- ensure the doc exists (JOIN in docs_running_jobs requires it) ---
    existing_doc = db.get(ProjectDoc, full_doc_id)
    if existing_doc is None:
        db.add(
            ProjectDoc(
                id=full_doc_id,
                project_id=project_id,
                doc_id=doc_id,
                title="IW AI Core — Architecture Diagram",
                slug=f"{project_id}-architecture-diagram",
                doc_type=DocType.architecture,
                tier=DocTier.fully_automated,
                editorial_category=EditorialCategory.technical,
                status=DocStatus.published,
                content=(
                    "# IW AI Core — Architecture Diagram\n\n"
                    "Architecture diagram placeholder. "
                    "This doc exists to satisfy browser verification.\n"
                ),
                version=1,
            )
        )
        db.flush()

    # --- ensure the failed job exists ---
    existing_job = db.get(DocGenerationJob, job_id)
    if existing_job is not None:
        return  # already seeded

    now = datetime.now(UTC)
    requested_at = now - timedelta(minutes=2)
    started_at = requested_at + timedelta(seconds=30)

    db.add(
        DocGenerationJob(
            id=job_id,
            public_id="DOC-00077",
            project_id=project_id,
            doc_id=full_doc_id,
            status=JobStatus.failed,
            requested_at=requested_at,
            started_at=started_at,
            completed_at=now,
            error="job context has no section_guides_snapshot — cannot generate content without editorial guidance",
        )
    )
    db.flush()