"""Seed non-research docs so doc cards render on the library page.

This fixture seeds:
  - 1 module doc (published)     — for verifying type/tier/status pills
  - 1 api doc (draft)           — for additional badge coverage
  - 1 stale module doc (draft)  — for verifying stale summary banner AC3

The CR-00012 browser verification cannot pass AC1-AC6 (V1-V6) without
non-research docs present in the E2E DB because docs_library.html
excludes DocType.research (docs.py:44).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory, ProjectDoc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"


def seed(db: Session) -> None:
    docs = [
        ProjectDoc(
            id=f"{PROJECT_ID}:module-iw-core-overview",
            project_id=PROJECT_ID,
            doc_id="module-iw-core-overview",
            title="IW AI Core — Module Overview",
            slug="iw-ai-core-module-overview",
            doc_type=DocType.module,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            content="# IW AI Core — Module Overview\n\nCore orchestration engine module.",
            version=1,
        ),
        ProjectDoc(
            id=f"{PROJECT_ID}:api-doc-generator",
            project_id=PROJECT_ID,
            doc_id="api-doc-generator",
            title="DocGenerator API Reference",
            slug="iw-ai-core-doc-generator-api",
            doc_type=DocType.api,
            tier=DocTier.semi_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.draft,
            content="# DocGenerator API\n\nREST API endpoints for the doc generator.",
            version=1,
        ),
        ProjectDoc(
            id=f"{PROJECT_ID}:module-stale-doc",
            project_id=PROJECT_ID,
            doc_id="module-stale-doc",
            title="Stale Module Doc",
            slug="iw-ai-core-stale-module",
            doc_type=DocType.module,
            tier=DocTier.human_authored,
            editorial_category=EditorialCategory.guide,
            status=DocStatus.draft,
            content="# Stale Module Doc\n\nThis doc is stale.",
            version=1,
        ),
    ]
    for doc in docs:
        existing = db.get(ProjectDoc, doc.id)
        if existing is None:
            db.add(doc)
        else:
            existing.title = doc.title
            existing.doc_type = doc.doc_type
            existing.tier = doc.tier
            existing.status = doc.status
            existing.content = doc.content
