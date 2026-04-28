# F-00064_S01_Database_prompt

**Work Item**: F-00064 — Code mapping diagram generation pipeline
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute docker container/volume/network management commands.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.
Your job is to WRITE the migration file only.

---

## Input Files

- `ai-dev/active/F-00064/F-00064_Feature_Design.md`

## Output Files

- `ai-dev/active/F-00064/reports/F-00064_S01_Database_report.md`
- `orch/db/models.py` (modified — `DocType` enum)
- `orch/db/migrations/versions/<rev>_add_diagram_doc_type.py` (new)

## Context

You are implementing the database layer for **F-00064: Code mapping diagram generation pipeline**.

Read the design document at `ai-dev/active/F-00064/F-00064_Feature_Design.md` first.
Read `CLAUDE.md` and `orch/CLAUDE.md` for project conventions and hard rules.

## Requirements

### 1. Add `DocType.diagram` to the Python enum

In `orch/db/models.py`, find the `DocType` enum (around line 184) and add:

```python
diagram = "diagram"
```

Place it after the existing `research = "research"` entry to keep alphabetical/logical order.

### 2. Generate the Alembic migration

Run:
```bash
uv run alembic revision --autogenerate -m "add_diagram_doc_type"
```

This creates a new file in `orch/db/migrations/versions/`. Open it and verify/fix the `upgrade()` function.

**Critical**: PostgreSQL `ALTER TYPE ... ADD VALUE` cannot run inside a transaction. Check how previous enum-extension migrations in this project handle this. Look at all existing migration files for the pattern:

```bash
grep -l "ADD VALUE\|add_value\|AUTOCOMMIT\|execute_if" orch/db/migrations/versions/
```

The correct pattern for this project (verify by reading the existing files) is likely one of:
- Using `op.execute("ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'diagram'")` with the migration marked non-transactional
- Or using `op.execute` with autocommit set via `connection.execution_options`

Match the pattern from existing enum migrations exactly. If autogenerate does not produce the correct DDL, write it manually.

The `downgrade()` function should be a no-op with a comment — PostgreSQL does not support removing enum values without table rewrite.

### 3. Verify the migration file is correct

After generating, inspect the file:
1. Confirm `upgrade()` contains the ADD VALUE statement
2. Confirm `downgrade()` is a no-op
3. Confirm transaction handling is correct for this DDL

Do NOT run `alembic upgrade head` — write the file only.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting complete, run in order:
1. `make format` — auto-fixes formatting; if it changes files, re-inspect
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00064",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_add_diagram_doc_type.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
