# F-00038_S02_Backend_prompt

**Work Item**: F-00038 — Instance Guide Overlay — Per-Document Editorial Override
**Step**: S02
**Agent**: Backend
**Parallel With**: None — depends on S01

---

## Input Files

- `ai-dev/active/F-00038/F-00038_Feature_Design.md` — Design document
- `ai-dev/active/F-00038/reports/F-00038_S01_Database_report.md` — Migration report

## Output Files

- `ai-dev/active/F-00038/reports/F-00038_S02_Backend_report.md`

## Context

You are implementing the Python model and service layer for per-document instance guides
in **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

## Requirements

### 1. Add `DocInstanceGuide` model to `orch/db/models.py`

After `DocTypeGuide` (added by F-00037), add:

```python
class DocInstanceGuide(Base):
    """Per-document editorial guide override — takes priority over the doc_type_guides row."""

    __tablename__ = "doc_instance_guides"

    doc_id: Mapped[str] = mapped_column(
        Text, primary_key=True,
        comment="Composite PK matching project_docs.id (format: project_id:doc_id)."
    )
    guide_md: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Markdown editorial instructions specific to this document."
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
        {"comment": "Per-document editorial guide overrides — highest priority, overrides doc_type_guides."},
    )
```

### 2. Add instance guide methods to `DocService`

Add to `orch/doc_service.py`:

```python
def get_instance_guide(self, project_id: str, doc_id: str) -> str | None:
    """Return the instance guide for the given document, or None if not set."""
    composite_id = f"{project_id}:{doc_id}"
    row = self._session.execute(
        select(DocInstanceGuide).where(DocInstanceGuide.doc_id == composite_id)
    ).scalar_one_or_none()
    return row.guide_md if row else None

def save_instance_guide(self, project_id: str, doc_id: str, guide_md: str) -> DocInstanceGuide:
    """Create or update the instance guide for the given document.

    Uses upsert — safe to call whether or not a row already exists.
    """
    composite_id = f"{project_id}:{doc_id}"
    row = self._session.execute(
        select(DocInstanceGuide).where(DocInstanceGuide.doc_id == composite_id)
    ).scalar_one_or_none()
    if row is None:
        row = DocInstanceGuide(doc_id=composite_id, guide_md=guide_md)
        self._session.add(row)
    else:
        row.guide_md = guide_md
    self._session.flush()
    return row

def delete_instance_guide(self, project_id: str, doc_id: str) -> bool:
    """Remove the instance guide for the given document. Returns True if a row was deleted."""
    composite_id = f"{project_id}:{doc_id}"
    row = self._session.execute(
        select(DocInstanceGuide).where(DocInstanceGuide.doc_id == composite_id)
    ).scalar_one_or_none()
    if row is not None:
        self._session.delete(row)
        self._session.flush()
        return True
    return False

def _effective_guide(self, project_id: str, doc_id: str, doc_type: str) -> str | None:
    """Return the effective editorial guide for a document.

    Priority: instance guide > type guide > None.
    Never raises — returns None when no guide is configured at either level.
    """
    instance = self.get_instance_guide(project_id, doc_id)
    if instance is not None:
        return instance
    return self.get_type_guide(doc_type)
```

### 3. Update `DocService.create_doc_job()` to use `_effective_guide`

Replace the existing guide snapshot logic (added by F-00037 which only used `get_type_guide`)
with a call to `_effective_guide`:

```python
# Snapshot the effective guide (instance overrides type) for audit purposes.
doc = self.get_doc(project_id, doc_id) if doc_id else None
if doc is not None:
    job.guide_snapshot = self._effective_guide(project_id, doc.doc_id, doc.doc_type.value)
```

Note: `doc.doc_id` is the short identifier within the project (not the composite `project_id:doc_id`).

### 4. Imports

Ensure `DocInstanceGuide` is imported in `doc_service.py`.

## TDD Requirement

Write unit tests in `tests/unit/test_instance_guide_service.py`:

1. **RED**: Write failing tests first:
   - `test_effective_guide_returns_instance_when_present` (mock: instance guide exists)
   - `test_effective_guide_falls_back_to_type` (mock: no instance guide, type guide exists)
   - `test_effective_guide_returns_none_when_neither_exists`
   - `test_get_instance_guide_returns_none_when_missing`
   - `test_save_instance_guide_inserts`
   - `test_save_instance_guide_updates`
   - `test_delete_instance_guide_returns_true_when_exists`
   - `test_delete_instance_guide_returns_false_when_absent`

2. **GREEN**: Implement.
3. **REFACTOR**: Clean up.

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/unit/ -x -q
.venv/bin/python -m ruff check orch/ tests/
.venv/bin/python -m mypy orch/db/models.py orch/doc_service.py
```

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "Backend",
  "work_item": "F-00038",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/doc_service.py",
    "tests/unit/test_instance_guide_service.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
