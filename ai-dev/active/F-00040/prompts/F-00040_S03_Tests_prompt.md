# F-00040_S03_Tests_prompt

**Work Item**: F-00040 — Enhanced Document Diff
**Step**: S03
**Agent**: Tests
**Parallel With**: None — depends on S01 and S02 being clean

---

## Input Files

- `ai-dev/active/F-00040/F-00040_Feature_Design.md` — Design document
- `ai-dev/active/F-00040/reports/F-00040_S01_Backend_report.md` — Implementation report
- `ai-dev/active/F-00040/reports/F-00040_S02_CodeReview_Backend_report.md` — Review report
- `orch/doc_diff.py` — Module to unit test
- `tests/integration/conftest.py` — Testcontainer fixtures

## Output Files

- `ai-dev/active/F-00040/reports/F-00040_S03_Tests_report.md`

## Context

You are adding unit and integration tests for F-00040 in **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

Read `tests/CLAUDE.md` before writing tests.

## Requirements

### 1. Unit test file: `tests/unit/test_doc_diff.py`

Test `diff_document_versions` from `orch.doc_diff`:

```python
from orch.doc_diff import diff_document_versions, SectionDiff

def test_diff_no_h2_headings():
    """No H2 headings → single 'Document' section."""
    old = "Hello world\n"
    new = "Hello universe\n"
    result = diff_document_versions(old, new, 1, 2)
    assert len(result.sections) == 1
    assert result.sections[0].section_name == "Document"
    assert result.sections[0].status == "changed"

def test_diff_unchanged_section():
    """Identical section content → status unchanged."""
    content = "## Purpose\nSame content\n"
    result = diff_document_versions(content, content, 1, 2)
    assert result.sections[0].status == "unchanged"
    assert result.sections[0].unified_diff == []

def test_diff_added_section():
    """Section present only in new version → status added."""
    old = "## Purpose\nOld purpose\n"
    new = "## Purpose\nOld purpose\n## Usage\nNew section\n"
    result = diff_document_versions(old, new, 1, 2)
    statuses = {s.section_name: s.status for s in result.sections}
    assert statuses["Purpose"] == "unchanged"
    assert statuses["Usage"] == "added"

def test_diff_removed_section():
    """Section present only in old version → status removed."""
    old = "## Purpose\nOld purpose\n## Deprecated\nGoing away\n"
    new = "## Purpose\nOld purpose\n"
    result = diff_document_versions(old, new, 1, 2)
    statuses = {s.section_name: s.status for s in result.sections}
    assert statuses["Purpose"] == "unchanged"
    assert statuses["Deprecated"] == "removed"

def test_diff_changed_section():
    """Modified section content → status changed with non-empty diff."""
    old = "## Purpose\nVersion 1 content\n"
    new = "## Purpose\nVersion 2 content\n"
    result = diff_document_versions(old, new, 1, 2)
    assert result.sections[0].status == "changed"
    assert len(result.sections[0].unified_diff) > 0

def test_diff_version_numbers_in_result():
    """version_old and version_new are preserved in DocDiff."""
    result = diff_document_versions("a\n", "b\n", 3, 7)
    assert result.version_old == 3
    assert result.version_new == 7
```

### 2. Integration test file: `tests/integration/api/test_docs_diff_api.py`

Test the three new endpoints via the test client:

```python
def test_sections_endpoint_returns_json(client, ...):
    """GET /diff/sections returns 200 JSON with section data."""
    # Must verify: version_old, version_new, sections list, section_name/status/unified_diff fields
    ...

def test_sections_single_section_endpoint(client, ...):
    """GET /diff/sections/{section_name} returns 200 HTML for a known section."""
    # Must verify: response is HTML, contains diff content for the named section
    # Must also verify: unknown section_name returns 404
    ...

def test_ai_summary_returns_204(client, ...):
    """GET /diff/ai-summary returns 204 with X-Stub header."""
    # Must verify: status_code == 204 AND response.headers["X-Stub"] == "waiting-for-F-00025"
    ...

def test_v1_gte_v2_returns_422(client, ...):
    """v1 >= v2 returns 422 on all new endpoints."""
    ...

def test_missing_version_returns_404(client, ...):
    """Non-existent version returns 404."""
    ...

def test_existing_diff_endpoint_unchanged(client, ...):
    """Original /diff endpoint still returns HTML unified diff."""
    ...
```

Follow the existing API test patterns for client fixture and project/doc/version setup.

## Semantic Correctness Warning

⚠️ **SEMANTIC CORRECTNESS**: Tests must verify actual content and behavior — not just status codes or that the function runs without error.

- `test_sections_endpoint_returns_json` must assert that `sections` is a non-empty list, that each entry has `section_name`, `status`, and `unified_diff` fields, and that the `status` value matches the actual change made between the two versions.
- `test_sections_single_section_endpoint` must assert that the HTML body contains diff content, not just that the response is 200.
- `test_ai_summary_returns_204` must assert BOTH `status_code == 204` AND the `X-Stub` response header value — a plain 204 without the header is a bug.
- A test that only asserts `response.status_code == 200` without checking any response content does not constitute meaningful coverage.

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/unit/test_doc_diff.py -x -v
.venv/bin/pytest tests/integration/api/test_docs_diff_api.py -x -v --timeout=300
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "F-00040",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_doc_diff.py",
    "tests/integration/api/test_docs_diff_api.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
