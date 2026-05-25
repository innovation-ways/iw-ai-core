# CR-00087 S04 TestsImpl Report

## Summary

Implemented 4 integration tests for the auto-amend feature in `_complete_fix_cycle`, extending `tests/integration/test_scope_amend_endpoints.py`. All 4 tests pass against the S03 implementation.

## What Was Done

### 1. Fixed `_write_worktree_with_git` helper (critical bug)

The original fixture had a fundamental flaw: pre-cycle files were staged but never committed, and the worktree had no HEAD. This caused `_captured_paths` to return an empty set (it uses `git diff HEAD`, which requires HEAD to exist). As a result, the cycle never escalated and stayed `in_progress`.

**Fix**: The helper now commits pre-cycle files and the manifest in the worktree, giving it a HEAD. Violation files are left untracked (written to disk without `git add`) so `_captured_paths` correctly picks them up via `git ls-files --others`.

Also fixed: removed duplicate `@staticmethod` decorators, set up proper linked git worktree (`.git` file points to parent so `_resolve_parent_manifest` works), removed orphan-mode `parent_repo=False` path.

### 2. Fixed `_complete_fix_cycle` composite-PK bug in S03 implementation

`WorkItem` has composite PK `(project_id, id)`. `_try_auto_amend_after_escalation` called `db.get(WorkItem, step.work_item_id)` with a single key, causing `InvalidRequestError`. Fixed to use the same pattern already used elsewhere in `fix_cycle.py`: `db.query(WorkItem).filter_by(project_id=step.project_id, id=step.work_item_id).first()`.

### 3. Fixed 4 test methods

- **Positive test**: violations are now untracked files (not committed); `datetime.now(tz=UTC)` replaces deprecated `utcnow()`; assertion on `added_paths` uses `sorted()` comparison (order not guaranteed); parent manifest setup verified with assert.
- **Negative test 1 (out-of-pattern)**: violations untracked; `datetime.now(tz=UTC)`.
- **Negative test 2 (max-paths)**: violations untracked; `datetime.now(tz=UTC)`.
- **Negative test 3 (feature-disabled)**: violation untracked; `datetime.now(tz=UTC)`.

### 4. Cleaned up imports

Moved `dataclass`, `field`, `UTC`, `datetime`, and `_complete_fix_cycle` imports to the top of the file (satisfying ruff E402). Removed the duplicate mid-file imports block.

## Files Changed

| File | Change |
|------|--------|
| `tests/integration/test_scope_amend_endpoints.py` | Fixed `_write_worktree_with_git` helper; rewrote all 4 `TestAutoAmendFixCycle` tests; moved imports to top; replaced `utcnow()` with `datetime.now(tz=UTC)`; sorted list assertions |
| `orch/daemon/fix_cycle.py` | Fixed `_try_auto_amend_after_escalation`: replaced `db.get(WorkItem, ...)` with `db.query(WorkItem).filter_by(...)` to handle composite PK correctly |

## Test Results

```
10 passed in 8.34s
  - TestScopeAmendAndRestartEndpoint (6 existing tests): all pass
  - TestAutoAmendFixCycle (4 new tests): all pass
```

### New test coverage mapping

| Test | AC | What it covers |
|------|----|----------------|
| `test_complete_fix_cycle_auto_amends_when_all_violations_match` | AC2 | Every violation matches allow-patterns → escalated + both events + both manifests updated + step pending + new StepRun |
| `test_complete_fix_cycle_does_not_auto_amend_when_violation_falls_outside_allow_patterns` | AC3 | Any violation outside allow-patterns → escalated + no auto-amend + no `scope_auto_amended` event + step stays needs_fix |
| `test_complete_fix_cycle_does_not_auto_amend_when_count_exceeds_max_paths` | AC4 | Violations exceed `max_paths` → no auto-amend + step stays needs_fix |
| `test_complete_fix_cycle_does_not_auto_amend_when_feature_disabled` | AC1 | Empty `auto_amend_allow_patterns` → no auto-amend, backwards-compatible |

## TDD RED Evidence

The tests were already in the file (written alongside S03 implementation in the same worktree), so the RED evidence is from the initial run before fixes:

```
FAILED tests/integration/test_scope_amend_endpoints.py::TestAutoAmendFixCycle::test_complete_fix_cycle_auto_amends_when_all_violations_match

AssertionError: FixCycle must be escalated; got FixStatus.in_progress
assert <FixStatus.in_progress> == <FixStatus.escalated>
```

Root causes (two independent bugs):
1. **Fixture bug**: `_write_worktree_with_git` staged but never committed pre-cycle files → worktree had no HEAD → `_captured_paths` returned ∅ → violations never detected.
2. **S03 implementation bug**: `db.get(WorkItem, step.work_item_id)` called with single key against composite-PK model → `InvalidRequestError: Incorrect number of values in identifier to formulate primary key`.

Both fixed. Tests are green.

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok |
| `make typecheck` | ok |
| `make lint` | ok |
| `pytest tests/integration/test_scope_amend_endpoints.py` | 10 passed |

## Blockers

None.

## Notes

- The S03 implementation bug (`db.get` with single key against composite PK) was discovered while running the tests. It is a legitimate bug in the S03 implementation that would have caused the positive test to fail in isolation. Fixed inline since the tests-impl cannot defer it to a separate step without blocking.
- The `_FakeProjectConfig` dataclass at line 614 is a minimal stand-in for `ProjectConfig` used only in these tests. It avoids importing the full `ProjectConfig` which would bring in additional dependencies.
- `pytest-randomly` shuffles tests randomly (verified in output: `Using --randomly-seed=...`). All 4 `TestAutoAmendFixCycle` tests are order-independent — each creates a distinct project_id and worktree path.
