# F-00081_S01_Database_prompt

**Work Item**: F-00081 -- Per-Item / Per-Step Agent + Model Override
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by pytest are exempt. Read-only `docker ps` / `docker inspect` / `docker logs` are allowed. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Your job is to **write** the Alembic migration file and the SQLAlchemy ORM additions. Do NOT run `alembic upgrade`, `alembic stamp`, or any migration mutation against the live DB on port 5433. The daemon applies migrations during the merge pipeline; testcontainer fixtures apply them inside isolated containers for tests.

You MAY run `uv run alembic revision --autogenerate -m "..."` (writes a file only) and `uv run alembic history|current|show` (read-only). You MAY also `make test-integration` or `make test-unit` to validate the migration in a testcontainer.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00081 --json`.
- `ai-dev/active/F-00081/F-00081_Feature_Design.md` — the design document.
- `orch/db/models.py` — existing ORM models (`WorkItem` near line ~580, `WorkflowStep` ~580+, `StepRun` ~675+).
- `orch/db/migrations/versions/` — recent migrations for style reference (look at the most recent one for header conventions and `op.bulk_insert` patterns).

## Output Files

- `ai-dev/active/F-00081/reports/F-00081_S01_Database_report.md` — step report.
- One Alembic migration file under `orch/db/migrations/versions/`.
- Edits to `orch/db/models.py` (new `AgentRuntimeOption` model + three `agent_runtime_option_id` FK columns).

## Context

You are implementing the database foundation of **F-00081 — Per-Item / Per-Step Agent + Model Override**. Read the design doc first to understand the full feature, then read `CLAUDE.md` and `orch/CLAUDE.md` for project-specific conventions (sync SQLAlchemy 2.0, `Mapped[]` declarative, psycopg v3, composite PKs, FTS triggers, append-only tables).

## Requirements

### 1. New table `agent_runtime_options`

Add to `orch/db/models.py`:

```python
class AgentRuntimeOption(Base):
    __tablename__ = "agent_runtime_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cli_tool: Mapped[str] = mapped_column(Text, nullable=False)  # 'opencode' | 'claude'
    model: Mapped[str] = mapped_column(Text, nullable=False)
    cli_label: Mapped[str] = mapped_column(Text, nullable=False)
    model_label: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("cli_tool", "model", name="uq_agent_runtime_options_cli_model"),
        Index(
            "uq_agent_runtime_options_one_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        {"comment": "Catalogue of curated (cli_tool, model) pairs the daemon can launch."},
    )
```

The partial unique index on `is_default = true` enforces at most one default row.

### 2. Three new FK columns

Add to `WorkItem`, `WorkflowStep`, `StepRun`:

```python
agent_runtime_option_id: Mapped[int | None] = mapped_column(
    Integer,
    ForeignKey("agent_runtime_options.id", ondelete="RESTRICT"),
    nullable=True,
    comment="Override pair to use for this {item|step|run}; NULL = inherit. F-00081.",
)
```

`ON DELETE RESTRICT` is required so a row referenced by historical step_runs cannot be silently dropped (boundary case in design doc).

### 3. Constraint: prevent disabling the default row

Add a CHECK constraint or trigger to `agent_runtime_options` that rejects `enabled=false` when `is_default=true`. Implement as a CHECK constraint on the table:

```python
CheckConstraint(
    "NOT (is_default = true AND enabled = false)",
    name="ck_agent_runtime_options_default_must_be_enabled",
),
```

### 4. Alembic migration

Generate a new revision (`uv run alembic revision --autogenerate -m "F-00081 agent runtime options"`), then **manually verify**:

- The migration creates `agent_runtime_options` with all columns, the unique constraint on `(cli_tool, model)`, the partial unique index on `is_default = true`, and the CHECK constraint.
- The migration adds the three FK columns to `work_items`, `workflow_steps`, `step_runs`.
- The migration includes an `op.bulk_insert` of these five seed rows (use `op.bulk_insert(table_definition, rows)`):

| cli_tool | model | cli_label | model_label | display_name | is_default | sort_order |
|---|---|---|---|---|---|---|
| opencode | minimax | OpenCode | MiniMax 2.7 | OpenCode + MiniMax 2.7 | true | 10 |
| opencode | claude-sonnet-4-6 | OpenCode | Claude Sonnet 4.6 | OpenCode + Claude Sonnet 4.6 | false | 20 |
| opencode | claude-opus-4-7 | OpenCode | Claude Opus 4.7 | OpenCode + Claude Opus 4.7 | false | 30 |
| claude | claude-sonnet-4-6 | Claude Code | Sonnet 4.6 | Claude Code + Sonnet 4.6 | false | 40 |
| claude | claude-opus-4-7 | Claude Code | Opus 4.7 | Claude Code + Opus 4.7 | false | 50 |

- The downgrade drops the FK columns first, then the table.

### 5. Validate against testcontainer

Run `make test-integration` to verify:
- The migration applies cleanly upgrade and downgrade in the testcontainer fixture.
- The seed rows land.
- A test that attempts `UPDATE agent_runtime_options SET enabled=false WHERE is_default=true` is rejected.
- A test that inserts a second `is_default=true` row is rejected.

If the autogenerate misses the partial index or CHECK constraint (Alembic occasionally omits these), edit the migration by hand to add them with `op.create_index(..., postgresql_where=...)` and `op.create_check_constraint(...)`.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`:

- Sync SQLAlchemy 2.0, `Mapped[]` declarative, psycopg v3 (`postgresql+psycopg://`).
- Composite PK pattern is project-wide, but this catalogue is global (no `project_id` column).
- Migration headers follow recent migrations' style — see `orch/db/migrations/versions/` for the latest.
- `Base.metadata.create_all()` is what tests rely on. Confirm the new model is picked up by importing it in `orch/db/models.py`'s namespace (which it will be automatically since you add the class to that module).

## TDD Requirement

Follow Red-Green-Refactor:

1. **RED**: Write integration tests in `tests/integration/test_agent_runtime_options.py` that assert the table exists, the seed rows are present, the CHECK constraint rejects `is_default=true` + `enabled=false`, the partial unique index rejects two `is_default=true` rows, and FK referential integrity prevents deletion of a referenced row.
2. **GREEN**: Add the model + migration; run tests; iterate until green.
3. **REFACTOR**: Clean up; ensure column comments are present and informative.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:
1. `make format` — auto-fixes formatting drift; re-stage if it edits files.
2. `make typecheck` — zero new errors involving files you touched.
3. `make lint` — zero errors.

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration` and `make test-unit` (the latter is fast and catches model-import problems). Do not report `tests_passed: true` unless both pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_f00081_agent_runtime_options.py",
    "tests/integration/test_agent_runtime_options.py"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
