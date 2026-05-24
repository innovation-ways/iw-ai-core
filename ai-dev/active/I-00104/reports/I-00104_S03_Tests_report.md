# I-00104 S03 Tests Report

**Step**: S03 — tests-impl
**Work Item**: I-00104 — Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Date**: 2026-05-23
**Completion Status**: complete

---

## What Was Done

Two test files were created to exercise the acceptance criteria for I-00104:

### 1. `tests/unit/test_batch_planner_overlap.py` (5 unit tests)

Pure unit tests against `orch.batch_planner.analyze_dependencies` and `generate_execution_plan_md`. All tests use plain `dict` inputs matching the schema those functions expect.

| Test | AC | Purpose |
|------|-----|---------|
| `test_glob_vs_concrete_file_overlap` | AC1 | `skills/iw-ai-core-testing/**` must overlap `skills/iw-ai-core-testing/SKILL.md`; asserts `"B" in analysis["A"].overlap_with` (semantic) |
| `test_dir_glob_vs_dir_glob_overlap` | AC1 | `a/**` must overlap `a/b/**`; asserts `"B" in analysis["A"].overlap_with` both ways |
| `test_strictly_disjoint_paths_no_overlap` | AC4 | `foo/bar.py` + `baz/qux.py` → `overlap_with == []` on both items; group == 0 |
| `test_cross_batch_overlap_uses_globs_intersect` | AC1 | Batch item `dashboard/static/x.js` vs active `dashboard/**` → `cross_batch_conflicts` contains the conflict entry |
| `test_execution_plan_md_renders_given_max_parallel` | AC3 | Calls `generate_execution_plan_md(..., max_parallel=n)` for n in (3, 7); asserts `"**Max Parallel**: {n}"` in result; GREEN regression-lock |

### 2. `tests/dashboard/test_batch_plan_max_parallel.py` (1 integration test)

End-to-end HTTP integration test via `FastAPI.TestClient`. Uses the testcontainer-backed `db_session` (from `tests/integration/conftest.py` via `tests/dashboard/conftest.py`). Seeds two approved `WorkItem`s with non-overlapping `impacted_paths`, POSTs to the batch-create endpoint, then reads `Batch.execution_plan_md` from the DB.

| Test | AC | Purpose |
|------|-----|---------|
| `test_create_batch_plan_reads_max_parallel` | AC3 | POSTs to `/project/{project_id}/api/batch/create-from-selection`; asserts `"**Max Parallel**: 5" in batch.execution_plan_md` and `"**Max Parallel**: 4" not in batch.execution_plan_md` |

---

## Files Changed

- `tests/unit/test_batch_planner_overlap.py` — new file (5 tests)
- `tests/dashboard/test_batch_plan_max_parallel.py` — new file (1 test)

---

## Test Results

```
tests/unit/test_batch_planner_overlap.py
  test_strictly_disjoint_paths_no_overlap           PASSED
  test_glob_vs_concrete_file_overlap                PASSED
  test_dir_glob_vs_dir_glob_overlap                  PASSED
  test_execution_plan_md_renders_given_max_parallel  PASSED
  test_cross_batch_overlap_uses_globs_intersect       PASSED

tests/dashboard/test_batch_plan_max_parallel.py
  test_create_batch_plan_reads_max_parallel          PASSED
```

6 passed across 2 files.

---

## TDD RED Evidence

The S01 fix (`orch/batch_planner.py` — `globs_intersect` in intra-batch loop; `dashboard/routers/actions.py:_build_plan` — `batch.max_parallel` instead of literal 4) is already on the branch. RED state cannot be reproduced at runtime without reverting shipped code. Analytic RED lines:

| Test | RED Evidence |
|------|-------------|
| `test_glob_vs_concrete_file_overlap` | Pre-fix Phase 3 uses `set(analysis[id_a].affected_files) & set(analysis[id_b].affected_files)`. `skills/iw-ai-core-testing/**` ∩ `skills/iw-ai-core-testing/SKILL.md` is empty (string equality — no glob matching). `analysis["A"].overlap_with == []` → `assert "B" in []` FAILS. |
| `test_dir_glob_vs_dir_glob_overlap` | Same pre-fix bug: `a/**` ∩ `a/b/**` is empty → `assert "B" in analysis["A"].overlap_with` FAILS. |
| `test_cross_batch_overlap_uses_globs_intersect` | Pre-fix Phase 3b uses `set(list(analysis[iid].affected_files)) & set(active_files)`. `dashboard/static/x.js` ∩ `dashboard/**` is empty → `cross_batch_conflicts == []` → assertion FAILS. |
| `test_create_batch_plan_reads_max_parallel` | Pre-fix `_build_plan` passes literal `4` to `generate_execution_plan_md(batch_id, _analysis, 4)`. The created `Batch.max_parallel` is 5. `execution_plan_md` contains `"**Max Parallel**: 4"` → `assert "**Max Parallel**: 5" in ...` FAILS. |

`test_execution_plan_md_renders_given_max_parallel` — **GREEN only** (regression-lock; the helper was always correct — the bug was the caller passing literal 4).

`test_strictly_disjoint_paths_no_overlap` — negative case; passes both before and after fix.

---

## Preflight Quality Gates

- **format**: `uv run ruff format --check .` — ok
- **typecheck**: `uv run mypy ...` — no issues
- **lint**: `uv run ruff check ...` — all checks passed

---

## Notes

- **Route path**: The `create_batch_from_selection` endpoint is registered at `/project/{project_id}/api/batch/create-from-selection` (the `actions` router has `prefix="/project/{project_id}/api"`). Initial test used `/project/{project_id}/batch/...` — corrected.
- **Cross-batch assertion**: `globs_intersect` returns items from the first list that match a glob in the second list. For `NEW-1` (batch item: `dashboard/static/x.js`) vs `ACTIVE-1` (active: `dashboard/**`), the result contains `dashboard/static/x.js`. The assertion was updated accordingly.
- **Batch.execution_plan_md**: `mypy` flagged the column type as `str | None`. Resolved by `plan_md = batch.execution_plan_md or ""`.
- **Test naming**: The helper `_item` parameter was renamed from `id` → `item_id` (and `type` → `item_type`) to avoid shadowing Python builtins, which would have triggered `ruff` rule `A002`.