# F-00039_S01_Database_prompt

**Work Item**: F-00039 — Section-Level Guide — Per-Section Editorial Guidelines
**Step**: S01
**Agent**: Database
**Parallel With**: None — depends on F-00037 and F-00038 migrations being chained first

---

## Input Files

- `ai-dev/active/F-00039/F-00039_Feature_Design.md` — Design document

## Output Files

- `ai-dev/active/F-00039/reports/F-00039_S01_Database_report.md`

## Context

You are creating two Alembic migrations for **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

Run `alembic heads` first to confirm the current head. Chain your migrations from it.

## Requirements

### 1. Migration: create `doc_section_guides` table

Create file: `orch/db/migrations/versions/20260414_add_doc_section_guides.py`

```
Revision ID: add_doc_section_guides
Revises: <current HEAD>
```

Upgrade DDL:
```sql
CREATE TABLE doc_section_guides (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id       TEXT NOT NULL REFERENCES project_docs(id) ON DELETE CASCADE,
    section_name TEXT NOT NULL,
    guide_md     TEXT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_doc_section_guides_doc_id ON doc_section_guides(doc_id);
CREATE UNIQUE INDEX uq_doc_section_guides_doc_section ON doc_section_guides(doc_id, section_name);

COMMENT ON TABLE doc_section_guides IS 'Per-section editorial guidelines keyed by (doc_id, section_name).';
COMMENT ON COLUMN doc_section_guides.doc_id IS 'FK to project_docs.id (composite: project_id:doc_id). ON DELETE CASCADE.';
COMMENT ON COLUMN doc_section_guides.section_name IS 'H2 heading text, or "Document" if no H2 headings exist.';
COMMENT ON COLUMN doc_section_guides.guide_md IS 'Markdown editorial guidelines for this specific section.';
COMMENT ON COLUMN doc_section_guides.updated_at IS 'Timestamp of last guide edit.';
```

Downgrade: `DROP TABLE IF EXISTS doc_section_guides`

### 2. Migration: add `section_guides_snapshot` to `doc_generation_jobs`

Create file: `orch/db/migrations/versions/20260414_add_section_guides_snapshot_to_jobs.py`

```
Revision ID: add_section_guides_snapshot_to_jobs
Revises: add_doc_section_guides
```

Upgrade:
```sql
ALTER TABLE doc_generation_jobs ADD COLUMN section_guides_snapshot JSONB;
COMMENT ON COLUMN doc_generation_jobs.section_guides_snapshot IS 'Section guides snapshotted at job creation: {section_name: guide_md, ...}.';
```

Downgrade:
```sql
ALTER TABLE doc_generation_jobs DROP COLUMN IF EXISTS section_guides_snapshot;
```

### 3. Validate

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/alembic heads
```

Expected: single head at `add_section_guides_snapshot_to_jobs`.

## Constraints

- Do NOT run `alembic upgrade head` against the development database
- Do NOT modify `orch/db/models.py`
- ON DELETE CASCADE is required on `doc_id` FK

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Database",
  "work_item": "F-00039",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/20260414_add_doc_section_guides.py",
    "orch/db/migrations/versions/20260414_add_section_guides_snapshot_to_jobs.py"
  ],
  "tests_passed": true,
  "test_summary": "N/A — migration chain validated via alembic heads",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
