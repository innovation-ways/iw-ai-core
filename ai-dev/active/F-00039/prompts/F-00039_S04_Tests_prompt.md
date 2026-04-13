# F-00039_S04_Tests_prompt

**Work Item**: F-00039 — Section-Level Guide
**Step**: S04
**Agent**: Tests
**Parallel With**: None — depends on S02 and S03 being clean

---

## Input Files

- `ai-dev/active/F-00039/F-00039_Feature_Design.md` — Design document
- `ai-dev/active/F-00039/reports/F-00039_S02_Backend_report.md` — Implementation report
- `ai-dev/active/F-00039/reports/F-00039_S03_CodeReview_Backend_report.md` — Review report
- `tests/integration/conftest.py` — Testcontainer fixtures

## Output Files

- `ai-dev/active/F-00039/reports/F-00039_S04_Tests_report.md`

## Context

You are adding integration tests for F-00039 in **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

Read `tests/CLAUDE.md` and `tests/integration/conftest.py` before writing any tests.
All integration tests use the testcontainer PostgreSQL — **never** connect to localhost:5433.

## Requirements

### 1. Integration test file: `tests/integration/test_doc_section_guides.py`

Write tests covering:

**Upsert and retrieve round-trip**
```python
def test_save_and_get_section_guide(db_session):
    """Saving and retrieving a section guide returns the saved content."""
    from orch.doc_service import DocService
    # Requires a project_docs row to exist for the FK — create one first.
    # Follow the existing integration test fixture pattern for creating projects and docs.
    ...
```

**List section guides**
```python
def test_list_section_guides_returns_all(db_session):
    """list_section_guides returns all guides for the document."""
    ...
```

**Delete section guide**
```python
def test_delete_section_guide_returns_false_when_not_found(db_session):
    """Deleting a non-existent section guide returns False without raising."""
    from orch.doc_service import DocService
    svc = DocService(db_session)
    result = svc.delete_section_guide("proj", "nonexistent-doc", "Purpose")
    assert result is False
```

**Upsert updates existing row**
```python
def test_save_section_guide_updates_existing(db_session):
    """Calling save_section_guide twice updates the existing row, not duplicates."""
    ...
```

**Snapshot captured at job creation**
```python
def test_section_guides_snapshot_captured_at_job_creation(db_session):
    """section_guides_snapshot in the created job reflects all section guides at creation time."""
    ...
```

**No section guides → snapshot is None**
```python
def test_section_guides_snapshot_none_when_no_guides(db_session):
    """If no section guides exist, section_guides_snapshot is None in the job."""
    ...
```

**AC5: Snapshot key is "Document" when section guide uses that name** (AC5 from design doc)
```python
def test_section_guides_snapshot_uses_document_key(db_session):
    """When a section guide with section_name='Document' exists, the snapshot key is 'Document'.

    This covers the case where a document has no H2 headings, so the guide is stored
    under the sentinel section name 'Document'.
    """
    from orch.doc_service import DocService
    svc = DocService(db_session)
    # Create a project, doc, and section guide for section_name="Document".
    # Create a generation job and assert:
    #   job.section_guides_snapshot == {"Document": "<guide_md>"}
    ...
```

Follow the project fixture patterns for creating required parent records (projects, docs).

## Constraints

- Follow `tests/CLAUDE.md` rules exactly
- All tests use testcontainer session — never localhost:5433
- Each test must be independent

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/integration/test_doc_section_guides.py -x -v --timeout=300
```

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "Tests",
  "work_item": "F-00039",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_doc_section_guides.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
