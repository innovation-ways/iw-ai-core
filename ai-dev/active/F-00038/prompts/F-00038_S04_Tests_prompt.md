# F-00038_S04_Tests_prompt

**Work Item**: F-00038 — Instance Guide Overlay — Per-Document Editorial Override
**Step**: S04
**Agent**: Tests
**Parallel With**: None — depends on S02 and S03 being clean

---

## Input Files

- `ai-dev/active/F-00038/F-00038_Feature_Design.md` — Design document
- `ai-dev/active/F-00038/reports/F-00038_S02_Backend_report.md` — Implementation report
- `ai-dev/active/F-00038/reports/F-00038_S03_CodeReview_Backend_report.md` — Review report
- `tests/integration/conftest.py` — Testcontainer fixtures

## Output Files

- `ai-dev/active/F-00038/reports/F-00038_S04_Tests_report.md`

## Context

You are adding integration tests for F-00038 in **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

Read `tests/CLAUDE.md` and existing integration tests before writing. Never connect to localhost:5433.

## Requirements

### Integration test file: `tests/integration/test_doc_instance_guides.py`

Cover all 4 acceptance criteria from the design document:

**AC1 — Instance guide overrides type guide in snapshot**
Create a doc with a known doc_type that has a type guide. Save an instance guide for that doc.
Create a generation job. Assert `job.guide_snapshot` equals the instance guide content.

**AC2 — Falls back to type guide when no instance override**
Create a doc with a known doc_type that has a type guide. Do NOT create an instance guide.
Create a generation job. Assert `job.guide_snapshot` equals the type guide content.

**AC3 — Falls back to None when neither guide exists**
Create a doc with a doc_type that has no type guide row. Do NOT create an instance guide.
Create a generation job. Assert `job.guide_snapshot is None` (no exception raised).

**AC4 — Instance guide CRUD round-trip**
```python
def test_instance_guide_crud_round_trip(db_session):
    # Create a project and doc first (follow existing fixture patterns)
    # ...
    svc = DocService(db_session)
    svc.save_instance_guide(project_id, doc_id, "## My Guide\nCustom content.")
    db_session.commit()
    assert svc.get_instance_guide(project_id, doc_id) == "## My Guide\nCustom content."
    deleted = svc.delete_instance_guide(project_id, doc_id)
    db_session.commit()
    assert deleted is True
    assert svc.get_instance_guide(project_id, doc_id) is None
```

Follow existing integration test fixture patterns for creating projects and docs.
If helpers exist (e.g., `create_test_project`, `create_test_doc`), use them.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert job.guide_snapshot is not None` (shape only)
- GOOD: `assert job.guide_snapshot == "## My Instance Guide\n..."` (semantic — verifies exact content)
- GOOD: `assert job.guide_snapshot != type_guide_content` (semantic — verifies override took effect)

Applied to this feature: assert the **exact guide content** in `guide_snapshot`, not merely
that it is non-None or non-empty. Verify that AC1 tests confirm the instance content specifically,
and AC2 tests confirm the type guide content specifically (not just "something was set").

## Constraints

- Use testcontainer session — never localhost:5433
- Each test is independent
- Commit between service calls when testing persistence

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/integration/test_doc_instance_guides.py -x -v --timeout=300
```

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "Tests",
  "work_item": "F-00038",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_doc_instance_guides.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
