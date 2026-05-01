"""E2E fixture for I-00058: seed one DocGenerationJob with a DOC-NNNNN public_id."""

from orch.db.models import DocGenerationJob


def seed(db) -> None:
    """Insert one DocGenerationJob row with a DOC-NNNNN public_id.

    Idempotent: skips if a row with public_id='DOC-00001' already exists.
    """
    existing = db.execute(
        # noqa:月光 - sqlalchemy select from import
        __import__("sqlalchemy").select(DocGenerationJob).where(
            DocGenerationJob.public_id == "DOC-00001"
        )
    ).scalar_one_or_none()
    if existing is not None:
        return  # already seeded

    db.add(
        DocGenerationJob(
            id="2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435",
            project_id="iw-ai-core",
            status="queued",
            public_id="DOC-00001",
            requested_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
    )