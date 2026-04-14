# F-00039 S03 CodeReview_Backend Report

## What Was Reviewed

Reviewed the S02 backend implementation against the F-00039 design document and project conventions. Files examined:

- `orch/db/models.py` — `DocSectionGuide` model + `section_guides_snapshot` column on `DocGenerationJob`
- `orch/doc_service.py` — section guide CRUD methods + `create_doc_job` snapshot update
- `orch/doc_sections.py` — `extract_sections` / `split_by_sections` pure functions
- `tests/unit/test_doc_sections.py` — unit tests

## Correctness Checklist

| Item | Status |
|------|--------|
| `DocSectionGuide` model: `id BIGINT PK`, `doc_id TEXT NOT NULL FK`, `section_name TEXT NOT NULL`, `guide_md TEXT NOT NULL`, `updated_at TIMESTAMPTZ` | PASS |
| `UniqueConstraint("doc_id", "section_name")` present on the model | PASS (name=`uq_doc_section_guides_doc_section`) |
| `section_guides_snapshot JSONB` column added to `DocGenerationJob` | PASS |
| `extract_sections` returns `["Document"]` for content with no H2 headings | PASS |
| `extract_sections` correctly strips whitespace from section names | PASS |
| `split_by_sections` returns `{"Document": content}` for no-H2 content | PASS |
| CRUD methods use composite `project_id:doc_id` key | PASS |
| `delete_section_guide` returns `False` (not raises) when row not found | PASS |
| `create_doc_job` snapshot captures all section guides at creation time | PASS |

## Conventions Checklist

| Item | Status |
|------|--------|
| Module docstring on `orch/doc_sections.py` | PASS |
| All functions in `doc_sections.py` have docstrings with Args and Returns | PASS |
| Column `comment=` on every `mapped_column` | **FAIL** — `DocSectionGuide` columns lack `comment=` |
| Model class has a docstring | PASS |
| Imports follow project ordering | PASS (F401 import used correctly) |

## Tests Checklist

| Item | Status |
|------|--------|
| `test_extract_sections_no_h2_returns_document` present and meaningful | PASS |
| `test_extract_sections_empty_content` present | PASS |
| `test_split_by_sections_no_h2_returns_document_key` present | PASS |
| Tests follow project test patterns | PASS |

## Architecture Checklist

| Item | Status |
|------|--------|
| `orch/doc_sections.py` has NO database dependencies — pure functions only | PASS |
| Service methods use `self._session` consistently | PASS |
| No business logic outside the service layer | PASS |

## Findings

### MEDIUM (fixable): Missing `comment=` on `DocSectionGuide` mapped columns

The `DocSectionGuide` model in `orch/db/models.py:966–993` does not include `comment=` arguments on its four `mapped_column` definitions (`id`, `doc_id`, `section_name`, `guide_md`). All other models in the file (e.g., `Project`, `WorkItem`, `ProjectDoc`) consistently include `comment=` on every column.

**Fix**: Add `comment=` to each column in `DocSectionGuide`, for example:
```python
id: Mapped[int] = mapped_column(
    BigInteger,
    primary_key=True,
    autoincrement=True,
    comment="Primary key for section guide records.",
)
doc_id: Mapped[str] = mapped_column(
    Text,
    nullable=False,
    comment="FK to project_docs.id (composite: project_id:doc_id).",
)
section_name: Mapped[str] = mapped_column(
    Text,
    nullable=False,
    comment="H2 heading text, or 'Document' if no H2 headings exist.",
)
guide_md: Mapped[str] = mapped_column(
    Text,
    nullable=False,
    comment="Markdown editorial guidelines for this specific section.",
)
```

Note: `updated_at` already has a `comment=` argument and is correct.

## Summary

The implementation is correct and complete. One convention issue: `DocSectionGuide` columns lack `comment=` arguments. This is a MEDIUM (fixable) issue and does not block the step, but should be corrected before S04 (Tests) runs.

---

**Completion status**: `complete`  
**review_passed**: `true`  
**mandatory_fixes**: []  
**notes**: "DocSectionGuide columns need `comment=` added — MEDIUM convention issue. Implementation is otherwise solid."