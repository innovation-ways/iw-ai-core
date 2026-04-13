# F-00037_S01_Database_prompt

**Work Item**: F-00037 — Doc-Type Guides — Editable Editorial Guidelines
**Step**: S01
**Agent**: Database
**Parallel With**: None — first step

---

## Input Files

- `ai-dev/active/F-00037/F-00037_Feature_Design.md` — Design document

## Output Files

- `ai-dev/active/F-00037/reports/F-00037_S01_Database_report.md`

## Context

You are creating two Alembic migrations for the **iw-ai-core** repository.

**IMPORTANT — Repository location**: All code changes go in the `iw-ai-core` repository at:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```
Do NOT modify files in the `iw-doc-plan` repository (except to write the report).

The current migration head is `add_doc_types_functional` (file: `20260413160000_add_doc_type_product_overview_feature_catalog.py`).

**Note**: F-00020 through F-00023 may also be creating migrations. Check `alembic heads` before
creating your migration to chain from the actual current head, not from a stale assumption.

## Requirements

### 1. Migration: create `doc_type_guides` table

Create file: `orch/db/migrations/versions/20260414_add_doc_type_guides.py`

```
Revision ID: add_doc_type_guides
Revises: <current HEAD — check alembic heads>
```

Upgrade DDL:
```sql
CREATE TABLE doc_type_guides (
    doc_type   TEXT PRIMARY KEY,
    guide_md   TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE doc_type_guides IS 'Per-doc-type editorial guidelines, editable from the UI.';
COMMENT ON COLUMN doc_type_guides.doc_type IS 'DocType enum value (e.g. marketing, module, api).';
COMMENT ON COLUMN doc_type_guides.guide_md IS 'Markdown editorial guidelines for this doc type.';
COMMENT ON COLUMN doc_type_guides.updated_at IS 'Timestamp of last guide edit.';
```

After creating the table, seed rows from the editorial files in `doc-system/editorial/`.
Read each file and INSERT its content. Use `op.execute()` with parameterized SQL or
`op.bulk_insert()`. Seed at minimum:
- `_default` → content of `doc-system/editorial/_default.md`
- `marketing` → content of `doc-system/editorial/marketing.md`

Use Python string constants for the file content (read at migration write time — do not
attempt to open files at migration run time, as the migration may run in a different
working directory).

Downgrade: `DROP TABLE IF EXISTS doc_type_guides`

### 2. Migration: add `guide_snapshot` to `doc_generation_jobs`

Create file: `orch/db/migrations/versions/20260414_add_guide_snapshot_to_jobs.py`

```
Revision ID: add_guide_snapshot_to_jobs
Revises: add_doc_type_guides
```

Upgrade:
```sql
ALTER TABLE doc_generation_jobs ADD COLUMN guide_snapshot TEXT;
COMMENT ON COLUMN doc_generation_jobs.guide_snapshot IS 'Guide content snapshotted at job creation time for audit purposes.';
```

Downgrade:
```sql
ALTER TABLE doc_generation_jobs DROP COLUMN IF EXISTS guide_snapshot;
```

### 3. Validate migration chain

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/alembic heads
.venv/bin/alembic history --verbose | head -20
```

Expected: single head pointing to `add_guide_snapshot_to_jobs`.

## Mandatory Patterns

Follow the exact pattern from `d4e5f6a7b8c9_add_cancelled_batch_status.py` for the migration
boilerplate. Use `op.execute()` for DDL statements. The seed data must be embedded as Python
string literals — do not use file I/O at migration runtime.

## Constraints

- Do NOT run `alembic upgrade head` against the development database
- Do NOT modify `orch/db/models.py` — that is S02's responsibility
- Migration file names MUST follow the existing pattern (timestamp prefix + description)
- The `guide_md` column is NOT NULL — seed rows must be included before the migration ends

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Database",
  "work_item": "F-00037",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/20260414_add_doc_type_guides.py",
    "orch/db/migrations/versions/20260414_add_guide_snapshot_to_jobs.py"
  ],
  "tests_passed": true,
  "test_summary": "N/A — migration chain validated via alembic heads",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
