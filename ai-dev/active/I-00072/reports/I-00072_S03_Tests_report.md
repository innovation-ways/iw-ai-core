# I-00072 S03 Tests Report

## Summary

Implemented test coverage for the `iw merge-queue retry-merge` CLI fix (I-00072). The tests verify that the CLI correctly accepts items in all four `OPERATOR_RECOVERABLE_MERGE_STATUSES` statuses and properly rejects legacy `failed` rows without merge-failure notes.

## Test Placement Decision

Tests were split across two files based on DB dependency:

- **`tests/unit/test_merge_queue_cli.py`** — import-only tests (parity, enum-coverage) that can run without a database. No testcontainer required.
- **`tests/integration/test_merge_queue_retry.py`** — full DB-backed regression tests that verify status flips and audit events. Requires testcontainer.

Rationale: The `live_db_guard` in `orch.db.session` raises `LiveDbConnectionRefusedError` when the CLI imports `dashboard.routers.actions` or `orch.cli.merge_queue_commands` from a unit-test context that has `IW_CORE_TEST_CONTEXT` set but no testcontainer session. Keeping import-only assertions in unit tests and DB-backed tests in integration tests avoids this. See the `tests/CLAUDE.md` gotcha about dashboard imports in unit tests.

## What Was Added

### `tests/unit/test_merge_queue_cli.py` (new tests)

**`TestRetryMergeParityOnly`** (new class):
- `test_i00072_cli_imports_recoverable_status_constant` — Identity check that `orch.cli.merge_queue_commands` imports `OPERATOR_RECOVERABLE_MERGE_STATUSES` by reference (not a copy). Also asserts the frozenset has exactly the four expected members.
- `test_i00072_every_recoverable_status_has_a_regression_case` — Enum-coverage assertion: adding a 5th status to the constant without a corresponding regression test fails loudly.

**Existing tests unchanged**: `TestUnfreezeRefusesWithoutAck`, `TestUnfreezeRefusesInAgentContext`, `TestStatusJsonOutput`, `TestUnfreezeSuccess`.

### `tests/integration/test_merge_queue_retry.py` (already existed, verified)

The integration file already contains the full regression suite written by S01/S02:
- `TestRetryMergeAcceptsRecoverableStatuses` — parametrised over all four statuses (`merge_failed`, `migration_invalid`, `migration_rebase_failed`, `migration_rolled_back`); verifies exit code 0, status flips to `completed`, `merge_retry_requested` event written.
- `TestRetryMergeLegacyBackCompat` — two cases: legacy `failed` + merge-notes (accept, exit 0); legacy `failed` + non-merge notes (reject, exit non-zero, error mentions "Merge failed" and "item restart").
- `TestRetryMergeWorktreeMissing` — verifies a `merge_failed` item with a missing worktree is rejected with "Worktree not found" and non-zero exit.
- `TestRetryMergeParity` — identity check that CLI and dashboard modules both import `OPERATOR_RECOVERABLE_MERGE_STATUSES` from the same source.

## Preflight Results

| Check | Result | Notes |
|-------|--------|-------|
| `make format` | `fixed` | ruff auto-formatted `tests/unit/test_merge_queue_cli.py` |
| `make typecheck` | `ok` | Zero type errors in `orch/` and `dashboard/` |
| `make lint` | `ok` for my files | Pre-existing E501 errors in `tests/integration/test_f00055_workflow_fixture.py` are out of scope |

## Test Results

- **`make test-unit`** — **2648 passed, 4 skipped, 5 xfailed, 1 xpassed** (all pre-existing)
- `tests/unit/test_merge_queue_cli.py` — **11 passed** (2 new + 9 pre-existing)
- `tests/integration/test_merge_queue_retry.py` — would be tested by `make test-integration` (testcontainer not available in current environment, but fixture wiring is verified correct)

## Coverage

- **Reproduction test** (`merge_failed` → accepted, status flips, audit event): in `tests/integration/test_merge_queue_retry.py::TestRetryMergeAcceptsRecoverableStatuses`
- **Four recoverable status regression cases**: parametrised in `TestRetryMergeAcceptsRecoverableStatuses` (all four enum members as separate rows)
- **Legacy back-compat**: `TestRetryMergeLegacyBackCompat` (2 cases)
- **Worktree-missing case**: `TestRetryMergeWorktreeMissing`
- **CLI/dashboard parity**: `TestRetryMergeParity` + `TestRetryMergeParityOnly::test_i00072_cli_imports_recoverable_status_constant`
- **Enum-coverage assertion**: `TestRetryMergeParityOnly::test_i00072_every_recoverable_status_has_a_regression_case`

## Notes

- The integration test file (`tests/integration/test_merge_queue_retry.py`) was pre-written by the S01/S02 backend work. My S03 contribution was adding the import-based parity and enum-coverage assertions to `tests/unit/test_merge_queue_cli.py`.
- `sample_worktree_path` fixture added to `tests/integration/conftest.py` in a prior session; this was already present and used by both `test_merge_queue_retry.py` and the new unit tests.

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/test_merge_queue_cli.py` | +63 lines: `TestRetryMergeParityOnly` class with 2 new tests; docstring updated |
| `tests/integration/test_merge_queue_retry.py` | Pre-existing — verified coverage is complete |
| `tests/integration/conftest.py` | `sample_worktree_path` and `cli_get_session` fixtures verified present |