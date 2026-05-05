# I-00064 S04 Code Review Report

## Step: S04 (Code Review Tests)
**Reviewed Agent**: tests-impl (S03)
**Work Item**: I-00064 — Job detail "View document" link 404s with double project_id prefix

---

## What Was Done

Reviewed the three integration tests written in S03 at
`tests/integration/test_i00064_doc_generation_view_document_url.py`.

---

## Pre-Review Lint & Format Gate

- **`make lint`**: 1 pre-existing error (TC004 `pathlib.Path` in TYPE_CHECKING block in `orch/daemon/worktree_compose.py`). Not caused by this step — confirmed pre-existing on main by S01 report.
- **`make format-check`**: ✅ All 605 files formatted correctly. No new violations in the new test file.

---

## Review Checklist

### 1. Falsifiability — does the reproduction test really fail pre-fix?

`test_i00064_reproduces_bug`:
- `assert row.raw["doc_id"] == "code-index"` ✅ Verifies the inner identifier, which pre-fix code does NOT return (it returns the composite).
- `assert ":" not in (row.raw["doc_id"] or "")` ✅ Strong anti-shape guard that fails on the composite `iw-ai-core:code-index`.
- `assert row.raw["doc_id"] != "iw-ai-core:code-index"` ✅ Explicit negative assertion against the composite.

**Verdict**: Test is falsifiable — FAILS on main (pre-fix), PASSES after S01 fix.

### 2. Semantic correctness, not shape

All assertions verify **specific expected values**, not just shape/truthiness/type:

| Test | Assertion | Type |
|------|-----------|------|
| `test_i00064_reproduces_bug` | `row.raw["doc_id"] == "code-index"` | Specific value ✅ |
| `test_i00064_reproduces_bug` | `":" not in row.raw["doc_id"]` | Specific unwanted pattern ✅ |
| `test_i00064_reproduces_bug` | `row.raw["doc_id"] != "iw-ai-core:code-index"` | Specific negative ✅ |
| `test_i00064_view_document_link_resolves` | `response.status_code == 200` | Specific value ✅ |
| `test_i00064_view_document_link_resolves` | `"code-index" in response.text or "Code Index" in response.text` | Content check ✅ |
| `test_i00064_orphan_doc_id_is_none` | `row.raw["doc_id"] is None` | Specific value (not just falsy) ✅ |

### 3. End-to-end reach

`test_i00064_view_document_link_resolves`:
- Calls `JobsAggregator.get_job()` to get the actual `row.raw['doc_id']` ✅
- Builds the URL using that value: `f"/project/iw-ai-core/docs/{row.raw['doc_id']}"` ✅
- Uses `client.get()` (FastAPI TestClient) ✅
- Asserts `response.status_code == 200` ✅
- Bonus: asserts doc title appears in response text ✅

### 4. Orphan case

`test_i00064_orphan_doc_id_is_none` covers **both** orphan sub-cases:
- Case 1: job with `doc_id=None` at insert ✅
- Case 2: FK set then doc deleted (ondelete=SET NULL) ✅

Both assert `row.raw["doc_id"] is None` (specific value), not just `not row.raw["doc_id"]` (truthiness).

### 5. Fixture hygiene

- Uses `db_session` (testcontainer-backed) ✅
- `db_session.flush()` used for setup within transaction bounds ✅
- `db_session.commit()` before TestClient read (correct — TestClient needs committed state) ✅
- No `importlib.reload(orch.config)` ✅
- No DB mocks ✅
- `client` fixture pops `IW_CORE_EXPECTED_INSTANCE_ID` from env to avoid live-DB guard ✅

### 6. No leakage between tests

- Each test creates its own `Project`, `ProjectDoc`, and `DocGenerationJob` rows ✅
- Tests use different `public_id` values (`DOC-00001`, `DOC-00098`, `DOC-00099`) to avoid collisions ✅
- No reliance on test ordering ✅

### 7. Naming and structure

- File: `tests/integration/test_i00064_doc_generation_view_document_url.py` ✅
- Function names: `test_i00064_reproduces_bug`, `test_i00064_view_document_link_resolves`, `test_i00064_orphan_doc_id_is_none` — all match `test_i00064_*` pattern ✅
- Each function has a docstring explaining its claim ✅

### 8. No collateral regressions

- `test_i00059_doc_generation_get_job.py` — 4 tests PASSED ✅
- The 6 pre-existing `test_worktree_compose.py` unit test failures are Jinja2 path issues unrelated to this change — confirmed pre-existing on main by S01 report ✅

---

## Test Verification Results

| Test Suite | Result |
|------------|--------|
| `pytest tests/integration/test_i00064_doc_generation_view_document_url.py -v` | **3 passed** ✅ |
| `pytest tests/integration/test_i00059_doc_generation_get_job.py -v` | **4 passed** ✅ |
| `make test-unit` | 2574 passed, **6 failed** (pre-existing `test_worktree_compose.py` failures) ✅ |

---

## Final Verdict

**PASS** — No CRITICAL, HIGH, or MEDIUM_FIXABLE findings. All tests are semantically correct, falsifiable, and follow conventions.

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00064",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "tests_passed": true,
  "test_summary": "3 passed (I-00064 tests), 4 passed (I-00059 regression), 2574 passed / 6 pre-existing failed (unit)"
}
```