# F-00037_S02_Backend_prompt

**Work Item**: F-00037 — Doc-Type Guides — Editable Editorial Guidelines
**Step**: S02
**Agent**: Backend
**Parallel With**: None — depends on S01

---

## Input Files

- `ai-dev/active/F-00037/F-00037_Feature_Design.md` — Design document
- `ai-dev/active/F-00037/reports/F-00037_S01_Database_report.md` — Migration report

## Output Files

- `ai-dev/active/F-00037/reports/F-00037_S02_Backend_report.md`

## Context

You are implementing the Python model and service layer for doc-type guides in **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

## Requirements

### 1. Add `DocTypeGuide` model to `orch/db/models.py`

After the `DocGenerationJob` class (around line 958), add:

```python
class DocTypeGuide(Base):
    """Per-doc-type editorial guidelines, editable from the dashboard UI."""

    __tablename__ = "doc_type_guides"

    doc_type: Mapped[str] = mapped_column(
        Text, primary_key=True, comment="DocType enum value (e.g. marketing, module, api)."
    )
    guide_md: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Markdown editorial guidelines for this doc type."
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp of last guide edit.",
    )

    __table_args__ = (
        {"comment": "Per-doc-type editorial guidelines, editable from the dashboard UI."},
    )
```

Also add `guide_snapshot: Mapped[str | None]` column to `DocGenerationJob`:
```python
guide_snapshot: Mapped[str | None] = mapped_column(
    Text, nullable=True, comment="Guide content snapshotted at job creation time for audit purposes."
)
```

### 2. Add guide methods to `DocService` in `orch/doc_service.py`

Add these two methods to `DocService`:

```python
def get_type_guide(self, doc_type: str) -> str | None:
    """Return the editorial guide markdown for the given doc_type, or None if not configured."""
    row = self._session.execute(
        select(DocTypeGuide).where(DocTypeGuide.doc_type == doc_type)
    ).scalar_one_or_none()
    return row.guide_md if row else None

def save_type_guide(self, doc_type: str, guide_md: str) -> DocTypeGuide:
    """Create or update the editorial guide for the given doc_type.

    Uses an upsert pattern so callers do not need to check existence.
    Updates updated_at automatically via the ORM onupdate.
    """
    row = self._session.execute(
        select(DocTypeGuide).where(DocTypeGuide.doc_type == doc_type)
    ).scalar_one_or_none()
    if row is None:
        row = DocTypeGuide(doc_type=doc_type, guide_md=guide_md)
        self._session.add(row)
    else:
        row.guide_md = guide_md
    self._session.flush()
    return row
```

### 3. Update `DocService.create_doc_job()` to snapshot the guide

In `orch/doc_service.py`, find `create_doc_job()` (around line 449). The method already
fetches `doc` at the top of the function and raises `KeyError` if not found — do NOT
re-fetch it. After building the `DocGenerationJob` object and before the `flush()`, add:

```python
# Snapshot the current type guide for audit purposes.
job.guide_snapshot = self.get_type_guide(doc.doc_type.value)
```

`doc` is already in scope (fetched earlier in the same method). `guide_snapshot` will be
`None` if no guide is configured for the doc_type — this is acceptable and expected.

### 4. Add necessary imports

Ensure `DocTypeGuide` is imported in `doc_service.py` alongside other model imports.

## Project Conventions

Read `orch/CLAUDE.md` and `CLAUDE.md` for:
- SQLAlchemy model patterns (`Mapped`, `mapped_column`, `_TIMESTAMPTZ`)
- `DocService` method style (all methods use `self._session`)
- Import order (stdlib → third-party → local)

Match exactly the style of existing model classes and service methods.

## TDD Requirement

Write unit tests in `tests/unit/test_doc_type_guide_service.py`:

1. **RED**: Write failing tests first:
   - `test_get_type_guide_returns_none_when_missing`
   - `test_get_type_guide_returns_content_when_present`
   - `test_save_type_guide_inserts_new_row`
   - `test_save_type_guide_updates_existing_row`

2. **GREEN**: Implement the methods to pass the tests.

3. **REFACTOR**: Clean up.

Unit tests may use `MagicMock` for the session, or use the testcontainer fixture from
`tests/integration/conftest.py` — follow the pattern of existing tests.

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/unit/ -x -q
.venv/bin/python -m ruff check orch/ tests/
.venv/bin/python -m mypy orch/db/models.py orch/doc_service.py
```

All must pass before reporting completion.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "Backend",
  "work_item": "F-00037",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/doc_service.py",
    "tests/unit/test_doc_type_guide_service.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
