# CR-00053 S03 Backend Report

## What Was Done

Implemented the backend half of CR-00053 — idempotent `iw next-id` via `--idempotency-key` flag:

1. **Modified `allocate_next_id()`** (`orch/cli/id_commands.py:28–138`):
   - Added `idempotency_key: str | None = None` as a **keyword-only** parameter
   - **No key path** (`idempotency_key is None`): unchanged original behavior — increments `id_sequences.next_number` via `SELECT … FOR UPDATE`, writes nothing to `id_allocations`
   - **Key path** (`idempotency_key is not None`):
     - First checks `id_allocations` for existing row `(prefix, idempotency_key)` — returns it if found (idempotent replay)
     - If not found, increments `id_sequences` and inserts into `id_allocations` inside a `SAVEPOINT` (`session.begin_nested()`)
     - If the INSERT raises `IntegrityError` (concurrent same-key INSERT won the race), the savepoint rollback undoes the speculative `id_sequences` increment and the retry loop fetches the winner's row
     - Maximum 3 retry attempts before re-raising

2. **Added `--idempotency-key` Click option** to the `next-id` command (`orch/cli/id_commands.py:170–176`) — threaded through to `allocate_next_id(idempotency_key=idempotency_key)`. Output format is bit-identical whether fresh or replayed.

3. **Created `tests/unit/test_id_allocations.py`** with 5 unit tests (RED-first, all green):
   - `test_no_key_path_unchanged` — AC1: sequential IDs, zero `id_allocations` rows
   - `test_repeat_key_returns_same_id` — AC2: same key returns same ID, no double-increment
   - `test_distinct_keys_distinct_ids` — AC3: two different keys produce two rows
   - `test_same_key_different_prefixes_independent` — AC4: same key on R and F prefixes is independent
   - `test_concurrent_same_key_retries_and_returns_winner` — SAVEPOINT rollback + retry works correctly

## Files Changed

| File | Change |
|------|--------|
| `orch/cli/id_commands.py` | Modified `allocate_next_id()` signature + new Click option |
| `tests/unit/test_id_allocations.py` | New — 5 unit tests covering AC1–AC4 + concurrent-INSERT retry |

## Backwards Compatibility Verification

All three existing call sites use positional arguments and don't pass `idempotency_key` — they all continue to work with the keyword-only default of `None`:

- `orch/cli/batch_commands.py:326` — `allocate_next_id(session, project_id, "BATCH")` ✓
- `dashboard/routers/actions.py:603` — `allocate_next_id(db, project_id, "BATCH")` ✓
- `tests/integration/test_cli_core.py:138` — `allocate_next_id(s, project_id, "I")` ✓

## Test Results

```
tests/unit/test_id_allocations.py::test_no_key_path_unchanged PASSED
tests/unit/test_id_allocations.py::test_repeat_key_returns_same_id PASSED
tests/unit/test_id_allocations.py::test_distinct_keys_distinct_ids PASSED
tests/unit/test_id_allocations.py::test_same_key_different_prefixes_independent PASSED
tests/unit/test_id_allocations.py::test_concurrent_same_key_retries_and_returns_winner PASSED
5 passed, 0 failed
```

## Pre-flight Quality Gates

- **Format**: `make format` — 686 files already formatted ✓
- **Typecheck**: `uv run mypy orch/cli/id_commands.py` — Success: no issues ✓
- **Lint**: `make lint` — All checks passed ✓

## TDD RED Evidence

```
tests/unit/test_id_allocations.py::test_no_key_path_unchanged FAILED
tests/unit/test_id_allocations.py::test_repeat_key_returns_same_id FAILED
tests/unit/test_id_allocations.py::test_distinct_keys_distinct_ids FAILED
tests/unit/test_id_allocations.py::test_same_key_different_prefixes_independent FAILED
tests/unit/test_id_allocations.py::test_concurrent_same_key_retries_and_returns_winner FAILED

TypeError: allocate_next_id() got an unexpected keyword argument 'idempotency_key'
(captured pre-implementation — all 5 tests failed with the same TypeError)
```

## Notes

- The `number` variable in the retry loop shadows the outer scope's `number` (from the no-key path), which is fine since the loop has its own binding
- The concurrent-INSERT test (`test_concurrent_same_key_retries_and_returns_winner`) uses `monkeypatch` on `session.execute` to inject an `IntegrityError` on the first INSERT attempt, verifying the SAVEPOINT rollback and retry logic
- The coverage failure (`total of 8 is less than fail-under=50`) is expected when running only `tests/unit/test_id_allocations.py` in isolation — the test suite's overall coverage is enforced at the full-suite QV gate, not per-file