# CR-00023_S01_Database_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following or any command that changes Docker
container/volume/network state. Allowed: testcontainers spun up by pytest
fixtures, read-only introspection (`docker ps`, `docker inspect`,
`docker logs`), and invoking `./ai-core.sh` / `make` targets.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live
orchestration DB (port 5433) from an agent context. Your job here is to
write the migration FILE via `alembic revision --autogenerate`. The
daemon applies it as part of the merge pipeline.

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design document (read **Database Changes** section)
- `orch/db/models.py` — current `WorkflowStep` model definition (line ~540)
- `orch/db/migrations/versions/` — existing migrations (use as style reference)

## Output Files

- `orch/db/models.py` — modified
- `orch/db/migrations/versions/<new_revision>_add_command_gate_timeout_to_workflow_steps.py` — new
- `ai-dev/active/CR-00023/reports/CR-00023_S01_Database_report.md` — your step report

## Context

You are adding three new optional columns to the `workflow_steps` table that will
let the DB store the QV-gate `command`/`gate`/`timeout` fields currently only
present in `workflow-manifest.json`. This is the schema foundation for the rest
of the CR. The columns must all be **nullable** so existing rows remain valid
without backfill — the daemon (S03) will fall back to manifest read for legacy
NULL rows.

## Requirements

### 1. Update the SQLAlchemy model

Add three new mapped columns to `WorkflowStep` in `orch/db/models.py`, placed
immediately after the existing `description` column (so related metadata stays
grouped). Use the project's standard `Mapped[]` declarative style and include a
SQL `comment` matching the existing pattern:

```python
command: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment=(
        "Shell command for qv-gate steps (e.g., 'make lint'). NULL for "
        "implementation steps and for items registered before CR-00023."
    ),
)
gate: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment=(
        "Gate name for qv-gate steps (e.g., 'lint', 'format', 'typecheck'). "
        "NULL for non-gate steps and for items registered before CR-00023."
    ),
)
timeout_secs: Mapped[int | None] = mapped_column(
    Integer,
    nullable=True,
    comment=(
        "Per-step timeout override in seconds. NULL = use project default. "
        "Sourced from the manifest's 'timeout' field at registration."
    ),
)
```

Place them after `description` and before `status`.

### 2. Generate the Alembic migration

Run `uv run alembic revision --autogenerate -m "add command/gate/timeout_secs to workflow_steps (CR-00023)"`.
This writes a file under `orch/db/migrations/versions/`.

Review the generated migration carefully:

- `upgrade()` must call `op.add_column("workflow_steps", sa.Column("command", sa.Text(), nullable=True, comment="..."))` for each new column.
- `downgrade()` must drop all three columns in reverse order: `op.drop_column("workflow_steps", "timeout_secs")`, then `gate`, then `command`.
- The `down_revision` must be the current head at the time you run `alembic revision --autogenerate`. As of design time (2026-04-27) the head is `c062b6bf5eb3` (CR-00022 OSS redesign). Verify with `uv run alembic history | head -3` and use whatever the current head is at run time — do NOT hardcode a value if a newer migration has merged ahead of you.
- Do NOT include any unrelated changes the autogenerator might have picked up. If autogenerate emits anything else, edit it out and explain why in your report.

### 3. Verify migration integrity

Without applying to the live DB, verify the migration loads cleanly:

```bash
uv run alembic check 2>&1
uv run alembic history --verbose 2>&1 | head -20
```

Both should succeed. The migration must be at the new head with the prior head's revision ID as `down_revision`.

## Hard Constraints

- All three new columns MUST be `nullable=True`. Do NOT add a default value or `NOT NULL` constraint — this would force backfill semantics we explicitly chose to avoid (see CR design's Data Migration section).
- Do NOT modify any other column or table. Do NOT change indexes or constraints.
- Do NOT run `alembic upgrade` or `make db-migrate`. The daemon applies migrations at merge time.

## Project Conventions

Read `orch/CLAUDE.md` and `docs/IW_AI_Core_Database_Schema.md` for ORM style,
column naming conventions, and migration patterns.

## TDD Requirement

Schema changes don't have a meaningful RED phase, but you MUST verify:

1. After model edit, `uv run mypy orch/db/models.py` passes with zero errors.
2. After migration generation, `uv run alembic check` passes.
3. The existing `tests/integration/test_models.py` (if present) still imports cleanly: `uv run python -c "from tests.integration import test_models"`.

The Tests step (S09) will write the round-trip and regression coverage.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00023",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<new_revision>_add_command_gate_timeout_to_workflow_steps.py"
  ],
  "tests_passed": true,
  "test_summary": "alembic check OK; mypy clean on orch/db/models.py",
  "blockers": [],
  "notes": "New revision ID: <revision>; down_revision: <prior head — verified via alembic history>"
}
```
