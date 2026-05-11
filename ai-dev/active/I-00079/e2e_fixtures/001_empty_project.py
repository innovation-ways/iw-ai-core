"""Fixture: a project with no work items, batches, or docs — for empty-state CTA verification.

All empty-state panels on Queue, History, Batches, Docs, and Research pages only render
when the list is empty. The E2E seed always creates `iw-ai-core` with items, so we add
a second project that has nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import Project


def seed(db: Session) -> None:
    """Insert a bare project with no child rows.

    Idempotent: first call creates, subsequent calls are no-ops.
    """
    existing = db.get(Project, "empty-test-project")
    if existing is not None:
        return

    db.add(
        Project(
            id="empty-test-project",
            display_name="Empty Test Project",
            repo_root="/tmp/empty-test-project",  # not a real repo; no worktrees will be launched
            config={},
            enabled=True,
            oss_enabled=False,
        )
    )
    db.flush()