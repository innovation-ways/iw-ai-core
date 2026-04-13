# F-00037_S04_Tests_prompt

**Work Item**: F-00037 — Doc-Type Guides — Editable Editorial Guidelines
**Step**: S04
**Agent**: Tests
**Parallel With**: None — depends on S02 and S03 being clean

---

## Input Files

- `ai-dev/active/F-00037/F-00037_Feature_Design.md` — Design document
- `ai-dev/active/F-00037/reports/F-00037_S02_Backend_report.md` — Implementation report
- `ai-dev/active/F-00037/reports/F-00037_S03_CodeReview_Backend_report.md` — Review report
- `tests/integration/conftest.py` — Testcontainer fixtures

## Output Files

- `ai-dev/active/F-00037/reports/F-00037_S04_Tests_report.md`

## Context

You are adding integration tests for F-00037 in **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

Read `tests/CLAUDE.md` and `tests/integration/conftest.py` before writing any tests.
All integration tests use the testcontainer PostgreSQL — **never** connect to localhost:5433.

## Requirements

### 1. Integration test file: `tests/integration/test_doc_type_guides.py`

Write tests covering:

**Seed data present after migration**
```python
def test_seed_data_present(db_session):
    """After migration, at least _default and marketing guides exist."""
    from orch.doc_service import DocService
    svc = DocService(db_session)
    default_guide = svc.get_type_guide("_default")
    marketing_guide = svc.get_type_guide("marketing")
    assert default_guide is not None
    assert len(default_guide) > 0
    assert marketing_guide is not None
```

**Get/save round-trip**
```python
def test_save_and_get_round_trip(db_session):
    """Saving a guide and reading it back returns the saved content."""
    from orch.doc_service import DocService
    svc = DocService(db_session)
    svc.save_type_guide("api", "# API Guide\nTest content.")
    db_session.commit()
    result = svc.get_type_guide("api")
    assert result == "# API Guide\nTest content."
```

**Unknown type returns None**
```python
def test_get_nonexistent_guide_returns_none(db_session):
    """get_type_guide returns None for an unregistered doc_type."""
    from orch.doc_service import DocService
    svc = DocService(db_session)
    assert svc.get_type_guide("does_not_exist_xyz") is None
```

**Update existing guide**
```python
def test_save_updates_existing_guide(db_session):
    """Calling save_type_guide twice updates the existing row."""
    from orch.doc_service import DocService
    svc = DocService(db_session)
    svc.save_type_guide("module", "Version 1")
    db_session.commit()
    svc.save_type_guide("module", "Version 2")
    db_session.commit()
    assert svc.get_type_guide("module") == "Version 2"
    # Verify only one row exists
    from sqlalchemy import select, func
    from orch.db.models import DocTypeGuide
    count = db_session.execute(
        select(func.count()).where(DocTypeGuide.doc_type == "module")
    ).scalar()
    assert count == 1
```

**Guide snapshot captured in generation job**
```python
def test_guide_snapshot_captured_at_job_creation(db_session):
    """create_doc_job snapshots the current type guide into guide_snapshot."""
    from orch.doc_service import DocService
    from orch.db.models import DocType, DocStatus, DocTier, EditorialCategory, Project, ProjectDoc
    import uuid

    # Create a project
    project = Project(
        id="guide-snap-proj",
        display_name="Guide Snap Test",
        repo_root="/repos/guide-snap",
        config={},
    )
    db_session.add(project)
    db_session.flush()

    # Create a document with a known doc_type
    doc = ProjectDoc(
        id="guide-snap-proj:test-doc",
        project_id="guide-snap-proj",
        doc_id="test-doc",
        title="Test Doc",
        doc_type=DocType.marketing,
        tier=DocTier.standard,
        status=DocStatus.active,
        editorial_category=EditorialCategory.technical,
        source_paths=[],
    )
    db_session.add(doc)
    db_session.flush()

    svc = DocService(db_session)

    # Seed a guide for marketing
    svc.save_type_guide("marketing", "# Marketing Guide\nContent here.")
    db_session.commit()

    # Create the job — should snapshot the guide
    job = svc.create_doc_job("guide-snap-proj", "test-doc")
    db_session.commit()

    assert job.guide_snapshot == "# Marketing Guide\nContent here."
```

Note: Read `tests/integration/test_doc_generation.py` to confirm the exact model fields
and enum values for `Project` and `ProjectDoc` used in this project's integration tests.
Adapt the helper data above to match the actual model signature — do not guess field names.

## Constraints

- Follow `tests/CLAUDE.md` rules exactly
- All tests use the testcontainer session — never `localhost:5433`
- Each test must be independent (no shared state between tests)
- Use `db_session.commit()` where needed to persist between service calls

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/integration/test_doc_type_guides.py -x -v --timeout=300
```

All tests must pass before reporting completion.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "Tests",
  "work_item": "F-00037",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_doc_type_guides.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
