# CR-00088 S01 — Backend Implementation Report

## Step Summary

**Agent**: backend-impl  
**Scope**: Partition semantics in `classify_conflicts()` + `deferred_files` field on `ClassificationResult`  
**Files changed**: `orch/daemon/auto_merge.py`, `tests/unit/test_auto_merge_classifier.py`

---

## What Was Done

### 1. Extended `ClassificationResult` dataclass (~line 266)

Added `deferred_files: tuple[str, ...] = ()` with a trailing default value so all ~6 existing call sites inside `classify_conflicts()` remain valid without modification.

### 2. Changed the allowlist gate (step 6) from all-or-nothing to partition semantics (~line 489)

Replaced the single-pass collect-then-skip-if-non-empty logic with:

- Two lists: `eligible_files` and `deferred_files` built in a single pass preserving input order
- If `eligible_files` is empty → `skipped_reason="not_allowlisted"` + `deferred_files` populated (preserves today's skip behaviour)
- If `eligible_files` is non-empty → `skipped_reason=None` + both lists populated (LLM invoked only for `eligible_files`)

### 3. Updated docstring on `classify_conflicts()` (~line 367)

Replaced step 6 description to reflect the new partition semantics.

### 4. Added 4 RED-first tests to `tests/unit/test_auto_merge_classifier.py`

- `test_partial_allowlist_returns_partition` — two files, one in allowlist → partition correctly
- `test_all_deferred_keeps_skip_reason` — no file in allowlist → deferred = full input, reason = not_allowlisted
- `test_refuselist_wins_over_partial_allowlist` — refuse-list short-circuits before partition, `deferred_files=()`
- `test_deferred_files_default_empty` — constructor without `deferred_files` kwarg defaults to `()`

### 5. Tightened existing test `test_non_allowlisted_file`

Added assertion `assert result.deferred_files == ("dashboard/static/foo.js",)` to match new partition behaviour.

---

## TDD RED Evidence

The four new tests were run against unmodified code before the production change. All failed as expected:

```
tests/unit/test_auto_merge_classifier.py::test_partial_allowlist_returns_partition FAILED
  AssertionError: assert () == ('docs/foo.md',)

tests/unit/test_auto_merge_classifier.py::test_deferred_files_default_empty FAILED
  AttributeError: 'ClassificationResult' object has no attribute 'deferred_files'

tests/unit/test_auto_merge_classifier.py::test_all_deferred_keeps_skip_reason FAILED
  AttributeError: 'ClassificationResult' object has no attribute 'deferred_files'

tests/unit/test_auto_merge_classifier.py::test_refuselist_wins_over_partial_allowlist FAILED
  AttributeError: 'ClassificationResult' object has no attribute 'deferred_files'
```

After applying the dataclass field and partition logic, all 22 tests in the file pass (4 new + 18 existing with 1 assertion tightened).

---

## Acceptance Criteria Verified

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `deferred_files` field with default `()` added to `ClassificationResult` | ✅ |
| AC2 | Partial allowlist: at least one eligible file → `skipped_reason is None` + `deferred_files` populated | ✅ |
| AC3 | All deferred → `skipped_reason == "not_allowlisted"` + `deferred_files` = full input | ✅ |
| AC4 | Refuse-list precedence unchanged (short-circuits before partition) | ✅ |
| AC5 | All 4 new tests pass; all 22 tests in file pass | ✅ |

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make test-assertions` | ✅ Baseline-compatible (1 pre-existing mypy violation on `_make_config` return type annotation; unchanged from baseline) |
| `make typecheck` | ✅ `orch/daemon/auto_merge.py` — zero errors |

> **Note on mypy pre-existing violation**: `_make_config` in `test_auto_merge_classifier.py` lacks a return type annotation. This violation existed before this step (confirmed via `git stash` + `mypy`). It is not introduced by this step and is tracked for cleanup separately.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/auto_merge.py` | `deferred_files` field on `ClassificationResult`; partition logic in step 6; updated docstring |
| `tests/unit/test_auto_merge_classifier.py` | 4 new tests (RED-first); tightened `test_non_allowlisted_file` assertion |

---

## Scope Boundaries (Not Touched)

- `attempt_resolution()` — S02's job
- `merge_queue.py` — S02's job
- `executor/auto_merge.toml` — no config change
- `executor/worktree_commit.sh` — no bash script change
- Event metadata threading — S02's job
- Integration tests — S02/S03's job