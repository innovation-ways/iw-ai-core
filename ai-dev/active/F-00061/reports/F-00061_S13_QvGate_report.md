# F-00061 S13 QV Gate Report — unit-tests

## What was done

Executed `make test-unit` to run the unit-test quality gate for work item F-00061.

## Bug Found and Fixed

**File changed:** `executor/scope_gate.py:74`

The scope gate had a silent bug: violations were correctly computed but never printed to stdout. The loop:
```python
for _v in violations:
    pass
```
was discarding all violation paths. This caused 3 tests to fail with empty `stdout` despite `returncode == 1`.

**Fix:** Changed `_v` to `v` and replaced `pass` with `print(v)` so that each out-of-scope path is printed to stdout as required by the contract.

## Test Results

- **Before fix:** 3 failures, 1330 passed
- **After fix:** 1333 passed, 19 warnings (pre-existing RuntimeWarnings unrelated to this change)

Failing tests were all in `tests/unit/executor/test_scope_gate.py`:
- `TestExactPath::test_exact_path_mismatch_flags_as_violation`
- `TestDirStarStar::test_dir_double_star_blocks_siblings`
- `TestViolationListing::test_violation_listing_preserves_input_order`

## Issues or Observations

The bug was a typo/oversight (`_v` with `pass`) — not a logic error. The scope matching logic itself (`_matches`, `fnmatch`, `**` prefix handling) was correct and untouched. All 14 scope_gate tests now pass.
