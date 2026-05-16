# I-00082 S03 — Tests Report

**Work Item**: I-00082 — Fix-cycle agent has no allowed_paths enforcement
**Step**: S03 (tests-impl)
**Status**: Complete

## What Was Done

Extended `tests/integration/test_fix_cycle_scope_enforcement.py` with two new tests covering AC3 and AC4. The existing AC1 test (from S01) was preserved verbatim.

### Tests Added

#### AC3 — `test_i00082_operator_pre_edit_outside_scope_is_preserved`

Verifies that an operator's uncommitted carry-over edit to a file outside `allowed_paths`, made BEFORE the fix cycle starts, is NOT flagged as a scope violation.

Key mechanism tested: `agent_touched = post_cycle_paths - pre_cycle_paths`. Because the operator's file appears in `pre_cycle_paths` (snapshotted before the agent runs), it is excluded from `agent_touched` and therefore not counted as a violation. The cycle returns `FixStatus.completed` and the operator's edit is preserved verbatim.

This directly pins the behavior that would have prevented the CR-00053/S15 revert-mode incident.

Assertions (semantic, not shape):
- `cycle.status == FixStatus.completed`
- `cycle.fix_metadata.get("scope_violations", []) == []`
- `(tmp_path / "operator_file.py").read_text() == "# operator carry-over edit\n"`

#### AC4 — `test_i00082_in_scope_fix_cycle_completes_normally`

Happy-path regression: when the agent edits only files inside `allowed_paths`, the cycle finishes with `FixStatus.completed` and no scope violations.

Assertions (semantic, not shape):
- `cycle.status == FixStatus.completed`
- `cycle.fix_metadata.get("scope_violations", []) == []`
- Belt-and-suspenders check: `"scope_violations" not in fix_metadata OR fix_metadata["scope_violations"] == []`

### Helper Added

`_setup_git_worktree(tmp_path, files)` — shared test helper that initialises a git repo, writes files, and commits them. Avoids repeating the 10-line git setup block from AC1 in each new test.

## Files Changed

- `tests/integration/test_fix_cycle_scope_enforcement.py` — added `_setup_git_worktree` helper + 2 new test functions

## Test Results

```
tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_fix_cycle_escalates_on_out_of_scope_edit PASSED
tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_operator_pre_edit_outside_scope_is_preserved PASSED
tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_in_scope_fix_cycle_completes_normally PASSED

3 passed in 0.06s
```

## Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ok (ruff + template check passed) |
| `make quality` | ok (lint + format-check + mypy all passed, 249 source files) |

## TDD Notes

AC1 RED->GREEN was captured by S01. AC3 and AC4 are regression tests added on top of the already-implemented fix. No runtime RED check is required for these (they are regression/preservation tests, not reproduction tests of a bug).

## Notes

- No DB fixtures needed — `run_fix_cycle()` is the DB-free test entry point from S01's implementation. All tests use `tmp_path` and `monkeypatch` only.
- The `_setup_git_worktree` helper is module-private (not exported to conftest) since it is only used in this file.
- Coverage failure when running this file in isolation is expected (total codebase coverage of 3% vs 50% threshold). The threshold applies to the full integration suite via `make test-integration`, not to individual files.
