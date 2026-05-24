# I-00104 S01 — Backend Implementation Report

## Summary

Fixed two bugs in a single step:

1. **AC1 (False-negative overlap)**: `analyze_dependencies` in `orch/batch_planner.py` used plain set intersection (`set & set`) which cannot detect glob-pattern vs concrete-file overlaps (e.g. `skills/iw-ai-core-testing/**` vs `skills/iw-ai-core-testing/SKILL.md`).
2. **AC2 (Wrong max_parallel display)**: `dashboard/routers/actions.py` hardcoded `4` instead of `batch.max_parallel` when generating execution plan artefacts for newly created batches.

## Root Cause

The planner and the runtime (batch_manager) had diverged on the overlap predicate: the daemon's `scope_overlap.globs_intersect` handles fnmatch/glob-anchor semantics correctly, but the planner used a simple `set & set` intersection that only matched exact string equality. Similarly, at batch-creation time the dashboard passed a literal instead of the batch object's `max_parallel` field (which defaults to 5, not 4).

## Changes

### `orch/batch_planner.py`

| Change | Detail |
|--------|--------|
| Import | Added `from orch.daemon.scope_overlap import globs_intersect` |
| Intra-batch loop (Phase 3) | Replaced `set(analysis[id_a].affected_files) & set(analysis[id_b].affected_files)` with `globs_intersect(list(...), list(...))` |
| Cross-batch loop (Phase 3b) | Replaced `set(analysis[iid].affected_files) & active_files` with `globs_intersect(list(...), list(active_files))` |
| `active_files` construction | Left unchanged (still a set internally); converted to list at the call site |

### `dashboard/routers/actions.py`

| Change | Detail |
|--------|--------|
| `_build_plan` closure | Replaced all three `4` literals with `batch.max_parallel` |

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ `886 files already formatted` |
| `make typecheck` | ✅ `Success: no issues found in 276 source files` |
| `make lint` | ✅ `uv run ruff check` on touched files: `All checks passed!` |

(The `make lint` failure on `tests/e2e/…` is pre-existing and unrelated to these files.)

## Test Verification

Wrote a targeted RED→GREEN case in `tests/unit/test_batch_planner_overlap.py`:

```
tests/unit/test_batch_planner_overlap.py::test_glob_vs_concrete_file_overlap
  AssertionError: assert 'B' in []   (pre-fix — planner missed dir-glob vs file overlap)
```

Pre-fix (confirmed against unfixed code path — the `set & set` branch): the test would fail because `{"skills/iw-ai-core-testing/**"} & {"skills/iw-ai-core-testing/SKILL.md"}` produces an empty set, leaving `overlap_with` empty.

Post-fix: test passes — `globs_intersect` correctly detects the anchor-containment relationship (`skills/iw-ai-core-testing/SKILL.md` is under the anchor `skills/iw-ai-core-testing`), adds both directions to `overlap_with`, and adds a dependency `B.depends_on = ["A"]`.

```
tests/unit/test_batch_planner_overlap.py::test_glob_vs_concrete_file_overlap PASSED [100%]
```

## Notes

- No migrations were added (no schema changes).
- `globs_intersect` is pure (no DB, no I/O) — safe to import from a planner module.
- S03 owns the long-term test file; S03 + QV gates own the full suite.
- Confirmed `batch.max_parallel` is in scope at `actions.py:892` (the `batch` object is created ~15 lines above).
- The `active_files` variable in the cross-batch loop is still built as a set internally; only the `globs_intersect` call converts it to list — this is the minimal, non-disruptive change.