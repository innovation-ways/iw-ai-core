"""E2E fixture: creates a running DocGenerationJob for V5 verification."""
from sqlalchemy.orm import Session

from orch.db.models import DocGenerationJob, ProjectDocs


def seed(db: Session) -> None:
    """Create a running DocGenerationJob for architecture-map doc."""
    doc = db.get(ProjectDocs, "iw-ai-core:architecture-map")
    if not doc:
        return

    # Check if a running job already exists for this doc
    existing = (
        db.query(DocGenerationJob)
        .filter(
            DocGenerationJob.doc_id == doc.id,
            DocGenerationJob.status == "running",
        )
        .first()
    )
    if existing:
        return

    job = DocGenerationJob(
        id=f"cr00038-v5-seed-{doc.id}",
        project_id=doc.project_id,
        doc_id=doc.id,
        status="running",
        requested_at=None,
    )
    db.add(job)
    db.commit()