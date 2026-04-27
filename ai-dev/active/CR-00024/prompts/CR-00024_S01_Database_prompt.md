# CR-00024_S01_Database_prompt

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Allowed: testcontainers via pytest fixtures, `docker ps`/`inspect`/`logs`,
`./ai-core.sh`, `make`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB
(port 5433). Your job here is to write the migration FILE via
`alembic revision --autogenerate`. The daemon applies it at merge time.

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00024 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (Database Changes section, AC4)
- `orch/db/models.py` — current `StepRun` model (line ~613)
- `orch/db/migrations/versions/` — existing migrations (style reference)

## Output Files

- `orch/db/models.py` — modified
- `orch/db/migrations/versions/<new_revision>_add_warned_50pct_at_to_step_runs.py` — new
- `ai-dev/active/CR-00024/reports/CR-00024_S01_Database_report.md` — your report

## Context

You are adding ONE nullable column (`warned_50pct_at`) to the `step_runs` table.
The column stamps the timestamp at which the daemon first emitted a 50%-timeout
warning for that run, used by `_check_step_health` (S03) to suppress duplicate
warnings on subsequent poll cycles. The column must be **nullable** so existing
rows remain valid without backfill — the warn is a one-time signal and missing
it on in-flight runs is fine.

## Requirements

### 1. Update the SQLAlchemy model

Add the new mapped column to `StepRun` in `orch/db/models.py`. Place it
adjacent to the other lifecycle timestamp columns (`started_at`, `completed_at`,
`last_heartbeat`) so related fields stay grouped. Use the project's
`Mapped[]` declarative style with a SQL `comment`:

```python
warned_50pct_at: Mapped[datetime | None] = mapped_column(
    _TIMESTAMPTZ,
    nullable=True,
    comment=(
        "Timestamp at which the daemon first emitted a step_warning_50pct event "
        "for this run. NULL = no warning emitted yet. Used to suppress duplicate "
        "warnings on subsequent poll cycles (CR-00024)."
    ),
)
```

(`_TIMESTAMPTZ` is the existing alias `StepRun` uses for its other timestamp
columns — match the existing pattern, do not invent a new type.)

### 2. Generate the Alembic migration

Run:

```bash
uv run alembic revision --autogenerate -m "add warned_50pct_at to step_runs (CR-00024)"
```

This writes a file under `orch/db/migrations/versions/`. Review it carefully:

- `upgrade()` must call `op.add_column("step_runs", sa.Column("warned_50pct_at", sa.TIMESTAMP(timezone=True), nullable=True, comment="..."))`.
- `downgrade()` must call `op.drop_column("step_runs", "warned_50pct_at")`.
- The `down_revision` must be the current head when you run autogenerate — verify with `uv run alembic history | head -3` and use whatever the head shows. Do NOT hardcode if a newer migration has merged ahead.
- No unrelated changes from autogenerate. If autogenerate emits anything else, edit it out and explain in your report.

### 3. Verify migration integrity

```bash
uv run alembic check 2>&1
uv run alembic history --verbose 2>&1 | head -20
```

Both must succeed. The new revision must be at the head with the prior head as `down_revision`.

## Hard Constraints

- The new column MUST be `nullable=True`. NOT NULL would force backfill semantics we explicitly chose to avoid.
- Do NOT modify any other column or table.
- Do NOT change indexes or constraints.
- Do NOT run `alembic upgrade` or `make db-migrate` against the live DB.

## Project Conventions

Read `orch/CLAUDE.md` for ORM style and `docs/IW_AI_Core_Database_Schema.md` for
column naming conventions. The append-only contract on `step_runs` is unchanged
— `warned_50pct_at` is set once per run lifecycle (never updated to NULL).

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run:

1. `uv run mypy orch/db/models.py` — must be clean
2. `uv run alembic check` — must pass
3. `make lint` — must be clean

Skipping any of these wastes a fix-cycle slot when QV gates catch the same
issue downstream.

## TDD Requirement

Schema changes don't have a meaningful RED phase. The Tests step (S08) writes
the round-trip and regression coverage.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00024",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<new_revision>_add_warned_50pct_at_to_step_runs.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "alembic check OK; mypy clean on orch/db/models.py",
  "blockers": [],
  "notes": "New revision ID: <revision>; down_revision: <prior head — verified via alembic history>"
}
```
