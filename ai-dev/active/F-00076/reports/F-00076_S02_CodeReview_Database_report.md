# F-00076 S02 Code Review — Database (S01)

## Review Summary

**Work Item**: F-00076 — Cross-batch file-conflict gate
**Step**: S02
**Agent**: code-review-impl
**Reviewed Agent**: database-impl (S01)
**Verdict**: **NEEDS FIXES**

---

## What Was Reviewed

Files from S01:
- `orch/db/models.py` (added `impacted_paths` column)
- `orch/db/migrations/versions/4876b3246ff2_add_impacted_paths_to_work_items_f_00076.py`
- `pyproject.toml` (added `pathspec` dependency)
- `uv.lock` (updated)
- `tests/unit/db/test_work_item_impacted_paths.py`
- `tests/integration/db/test_migration_impacted_paths_backfill.py`

---

## Findings

### CRITICAL

#### 1. Migration uses raw `COMMIT`/`BEGIN` instead of Alembic's `autocommit_block()`
**File**: `orch/db/migrations/versions/4876b3246ff2_add_impacted_paths_to_work_items_f_00076.py:35-36`

The migration uses raw SQL `COMMIT` and `BEGIN` statements to work around PostgreSQL's requirement that `ALTER TYPE ... ADD VALUE` must run outside a transaction block:

```python
op.execute(sa.text("COMMIT"))
op.execute(sa.text("BEGIN"))
```

**Every other enum-extending migration in this codebase** uses Alembic's official API:
```python
with op.get_context().autocommit_block():
    op.execute("ALTER TYPE work_item_status ADD VALUE IF NOT EXISTS 'archived'")
```

Examples: `a9861af32872_add_self_assess_to_step_type_enum.py:31`, `40af3b76e1d5_cr_00021_rebase_pipeline_phase.py:36`, `bd4ed52cad71_i_00042_add_batch_item_status_labels.py:35`.

**Impact**: Raw `COMMIT`/`BEGIN` bypasses Alembic's migration context, risks leaving the connection in an inconsistent state, and interacts badly with testcontainer session management (confirmed in the S01 report's own blocker analysis). The integration test fails because the testcontainer connection is torn down mid-transaction after the migration's `COMMIT`.

**Recommended fix**: Replace lines 35–36 with:
```python
with op.get_context().autocommit_block():
    op.execute("ALTER TYPE work_item_status ADD VALUE IF NOT EXISTS 'archived'")
```
Remove the `COMMIT` and `BEGIN` lines entirely.

---

### HIGH

#### 2. Integration test architecture issue — `module`-scoped fixtures + rollback interaction
**File**: `tests/integration/db/test_migration_impacted_paths_backfill.py:45-83`

The `pg_container` and `migrated_engine` fixtures are `scope="module"`, while the test inserts rows and then rolls back the transaction (line 169). The migration has already been applied at head, and the rollback combined with `module`-scope engine causes the testcontainer connection to close during teardown.

**Recommended fix options**:
- **Option A (preferred)**: Switch to `scope="function"` for `pg_container` and `db_engine` fixtures, removing the explicit rollback and relying on the test's transaction lifecycle.
- **Option B**: Use a context manager approach (like `test_iw_core_instance_migration.py`) that applies the migration inside a `with engine.connect() as conn:` block.
- **Option C (defer)**: As noted in the S01 report, this is correctly diagnosed and the fix can be deferred to S09 (tests-impl), since the migration logic itself is correct and unit tests confirm the column behavior.

The S01 agent correctly identified the root cause and proposed fixes. The issue is architectural, not correctness of the migration SQL.

---

### MEDIUM

#### 3. `downgrade()` does not clean up the `archived` enum value
**File**: `orch/db/migrations/versions/4876b3246ff2_add_impacted_paths_to_work_items_f_00076.py:81-85`

PostgreSQL does not support `DROP VALUE` for enum types, so the comment correctly notes the value remains. However, this means downgrading and re-upgrading will hit `IF NOT EXISTS` and be safe. No action needed — documented as expected behavior.

**No fix required** — just noting it's by design.

---

## Design Contract Verification

| Requirement | Status | Notes |
|-------------|--------|-------|
| `WorkItem.impacted_paths` column exists as JSONB | ✅ PASS | `orch/db/models.py:443-455` |
| NOT NULL with server default `'[]'` | ✅ PASS | `server_default=text("'[]'")`, `nullable=False` |
| Comment references F-00076 | ✅ PASS | Lines 448–454 explain source-of-truth role |
| No `WorkItem.notes` column added | ✅ PASS | Correctly absent; warnings live in `config["scope_extraction"]` |
| Single revision, single column | ✅ PASS | One migration, one column add |
| Backfill uses `op.get_bind()` with parameterized SQL | ✅ PASS | Lines 52–75 use `sa.text()` + dict params |
| `extract_affected_files` imported from `orch.batch_planner` | ✅ PASS | Line 50 |
| Backfill skips terminal-status rows | ✅ PASS | Line 57: `status NOT IN ('completed', 'archived')` |
| `downgrade()` drops the column | ✅ PASS | Line 82 |
| Revision's `down_revision` points at previous head | ✅ PASS | Line 21: `down_revision: str | None = "a9861af32872"` |

---

## `pathspec` Dependency Verification

| Requirement | Status | Notes |
|-------------|--------|-------|
| Added to `pyproject.toml` dependencies | ✅ PASS | Line 37: `"pathspec>=1.0.4"` |
| `uv.lock` updated | ✅ PASS | 6 matches found for pathspec in uv.lock |

---

## Test Results

### Unit Tests
```
make test-unit 2>&1 | tail -5
===== 2421 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings in 42.15s =====
```
All 3 F-00076 unit tests pass (verified separately):
- `test_impacted_paths_defaults_to_empty_list` ✅
- `test_impacted_paths_can_be_set_explicitly` ✅
- `test_impacted_paths_not_null_constraint` ✅

### Integration Test
```
FAILED tests/integration/db/test_migration_impacted_paths_backfill.py::test_migration_backfill_impacted_paths
```
Confirmed failure: `psycopg.OperationalError: server closed the connection unexpectedly`

Root cause: The `COMMIT`/`BEGIN` pattern in the migration (Finding #1) interacts with the `module`-scoped testcontainer fixture to corrupt the connection state during teardown. This is the same issue documented by S01 as a Blocker.

---

## Verdict: NEEDS FIXES

### Mandatory Fix Count: 1

**CRITICAL** finding requires fixing before S11 (final review):
1. Replace raw `COMMIT`/`BEGIN` in the migration with Alembic's `autocommit_block()` context manager.

**HIGH** finding (integration test architecture) is correctly diagnosed and documented by S01. Fix can be deferred to S09 per the S01 agent's own recommendation.

**AC1** (backfill correctness) cannot be fully verified via integration test due to the `COMMIT`/`BEGIN` issue, but the unit tests confirm column defaults and NOT NULL constraint behavior. Manual verification and S09's integration test will provide full coverage.

---

## JSON Report

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00076",
  "reviewed_agent": "database-impl",
  "verdict": "NEEDS_FIXES",
  "mandatory_fix_count": 1,
  "findings": [
    {
      "severity": "CRITICAL",
      "file": "orch/db/migrations/versions/4876b3246ff2_add_impacted_paths_to_work_items_f_00076.py:35-36",
      "problem": "Uses raw COMMIT/BEGIN SQL to handle PostgreSQL enum transaction requirement instead of Alembic's official autocommit_block() API used by every other enum-extending migration in this codebase. Causes connection corruption in testcontainer lifecycle.",
      "fix": "Replace op.execute(sa.text('COMMIT')) and op.execute(sa.text('BEGIN')) with: with op.get_context().autocommit_block(): op.execute(\"ALTER TYPE work_item_status ADD VALUE IF NOT EXISTS 'archived'\")"
    },
    {
      "severity": "HIGH",
      "file": "tests/integration/db/test_migration_impacted_paths_backfill.py:45-83",
      "problem": "Integration test fails due to module-scoped fixtures + COMMIT/BEGIN migration interaction causing server closed connection during teardown. Root cause correctly diagnosed by S01; fix deferred to S09 per S01 recommendation.",
      "fix": "Option A: switch to scope='function' for pg_container/db_engine fixtures. Option B: refactor to apply migration inside engine.connect() context. Option C: defer to S09."
    },
    {
      "severity": "MEDIUM",
      "file": "orch/db/migrations/versions/4876b3246ff2_add_impacted_paths_to_work_items_f_00076.py:81-85",
      "problem": "downgrade() leaves 'archived' enum value in place (PostgreSQL limitation). Documented but no action needed.",
      "fix": "No fix required — by design."
    }
  ],
  "test_summary": "Unit: 2421 passed, 2 skipped, 5 xfailed, 1 xpassed (48 warnings). Integration: 1 failed (COMMIT/BEGIN + testcontainer lifecycle issue; migration logic correct).",
  "blockers": [
    "Migration uses raw COMMIT/BEGIN instead of autocommit_block() — must fix before S11 final review"
  ]
}
```