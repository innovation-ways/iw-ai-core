# CR-00035_S01_Database_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

Standard policy. You MUST NOT run `docker kill | stop | rm | restart`, any `docker compose` lifecycle command, or volume/network/system pruning. Testcontainer fixtures spun up by pytest are exempt. Read-only `docker ps / inspect / logs` is allowed. If your task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade <anything>`, `alembic downgrade <anything>`, or `alembic stamp <anything>` against the live orchestration DB. Your job is to WRITE the migration FILE only. Allowed for agents: `alembic revision --autogenerate -m "..."` (writes the file), `alembic history / current / show` (read-only), and migrations inside testcontainer fixtures. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json` (authoritative; the manifest may be out of date — CR-00023).
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` — design document (required reading).
- `orch/db/models.py` — existing `DocGenerationJob` definition at lines 1372–1452.
- `orch/db/migrations/versions/` — pattern reference for new revisions.
- `docs/IW_AI_Core_Database_Schema.md` — schema documentation (update if it documents the column list).

## Output Files

- `orch/db/migrations/versions/<rev>_add_report_to_doc_generation_jobs.py` — new migration file
- `orch/db/models.py` — updated `DocGenerationJob` model (one new field)
- `ai-dev/active/CR-00035/reports/CR-00035_S01_Database_report.md` — step report

## Context

This step adds a single nullable JSONB column to `doc_generation_jobs` so subsequent backend work (S05, observability unit) can persist a structured execution report when a job terminates. **Schema-only change. No data migration. Reversible.**

Read the design document first — particularly the `## Desired Behavior` and `## Database Changes` sections — before touching any file.

## Requirements

### 1. Generate the Alembic migration

Use the autogenerate flow:

```bash
uv run alembic revision --autogenerate -m "add report to doc_generation_jobs"
```

Then **manually inspect the generated file** and ensure:

- `op.add_column("doc_generation_jobs", sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Structured post-mortem of the doc-generation job: outcome, duration, tool calls, diagnosis, etc."))`
- `op.drop_column("doc_generation_jobs", "report")` in the downgrade.
- No spurious diff lines from unrelated drift (autogenerate sometimes invents `alter_column` diffs against existing FTS triggers — remove those if they appear).
- `down_revision` points at the current head.

If autogenerate misses the column entirely (it can — JSONB additions are sometimes detected as no-op when the model isn't yet updated), write the migration manually using the same skeleton as `6a5e03db855a_add_project_docs_tables.py`.

### 2. Update the ORM model

In `orch/db/models.py`, add the field to `DocGenerationJob` (after `lint_warnings`, before `duration_seconds`):

```python
report: Mapped[dict[str, Any] | None] = mapped_column(
    JSONB,
    nullable=True,
    comment=(
        "Structured post-mortem of the job: outcome, duration_seconds, "
        "skill_used, cli_tool, command_issued, log_size_bytes, log_line_count, "
        "tool_calls, doc_update_invocations, lint_warning_count, diagnosis."
    ),
)
```

Match the import style already in use (`JSONB` from `sqlalchemy.dialects.postgresql`, already imported in this file).

### 3. Verify the migration round-trips

Run the project's migration test in a testcontainer (do NOT touch the live DB):

```bash
make test-integration -- -k doc_generation
```

If the project has a dedicated migration round-trip test, run it. If not, the integration suite already runs `Base.metadata.create_all()` against testcontainers — your model change must be compatible with that. Verify locally:

```bash
uv run alembic upgrade head    # ONLY inside a testcontainer fixture, not against port 5433
```

If you cannot easily exercise the round-trip without touching the live DB, STOP and raise it as a blocker — do not run alembic against port 5433.

### 4. Update schema docs

If `docs/IW_AI_Core_Database_Schema.md` enumerates columns of `doc_generation_jobs`, add `report` with the comment from above. If it only describes the table at a high level, no doc change is needed.

## Project Conventions

Read `orch/CLAUDE.md` and `tests/CLAUDE.md`. Critical rules for this step:

- ORM is **SQLAlchemy 2.0 sync** with `Mapped[]` declarative style.
- Driver is **psycopg v3** — never psycopg2.
- `DaemonEvent.metadata` → `event_metadata` Python attribute (DB column is still `metadata`). Trap: don't accidentally rename our `report` to a reserved name.
- Append-only tables (`step_runs`, `fix_cycles`, `daemon_events`, `test_runs`, `project_doc_versions`) — `doc_generation_jobs` is **not** append-only, so adding an updateable column here is fine.
- FTS triggers (`FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`) live in raw DDL — your migration must NOT touch them.

## TDD Requirement

Schema-only changes are not directly TDD-able, but you MUST verify the migration round-trips inside a testcontainer fixture (not the live DB). The integration test suite is your safety net — run it.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `complete`:

1. `make format` — auto-fixes drift; re-stage if changed.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Skipping any of these wastes a fix-cycle slot when the QV gate steps catch the same issue downstream.

## Test Verification

Run `make test-unit` and `make test-integration` (or `make allure-integration`). Do NOT report `tests_passed: true` unless ALL pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00035",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/<rev>_add_report_to_doc_generation_jobs.py",
    "orch/db/models.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Down-revision: <prev_rev>. Column type: JSONB nullable. No data backfill. Reversible."
}
```
