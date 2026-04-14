"""Integration tests for DocTypeGuide CRUD and guide_snapshot in DocGenerationJob.

All tests use the testcontainer PostgreSQL session — never connect to localhost:5433.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, select

from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    DocTypeGuide,
    EditorialCategory,
    Project,
    ProjectDoc,
)
from orch.doc_service import DocService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_DEFAULT_GUIDE = """# Global Editorial Guidelines

## Voice & Tone

Innovation Ways documents are written with authority and clarity. We do not hedge.
We do not use filler phrases. Every sentence earns its place.

**Always:**
- Active voice, present tense
- Concrete specifics over vague generalities
- One idea per paragraph
- Short sentences for key points, longer for explanations

**Never:**
- "Leverage" — use "use"
- "Utilize" — use "use"
- "Solution" as a noun standing alone
- "Best-in-class", "world-class", "cutting-edge" without evidence
- Passive voice unless unavoidable
- Nested bullet lists more than one level deep
- Starting a sentence with "This"

## Structure Rules

- Every document starts with a one-paragraph executive summary
- Heading hierarchy: H1 (title only), H2 (sections), H3 (subsections)
- Tables for comparisons — not bullet lists with parallel items
- Diagrams before prose: show the picture, then explain it
- Code blocks always carry a language identifier

## Numbers & Claims

- Round numbers are suspicious: prefer "under 2 seconds" to "2 seconds"
- Every metric must be traceable to a source file or measurement
- Do not invent future capability — only document what exists

## Formatting

- Bold for the first introduction of a key term only
- Italics for titles and emphasis (use sparingly)
- Avoid ALL CAPS except in code
- Em dash (—) for interruptions; en dash (–) for ranges
"""

_MARKETING_GUIDE = """# Marketing Document Editorial Guidelines

Applies to: MKT-* documents (product_overview, one-pagers, promotional)

## Audience

Non-technical stakeholders, executives, engineering managers, potential partners.
Assume familiarity with software development concepts but not implementation details.

## Tone

Confident, not boastful. Specific, not fluffy. The reader is busy — respect their time.
Lead with the problem. Earn the pitch.

## Structure for Product Overview (MKT)

1. **Headline** — One sentence: what the product does and for whom
2. **The Problem** — Two to four sentences. Make the reader feel the pain before offering the cure
3. **What It Is** — One paragraph. Clear, jargon-light description
4. **How It Works** — High-level diagram + two to four sentences. No implementation detail
5. **Key Capabilities** — Table or short list. Name + one-line description each. Max eight items
6. **Why It Matters** — Three to five bullet points. Outcomes, not features
7. **Current Status** — One paragraph on where the platform stands today
8. **Contact / Next Steps** — Optional; include if doc is externally facing

## Do

- Lead with pain points engineers actually feel
- Use the platform's real capability names (daemon, CLI, dashboard) — they signal substance
- One diagram maximum: a clean component overview
- Keep total length under three pages (printed A4)

## Do Not

- Do not describe internal implementation (SQL queries, Python classes, bash scripts)
- Do not mention version numbers, port numbers, or file paths
- Do not use "AI" as a magic word — describe what the AI agents actually do
- Do not write a feature list disguised as prose — use a table
- Do not end with a generic call to action
"""


@pytest.fixture
def seed_type_guides(db_session: Session) -> None:
    """Insert _default and marketing guides (mirrors the migration seed data)."""
    db_session.add(DocTypeGuide(doc_type="_default", guide_md=_DEFAULT_GUIDE))
    db_session.add(DocTypeGuide(doc_type="marketing", guide_md=_MARKETING_GUIDE))
    db_session.flush()


def test_seed_data_present(db_session: Session, seed_type_guides: None) -> None:
    """After migration, at least _default and marketing guides exist."""
    svc = DocService(db_session)
    default_guide = svc.get_type_guide("_default")
    marketing_guide = svc.get_type_guide("marketing")
    assert default_guide is not None
    assert len(default_guide) > 0
    assert marketing_guide is not None
    assert len(marketing_guide) > 0


def test_save_and_get_round_trip(db_session: Session) -> None:
    """Saving a guide and reading it back returns the saved content."""
    svc = DocService(db_session)
    svc.save_type_guide("api", "# API Guide\nTest content.")
    db_session.commit()
    result = svc.get_type_guide("api")
    assert result == "# API Guide\nTest content."


def test_get_nonexistent_guide_returns_none(db_session: Session) -> None:
    """get_type_guide returns None for an unregistered doc_type."""
    svc = DocService(db_session)
    assert svc.get_type_guide("does_not_exist_xyz") is None


def test_save_updates_existing_guide(db_session: Session) -> None:
    """Calling save_type_guide twice updates the existing row."""
    svc = DocService(db_session)
    svc.save_type_guide("module", "Version 1")
    db_session.commit()
    svc.save_type_guide("module", "Version 2")
    db_session.commit()
    assert svc.get_type_guide("module") == "Version 2"
    count = db_session.execute(
        select(func.count()).where(DocTypeGuide.doc_type == "module")
    ).scalar()
    assert count == 1


def test_guide_snapshot_captured_at_job_creation(db_session: Session) -> None:
    """create_doc_job snapshots the current type guide into guide_snapshot."""
    project = Project(
        id="guide-snap-proj",
        display_name="Guide Snap Test",
        repo_root="/repos/guide-snap",
        config={},
    )
    db_session.add(project)
    db_session.flush()

    doc = ProjectDoc(
        id="guide-snap-proj:test-doc",
        project_id="guide-snap-proj",
        doc_id="test-doc",
        title="Test Doc",
        slug="test-doc",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.marketing,
        status=DocStatus.planned,
        audience=[],
        source_paths=[],
    )
    db_session.add(doc)
    db_session.flush()

    svc = DocService(db_session)
    svc.save_type_guide("module", "# Module Guide\nContent here.")
    db_session.commit()

    job = svc.create_doc_job("guide-snap-proj", "test-doc")
    db_session.commit()

    assert job.guide_snapshot == "# Module Guide\nContent here."
