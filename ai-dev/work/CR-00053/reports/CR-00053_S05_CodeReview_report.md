# CR-00053 S05 — Code Review Report

**Work Item**: CR-00053 — Idempotent `iw next-id` via `--idempotency-key` flag
**Step**: S05 — Code review (reviewing S01/S03/S04)
**Agent**: code-review-impl
**Status**: ✅ PASS

---

## What Was Reviewed

Review of S01 (database-impl), S03 (backend-impl), and S04 (tests-impl) for CR-00053.

### Files Changed

| Step | File | Change |
|------|------|--------|
| S01 | `orch/db/models.py` | Added `IdAllocation` ORM model |
| S01 | `orch/db/migrations/versions/7ef0b420c58f_…py` | New migration (committed) |
| S03 | `orch/cli/id_commands.py` | Modified `allocate_next_id()` + new Click option |
| S04 | `tests/unit/test_id_allocations.py` | 5 unit tests (new) |
| S04 | `tests/integration/test_idempotency_key_cli.py` | 3 integration tests (new) |

### Verification Performed

- Migration commit confirmed: `137f8ae9 Add id_allocations table for idempotent next-id (CR-00053)`
- `make migration-check`: all 3 round-trip tests pass
- Unit tests (`test_id_allocations.py`): 5/5 PASSED
- Integration tests (`test_idempotency_key_cli.py`): 3/3 PASSED
- Migration round-trip tests: 3/3 PASSED
- `uv run ruff check`: all checks passed
- `uv run mypy`: no errors
- `git diff HEAD` on `dashboard/` and `batch_commands.py`: no changes (out-of-scope items unchanged)

---

## Schema Review (S01)

| Requirement | Finding | Status |
|-------------|---------|--------|
| `IdAllocation` model exists with composite PK `(prefix, number)` | `models.py:451–492` — `prefix` + `number` as `primary_key=True` | ✅ |
| Partial unique index named `idx_id_allocations_key` on `(prefix, idempotency_key) WHERE idempotency_key IS NOT NULL` | `models.py:483–490` — `Index(…, postgresql_where=text("idempotency_key IS NOT NULL"))` | ✅ |
| `created_at` has `server_default=text("now()")` | `models.py:476–481` — `server_default=text("now()")` | ✅ |
| Migration `downgrade()` drops index first, then table | `7ef0b420c58f_…py:64–71` — `drop_index` then `drop_table` | ✅ |
| Migration file is committed | Git log shows `137f8ae9` | ✅ |
| `make migration-check` passed in S01 | S01 report shows all 3 tests pass | ✅ |

**Finding**: No schema issues. The partial unique index `WHERE` clause is correctly implemented in both the model and the migration, and is preserved in `downgrade()`.

---

## Allocator Behavior Review (S03)

| Requirement | Finding | Status |
|-------------|---------|--------|
| `idempotency_key` is keyword-only | `id_commands.py:32–33` — `*, idempotency_key: str \| None = None` | ✅ |
| No-key path is bit-identical to today | `id_commands.py:59–74` — same `pg_insert … ON CONFLICT DO NOTHING`, same `SELECT … FOR UPDATE`, same return shape, no `id_allocations` write | ✅ |
| Keyed path is transactional | `id_commands.py:91–133` — `id_sequences` increment and `id_allocations` INSERT both inside `session.begin_nested()` SAVEPOINT | ✅ |
| Concurrent-INSERT race handled by catching `IntegrityError` + retry (≤3) | `id_commands.py:126–133` — `IntegrityError` caught, retry loop `for attempt in range(3)`, re-raises after 3 failures | ✅ |
| New `--idempotency-key` Click option is `required=False` with `default=None` | `id_commands.py:169–176` — `required=False, default=None` | ✅ |
| Output shape on idempotent replay is identical (plain + `--json`) | Both paths return `(number, format_id(prefix, number))` / JSON `{"id": …}` — same code path for both fresh and replay | ✅ |

**Finding**: No behavioral issues. The SAVEPOINT/rollback/retry pattern is correctly implemented. All three existing call sites (`batch_commands.py:326`, `dashboard/routers/actions.py:603`, `tests/integration/test_cli_core.py:138`) are positional callers and continue to work unchanged.

---

## Test Coverage Review (S03 unit + S04 integration)

| Requirement | Finding | Status |
|-------------|---------|--------|
| Five unit tests cover AC1–AC4 and concurrent-INSERT | `test_id_allocations.py`: `test_no_key_path_unchanged` (AC1), `test_repeat_key_returns_same_id` (AC2), `test_distinct_keys_distinct_ids` (AC3), `test_same_key_different_prefixes_independent` (AC4), `test_concurrent_same_key_retries_and_returns_winner` | ✅ |
| TDD RED evidence is a real failure, not an import error | S03 report shows `TypeError: allocate_next_id() got an unexpected keyword argument 'idempotency_key'` — genuine RED failure | ✅ |
| Three CLI-level integration tests cover both paths + JSON | `test_idempotency_key_cli.py`: `test_cli_repeat_with_same_key_returns_same_id` (keyed), `test_cli_no_key_still_works` (no-key regression guard), `test_cli_repeat_with_same_key_json_output` (JSON) | ✅ |
| Tests use PostgreSQL testcontainer (not sqlite) | Both test files use `PostgresContainer("postgres:15-alpine")` + `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")` | ✅ |
| FTS-trigger setup rule followed | `test_id_allocations.py:36–39` — `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `create_all()` | ✅ |

**Finding**: No test issues. Coverage failure (`total of 8 is less than fail-under=50`) is expected when running a single test file in isolation; the project-wide gate (enforced at the full-suite QV gate) is not applicable at this review level.

---

## Backwards Compatibility

| Requirement | Finding | Status |
|-------------|---------|--------|
| All callers of `allocate_next_id` confirmed positional-args compatible | S03 report names 3 call sites: `batch_commands.py:326`, `dashboard/routers/actions.py:603`, `tests/integration/test_cli_core.py:138` — all use positional args, get `idempotency_key=None` via keyword-only default | ✅ |
| No changes to `iw register` or `iw doc-update` | `git diff HEAD` on `orch/cli/project_commands.py` and `orch/cli/doc_commands.py`: no changes | ✅ |
| No changes to dashboard or chat feature | `git diff HEAD` on `dashboard/`: no changes | ✅ |
| No new dependencies in `pyproject.toml` | Not modified per reports | ✅ |

---

## Out-of-Scope Scope Creep Check

| Item | Status |
|------|--------|
| `iw register` unchanged | ✅ |
| `iw doc-update` unchanged | ✅ |
| Dashboard code unchanged | ✅ |
| New dependencies added | ✅ None |

---

## Quality Gate Results

| Gate | Command | Result |
|------|---------|--------|
| Format | `make format` | ✅ ok |
| Typecheck | `make typecheck` | ✅ ok |
| Lint | `make lint` | ✅ ok |
| Migration round-trip | `make migration-check` | ✅ 3/3 passed |
| Unit tests | `pytest tests/unit/test_id_allocations.py` | ✅ 5/5 passed |
| Integration tests | `pytest tests/integration/test_idempotency_key_cli.py` | ✅ 3/3 passed |

---

## Findings

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "CR-00053",
  "reviewed_agent": "database-impl, backend-impl, tests-impl",
  "verdict": "PASS",
  "mandatory_fix_count": 0,
  "findings": [],
  "notes": "All CRITICAL/HIGH items from the review checklist pass. No regressions detected. No-key path is bit-identical to original behavior. Migration is committed. Tests use testcontainers (not sqlite). S06 may be a no-op."
}
```

**Conclusion**: All items in the review checklist pass. The implementation is correct, complete, and backwards-compatible. S06 (code review fix) may proceed as a no-op — there are no CRITICAL or HIGH findings to address.