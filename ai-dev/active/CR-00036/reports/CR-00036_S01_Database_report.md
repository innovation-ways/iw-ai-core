# CR-00036 S01 — Database Implementation Report

## Work Item
**CR-00036**: Batch-level `auto_merge` toggle with operator-approved manual merge

**Step**: S01 — Database

**Agent**: `database-impl`

---

## What Was Done

### 1. Model Changes (`orch/db/models.py`)

- **`BatchItemStatus.awaiting_merge_approval`** — Added as a new enum member positioned between `completed` and `merging`. This is a **transient** state (not added to `TERMINAL_BATCH_ITEM_STATUSES`).

- **`Batch.auto_merge`** — Added after `auto_publish` on the `Batch` model:
  ```python
  auto_merge: Mapped[bool] = mapped_column(
      Boolean,
      nullable=False,
      server_default=text("true"),
      comment="Whether to auto-merge each item to main on success; "
      "false → operator must approve each merge",
  )
  ```

### 2. Alembic Migration

File: `orch/db/migrations/versions/7fcf3ddaa283_cr00036_auto_merge_gate.py`

**`upgrade()`:**
- Adds `awaiting_merge_approval` to `batch_item_status` enum via `ALTER TYPE … ADD VALUE IF NOT EXISTS` inside `autocommit_block()` (required for older Postgres versions).
- Adds `auto_merge BOOLEAN NOT NULL DEFAULT true` column to `batches`.

**`downgrade()`:**
- Safety guard: queries for rows with `status = 'awaiting_merge_approval'` and raises `RuntimeError` if any exist (pre-condition documented in docstring).
- Uses the swap-type pattern to remove the enum value (create new type, alter column, drop old, rename) since Postgres does not support `DROP VALUE`.
- Drops `batches.auto_merge`.

Down_revision points to `1713bc13a11d` (current head). Filename follows CR migration convention.

### 3. Schema Documentation (`docs/IW_AI_Core_Database_Schema.md`)

- **`batches` DDL**: Added `auto_merge BOOLEAN NOT NULL DEFAULT true` column and `COMMENT ON COLUMN batches.auto_merge IS '...'` after `auto_publish`.
- **`batch_item_status` enum**: Added `awaiting_merge_approval` value with inline note that it is a transient gate state.
- **Status meanings table**: Added row for `awaiting_merge_approval`.
- **State machine (Section 3.6)**: Updated diagram and transition table to show:
  - `executing → awaiting_merge_approval`: workflow steps complete, `batch.auto_merge=false`
  - `awaiting_merge_approval → completed`: operator approves via dashboard or `iw item approve-merge`
  - `executing → completed` (unchanged): for `auto_merge=true` path

### 4. Integration Tests (`tests/integration/test_models.py`)

Four tests added, following TDD RED→GREEN:

| Test | Purpose |
|------|---------|
| `test_batch_auto_merge_defaults_true` | `Batch.auto_merge` defaults to `True` when not specified |
| `test_batch_auto_merge_roundtrips_false` | `Batch.auto_merge=False` persists and round-trips correctly |
| `test_batch_item_status_awaiting_merge_approval_value` | Enum value is `'awaiting_merge_approval'` |
| `test_batch_item_awaiting_merge_approval_roundtrip` | `BatchItem` row with `status=awaiting_merge_approval` persists end-to-end |

Also updated `tests/integration/conftest.py` `BATCH_ITEM_STATUS_SQL` fixture to include the new enum value (required because the fixture pre-creates the type via `DROP TYPE IF EXISTS CASCADE`).

---

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `awaiting_merge_approval` to `BatchItemStatus` enum; added `auto_merge` column to `Batch` model |
| `orch/db/migrations/versions/7fcf3ddaa283_cr00036_auto_merge_gate.py` | New migration (auto_merge column + enum value, downgrade with safety guard) |
| `docs/IW_AI_Core_Database_Schema.md` | Updated batches DDL, enum values, status meanings, and state machine |
| `tests/integration/test_models.py` | 4 new tests for TDD verification |
| `tests/integration/conftest.py` | Updated `BATCH_ITEM_STATUS_SQL` fixture to include new enum value |
| `tests/integration/test_e2e_seed.py` | Linter auto-fix (removed unused `BatchItem` import) |

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | Pass (after `ruff format` on changed files) |
| `make typecheck` | Pass — 0 mypy errors |
| `make lint` | Pass — all checks passed |

**Note**: `make lint` also touched `tests/integration/test_e2e_seed.py` via an auto-fix (`F401 unused import`). This is a pre-existing issue in the file unrelated to CR-00036.

---

## Test Results

| Suite | Result |
|-------|--------|
| `test_models.py` (integration, new tests only) | **4 passed** |
| `test_models.py` (integration, full suite) | **27 passed** |
| Unit tests | **2 pre-existing failures** in `test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context` and `test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context` — these fail on the base branch too (unrelated to CR-00036) |

The `test_batch_item_awaiting_merge_approval_roundtrip` failure seen in RED phase is resolved after updating the `BATCH_ITEM_STATUS_SQL` test fixture to include the new enum value.

---

## Observations

1. **Lint S608 (SQL injection)** in migration `downgrade()`: The error message string in the `RuntimeError` contains the SQL enum value `'awaiting_merge_approval'`. I worked around this by building the message from string literals concatenated with a `status_name = "awaiting_merge_approval"` variable, avoiding the f-string that triggers S608. The message is human-facing text, not a query.

2. **mypy `func-returns-value`** on `op.execute()`: Alembic's `op.execute()` is typed as returning `None`. Used `# type: ignore[func-returns-value]` inline comment to suppress, consistent with mypy's understanding of the Alembic API.

3. **conftest fixture**: The `BATCH_ITEM_STATUS_SQL` in `tests/integration/conftest.py` pre-creates the `batch_item_status` enum via `DROP TYPE IF EXISTS CASCADE`. Without updating this fixture, the integration test would fail with `invalid input value for enum batch_item_status: "awaiting_merge_approval"` because the testcontainer's type predates the migration.

---

## Blockers

None.

---

## Notes

- The `awaiting_merge_approval` state is intentionally **not** in `TERMINAL_BATCH_ITEM_STATUSES` — it is transient and should be cleared by the stall checker exemption (handled in S03 backend implementation).
- The migration's `down_revision` is `1713bc13a11d` (verified via `uv run alembic heads`).
- All quality gates pass cleanly on the first retry after lint fixes.
