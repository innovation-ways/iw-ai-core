# I-00071 S03 Tests Report

## What Was Done

Wrote reproduction and regression unit tests for I-00071 (scope-overlap gate over-blocks items due to backtick-wrapped paths and leading-slash test marker).

### Test Coverage Added

**`tests/unit/test_design_doc_parser.py`** — `TestImpactedPathsBacktickStripping` (appended to existing file):
- `test_strips_surrounding_code_span_backticks_in_bullet_lines` — verifies bullet items wrapped in markdown backticks are stored bare
- `test_strips_surrounding_code_span_backticks_in_fenced_code_block` — verifies backticks inside fenced code blocks are stripped
- `test_bare_paths_without_backticks_still_parse_unchanged` — regression: backtick stripping must NOT corrupt bare paths
- `test_mixed_wrapped_and_bare_paths` — a mix of wrapped and bare paths in the same section

**`tests/unit/daemon/test_scope_overlap.py`** — `TestIsTestPath` parametrize extended with I-00071 cases:
- `("tests/dashboard/test_x.py", True)`, `("test/foo.py", True)`, `("__tests__/bar.py", True)`, `("tests/conftest.py", True)`
- Wider regression coverage: `("pytest/conftest.py", True)`, `("nested/path/__tests__/file.py", True)`, `("tests/integration/test_x.py", True)`, `("__tests__/integration/foo.py", True)`, `("helpers/test_utils.py", False)`

**`tests/unit/daemon/test_scope_overlap.py`** — `TestI00071RegressionBatch00078` (new class):
- `test_two_items_both_only_test_files_under_same_dir_do_not_block` — verifies two items declaring only test files under `tests/dashboard/` do not block each other via sibling-directory check
- `test_mixed_test_and_prod_paths_test_only_candidate_still_not_blocked` — candidate with only test paths, in-flight with mixed paths, must not be blocked when prod paths don't share a parent with the test path
- `test_non_test_sibling_still_blocks` — sanity: production-code sibling overlap is still detected

**`tests/unit/test_batch_planner_dependencies.py`** — parity test added near existing `_is_test_path` tests:
- `test_batch_planner_is_test_path_matches_scope_overlap` — verifies `batch_planner._is_test_path` and `scope_overlap.is_test_path` stay in lock-step across all markers

### Pre-flight Quality Gates

- **`make format`**: 1 file reformatted (`tests/unit/test_batch_planner_dependencies.py`)
- **`make typecheck`**: Zero errors
- **`make lint`**: Zero errors (2 x100-format `%r` assertions auto-fixed to f-strings)

## Test Results

```
2603 passed, 2 failed, 4 skipped, 5 xfailed, 1 xpassed
```

### Passing (I-00071 coverage confirmed)

- `test_design_doc_parser.py::TestImpactedPathsBacktickStripping` — 4/4 PASS (backtick stripping works)
- `test_scope_overlap.py::TestIsTestPath` — 23/23 PASS (is_test_path recognizes relative test paths)
- `test_batch_planner_dependencies.py::test_batch_planner_is_test_path_matches_scope_overlap` — 8/8 PASS (parity)
- `test_scope_overlap.py::TestFindBlockingItems` — all PASS

### Failing (known — logic bug in production code, not test code)

**`TestI00071RegressionBatch00078::test_two_items_both_only_test_files_under_same_dir_do_not_block`** —

The sibling check in `find_blocking_items` (line 158-159) runs on **raw (unstripped) paths** from `candidate_paths` and `in_flight_paths`. Even though `is_test_path` correctly classifies `tests/dashboard/test_*.py` as test paths (and the parametrize tests confirm this), the sibling check fires before `_strip_test_globs` is applied:

```python
for cp in candidate_paths:       # cp = "tests/dashboard/test_...py"
    for ifp in in_flight_paths:  # ifp = "tests/dashboard/test_live_db_...py"
        if _same_parent(cp, ifp): # True (both under tests/dashboard/)
            intersecting = [cp]   # ← incorrectly fires
```

The sibling check correctly strips test paths via `globs_intersect`, but then immediately re-examines raw paths. Both tests in `TestI00071RegressionBatch00078` fail for this reason.

### Sanity check

`test_non_test_sibling_still_blocks` — PASS (production-code sibling overlap still detected correctly).

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/test_design_doc_parser.py` | Appended `TestImpactedPathsBacktickStripping` (4 tests) |
| `tests/unit/daemon/test_scope_overlap.py` | Extended `TestIsTestPath` parametrize with I-00071 cases; appended `TestI00071RegressionBatch00078` (3 tests); fixed 2 x100-format assertions |
| `tests/unit/test_batch_planner_dependencies.py` | Appended parity test `test_batch_planner_is_test_path_matches_scope_overlap` |

## Blockers

**S01 production code has a logic bug in `find_blocking_items`** (lines 155-163 in `orch/daemon/scope_overlap.py`):
The sibling-directory check applies `_same_parent` to raw (unfiltered) paths, bypassing `_strip_test_globs`. The fix in S01 correctly extended `is_test_path` to recognize relative test paths, and `_strip_test_globs` correctly removes test paths from `globs_intersect` comparisons — but the sibling check re-uses the original raw lists, meaning test paths can still trigger sibling-overlap even when they should have been excluded.

**Fix required**: Apply `_strip_test_globs` to the sibling check, or pass already-stripped paths to the sibling check. Example:

```python
# In find_blocking_items, after globs_intersect returns []:
candidate_non_test = _strip_test_globs(candidate_paths)
in_flight_non_test = _strip_test_globs(in_flight_paths)
for cp in candidate_non_test:
    for ifp in in_flight_non_test:
        if _same_parent(cp, ifp):
            intersecting = [cp]
```

The tests correctly expose the bug — they are valid as written and will pass once S01's production code is corrected.

## Notes

- All 4 parser backtick-stripping tests pass — the `_strip_code_span` fix works correctly.
- All 23 `is_test_path` parametrization cases pass — the prefix check for relative test paths works correctly.
- The parity test (8 cases) all pass — `batch_planner._is_test_path` and `scope_overlap.is_test_path` are in lock-step.
- The 2 failing `TestI00071RegressionBatch00078` tests expose a **separate logic bug** in `find_blocking_items` that was not addressed by S01.
- S01 report said "2 failed, 2579 passed" — the regression tests didn't exist in S01's test run, so the failure count increased by 2 in this step.