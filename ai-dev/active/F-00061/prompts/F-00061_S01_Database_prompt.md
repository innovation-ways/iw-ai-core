# F-00061_S01_Database_prompt

**Work Item**: F-00061 -- Baseline QV gates to prevent fix-cycle scope expansion
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in this Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline. If the migration is broken,
the daemon will refuse to merge the batch.

Allowed for you:
  - `uv run alembic revision --autogenerate -m "add qv_baselines table (F-00061)"` (writes a file only)
  - `uv run alembic history / current / show` (read-only)
  - Running migrations inside testcontainer fixtures via pytest (your tests may exercise them, but S07 owns the full test suite)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00061/F-00061_Feature_Design.md` — read the **Database Changes**, **Scope → In Scope**, **Invariants**, and **Acceptance Criteria AC3/AC4** sections before writing anything
- `orch/db/models.py` — follow the style of `WorkflowStep` (lines ~449–515), `StepRun` (~518–598), `FixCycle` (~602–647)
- `orch/db/migrations/versions/` — read the two most recent migrations (`fb7e5859d479_add_fix_summary_to_fix_cycles.py`, `637c16395a0b_add_pending_migration_log.py`) to see the house style for up/down, index/constraint declarations, and docstrings
- `orch/CLAUDE.md` — ORM rules (`event_metadata` reservation, `_TIMESTAMPTZ` pattern, etc.)
- `docs/IW_AI_Core_Database_Schema.md` — existing schema reference

## Output Files

- Modified: `orch/db/models.py` (add `QvBaseline` class near the existing workflow-related models)
- New: `orch/db/migrations/versions/<uuid>_add_qv_baselines.py` (generated via `alembic revision --autogenerate`)
- `ai-dev/active/F-00061/reports/F-00061_S01_Database_report.md` — step report

## Context

F-00061 introduces a new per-`workflow_step` + per-gate persistence surface so the daemon can store a canonical failure fingerprint computed against the branch's base SHA, then subtract it from later runs on HEAD. This step (S01) delivers ONLY the schema — no daemon code, no parsers, no tests beyond what the migration naturally exercises via `alembic revision --autogenerate`. Scope in the module and daemon hooks is S03/S05; the full test suite is S07.

## Requirements

### 1. `QvBaseline` ORM model

Add a new SQLAlchemy class in `orch/db/models.py` near the other workflow-related models (place it AFTER `FixCycle`). Required columns:

| Column | Type | Notes |
|--------|------|-------|
| `id` | `BigInteger` PK | Surrogate; style matches `StepRun.id` |
| `step_id` | `BigInteger` FK → `workflow_steps.id` ON DELETE CASCADE | `nullable=False`, `index=True` |
| `gate_name` | `Text` | Matches `WorkflowStep.gate` value (e.g. `"lint"`, `"unit-tests"`). `nullable=False` |
| `base_sha` | `Text` | Full git SHA (40 chars). `nullable=False` |
| `fingerprint` | `JSONB` | Parser-produced canonical failure set. `nullable=False`, default `{"failures": []}` via `server_default` |
| `computed_at` | `TIMESTAMPTZ` | `server_default=func.now()`, `nullable=False` |

Constraints:
- `UniqueConstraint("step_id", "gate_name", "base_sha", name="uq_qv_baselines_step_gate_sha")`

Relationships:
- `step: Mapped["WorkflowStep"] = relationship(back_populates="baselines")` on this model
- Add `baselines: Mapped[list["QvBaseline"]] = relationship(back_populates="step", cascade="all, delete-orphan")` on `WorkflowStep`

Use the existing `_TIMESTAMPTZ` / timestamp helpers the file already uses — do NOT introduce a new timestamp style. Use `JSONB` from the same import path other models use (`sqlalchemy.dialects.postgresql.JSONB`).

### 2. Alembic migration

Run `uv run alembic revision --autogenerate -m "add qv_baselines table (F-00061)"` from the repo root. Verify the generated file:

- Up: `op.create_table("qv_baselines", ...)` with all columns, the FK to `workflow_steps.id` with `ondelete="CASCADE"`, the unique constraint, and an index on `step_id` (autogenerate usually emits this from `index=True`)
- Down: `op.drop_table("qv_baselines")` (drop the unique constraint + index implicitly via DROP TABLE is acceptable since autogenerate will emit them first)
- The revision docstring MUST contain the marker string `iw_core_baseline` on its own line so the migration pipeline can associate it with F-00061

If autogenerate produces spurious non-F-00061 diffs (e.g. case changes on enum names, trivial server_default string reformats), edit the file to remove them — F-00061 is additive only.

### 3. Verification

After writing:

1. `uv run alembic history --verbose` — confirm your new revision appears at the head
2. `uv run alembic upgrade head` *inside a testcontainer fixture* if your exploratory script uses one (optional — S07 owns the real test). Do NOT run against port 5433.
3. `uv run mypy orch/db/models.py` — must pass with zero errors
4. `uv run ruff check orch/db/models.py orch/db/migrations/versions/` — zero errors

## Project Conventions

Read `orch/CLAUDE.md` for the ORM rules. Key gotchas:
- `DaemonEvent.metadata` → `event_metadata` in Python (SQLAlchemy reserves `metadata`). Name your fields carefully — don't introduce any that collide with reserved attrs.
- Tests NEVER hit port 5433. Your migration is exercised via testcontainer only.

## TDD Requirement

For a schema step the TDD loop is: write the model + migration, then verify with `alembic history` and `mypy`. Full RED→GREEN→REFACTOR tests come in S07.

## Test Verification (NON-NEGOTIABLE)

Before reporting complete:
1. `uv run alembic history --verbose` shows your revision at the head
2. `uv run mypy orch/db/models.py` — zero errors
3. `uv run ruff check .` — zero NEW errors (pre-existing errors OK; do NOT fix them)

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00061",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<generated>_add_qv_baselines.py"
  ],
  "tests_passed": true,
  "test_summary": "alembic history shows revision at head; mypy clean; ruff clean on changed files",
  "blockers": [],
  "notes": "migration revision id: <hex>"
}
```

- Report the actual migration revision id in `notes` so downstream reviewers and S05 (which references it by name) can find it quickly.
- `completion_status: "complete"` only when mypy + ruff are clean on your changed files and alembic history is happy.
