# F-00064_S02_CodeReview_Database_prompt

**Work Item**: F-00064 — Code mapping diagram generation pipeline
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00064/F-00064_Feature_Design.md`
- `ai-dev/active/F-00064/reports/F-00064_S01_Database_report.md`
- `orch/db/models.py`
- `orch/db/migrations/versions/<rev>_add_diagram_doc_type.py` (the new migration file from S01)

## Output Files

- `ai-dev/active/F-00064/reports/F-00064_S02_CodeReview_Database_report.md`

## Review Checklist

### Migration correctness
- [ ] `upgrade()` uses `ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'diagram'`
- [ ] The migration handles the PostgreSQL restriction: `ADD VALUE` cannot run inside a transaction — verify the migration uses the same autocommit/non-transactional pattern as other enum migrations in this project
- [ ] `downgrade()` is a documented no-op (PostgreSQL cannot remove enum values without table rewrite)
- [ ] Migration file has a unique revision ID and correct `down_revision`

### Python enum
- [ ] `DocType.diagram = "diagram"` added to `orch/db/models.py`
- [ ] Enum value placement is consistent with existing order
- [ ] No other references to `DocType` are broken

### General
- [ ] No live DB commands run (no `alembic upgrade`)
- [ ] Preflight gates (format, typecheck, lint) passed per S01 report

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00064",
  "completion_status": "complete|partial|blocked",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}
  ],
  "approved": true,
  "notes": ""
}
```
