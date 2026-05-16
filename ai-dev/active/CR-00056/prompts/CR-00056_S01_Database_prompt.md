# CR-00056_S01_Database_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
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
will apply it as part of the merge pipeline.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00056 --json` over the static manifest snapshot.
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — Design document
- `orch/db/models.py` — read the `StepRun` class around line 778 to see the existing column style (psycopg v3 + SQLAlchemy 2.0 Mapped[] declarative syntax, server_default text() patterns, comments)

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S01_Database_report.md` — Step report

## Context

You are implementing the schema half of **CR-00056 — Surface step prompts in dashboard**.

The end goal is to let operators view the prompt sent to each AI agent from the item-detail page in the dashboard, including for historical items where the worktree has been reaped. Reading from disk on demand is not viable — the file disappears post-merge. So we snapshot the prompt **content** into the DB at step launch time.

This step adds the storage. Subsequent steps (S04) wire the daemon to populate it, (S06) add the dashboard route, and (S08) add the UI.

Read the design document (`Impact Analysis → Affected Components` and `Acceptance Criteria → AC1`) first. Then read `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md` for project conventions.

## Requirements

### 1. Add two TEXT NULL columns to the `StepRun` ORM model

In `orch/db/models.py`, locate the `StepRun` class (around line 778). Add two new columns *after* the existing column declarations and *before* `__table_args__`:

```python
prompt_text: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment=(
        "Snapshot of the prompt content captured at step launch. "
        "Set by the daemon when this StepRun is created. NULL for pre-CR-00056 rows. "
        "Append-only — never updated after creation. (CR-00056)"
    ),
)
fix_prompt_text: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment=(
        "Snapshot of the fix-cycle prompt content for retry runs. "
        "Set by the daemon when a fix-cycle StepRun is created. NULL for "
        "non-fix-cycle runs and pre-CR-00056 rows. Append-only. (CR-00056)"
    ),
)
```

Match the style of the existing nullable Text columns nearby (e.g., `command`, `worktree_path`, `error_message`, `log_content`). Do NOT add an index — these are display-only and never appear in WHERE clauses.

Do **NOT** modify `WorkflowStep.prompt_file`, `FixCycle.fix_prompt`, or any other existing column. The new columns live alongside the path columns; the path columns stay for debugging.

### 2. Generate the alembic migration

From the project root, run:

```bash
uv run alembic revision --autogenerate -m "CR-00056: add prompt_text and fix_prompt_text to step_runs"
```

This creates a new file under `orch/db/migrations/versions/`. Open it and verify:

- The `upgrade()` body calls `op.add_column("step_runs", sa.Column("prompt_text", sa.Text(), nullable=True, comment=...))` and same for `fix_prompt_text`.
- The `downgrade()` body calls `op.drop_column("step_runs", "fix_prompt_text")` then `op.drop_column("step_runs", "prompt_text")` (reverse order from upgrade).
- `down_revision` points at the current head revision (whatever `alembic history` shows as latest).
- The revision is **not** flagged with extraneous DDL (e.g., dropping/recreating triggers, touching FTS columns, modifying unrelated tables). If autogenerate produced noise, manually edit the file to keep only the two add_column statements (and their drop counterparts).
- The comment strings on the migration columns match the ORM model comments — they are what shows up in PostgreSQL's `\d+ step_runs`.

### 3. Run `make migration-check` to verify drift + round-trip

Per the **Migration Verification (NON-NEGOTIABLE)** section below, run:

```bash
make migration-check
```

This must pass before you report completion. It spins a fresh testcontainer, runs `alembic upgrade head` from base, compares the resulting schema to `Base.metadata.create_all()` (catches model↔migration drift), and round-trips through `downgrade base → upgrade head`. If it fails, fix the migration file (or the ORM model) and re-run.

### 4. Do NOT apply the migration to the live DB

The new migration must remain **unapplied** on the orchestration DB at port 5433. The daemon's merge pipeline will apply it via `iw migrations apply` on its own schedule. Agents never call `alembic upgrade` against port 5433 — that path destroys worktree compose stacks (see I-00075 / I-00076 in `CLAUDE.md`).

## Project Conventions

Read the project's `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md` for:

- SQLAlchemy 2.0 sync `Mapped[]` declarative style
- psycopg v3 driver (NOT psycopg2)
- Migration patterns and the agents-generate / daemon-applies split
- `step_runs` is append-only — never UPDATE
- The `DaemonEvent.metadata` → `event_metadata` Python rename gotcha (does not apply here, but illustrates the team's reserved-attribute discipline)

## TDD Requirement

For a pure schema-add step there is no behavioural logic to TDD. Use the `tdd_red_evidence` field with `"n/a — schema-only column addition, behaviour is exercised by the daemon-snapshot integration test in S11"`.

The S11 (tests-impl) step will add a unit test that constructs `StepRun(..., prompt_text="...", fix_prompt_text="...")` — that test is the RED-first evidence for the column existence, but it lives in the dedicated tests step per project convention.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage.
2. **`make typecheck`** — must report zero errors involving files you touched.
3. **`make lint`** — must report zero errors.

Populate the `preflight` object in the result contract.

## Migration Verification (Database steps only — NON-NEGOTIABLE)

You MUST run **`make migration-check`** before reporting completion. Do not report `tests_passed: true` while it is red — downstream agents will inherit a wrong schema (see F-00079 post-mortem).

## Test Verification (NON-NEGOTIABLE)

This is a Database step. Run only the **targeted** test:

```bash
uv run pytest tests/integration/test_migrations_round_trip.py -v
```

Do NOT run `make test-integration` (full suite owned by S19 QV gate).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<new_revision_filename>.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "migration-check passed; round-trip + drift check green",
  "tdd_red_evidence": "n/a — schema-only column addition, behaviour exercised by daemon-snapshot integration test in S11",
  "blockers": [],
  "notes": ""
}
```
