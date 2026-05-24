# I-00104 S02 — Code Review Report

**Step**: S02
**Agent**: code-review-impl
**Work Item**: I-00104
**Completion Status**: complete

---

## Review Scope

Review of S01's implementation of the two bugs fixed in `orch/batch_planner.py` and `dashboard/routers/actions.py`.

---

## Findings

### ✅ CRITICAL — `& set()` eliminated

```
grep '& set(' orch/batch_planner.py  →  (no output)
```

Zero remaining instances of plain set intersection in the overlap loops. Both Phase 3 (intra-batch) and Phase 3b (cross-batch) now use `globs_intersect`.

### ✅ CRITICAL — `globs_intersect` import present (2 call sites confirmed)

```
grep 'globs_intersect' orch/batch_planner.py
20: from orch.daemon.scope_overlap import globs_intersect  # noqa: E402
211: overlap = globs_intersect(files_a, files_b)
233: overlap = globs_intersect(list(analysis[iid].affected_files), list(active_files))
```

- Line 20: single import, no shadowing ✅
- Line 211: intra-batch loop ✅
- Line 233: cross-batch loop ✅

Both loops are fixed. The "at least two lines" threshold is met (3 including the import).

### ✅ CRITICAL — `max_parallel` literal replaced in actions.py

```python
_md = generate_execution_plan_md(batch_id, _analysis, batch.max_parallel)
_drawio = generate_drawio(batch_id, _analysis, batch.max_parallel)
_png = generate_png(batch_id, _analysis, batch.max_parallel)
```

All three plan-generation calls now pass `batch.max_parallel`. `batch` is in scope (created ~15 lines above the closure).

```
grep -n ', 4)' dashboard/routers/actions.py  →  (no output)
```

No literal `4` remains around the three plan-gen calls.

### ✅ HIGH — Scope discipline

The S01 diff touched only:
- `orch/batch_planner.py` ✅ (expected)
- `dashboard/routers/actions.py` ✅ (expected)

No changes to `orch/daemon/` or other dashboard routers. No new functions added. No schema changes.

### ✅ HIGH — `overlap_with` schema preserved

`analysis[id_a].overlap_with.append(id_b)` and `analysis[id_b].overlap_with.append(id_a)` — both append **item ID strings**, not glob strings. Correct.

The dependency injection line is preserved:
```python
if id_a not in analysis[id_b].depends_on:
    analysis[id_b].depends_on.append(id_a)
```

### ✅ MEDIUM — Import placed correctly (E402 suppress)

The `# noqa: E402` on the `globs_intersect` import is appropriate — the import is inside a module body, not at the top, so ruff would normally flag it. This is acceptable project style.

---

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make lint` (ruff on touched files) | ✅ All checks passed |
| `make type-check` (mypy on touched files) | ✅ Success: no issues found in 2 source files |
| `make format-check` (ruff format) | ✅ 2 files already formatted |

---

## Test Results

Review-only step — no test execution required. S01's report verified the unit test `test_glob_vs_concrete_file_overlap` passes post-fix (RED→GREEN on the glob-vs-concrete-file case).

---

## TDD Red Evidence

n/a — review step.

---

## Blockers

None.

---

## Summary

```
CRITICAL findings:  0
HIGH findings:      0
MEDIUM findings:    0
LOW findings:       0
─────────────────────────
Total findings:     0
```

S01's implementation is clean. All 5 review dimensions pass. The fix correctly replaces plain set intersection with `globs_intersect` in both overlap loops, replaces the three `4` literals with `batch.max_parallel`, and introduces no scope violations, schema changes, or behavioral regressions.

**Recommendation**: proceed to S03 (tests).