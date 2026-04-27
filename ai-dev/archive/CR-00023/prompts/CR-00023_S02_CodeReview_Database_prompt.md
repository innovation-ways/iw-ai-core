# CR-00023_S02_CodeReview_Database_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S02
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design document (acceptance criteria AC3)
- `ai-dev/active/CR-00023/reports/CR-00023_S01_Database_report.md` — S01's report
- `orch/db/models.py` — modified `WorkflowStep`
- `orch/db/migrations/versions/<new_revision>_add_command_gate_timeout_to_workflow_steps.py` — new migration

## Output Files

- `ai-dev/active/CR-00023/reports/CR-00023_S02_CodeReview_Database_report.md` — review findings

## Context

Review S01's schema change for correctness, reversibility, and convention
adherence. This step does NOT modify code — it produces findings for S03 to
consume (via fix-cycle if any are CRITICAL/HIGH).

## Review Checklist

### Schema Correctness
- [ ] All three columns (`command`, `gate`, `timeout_secs`) are `nullable=True` — NOT NULL would break legacy items
- [ ] `command` and `gate` use `Text` type; `timeout_secs` uses `Integer`
- [ ] No default values are set on the columns (a default would silently backfill, masking the legacy/new distinction)
- [ ] Columns include SQL `comment` strings matching the project's convention (other `WorkflowStep` columns have comments)

### Migration Correctness
- [ ] `down_revision` matches whatever was the current head when S01 ran (verify with `uv run alembic history | head -3` — at design time 2026-04-27 the head was `c062b6bf5eb3`, but a newer migration may have merged in the meantime; what matters is that the new revision chains correctly from the prior head with no gap)
- [ ] `upgrade()` adds all three columns with `nullable=True`
- [ ] `downgrade()` drops all three columns in reverse order (`timeout_secs` → `gate` → `command`)
- [ ] No unrelated changes from autogenerate (e.g., index/comment updates on other tables) — flag any such drift as a HIGH finding

### Naming + Conventions
- [ ] Column names match the manifest field names that source them (`command` ↔ `command`, `gate` ↔ `gate`, `timeout_secs` derives from `timeout` with `_secs` suffix per project convention — see `StepRun.timeout_secs` for precedent)
- [ ] Migration filename follows the project's `<hash>_<descriptor>.py` pattern
- [ ] Migration message matches the requested format

### Forward/Backward Safety
- [ ] Migration is reversible — `downgrade()` cleanly drops what `upgrade()` adds with no side effects
- [ ] No data migration in the migration file (the CR explicitly chose NULL-default for legacy rows)

### Hard Rules
- [ ] No `alembic upgrade/downgrade/stamp` was executed against the live DB
- [ ] No other table or column was touched
- [ ] mypy clean on `orch/db/models.py`

## Findings Format

For each finding, classify severity:

- **CRITICAL**: blocks merge (e.g., NOT NULL constraint, wrong down_revision)
- **HIGH**: must fix before merge (e.g., missing downgrade, unrelated changes)
- **MEDIUM**: should fix (e.g., missing column comment, naming drift)
- **LOW**: nice to have (e.g., comment wording)

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00023",
  "completion_status": "complete",
  "files_reviewed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<new_revision>_add_command_gate_timeout_to_workflow_steps.py"
  ],
  "findings": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "verdict": "approved|fix-required",
  "blockers": [],
  "notes": ""
}
```
