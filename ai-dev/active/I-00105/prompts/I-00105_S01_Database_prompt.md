# I-00105_S01_Database_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

Do NOT run any command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down`, `docker volume rm`,
`docker system prune`, …). Testcontainers spun up by pytest fixtures are the
only exception; read-only `docker ps|inspect|logs` and `./ai-core.sh` / `make`
targets are allowed. If your task seems to need a prohibited command, STOP and
raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Your job is to WRITE the migration FILE. You MUST NOT run `alembic upgrade`,
`downgrade`, or `stamp` against the live orchestration DB (port 5433). Allowed:
`alembic revision --autogenerate -m "..."` (writes a file), `alembic history`,
and migrations inside testcontainer fixtures. The daemon applies the migration
in the merge pipeline. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — the design document. Read it in full first.
- `docs/research/R-00078-agent-tool-output-context-capping.md` — research context.
- `orch/db/models.py` — the `agent_runtime_options` model (class near line 63; `context_window_tokens` near line 74).
- `orch/db/migrations/versions/891343247f66_cr00066_add_context_tokens_columns.py` — CR-00066's migration that added `context_window_tokens`; mirror its shape.

## Output Files

- `orch/db/models.py` (modified)
- `orch/db/migrations/versions/<new revision>.py` (created)
- `ai-dev/work/I-00105/reports/I-00105_S01_Database_report.md` — step report.

## Context

You are implementing S01 of I-00105. The dashboard context gauge currently
measures usage against a model's *full* context window. To compute the
*effective* input budget (`window − max_output − buffer`) the system must store
each runtime's maximum output size. This step adds that field.

## Requirements

### 1. Add `max_output_tokens` to the `agent_runtime_options` model

In `orch/db/models.py`, add a nullable column to the `agent_runtime_options`
model, directly mirroring the existing `context_window_tokens` column
(CR-00066):

```python
max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Match the surrounding column style, ordering, and any comment convention. The
column MUST be nullable — not every runtime publishes an output limit, and the
meter (S03) treats `NULL` as "no reservation".

### 2. Generate the Alembic migration

Run `uv run alembic revision --autogenerate -m "I-00105 add max_output_tokens to agent_runtime_options"`.
Inspect the generated file — autogenerate must produce exactly one
`add_column` (and the matching `drop_column` in `downgrade()`), nothing else.
If it picks up unrelated drift, STOP and raise a blocker.

### 3. Backfill known runtimes in the migration

In the migration's `upgrade()`, after `add_column`, backfill known rows with an
`op.execute(...)` `UPDATE`, exactly as CR-00066's migration backfilled
`context_window_tokens = 200000`:

- The `pi` / `minimax/MiniMax-M2.7` runtime → `max_output_tokens = 131072`
  (MiniMax-M2.7: 204,800-token window, 131,072-token max output — see the design doc / R-00078).
- For `claude` / `opencode` rows, set the documented max output **only where you
  are confident** (otherwise leave `NULL` — that is a safe default). Do not guess.

Match each row by the columns CR-00066 used (`cli_tool` / `model`). The
`downgrade()` simply drops the column.

### 4. Verify the migration

Run **`make migration-check`** — it spins a fresh testcontainer, applies all
migrations from base, asserts the alembic schema matches
`Base.metadata.create_all()`, and round-trips downgrade→upgrade. It MUST pass
before you report completion. If it fails, fix the migration (or the model) so
both agree.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for ORM conventions (SQLAlchemy 2.0
`Mapped[]` style, psycopg v3). **CRITICAL rule from `CLAUDE.md`**: never apply
an uncommitted migration to the production orch DB — you only write the file.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything reported:

1. `make format`
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "I-00105",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "make migration-check: passed",
  "tdd_red_evidence": "n/a — schema + migration only, no production logic",
  "blockers": [],
  "notes": "New revision ID: <id>. Down-revision: <id>. Rows backfilled: <list>."
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S01`
On success: write the report, then
`uv run iw step-done I-00105 --step S01 --report ai-dev/work/I-00105/reports/I-00105_S01_Database_report.md`
On failure: `uv run iw step-fail I-00105 --step S01 --reason "<brief reason>"`
You MUST call `step-done` (with `--report`) or `step-fail` before exiting.
