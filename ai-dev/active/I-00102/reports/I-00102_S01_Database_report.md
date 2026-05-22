# I-00102 S01 — Database (Schema) Report

## Step Summary

**Step**: S01 — Database
**Agent**: database-impl
**Work Item**: I-00102
**Completion**: ✅ complete

## What Was Done

Added the `manifest_digest` column to the `WorkItem` ORM model and created the Alembic migration to add it to the `work_items` table.

### Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `manifest_digest: Mapped[str \| None]` column to `WorkItem` |
| `orch/db/migrations/versions/aeb0e4106b55_add_manifest_digest_to_work_items_i_.py` | New alembic revision (down_revision: `891343247f66`) |

### ORM Addition (`orch/db/models.py`)

```python
manifest_digest: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment=(
        "SHA-256 hex digest of the canonicalized steps array from "
        "workflow-manifest.json at register/approve time. NULL for "
        "pre-I-00102 items. Used by iw approve to detect on-disk "
        "manifest drift and auto-refresh workflow_steps when the "
        "item is still in draft. See I-00102."
    ),
)
```

Placed immediately after `impacted_paths` and before `design_doc_path`, matching the existing field grouping.

### Migration (`aeb0e4106b55`)

- **upgrade()**: adds `manifest_digest TEXT NULL` with no server default and a descriptive comment.
- **downgrade()**: drops the column.
- **down_revision**: `891343247f66` (confirmed single head; `alembic heads` returned exactly one revision).
- No backfill required — nullable with no default; existing rows get NULL.
- Clean import set matching adjacent migrations (no `from sqlalchemy.dialects import postgresql` needed).

## Test Results

```
make migration-check
  test_alembic_upgrade_head_succeeds_from_empty        ✅ PASSED
  test_alembic_downgrade_base_then_upgrade_head         ✅ PASSED
  test_alembic_schema_matches_create_all                 ✅ PASSED
```

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ 829 files already formatted |
| `make typecheck` | ✅ no issues found in 274 source files |
| `make lint` | ✅ All checks passed |
| `make migration-check` | ✅ All 3 tests passed |

## Observations

- Alembic's autogenerate picked up some spurious `chat_tabs` comment-sync alterations (from the large sync migration `7f1a75bb5c2d`) that were not part of this step's scope. Hand-tuned the migration to contain only the `manifest_digest` addition.
- Single-head confirmed: `uv run alembic heads` returned `891343247f66` only — no conflict.
- The column is intentionally nullable with no default, per AC5 (backfill-safe migration). S02 will populate it at register and re-validate at approve.

## Blockers

None.

## Next Step

S02 (Backend) depends on `WorkItem.manifest_digest` existing in both the ORM and the DB. The schema is now ready.
