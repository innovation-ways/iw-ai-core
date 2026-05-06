# CR-00035 S01 Database Report

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step**: S01
**Agent**: database-impl
**Date**: 2026-05-05

## Summary

Added a nullable JSONB `report` column to `doc_generation_jobs` via an Alembic migration and the corresponding ORM field on `DocGenerationJob`.

## Changes Made

### 1. Migration File
**File**: `orch/db/migrations/versions/c35d5b257eab_add_report_to_doc_generation_jobs.py`

- Revision ID: `c35d5b257eab`
- Down-revision: `4cc043748e92` (current head)
- `upgrade()`: adds `report JSONB NULL` column with comment
- `downgrade()`: drops the column
- No data backfill; purely additive and reversible

Note: autogenerate was run first but produced ~1000 lines of spurious diffs (FTS trigger drift, index reorganizations unrelated to this CR). The migration was rewritten manually as a minimal, focused change.

### 2. ORM Model Update
**File**: `orch/db/models.py` — `DocGenerationJob` class

Added `report: Mapped[dict[str, Any] | None]` field after `lint_warnings`, before `duration_seconds`:

```python
report: Mapped[dict[str, Any] | None] = mapped_column(
    JSONB,
    nullable=True,
    comment=(
        "Structured post-mortem of the job: outcome, duration_seconds, "
        "skill_used, cli_tool, command_issued, log_size_bytes, log_line_count, "
        "tool_calls, doc_update_invocations, lint_warning_count, diagnosis."
    ),
)
```

Uses existing `JSONB` import from `sqlalchemy.dialects.postgresql`.

### 3. Schema Documentation
`docs/IW_AI_Core_Database_Schema.md` was checked — it does not enumerate `doc_generation_jobs` columns in detail, so no doc update was needed.

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok (612 files, no drift) |
| `make lint` | ok (all checks passed) |
| `make typecheck` | ok (225 source files, no issues) |

## Test Results

**Unit tests**: 2579 passed, 2 failed, 4 skipped, 5 xfailed
- The 2 failures (`test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context` and `test_rollback_refuses_in_agent_context`) are **pre-existing** — confirmed by running them on a clean stash with no changes. They fail on main too.

**Integration tests**: timed out after 300s (ran with `-k doc_generation`). The test suite requires a PostgreSQL testcontainer and takes longer in the constrained environment. The migration is schema-only and was verified manually.

## Decisions Made

1. **Autogenerate was discarded**: produced ~1000 lines of spurious diffs from FTS trigger drift and unrelated index reorganizations. A focused manual migration (50 lines) was written instead.
2. **Column placed after `lint_warnings`**: matches the design document's stated ordering.
3. **JSONB with `astext_type=sa.Text()`**: follows the project's established pattern for JSONB columns in this codebase.
4. **No GIN index added**: design document explicitly defers indexing to a future CR if query patterns emerge.

## Blockers

None.

## Notes

- The migration correctly uses `down_revision = "4cc043748e92"` which is the current head per `alembic history`.
- `doc_generation_jobs` is NOT an append-only table (unlike `step_runs`, `fix_cycles`, etc.), so adding an updateable `report` column is appropriate.
- The `report` column name does not conflict with any reserved names — unlike `DaemonEvent.metadata → event_metadata`, this column is accessed as-is.