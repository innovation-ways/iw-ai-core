"""E2E fixture for I-00064: seed a code-index ProjectDoc and its DocGenerationJob.

This fixture supplies the data needed by the browser verification S14 so that
V1 ("View document link resolves") has a valid doc_generation job with a
linked ProjectDoc to follow.

Without this fixture the E2E seed contains DOC-00001 as an orphan
(doc_id=None) and V1 cannot be verified.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from orch.db.models import DocTier, DocType, EditorialCategory, JobStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"
DOC_ID = "code-index"
DOC_PK = f"{PROJECT_ID}:{DOC_ID}"
JOB_PUBLIC_ID = "DOC-00001"


def seed(db: Session) -> None:
    from datetime import UTC, datetime
    from orch.db.models import DocGenerationJob, ProjectDoc
    from sqlalchemy import select

    existing_doc = db.get(ProjectDoc, DOC_PK)
    if existing_doc is None:
        # Insert ProjectDoc (inner id = "code-index")
        doc = ProjectDoc(
            id=DOC_PK,
            project_id=PROJECT_ID,
            doc_id=DOC_ID,
            title="Code Index",
            slug=f"{PROJECT_ID}-code-index",
            doc_type=DocType.module,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            status="published",
            audience=[],
            source_paths=[],
        )
        db.add(doc)
        db.flush()
    else:
        doc = existing_doc

    # Check if the job already exists (may be orphan with doc_id=None)
    existing_job = db.scalar(
        select(DocGenerationJob).where(
            DocGenerationJob.public_id == JOB_PUBLIC_ID,
            DocGenerationJob.project_id == PROJECT_ID,
        )
    )
    if existing_job is not None:
        # Update existing orphan job to point at the new doc
        existing_job.doc_id = DOC_PK
        existing_job.status = JobStatus.completed
        existing_job.skill_used = "iw-doc-generator"
        existing_job.trigger_reason = "manual"
        existing_job.started_at = datetime.now(UTC).replace(tzinfo=None)
        existing_job.completed_at = datetime.now(UTC).replace(tzinfo=None)
    else:
        # Insert DocGenerationJob pointing at the composite PK
        job = DocGenerationJob(
            id="00000000-0000-0000-0000-000000000001",
            project_id=PROJECT_ID,
            doc_id=DOC_PK,  # composite FK value
            public_id=JOB_PUBLIC_ID,
            status=JobStatus.completed,
            skill_used="iw-doc-generator",
            trigger_reason="manual",
            requested_at=datetime.now(UTC).replace(tzinfo=None),
            started_at=datetime.now(UTC).replace(tzinfo=None),
            completed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(job)
    db.flush()
