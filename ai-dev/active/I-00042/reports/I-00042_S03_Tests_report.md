# I-00042 S03 Tests — Step Report (Rework)

## Rework Rationale

The original S03 test was defective: it bound to the shared `db_engine` fixture from
`tests/integration/conftest.py`, which builds the schema via `Base.metadata.create_all()`.
That call creates the `batch_item_status` PG enum directly from the Python
`BatchItemStatus` declaration, so all 13 labels are always present regardless of whether
any migration adds them.  The test therefore passed both before and after the fix — it
validated nothing.

The fix is to spin up a private `pg_container` + `migrated_engine` that runs
`alembic upgrade head` against a fresh empty DB.  This mirrors the production scenario
exactly: labels missing from a migration are absent from the PG enum.

## What Was Done

Rewrote `tests/integration/test_batch_item_status_enum_drift.py` to:

1. Declare a module-scoped `pg_container` fixture — private, never shares the
   session-scoped container from conftest.py.
2. Declare a module-scoped `migrated_engine` fixture that calls
   `alembic command.upgrade(cfg, "head")` against the empty container (not
   `Base.metadata.create_all()`).
3. The single test function `test_pg_batch_item_status_enum_includes_i_00042_labels`
   queries `pg_enum` for `batch_item_status` labels and asserts:
   - `"migration_invalid" in pg_labels` (semantic, specific value)
   - `"migration_rolled_back" in pg_labels` (semantic, specific value)
   - `{e.value for e in BatchItemStatus} - pg_labels == {}` (drift-prevention subset)

## RED -> GREEN Proof

### GREEN (migration present): test PASSES

```
collected 1 item

tests/integration/test_batch_item_status_enum_drift.py::test_pg_batch_item_status_enum_includes_i_00042_labels PASSED [100%]

1 passed, 1 warning in 3.83s
```

### RED (migration renamed to .disabled): test FAILS

```
FAILED tests/integration/test_batch_item_status_enum_drift.py::test_pg_batch_item_status_enum_includes_i_00042_labels

____________ test_pg_batch_item_status_enum_includes_i_00042_labels ____________

    def test_pg_batch_item_status_enum_includes_i_00042_labels(migrated_engine: Engine) -> None:
        ...
        # Semantic checks — assert the specific values that were missing before I-00042
>       assert "migration_invalid" in pg_labels
E       AssertionError: assert 'migration_invalid' in {'completed', 'executing', 'failed', 'merged', 'merging', 'migration_rebase_failed', ...}

tests/integration/test_batch_item_status_enum_drift.py:101: AssertionError

1 failed, 1 warning in 3.85s
```

### GREEN again (migration restored): test PASSES

```
collected 1 item

tests/integration/test_batch_item_status_enum_drift.py::test_pg_batch_item_status_enum_includes_i_00042_labels PASSED [100%]

1 passed, 1 warning in 3.83s
```

The migration file was restored to
`orch/db/migrations/versions/bd4ed52cad71_i_00042_add_batch_item_status_labels.py`
before declaring done.

## Quality Gates

### `make lint`

```
uv run ruff check .
All checks passed!
```

### `make test-unit`

```
1759 passed, 2 skipped, 48 warnings in 12.75s
```

Zero failures, zero regressions.

## Files Changed

- `tests/integration/test_batch_item_status_enum_drift.py` (rewrote; same path)

## Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00042",
  "completion_status": "complete",
  "files_changed": [
    "tests/integration/test_batch_item_status_enum_drift.py"
  ],
  "tests_passed": true,
  "test_summary": "1 new integration test passed (alembic-built schema); 1759 unit passed, 0 failed; lint clean",
  "blockers": [],
  "notes": "Test now uses a private pg_container + migrated_engine (alembic upgrade head) instead of the shared db_engine (create_all). RED proof captured: without the I-00042 migration, the assertion fails with 'migration_invalid' absent from the PG enum set."
}
```
