# F-00085 — S02 Code Review (Database / S01)

## Scope reviewed

- Design: `ai-dev/active/F-00085/F-00085_Feature_Design.md`
- S01 report: `ai-dev/active/F-00085/reports/F-00085_S01_Database_report.md`
- Implementation files reviewed in full:
  - `orch/db/models.py`
  - `orch/db/migrations/versions/678ac4dd44b7_f00085_observability_and_control.py`

## What was validated

### `merge_auto_verdicts`
- Composite PK `(project_id, daemon_event_id)` present in ORM and migration.
- FK `daemon_event_id -> daemon_events(id)` with `ON DELETE CASCADE` present.
- FK `project_id -> projects(id)` with `ON DELETE CASCADE` present.
- CHECK constraint `verdict IN ('pending','correct','wrong','partial')` present.
- `verdict_notes` is `NOT NULL DEFAULT ''` (`server_default=text("''")`) in ORM and migration.
- `verdicted_at` is TIMESTAMPTZ (`_TIMESTAMPTZ` / `DateTime(timezone=True)`) with server default `now()`.
- ORM class name is `MergeAutoVerdict` and uses SQLAlchemy 2.0 `Mapped[]` style.

### `auto_merge_project_config`
- Single PK on `project_id` present in ORM and migration.
- FK `project_id -> projects(id)` with cascade present.
- FK `runtime_option_id -> agent_runtime_options(id)` with `ON DELETE SET NULL` present.
- CHECK constraint `phase IS NULL OR phase IN (0, 1)` present (Phase 2/3 correctly blocked).
- `phase` and `runtime_option_id` are both nullable.
- ORM class name is `AutoMergeProjectConfig`.

### Migration integrity
- One migration file added for this DB step: `678ac4dd44b7_f00085_observability_and_control.py`.
- `down_revision = "d1e2f3gpt53c"` and chain resolves to single head (`uv run alembic heads` => `678ac4dd44b7`).
- `upgrade()` creates both tables in one migration.
- `downgrade()` drops both tables in reverse order.
- S01 report records `make migration-check: PASS`.

### Invariants / conventions
- No UPDATE/DELETE logic against `daemon_events` introduced.
- No new columns added to `daemon_events`.
- `_TIMESTAMPTZ` alias reused (not redefined).
- Composite PK pattern uses `PrimaryKeyConstraint` consistently with neighbors.
- No psycopg2 references introduced.

## Quality checks run in S02

- `make lint`: **PASS**
- `make test-unit`: **PASS**

## Findings

No mandatory fixes.

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00085",
  "reviewed_agent": "database-impl",
  "verdict": "PASS",
  "mandatory_fix_count": 0,
  "findings": [],
  "notes": "Review scoped to S01 database deliverables (models + migration) per step prompt."
}
```
