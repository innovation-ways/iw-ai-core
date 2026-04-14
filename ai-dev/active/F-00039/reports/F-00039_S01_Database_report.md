# F-00039 S01 Database Report

## Summary

Two Alembic migrations created for the Section-Level Guide feature.

## Files Changed

- `orch/db/migrations/versions/20260414_add_doc_section_guides.py`
- `orch/db/migrations/versions/20260414_add_section_guides_snapshot_to_jobs.py`

## Migration 1: `add_doc_section_guides`

- **Revision ID**: `add_doc_section_guides`
- **Revises**: `add_doc_type_research`
- Creates `doc_section_guides` table with columns: `id`, `doc_id`, `section_name`, `guide_md`, `updated_at`
- Creates index `idx_doc_section_guides_doc_id` and unique constraint `uq_doc_section_guides_doc_section`
- FK to `project_docs.id` with ON DELETE CASCADE

## Migration 2: `add_section_guides_snapshot_to_jobs`

- **Revision ID**: `add_section_guides_snapshot_to_jobs`
- **Revises**: `add_doc_section_guides`
- Adds `section_guides_snapshot` JSONB column to `doc_generation_jobs`

## Validation

```
$ alembic heads
add_section_guides_snapshot_to_jobs (head)
```

Migration chain validated — single head as expected.

## Notes

- No `alembic upgrade head` executed against development database
- `orch/db/models.py` not modified
