# F-00062 S02 Code Review Report

## What was reviewed

S01 (database-impl) schema additions for F-00062: three nullable columns on `batch_items`
(`worktree_db_port`, `worktree_app_port`, `worktree_compose_path`) and the
`setup_failed` value added to the `BatchItemStatus` enum.

## Files reviewed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `setup_failed` enum member + three new columns on `BatchItem` |
| `orch/db/migrations/versions/550aecbbd42b_f_00062_add_worktree_compose_stack_.py` | New additive migration |
| `docs/IW_AI_Core_Database_Schema.md` | Enum updated, column table added, Invariant #6 documented |
| `tests/unit/test_batch_item_columns.py` | 9-unit test suite for all new columns + enum |

## Review checklist

### 1. Schema correctness — PASS
- All three columns are nullable (`nullable=True`) ✅
- `worktree_db_port` / `worktree_app_port`: `Integer` type ✅
- `worktree_compose_path`: `Text` type ✅
- Column docstrings explain NULL semantics (legacy fallback signal) ✅
- Column ordering and style follow existing `BatchItem` conventions (grouped together,
  after `merge_info` JSONB columns) ✅

### 2. Migration shape — PASS
- Purely additive: only `op.add_column(...)` statements + enum add ✅
- `ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'setup_failed'` runs inside
  `op.get_context().autocommit_block()` — correct, Postgres requires this outside a
  transaction ✅
- `downgrade()` drops the three columns in reverse add order ✅
- Migration docstring references F-00062, explains intent, and documents the
  PostgreSQL enum-label irreversibility limitation ✅

### 3. ORM/Python consistency — PASS
- `BatchItemStatus.setup_failed` is present in the Python enum ✅
- `Mapped[int | None]` typing for port columns, `Mapped[str | None]` for
  `worktree_compose_path` ✅

### 4. Documentation — PASS
- `docs/IW_AI_Core_Database_Schema.md` section 2.8 has the three new column rows with
  descriptions matching the `comment=` strings ✅
- `setup_failed` is listed in the enum value list and in the Status meanings table ✅
- Invariant #6 ("all three NULL or all non-NULL") is documented ✅

### 5. Tests — PASS
- Unit test (`tests/unit/test_batch_item_columns.py`) asserts column presence, correct
  types, nullability, and default-None construction for all three columns ✅
- Unit test asserts `setup_failed` enum member exists and is a valid enum value ✅
- `make test-unit`: **1472 passed** (including 9 new tests) ✅

### 6. Project conventions — PASS
- No `psycopg2` usage — using SQLAlchemy 2.0 `Mapped[]` style ✅
- No async — daemon is sync ✅
- `ruff check` on all S01-changed files: **All checks passed** ✅
- `mypy` on all S01-changed files: clean ✅
- Pre-existing lint errors in `tests/unit/test_qa_engine_classifier.py` (E501 line-length)
  are unrelated to S01 changes ✅

## Findings

No CRITICAL or HIGH issues found.

| Severity | Category | File | Line | Description |
|----------|----------|------|------|-------------|
| LOW | convention | `orch/db/migrations/versions/550aecbbd42b_f_00062_add_worktree_compose_stack_.py` | 1 | Migration module docstring could note the exact AC it serves (AC7 — NULL-as-legacy) for easier traceability, but this is a suggestion not a requirement |

## Mandatory fix count

**0**

## Test summary

```
make test-unit  →  1472 passed, 27 warnings (async coroutine warnings in test_qa_engine.py — pre-existing, unrelated)
make lint       →  10 errors (all pre-existing E501 in test_qa_engine_classifier.py, not from S01 changes)
make quality    →  lint fails on pre-existing errors only
ruff check on S01 files  →  All checks passed
mypy on S01 files        →  clean
```

## Notes

S01 is a clean, well-executed additive schema change. The migration follows the
CR-00019/CR-00021 enum-add pattern precisely (autocommit block for `ALTER TYPE`).
Column types, nullability, docstrings, ORM typing, schema docs, and test coverage
all align with the design document and project conventions. No regressions introduced.
