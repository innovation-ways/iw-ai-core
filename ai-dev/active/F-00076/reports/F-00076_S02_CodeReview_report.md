# F-00076 S02 — Code Review (Database)

## What Was Done

Reviewed S01 (database-impl) output for the `impacted_paths` column addition:

1. **Design contract**: ORM column, JSONB, NOT NULL with `[]` default, correct comment referencing F-00076 and the source-of-truth role. No extraneous columns added. ✅
2. **Migration**: Correctly adds the column with backfill. However, uses raw `COMMIT`/`BEGIN` for the enum-add instead of Alembic's `autocommit_block()` API — this is inconsistent with every other enum-extending migration in the codebase and causes testcontainer connection corruption.
3. **pathspec dependency**: Properly added to `pyproject.toml` as a main dependency (not dev), `uv.lock` updated.
4. **Unit tests**: 3 tests all pass — default `[]`, round-trip, NOT NULL constraint.

## Test Results

- **Unit tests**: `make test-unit` → 2421 passed, 2 skipped, 5 xfailed, 1 xpassed ✅
- **F-00076 unit tests** (3): all pass ✅
- **Integration test**: fails due to `COMMIT`/`BEGIN` in migration corrupting testcontainer connection state during teardown. Migration logic is correct; test architecture needs refinement (deferred to S09 per S01's own recommendation).

## Findings

| Severity | Count | Summary |
|----------|-------|---------|
| CRITICAL | 1 | Migration uses raw COMMIT/BEGIN instead of `autocommit_block()` — must fix |
| HIGH | 1 | Integration test fails (correctly diagnosed by S01, defer fix to S09) |
| MEDIUM | 1 | downgrade() leaves archived enum value (by design, no action needed) |

## Verdict: NEEDS FIXES (1 mandatory fix)

**Mandatory fix**: Replace raw `COMMIT`/`BEGIN` in migration with:
```python
with op.get_context().autocommit_block():
    op.execute("ALTER TYPE work_item_status ADD VALUE IF NOT EXISTS 'archived'")
```