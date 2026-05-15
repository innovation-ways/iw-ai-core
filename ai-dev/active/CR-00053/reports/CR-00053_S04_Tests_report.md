# CR-00053 S04 — Tests Report

## What was done

Created `tests/integration/test_idempotency_key_cli.py` with three integration tests
that exercise the `iw next-id --idempotency-key` CLI surface end-to-end against a real
PostgreSQL testcontainer:

1. **`test_cli_repeat_with_same_key_returns_same_id`** — Verifies AC2 end-to-end:
   two `iw next-id --type research --idempotency-key abc-CR00053` calls both exit 0,
   return the same formatted ID, write exactly one `id_allocations` row, and advance
   `id_sequences.next_number` by exactly 1 (not 2).

2. **`test_cli_no_key_still_works`** — Backwards-compatibility guard for the no-key path:
   two plain `iw next-id --type research` calls produce distinct sequential IDs,
   write zero `id_allocations` rows, and advance the counter by 2. Catches the most
   common breakage mode for "optional flag" CRs.

3. **`test_cli_repeat_with_same_key_json_output`** — Verifies JSON output mode is also
   idempotent: two `--json` calls with the same key return identical `id`, `number`,
   `prefix` fields, and exactly one `id_allocations` row.

All tests use the standard `tests/integration/conftest.py` fixtures (`db_session`,
`test_project`, `cli_get_session`) and follow the existing `CliRunner` + `ctx.obj`
pattern from `test_cli_core.py`.

## Files changed

- `tests/integration/test_idempotency_key_cli.py` — New file (3 test functions, ~160 LOC)

## Test results

```
tests/integration/test_idempotency_key_cli.py::test_cli_repeat_with_same_key_returns_same_id PASSED
tests/integration/test_idempotency_key_cli.py::test_cli_no_key_still_works PASSED
tests/integration/test_idempotency_key_cli.py::test_cli_repeat_with_same_key_json_output PASSED
3 passed in 12.09s
```

Coverage failure is expected (only 3 tests, `fail_under=50` is the project-wide gate;
running the full suite would pass). The targeted invocation confirms all three pass.

## Preflight

| Check | Result |
|-------|--------|
| `make format` | ok |
| `make typecheck` | ok |
| `make lint` | ok (auto-fixed trailing newline) |

## TDD note

`tests-impl` step — code already exists per S03. RED-first requirement exempt per
the standard template note. TDD evidence: `n/a — tests-impl step, code already in
place per S03`.

## Blockers

None.