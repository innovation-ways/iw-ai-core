# I-00064 S05 Code Review Final Report

## Step: S05 (Final Cross-Step Review)
**Work Item**: I-00064 — Job detail "View document" link 404s with double project_id prefix
**Steps Reviewed**: S01 (backend fix) and S03 (tests)
**Verdict**: PASS

---

## Pre-Review Lint & Format Gate

| Gate | Result | Notes |
|------|--------|-------|
| `make lint` | ⚠️ 1 error | TC004 pre-existing in `orch/daemon/worktree_compose.py:47` (`pathlib.Path` in `TYPE_CHECKING` block). Confirmed pre-existing on main by S01 and S02. NOT introduced by S01 or S03. |
| `make format-check` | ✅ PASS | 605 files already formatted. No violations. |

---

## Test Verification

### Unit Tests
```
make test-unit → 2574 passed, 6 failed
```

The 6 failures are all pre-existing `test_worktree_compose.py` tests (`NameError: name 'Path' is not defined` at `worktree_compose.py:235`). These are caused by the same `pathlib.Path` TC004 lint violation that pre-exists on main — confirmed by S01 report (which stashed changes and ran against clean main). **Zero failures introduced by S01 or S03.**

### Integration Tests
```
pytest tests/integration/test_i00064_doc_generation_view_document_url.py -v → 3 passed
pytest tests/integration/test_i00059_doc_generation_get_job.py -v → 4 passed
```

All 7 tests pass:
- `test_i00064_reproduces_bug` — asserts `row.raw["doc_id"] == "code-index"` (inner id, not composite)
- `test_i00064_view_document_link_resolves` — end-to-end TestClient: `/project/iw-ai-core/docs/{row.raw['doc_id']}` → HTTP 200
- `test_i00064_orphan_doc_id_is_none` — both orphan sub-cases produce `doc_id=None`
- 4 existing I-00059 tests still pass (no regression in other `doc_generation` raw fields)

---

## Cross-Step Integration Review

### 1. Fix and tests agree on the field and convention

- **Fix (S01)**: `_build_doc_generation_raw` now accepts `inner_doc_id: str | None` and sets `raw["doc_id"] = inner_doc_id`. Two call sites:
  - `_fetch_doc_generation` (list): builds `doc_inner_ids` map alongside existing `doc_titles` in the same batch query (line 372), passes to `_build_doc_generation_raw` at line 386.
  - `_get_doc_generation` (detail): does a single `self._session.get(ProjectDoc, job.doc_id)` lookup, captures `inner_doc_id = doc.doc_id` when doc exists, passes to `_build_doc_generation_raw` at line 653.
- **Tests (S03)**: use `JobsAggregator.get_job()` and assert directly on `row.raw["doc_id"]` — same field, same code path.

### 2. The reproduction test exercises the exact changed lines

`test_i00064_reproduces_bug` calls `aggregator.get_job(project_id, JobType.doc_generation, "DOC-00001")`, which dispatches to `_get_doc_generation` → `_build_doc_generation_raw(job, inner_doc_id=...)`. The test asserts `row.raw["doc_id"] == "code-index"` — proving the composite-prefix bug is eliminated.

### 3. Other consumers of `raw["doc_id"]` are unharmed

Grep results for `raw["doc_id"]` / `raw.get("doc_id")` / `raw_doc["doc_id"]` outside `test_i00064`:
- `job_detail.html:124-126` — the fixed "View document" link. Now receives the inner id → correct URL.
- `job_detail.html:85` — "View code map" link for `code_mapping` rows. Uses `raw["doc_id"]` only as a presence check (value is truthy when FK is set); the link URL is `/project/{id}/code` with no doc_id. **Not affected.**
- `job_detail.html:232-234` — research "View research" link. `_fetch_research` already sets `raw["doc_id"] = doc.doc_id` (inner id). **Not affected.**
- `test_i00059_doc_generation_get_job.py:92` — asserts `row.raw.get("doc_id") is None` for orphans. Still passes with the fix (when doc is missing, `inner_doc_id` stays `None`). **Not affected.**

### 4. No new DB query loop introduced

`_fetch_doc_generation` adds `doc_inner_ids` dict alongside the existing `doc_titles` dict in the same batch query (line 370-372). No per-row queries. `_get_doc_generation` reuses the single doc lookup already done for the title.

---

## Acceptance Criteria Verification

| AC | Requirement | Status |
|----|-------------|--------|
| AC1 | Bug fixed: "View document" → HTTP 200 at `/project/{pid}/docs/{inner_doc_id}` | ✅ Verified by `test_i00064_view_document_link_resolves` (TestClient GET returns 200) |
| AC2 | Regression test exists and passes | ✅ 3 tests in `test_i00064_doc_generation_view_document_url.py` — all pass |
| AC3 | Orphan handling unchanged: `raw["doc_id"]` is `None` when FK is null/deleted | ✅ Verified by `test_i00064_orphan_doc_id_is_none` (both sub-cases) and existing I-00059 assertion |

---

## Architecture Compliance

| Rule | Status |
|------|--------|
| Aggregator stays in `orch/jobs/aggregator.py` | ✅ Only file modified by S01 |
| No router or template changes | ✅ Template and docs router untouched |
| SQLAlchemy 2.0 idiom (`select(...).where(...)`) | ✅ Line 370 uses `select(ProjectDoc).where(ProjectDoc.id.in_(doc_ids))` |
| No new DB query loop | ✅ Batch lookup reused |
| Comment in `_fetch_code_mapping` documenting the convention | ✅ Lines 266-269 |

---

## Security & Data Integrity

- No new identifier exposed to users — inner `doc_id` is already visible in the docs catalog URLs.
- Uses ORM (`self._session.get()`, `select(...).where(...)`) — no string-built SQL, no injection risk.
- No authorization or access-control change.

---

## Summary

| Metric | Result |
|--------|--------|
| Files changed (S01) | `orch/jobs/aggregator.py` only |
| Files changed (S03) | `tests/integration/test_i00064_doc_generation_view_document_url.py` (new) |
| CRITICAL findings | 0 |
| HIGH findings | 0 |
| MEDIUM_FIXABLE findings | 0 |
| Unit tests | 2574 passed, 6 pre-existing failures |
| Integration tests | 7 passed (3 new I-00064 + 4 existing I-00059) |
| Lint violations (new) | 0 |
| Format violations (new) | 0 |

---

## JSON Summary

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00064",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "PASS",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2574 unit passed, 6 pre-existing failures (test_worktree_compose.py); 7 integration passed (3 I-00064 + 4 I-00059)",
  "missing_requirements": [],
  "findings": [],
  "notes": "The 6 unit test failures and the TC004 lint error are pre-existing on main (confirmed by S01 by stashing and running against clean main). The fix is minimal, correct, and introduces no regressions. All three acceptance criteria are verified by the new tests."
}
```