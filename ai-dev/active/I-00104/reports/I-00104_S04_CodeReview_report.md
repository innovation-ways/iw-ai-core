# I-00104 S04 Code Review Report

**Step**: S04 — code-review-impl
**Work Item**: I-00104 — Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Date**: 2026-05-23
**Completion Status**: complete

---

## What Was Reviewed

S03's two test files were reviewed against the IW AI Core testing red-flag checklist:

1. `tests/unit/test_batch_planner_overlap.py` — 5 unit tests
2. `tests/dashboard/test_batch_plan_max_parallel.py` — 1 dashboard integration test

The review covered assertion semantics, cross-batch path coverage, negative cases, endpoint correctness, testcontainer isolation, TDD RED evidence, and `xfail`/`skip` hygiene.

---

## Review Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

**TDD RED evidence: acceptable analytic form used for 3 of 4 failing tests**

The S01 fix (`globs_intersect` replacement + `batch.max_parallel` correction) is already applied on the branch, so runtime RED reproduction is not possible without reverting. S03 correctly uses the **design-time analytic form**: pre-fix code is read, the specific failing assertion is identified, and the failure line is pasted. This is explicitly accepted per the review scope ("Acceptable forms: real captured `AssertionError`, OR the design-time analytic form").

However, the S03 report groups `test_execution_plan_md_renders_given_max_parallel` under RED evidence as "GREEN only (regression-lock; the helper was always correct)". This is correct — the test was always green because the bug was in the *caller*, not the helper. Documenting this as GREEN (not RED) with the reason clearly stated is appropriate.

### LOW

**The `test_execution_plan_md_renders_given_max_parallel` comment is slightly misleading in one file**

The test file `test_batch_planner_overlap.py` comments say "This is a GREEN regression-lock: the helper was always correct; the bug was the caller." The word "GREEN" here can confuse reviewers about whether the test needs RED evidence. It doesn't — it's a regression-lock test, and S03 correctly documents it as such. This is a documentation clarity note, not a functional issue.

---

## Checklist Verification

### 1. Semantic assertions ✅

- `test_glob_vs_concrete_file_overlap`: `"B" in analysis["A"].overlap_with` — semantic ✅
- `test_dir_glob_vs_dir_glob_overlap`: `"B" in analysis["A"].overlap_with` — semantic ✅
- `test_strictly_disjoint_paths_no_overlap`: `analysis["A"].overlap_with == []` (empty list identity check) — correct negative assertion ✅
- `test_cross_batch_overlap_uses_globs_intersect`: `len(entry) == 1` + batch_id/active_id/overlap_globs field checks — semantic ✅
- `test_create_batch_plan_reads_max_parallel`: `"**Max Parallel**: 5" in plan_md` (exact substring with markdown formatting) ✅
- `test_create_batch_plan_reads_max_parallel`: `"**Max Parallel**: 4" not in plan_md` — negative assertion present ✅ (defends against regressions)
- `test_execution_plan_md_renders_given_max_parallel`: `f"**Max Parallel**: {n}" in md` for n=3,7 ✅

### 2. Cross-batch case exercises the cross-batch path ✅

`test_cross_batch_overlap_uses_globs_intersect` passes a non-empty `active_items_data` argument to `analyze_dependencies`. The active item declares `impacted_paths: ["dashboard/**"]`; the batch item declares `impacted_paths: ["dashboard/static/x.js"]`. This is a genuine cross-batch call, not intra-batch reuse.

### 3. Disjoint case ✅

`test_strictly_disjoint_paths_no_overlap` is present and asserts `overlap_with == []` for both items, AND asserts `group == 0` (parallel group). Defends against `globs_intersect` matching too aggressively.

### 4. Batch-create endpoint URL ✅

The test POSTs to `/project/{project_id}/api/batch/create-from-selection`. Verified against `dashboard/routers/actions.py`:
- `router = APIRouter(prefix="/project/{project_id}/api")` (line 53) ✅
- `@router.post("/batch/create-from-selection")` (line 757) ✅
- Full path: `/project/{project_id}/api/batch/create-from-selection` ✅

Value-variation test correctly lives in the unit file (`test_execution_plan_md_renders_given_max_parallel`) because `create-from-selection` hardcodes `max_parallel=5` — a `max_parallel=3` dashboard test is structurally impossible through that endpoint.

### 5. Testcontainer isolation ✅

- `test_create_batch_plan_reads_max_parallel` uses `db_session` fixture from `tests/integration/conftest.py` (testcontainers-backed) ✅
- The `db_session` fixture is re-exported in `tests/dashboard/conftest.py` so it is visible to the dashboard test collector ✅
- No `postgresql://...5433` strings in the test files ✅ (The hits in `test_live_db_guard_reproduction.py` and `test_live_db_guard.py` are *testing the guard itself*, not using live DB in other tests)

### 6. TDD RED evidence ✅

Analytic RED lines present for both files:

| Test | RED Evidence |
|------|-------------|
| `test_glob_vs_concrete_file_overlap` | Pre-fix: plain `set & set` on strings → `skills/iw-ai-core-testing/**` ∩ `skills/iw-ai-core-testing/SKILL.md` is empty → `assert "B" in []` FAILS |
| `test_dir_glob_vs_dir_glob_overlap` | Pre-fix: same plain set intersection → `a/**` ∩ `a/b/**` is empty → FAILS |
| `test_cross_batch_overlap_uses_globs_intersect` | Pre-fix: cross-batch loop uses `set & set` → `dashboard/**` ∩ `dashboard/static/x.js` is empty → FAILS |
| `test_create_batch_plan_reads_max_parallel` | Pre-fix: `_build_plan` passes literal `4` → markdown says `"**Max Parallel**: 4"` → `assert "**Max Parallel**: 5"` FAILS |

`test_execution_plan_md_renders_given_max_parallel` — correctly documented as GREEN (regression-lock; helper was always correct, bug was in caller). No RED evidence needed.

`test_strictly_disjoint_paths_no_overlap` — negative case; passes both before and after.

### 7. No `xfail`/`skip` ✅

No test in either file uses `xfail` or `skip`. 6 tests all run to completion.

---

## Files Changed

None — this is a review-only step. The test files were reviewed in place.

---

## Test Results

```
tests/unit/test_batch_planner_overlap.py
  test_glob_vs_concrete_file_overlap                PASSED
  test_dir_glob_vs_dir_glob_overlap                  PASSED
  test_strictly_disjoint_paths_no_overlap            PASSED
  test_cross_batch_overlap_uses_globs_intersect      PASSED
  test_execution_plan_md_renders_given_max_parallel   PASSED

tests/dashboard/test_batch_plan_max_parallel.py
  test_create_batch_plan_reads_max_parallel           PASSED
```

6 passed. (Coverage failure is expected — `fail-under=50` is a project-wide gate; the new tests don't cover enough of the codebase individually. This is pre-existing and unrelated to I-00104.)

---

## S03 Diff Verification

The tests written by S03 correctly target the S01 fix:

1. **`orch/batch_planner.py`** — S01 replaced `set(analysis[id_a].affected_files) & set(analysis[id_b].affected_files)` with `globs_intersect(list(...), list(...))` in both the intra-batch loop (line ~211) and cross-batch loop (line ~233). S03's 4 overlap tests exercise these two loops.

2. **`dashboard/routers/actions.py`** — S01 replaced the three literal `4` arguments in `_build_plan` (line ~892-894) with `batch.max_parallel`. S03's `test_create_batch_plan_reads_max_parallel` exercises this path end-to-end.

3. **`generate_execution_plan_md`** — unchanged by S01 (the bug was the caller). S03's `test_execution_plan_md_renders_given_max_parallel` regression-locks this function directly.

---

## Summary

| Category | Result |
|----------|--------|
| Semantic assertions | ✅ All specific, none vacuous |
| Cross-batch path | ✅ Non-empty `active_items_data` passed |
| Disjoint negative case | ✅ Present with `overlap_with == []` |
| Endpoint URL | ✅ Correct `/project/{project_id}/api/batch/create-from-selection` |
| Testcontainer isolation | ✅ `db_session` used; no live-DB strings |
| TDD RED evidence | ✅ Analytic form present for all RED-able tests |
| No `xfail`/`skip` | ✅ All 6 tests run to completion |
| Finding count | 0 CRITICAL · 0 HIGH · 0 MEDIUM · 1 LOW |

---

## Subagent Result

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00104",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "6/6 passed (unit: 5, dashboard: 1); no live-DB strings",
  "tdd_red_evidence": "analytic form present for all 4 RED-able tests; GREEN regression-lock documented correctly for test_execution_plan_md_renders_given_max_parallel; disjoint case documented as GREEN (negative; passes both before and after)",
  "blockers": [],
  "notes": "0 CRITICAL / 0 HIGH / 0 MEDIUM / 1 LOW (comment clarity on regression-lock test naming)"
}
```