# I-00064 S02 Code Review Report (Backend)

## What Was Reviewed

Reviewed S01 implementation by `backend-impl` for work item I-00064 — "Job detail 'View document' link 404s with double project_id prefix".

## Files Changed

| File | Change |
|------|--------|
| `orch/jobs/aggregator.py` | Fix: expose inner `ProjectDoc.doc_id` as `raw["doc_id"]`, add comment to `_fetch_code_mapping` |
| `orch/llm_usage.py` | Unrelated: auto-formatting blank line added by `make format` |

## Pre-Flight Lint & Format

- **`make lint`**: 1 pre-existing violation in `orch/daemon/worktree_compose.py:47` (TC004: `pathlib.Path` imported inside `TYPE_CHECKING`). **Pre-exists on main** — confirmed by stashing changes and running lint against clean main. Not introduced by S01.
- **`make format-check`**: ✅ PASS — 604 files already formatted.

## Test Results

- **`make test-unit`**: 2574 passed, 6 failed
  - 6 failures are **pre-existing** in `tests/unit/daemon/test_worktree_compose.py` — same `Path` import issue (NameError at line 235). Confirmed by running against clean main.
  - 0 failures introduced by S01 changes.
- **`tests/integration/test_i00059_doc_generation_get_job.py`**: 4 passed — confirms the orphan case (`row.raw.get("doc_id") is None`) still works correctly.

## Correctness Checklist

### 1. Bug fix (`_build_doc_generation_raw`)
- ✅ Line 425: `raw["doc_id"]` is set to `inner_doc_id` (the inner `ProjectDoc.doc_id`), NOT `job.doc_id` (the composite FK).
- ✅ Docstring (lines 415-419) explicitly documents the contract.

### 2. Orphan handling
- **`_fetch_doc_generation` (list)**: When `job.doc_id` is set but the `ProjectDoc` row is missing, `doc_inner_ids.get(job.doc_id)` returns `None` → `raw["doc_id"] = None`.
- **`_get_doc_generation` (detail)**: When doc is missing, `inner_doc_id` stays `None` → `raw["doc_id"] = None`.
- ✅ Template guards with `{% if raw.get('doc_id') %}` will hide the link in orphan cases — no broken output.

### 3. No N+1 regression
- ✅ `_fetch_doc_generation` adds `doc_inner_ids` map alongside the existing `doc_titles` map in the same batch query (lines 368-372). No per-row queries added.
- ✅ `_get_doc_generation` captures `inner_doc_id = doc.doc_id` in the same `self._session.get(ProjectDoc, job.doc_id)` lookup already done for the title — single query, no duplication.

### 4. Convention comment in `_fetch_code_mapping`
- ✅ Lines 266-269: Comment explicitly calls out that `raw["doc_id"]` is the composite FK used as a presence flag only, and MUST NOT be used to build a `/docs/{id}` URL. References I-00064.
- ✅ Value unchanged — only the comment was added.

### 5. Other consumers not regressed
- ✅ Grep of `raw["doc_id"]` / `raw.get("doc_id")` / `raw_doc["doc_id"]` shows only `orch/jobs/aggregator.py` as a production consumer.
- ✅ `tests/integration/test_i00059_doc_generation_get_job.py:92` (`row.raw.get("doc_id") is None` for orphans) still holds.

### 6. Type hints & SQLAlchemy idioms
- ✅ `inner_doc_id: str | None = None` is properly annotated in both `_build_doc_generation_raw` (line 407) and the call sites.
- ✅ Batch query uses `select(ProjectDoc).where(ProjectDoc.id.in_(doc_ids))` — no string concatenation, no raw `text()`.

### 7. No scope creep
- ✅ Only `orch/jobs/aggregator.py` modified.
- ✅ No changes to `orch/db/models.py`, `orch/doc_service.py`, `dashboard/routers/docs.py`, or `dashboard/templates/pages/project/job_detail.html`.

## Verdict

**PASS** — The fix is correct, minimal, and introduces no regressions. Mandatory fix count: 0.

## JSON Summary

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00064",
  "reviewed_agent": "backend-impl",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2574 passed, 6 pre-existing failures (test_worktree_compose.py Path import); 4 passed in test_i00059_doc_generation_get_job.py",
  "findings": [],
  "notes": "The 6 test failures and 1 lint error are pre-existing on main and unrelated to this change. The llm_usage.py diff is auto-formatting from make format, not part of the fix."
}
```