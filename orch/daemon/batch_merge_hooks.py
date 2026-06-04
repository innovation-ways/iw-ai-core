"""Post-merge hooks for documentation automation.

Called by merge_queue after a BatchItem transitions to merged.
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import BatchItem, Project

logger = logging.getLogger(__name__)


def trigger_doc_regeneration_on_merge(
    session: Session,
    batch_item: BatchItem,
    project: Project,
) -> list[Any]:
    """Enqueue doc regeneration jobs for docs whose source files changed in this merge.

    Called immediately after a BatchItem transitions to merged (squash commit landed).
    Returns list of newly created DocGenerationJob records.
    """
    from orch.doc_service import DocService

    auto_trigger = (
        project.config.get("doc_generation", {}).get("auto_trigger_on_merge", False)
        if project.config
        else False
    )
    if not auto_trigger:
        return []

    result = subprocess.run(
        ["git", "diff", "HEAD^..HEAD", "--name-only"],  # noqa: S603,S607
        cwd=project.repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        logger.warning("[%s] git diff failed: %s", project.id, result.stderr)
        return []

    changed_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not changed_files:
        return []

    svc = DocService(session)
    matched_docs = svc.find_docs_by_source_path(project.id, changed_files)

    created_jobs: list[Any] = []
    for doc in matched_docs:
        trigger_reason = f"batch-merge:{batch_item.batch_id}:{batch_item.work_item_id}"
        job = svc.create_doc_job(
            project.id,
            doc.doc_id,
            requested_by="auto:batch-merge",
            trigger_reason=trigger_reason,
        )
        session.flush()
        created_jobs.append(job)

    if created_jobs:
        logger.info(
            "[%s] Created %d doc regeneration jobs after merge of %s",
            project.id,
            len(created_jobs),
            batch_item.work_item_id,
        )

    return created_jobs
