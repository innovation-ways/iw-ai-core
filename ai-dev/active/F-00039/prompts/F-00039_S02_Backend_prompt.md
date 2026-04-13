# F-00039_S02_Backend_prompt

**Work Item**: F-00039 — Section-Level Guide — Per-Section Editorial Guidelines
**Step**: S02
**Agent**: Backend
**Parallel With**: None — depends on S01

---

## Input Files

- `ai-dev/active/F-00039/F-00039_Feature_Design.md` — Design document
- `ai-dev/active/F-00039/reports/F-00039_S01_Database_report.md` — Migration report

## Output Files

- `ai-dev/active/F-00039/reports/F-00039_S02_Backend_report.md`

## Context

You are implementing the Python model, module, and service layer for section-level guides
in **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

## Requirements

### 1. Add `DocSectionGuide` model to `orch/db/models.py`

After `DocInstanceGuide` (added by F-00038), add:

```python
class DocSectionGuide(Base):
    """Per-section editorial guidelines, keyed by (doc_id, section_name)."""

    __tablename__ = "doc_section_guides"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(
        Text, nullable=False, comment="FK to project_docs.id (composite: project_id:doc_id)."
    )
    section_name: Mapped[str] = mapped_column(
        Text, nullable=False, comment="H2 heading text, or 'Document' if no H2 headings exist."
    )
    guide_md: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Markdown editorial guidelines for this specific section."
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp of last guide edit.",
    )

    __table_args__ = (
        ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="CASCADE"),
        UniqueConstraint("doc_id", "section_name", name="uq_doc_section_guides_doc_section"),
        Index("idx_doc_section_guides_doc_id", "doc_id"),
        {"comment": "Per-section editorial guidelines keyed by (doc_id, section_name)."},
    )
```

Also add `section_guides_snapshot: Mapped[dict | None]` to `DocGenerationJob`:
```python
section_guides_snapshot: Mapped[dict[str, str] | None] = mapped_column(
    JSONB, nullable=True,
    comment="Section guides snapshotted at job creation: {section_name: guide_md, ...}."
)
```

### 2. Create `orch/doc_sections.py` module

```python
"""Markdown section extraction utilities for the IW AI Core doc system.

Provides pure functions for parsing H2-level sections from document markdown content.
These functions have no side effects and do not interact with the database.
"""

import re


def extract_sections(content: str) -> list[str]:
    """Return the list of section names derived from H2 headings.

    Each ``## Heading`` line yields one section name. If no H2 headings are
    found the document is treated as a single section named "Document".

    Args:
        content: Full markdown content of the document.

    Returns:
        List of section name strings in document order.
    """
    names = re.findall(r"^## (.+)$", content, re.MULTILINE)
    # Strip whitespace from each extracted name
    names = [n.strip() for n in names]
    return names if names else ["Document"]


def split_by_sections(content: str) -> dict[str, str]:
    """Map each H2 section name to its body text.

    The body text runs from the H2 heading line up to (but not including) the
    next H2 heading or the end of the document.  The heading line itself is
    included in the body so that reassembly is lossless.

    If no H2 headings are found, the entire content is returned under the key
    "Document".

    Args:
        content: Full markdown content of the document.

    Returns:
        Ordered dict mapping section_name → body_text.
    """
    pattern = re.compile(r"^## .+$", re.MULTILINE)
    matches = list(pattern.finditer(content))

    if not matches:
        return {"Document": content}

    result: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(0)[3:].strip()  # strip leading "## "
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        result[name] = content[start:end].rstrip("\n")

    return result
```

### 3. Add section guide methods to `DocService`

```python
def get_section_guide(
    self, project_id: str, doc_id: str, section_name: str
) -> str | None:
    """Return the editorial guide for a specific section, or None if not set."""
    composite_id = f"{project_id}:{doc_id}"
    row = self._session.execute(
        select(DocSectionGuide)
        .where(DocSectionGuide.doc_id == composite_id)
        .where(DocSectionGuide.section_name == section_name)
    ).scalar_one_or_none()
    return row.guide_md if row else None

def save_section_guide(
    self, project_id: str, doc_id: str, section_name: str, guide_md: str
) -> DocSectionGuide:
    """Create or update the section guide for the given (doc, section) pair."""
    composite_id = f"{project_id}:{doc_id}"
    row = self._session.execute(
        select(DocSectionGuide)
        .where(DocSectionGuide.doc_id == composite_id)
        .where(DocSectionGuide.section_name == section_name)
    ).scalar_one_or_none()
    if row is None:
        row = DocSectionGuide(doc_id=composite_id, section_name=section_name, guide_md=guide_md)
        self._session.add(row)
    else:
        row.guide_md = guide_md
    self._session.flush()
    return row

def delete_section_guide(
    self, project_id: str, doc_id: str, section_name: str
) -> bool:
    """Remove the section guide for a (doc, section) pair. Returns True if deleted."""
    composite_id = f"{project_id}:{doc_id}"
    row = self._session.execute(
        select(DocSectionGuide)
        .where(DocSectionGuide.doc_id == composite_id)
        .where(DocSectionGuide.section_name == section_name)
    ).scalar_one_or_none()
    if row is not None:
        self._session.delete(row)
        self._session.flush()
        return True
    return False

def list_section_guides(
    self, project_id: str, doc_id: str
) -> list[DocSectionGuide]:
    """Return all section guides for the given document, ordered by section_name."""
    composite_id = f"{project_id}:{doc_id}"
    return list(
        self._session.execute(
            select(DocSectionGuide)
            .where(DocSectionGuide.doc_id == composite_id)
            .order_by(DocSectionGuide.section_name)
        ).scalars().all()
    )
```

### 4. Update `DocService.create_doc_job()` to snapshot section guides

After setting `job.guide_snapshot` (from F-00038), add:

```python
# Snapshot section guides for audit purposes.
if doc is not None:
    section_rows = self.list_section_guides(project_id, doc.doc_id)
    if section_rows:
        job.section_guides_snapshot = {row.section_name: row.guide_md for row in section_rows}
```

### 5. Imports

Add `DocSectionGuide` to imports in `doc_service.py`. Add `from orch.doc_sections import extract_sections, split_by_sections` (even if not yet used in the service — this makes the module importable and tested by mypy).

## TDD Requirement

Write unit tests in `tests/unit/test_doc_sections.py`:

1. **RED** first:
   - `test_extract_sections_with_h2_headings`
   - `test_extract_sections_no_h2_returns_document`
   - `test_extract_sections_empty_content`
   - `test_extract_sections_h3_only_returns_document`
   - `test_split_by_sections_correct_bodies`
   - `test_split_by_sections_no_h2_returns_document_key`

2. **GREEN**: Implement `orch/doc_sections.py`.
3. **REFACTOR**.

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/unit/test_doc_sections.py -x -q
.venv/bin/python -m ruff check orch/ tests/
.venv/bin/python -m mypy orch/db/models.py orch/doc_service.py orch/doc_sections.py
```

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "Backend",
  "work_item": "F-00039",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/doc_service.py",
    "orch/doc_sections.py",
    "tests/unit/test_doc_sections.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
