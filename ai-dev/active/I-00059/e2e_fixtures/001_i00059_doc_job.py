"""E2E fixture: seed I-00059 DocGenerationJob for S11 browser verification.

The browser verification steps V1–V4 navigate to the job detail page for
job ID 2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435 and assert:
  V1: Error block is visible
  V2: Parameters card shows skill_used and duration_seconds
  V3: View document link is present
  V4: No regressions on the jobs list page

This fixture creates that exact job row in the E2E database so the
dashboard serves the detail page correctly.

The fixture is idempotent — skips if the job already exists.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import DocGenerationJob, JobStatus

PROJECT_ID = "iw-ai-core"
JOB_ID = "2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435"
DOC_ID = None
SKILL_USED = "iw-doc-generator"
TRIGGER_REASON = "manual"
ERROR = "generation timeout after 15 minutes"
DURATION_SECONDS = 600


def seed(db: Session) -> None:
    existing = db.get(DocGenerationJob, JOB_ID)
    if existing is not None:
        return

    now = datetime.now(UTC)
    db.add(
        DocGenerationJob(
            id=JOB_ID,
            project_id=PROJECT_ID,
            doc_id=DOC_ID,
            status=JobStatus.failed,
            requested_at=now,
            started_at=now,
            completed_at=now,
            agent_output=None,
            error=ERROR,
            agent_pid=None,
            skill_used=SKILL_USED,
            trigger_reason=TRIGGER_REASON,
            lint_warnings=None,
            duration_seconds=DURATION_SECONDS,
            section_guides_snapshot=None,
            guide_snapshot=None,
            created_at=now,
        )
    )
    db.flush()