# F-00041_S03_Tests_prompt

**Work Item**: F-00041 — Interactive Document IDE — Guide Editor & Diff Viewer UI
**Step**: S03
**Agent**: Tests
**Parallel With**: None — depends on S01 and S02 being clean

---

## Input Files

- `ai-dev/active/F-00041/F-00041_Feature_Design.md` — Design document
- `ai-dev/active/F-00041/reports/F-00041_S01_Frontend_report.md` — Implementation report
- `ai-dev/active/F-00041/reports/F-00041_S02_CodeReview_Frontend_report.md` — Review report
- `tests/integration/conftest.py` — Testcontainer fixtures

## Output Files

- `ai-dev/active/F-00041/reports/F-00041_S03_Tests_report.md`

## Context

You are adding integration tests for the F-00041 htmx endpoints in **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

Read `tests/CLAUDE.md` before writing tests.

## Requirements

### Integration test file: `tests/integration/api/test_docs_ide_api.py`

Cover all 9 new htmx endpoints:

```python
# GET /api/docs/{doc_id}/ide — IDE tab loads
def test_ide_tab_loads(client, ...):
    response = client.get(f"/project/{proj}/api/docs/{doc_id}/ide")
    assert response.status_code == 200
    assert "guide" in response.text.lower()  # panel present

# GET /api/docs/{doc_id}/guide/type — type guide panel
def test_get_type_guide_panel(client, ...):
    response = client.get(f"/project/{proj}/api/docs/{doc_id}/guide/type")
    assert response.status_code == 200
    assert "textarea" in response.text

# POST /api/docs/{doc_id}/guide/type — save type guide
def test_save_type_guide(client, ...):
    response = client.post(
        f"/project/{proj}/api/docs/{doc_id}/guide/type",
        data={"guide_md": "# New Guide\nContent."}
    )
    assert response.status_code == 200
    assert "New Guide" in response.text

# GET /api/docs/{doc_id}/guide/instance — instance guide panel (no override)
def test_get_instance_guide_panel_no_override(client, ...):
    response = client.get(f"/project/{proj}/api/docs/{doc_id}/guide/instance")
    assert response.status_code == 200
    # Should show "inheriting" message when no override

# POST /api/docs/{doc_id}/guide/instance — save instance guide
# DELETE /api/docs/{doc_id}/guide/instance — delete instance guide
# GET /api/docs/{doc_id}/guide/sections — section guide list
# POST /api/docs/{doc_id}/guide/sections/{section_name} — save section guide
# DELETE /api/docs/{doc_id}/guide/sections/{section_name} — delete section guide
```

Follow the project fixture patterns for setting up required parent records.
Each test must be independent.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "textarea" in response.text` (shape only — proves element exists, not its content)
- GOOD: `assert "# New Guide\nContent." in response.text` (semantic — verifies exact saved content round-trips)
- GOOD: `assert "Inheriting from type guide" in response.text` after DELETE (semantic — verifies specific state message)

Applied to this feature: assert **exact guide content** is reflected in the HTML response after POST,
not merely that a textarea or status code is present. Verify GET round-trips return what was saved.
For section guides, assert the specific `section_name` and content appear in the fragment response.

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/integration/api/test_docs_ide_api.py -x -v --timeout=300
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "F-00041",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/api/test_docs_ide_api.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
