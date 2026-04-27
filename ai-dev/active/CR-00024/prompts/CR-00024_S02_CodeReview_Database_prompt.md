# CR-00024_S02_CodeReview_Database_prompt

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
**Step**: S02
**Agent**: code-review-impl

---

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00024 --json` over reading workflow-manifest.json (CR-00023).
- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (AC4 idempotency contract relies on this column)
- `ai-dev/active/CR-00024/reports/CR-00024_S01_Database_report.md` — S01's report
- `orch/db/models.py` — modified `StepRun`
- `orch/db/migrations/versions/<new_revision>_add_warned_50pct_at_to_step_runs.py` — new migration

## Output Files

- `ai-dev/active/CR-00024/reports/CR-00024_S02_CodeReview_Database_report.md`

## Review Checklist

### Schema correctness
- [ ] `warned_50pct_at` is `nullable=True` (NOT NULL would force backfill semantics)
- [ ] Column type is `TIMESTAMPTZ` (timezone-aware) — matches the project's `_TIMESTAMPTZ` alias
- [ ] No default value is set (a default would silently stamp existing rows)
- [ ] Column includes a SQL `comment` matching the project's convention
- [ ] Column is placed adjacent to other lifecycle timestamps (started_at / completed_at / last_heartbeat) for readability

### Migration correctness
- [ ] `down_revision` matches whatever the head was when S01 ran (verify via `alembic history | head -3`)
- [ ] `upgrade()` adds the column with `nullable=True`
- [ ] `downgrade()` drops the column
- [ ] No unrelated changes from autogenerate

### Naming + conventions
- [ ] Column name is `warned_50pct_at` (not `warn_50pct_at` or other variant) — matches the design doc and S03's expected attribute access
- [ ] Migration filename follows `<hash>_<descriptor>.py` pattern
- [ ] Migration message matches the requested format

### Forward/backward safety
- [ ] Migration is reversible
- [ ] No data migration in the migration file (the design explicitly chose NULL-default for legacy rows)

### Hard rules
- [ ] No `alembic upgrade/downgrade/stamp` was executed against the live DB
- [ ] No other column or table touched
- [ ] mypy clean on `orch/db/models.py`

## Findings Severity

- **CRITICAL**: NOT NULL constraint, wrong down_revision, name mismatch with design
- **HIGH**: missing downgrade, unrelated changes
- **MEDIUM**: missing comment, naming drift
- **LOW**: comment wording

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00024",
  "completion_status": "complete",
  "files_reviewed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<new_revision>_add_warned_50pct_at_to_step_runs.py"
  ],
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "verdict": "approved|fix-required",
  "blockers": [],
  "notes": ""
}
```
