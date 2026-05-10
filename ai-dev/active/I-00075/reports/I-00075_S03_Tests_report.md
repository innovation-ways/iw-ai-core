# I-00075 S03 Tests Report

## What Was Done

Authored `tests/integration/test_i00075_fix_cycle_fixture.py` — a regression net of 4 integration tests that verify the S01 fix-cycle fixture (`ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py`) seeds the correct rows and is idempotent.

## Files Changed

| File | Type | Change |
|------|------|--------|
| `tests/integration/test_i00075_fix_cycle_fixture.py` | Created | 4 new integration tests |
| `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` | Modified | Fixed insert-order bug (WorkItem must flush before BatchItem) and added missing `WorkItemStatus` + `WorkItemPhase` imports |

## Tests Authored

1. **`test_i00075_fixture_file_exists`** — File-presence guard; proves the fixture file exists at the exact path the daemon resolves.

2. **`test_i00075_fixture_seeds_at_least_one_fix_cycle`** — Semantic assertion verifying exactly 2 `FixCycle` rows exist with cycle_numbers `{1, 2}`, both on `S02`, both with `trigger_type=code_review` and `status=completed`.

3. **`test_i00075_fixture_idempotent`** — Running the fixture twice on the same session produces identical row counts (no duplicate inserts, no IntegrityError).

4. **`test_i00075_fixture_seeds_workflow_steps`** — Verifies exactly 3 `WorkflowStep` rows for I-99001 with correct `step_id` sequence (`S01`, `S02`, `S03`), correct `step_type` order, and all `status=completed`.

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | `ok` — 662 files formatted |
| `make typecheck` | `ok` — no issues in 239 source files |
| `make lint` | `ok` — All checks passed! |

## Test Results

```
tests/integration/test_i00075_fix_cycle_fixture.py::test_i00075_fixture_file_exists PASSED
tests/integration/test_i00075_fix_cycle_fixture.py::test_i00075_fixture_seeds_at_least_one_fix_cycle PASSED
tests/integration/test_i00075_fix_cycle_fixture.py::test_i00075_fixture_idempotent PASSED
tests/integration/test_i00075_fix_cycle_fixture.py::test_i00075_fixture_seeds_workflow_steps PASSED

4 passed, 0 failed
```

## Fixture Bugs Found and Fixed

During test authoring, two bugs were discovered in the S01-authored fixture file:

1. **Missing imports**: `WorkItemStatus` and `WorkItemPhase` were used in the `WorkItem` constructor but not imported.

2. **Insert-order violation**: The fixture flushed `BatchItem` (which has FK to `WorkItem`) before flushing `WorkItem`, causing `IntegrityError: ForeignKeyViolation` at runtime. Fixed by reordering to flush `WorkItem` before `BatchItem`.

## Notes

- The tests use the existing `db_session` fixture from `tests/integration/conftest.py` and a new local `iw_core_project` fixture that creates the `iw-ai-core` project row (required because the fixture inserts rows with `project_id='iw-ai-core'`).
- All assertions follow the "semantic correctness over shape checking" rule — they verify specific values (cycle numbers `{1, 2}`, trigger types, step types), not just that rows exist.
