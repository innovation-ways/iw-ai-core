# F-00038_S01_Database_prompt

**Work Item**: F-00038 — Instance Guide Overlay — Per-Document Editorial Override
**Step**: S01
**Agent**: Database
**Parallel With**: None — depends on F-00037 migrations being applied

---

## Input Files

- `ai-dev/active/F-00038/F-00038_Feature_Design.md` — Design document
- `ai-dev/active/F-00037/reports/F-00037_S01_Database_report.md` — Prior migration report (for chain reference)

## Output Files

- `ai-dev/active/F-00038/reports/F-00038_S01_Database_report.md`

## Context

You are creating one Alembic migration for the **iw-ai-core** repository.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

Before creating the migration, run `alembic heads` to confirm the current head and chain from it.

## Requirements

### 1. Migration: create `doc_instance_guides` table

Create file: `orch/db/migrations/versions/20260414_add_doc_instance_guides.py`

```
Revision ID: add_doc_instance_guides
Revises: <current HEAD — check alembic heads>
```

Upgrade DDL:
```sql
CREATE TABLE doc_instance_guides (
    doc_id     TEXT PRIMARY KEY REFERENCES project_docs(id) ON DELETE CASCADE,
    guide_md   TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE doc_instance_guides IS 'Per-document editorial guide overrides — highest priority, overrides doc_type_guides.';
COMMENT ON COLUMN doc_instance_guides.doc_id IS 'Composite PK matching project_docs.id (format: project_id:doc_id).';
COMMENT ON COLUMN doc_instance_guides.guide_md IS 'Markdown editorial instructions specific to this document.';
COMMENT ON COLUMN doc_instance_guides.updated_at IS 'Timestamp of last guide edit.';
```

Downgrade: `DROP TABLE IF EXISTS doc_instance_guides`

### 2. Validate migration chain

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/alembic heads
```

Expected: single head pointing to `add_doc_instance_guides`.

## Constraints

- Do NOT run `alembic upgrade head` against the development database
- Do NOT modify `orch/db/models.py` — S02's responsibility
- ON DELETE CASCADE is required so removing a doc removes its instance guide

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Database",
  "work_item": "F-00038",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/20260414_add_doc_instance_guides.py"
  ],
  "tests_passed": true,
  "test_summary": "N/A — migration chain validated via alembic heads",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
