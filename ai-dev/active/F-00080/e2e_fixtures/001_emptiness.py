"""F-00080 E2E fixture: guarantee at least one empty list view.

The S18 browser verification's V6 step requires a list page that is *truly
empty* in the seeded DB so the new ``empty_state`` macro markup
(``data-empty-state``, ``h3``, ``p``, ``a.empty-state__cta-primary``) can
be observed in the rendered HTML.

The seeded DB is a ``pg_dump`` of the live orchestration DB, which always
contains at least one CodeIndexJob (CM-00001) and various DocGenerationJobs.
That makes the unified Jobs page non-empty, and V6 cannot be verified there.

This fixture deletes every row that the unified-jobs aggregator surfaces for
project ``iw-ai-core`` so the Jobs page renders the empty state. It does NOT
touch the orchestration core (work items, batches metadata that other Vs may
depend on for navigation) — only the rows that the jobs aggregator queries.

Other list pages (research, docs, code, history) are intentionally untouched
so V9 (no regressions on adjacent flows) can still see populated content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete

from orch.db.models import (
    Batch,
    BatchItem,
    CodeIndexJob,
    DocGenerationJob,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"


def seed(db: Session) -> None:
    """Empty every table the Jobs aggregator pulls from, for PROJECT_ID."""
    # Order matters: BatchItem references Batch; delete children first.
    db.execute(delete(BatchItem).where(BatchItem.project_id == PROJECT_ID))
    db.execute(delete(Batch).where(Batch.project_id == PROJECT_ID))
    db.execute(delete(CodeIndexJob).where(CodeIndexJob.project_id == PROJECT_ID))
    db.execute(delete(DocGenerationJob).where(DocGenerationJob.project_id == PROJECT_ID))
    db.flush()
