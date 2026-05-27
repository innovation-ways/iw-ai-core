# F-00090_S01_Database_prompt

**Work Item**: F-00090 -- Regression-rate tracking — correlate filed Incidents back to the merge that introduced the regression
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
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00090 --json`.
- `ai-dev/active/F-00090/F-00090_Feature_Design.md` -- Design document
- `orch/db/models.py` — `WorkItem` model lives at line 514; extend it here.
- `orch/db/migrations/versions/` — directory for the new revision file.
- `docs/IW_AI_Core_Database_Schema.md` — must mention the new columns in this step.

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_S01_Database_report.md` -- Step report
- New file: `orch/db/migrations/versions/<rev>_f_00090_regression_link_fields.py`
- Modified: `orch/db/models.py`
- Modified: `docs/IW_AI_Core_Database_Schema.md`

## Context

You are implementing the database layer for **F-00090 — Regression-rate tracking**. Add five new nullable fields to the `WorkItem` model so each Incident can be linked back to the merge that introduced the regression, plus an index and an ENUM. The Alembic migration must round-trip cleanly.

Read the design document first (`F-00090_Feature_Design.md`) for full scope. Then read `CLAUDE.md` for project conventions.

## Requirements

### 1. Add fields to the `WorkItem` model (`orch/db/models.py`)

Append five new columns to the existing `WorkItem` class (line 514):

- `introduced_by_work_item_id: Mapped[str | None] = mapped_column(Text, nullable=True, comment="ID of the work item whose merge introduced the regression this Incident reports. NULL when not yet classified or when the classification is pre-existing/unknown. Indexed for badge-count rollups on Batches/History views (F-00090).")`
- `introduced_by_commit_sha: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Optional commit SHA the operator pasted alongside the introducing work item; used when the operator knows the exact commit (F-00090).")`
- `regression_classification: Mapped[<EnumType> | None] = mapped_column(<enum col>, nullable=True, comment="How this Incident relates to a prior merge: regression / pre_existing / unknown. NULL means not yet classified (F-00090).")`
- `classified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True, comment="UTC timestamp when the regression classification was last persisted (F-00090).")`
- `classified_by: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Identity that performed the classification — 'operator:<user>' for UI submissions, 'heuristic:auto' when the operator accepted the heuristic's top suggestion (F-00090).")`

Define the ENUM the same way other `WorkItem` enums are defined in this file (e.g. `WorkItemStatus`); use a Python `enum.Enum` class `RegressionClassification` with values `regression`, `pre_existing`, `unknown` and bind it via SQLAlchemy `Enum(..., name="regression_classification_enum", create_type=False)` for the model, and create the PG ENUM in the migration. Match the style and module location of `WorkItemStatus` and the `_work_item_status_col` helper at the top of the file.

### 2. Create the Alembic revision

Run `uv run alembic revision --autogenerate -m "F-00090 regression link fields"` and then EDIT the generated file to:

- Create the PG ENUM type `regression_classification_enum` in `upgrade()`.
- Add the five `op.add_column(...)` calls with the same `comment=` strings as the model.
- Add `op.create_index("ix_work_items_introduced_by_work_item_id", "work_items", ["introduced_by_work_item_id"])`.
- Implement a complete `downgrade()` that drops the index, drops the five columns, and drops the ENUM. The round-trip test will catch any omission.

The autogenerate output is a starting point only — verify every operation by reading the generated file. **Do not** delete the file and regenerate without understanding what changed.

### 3. Document the new fields

Append a short subsection to `docs/IW_AI_Core_Database_Schema.md` under the `work_items` table description listing the five new fields, their nullability, and a one-line rationale. Cross-reference F-00090.

### 4. Verify the migration

After writing the revision file, run:

```bash
make migration-check
```

This is the canonical round-trip gate. It must report PASS. If it fails (e.g. drift between model and migration), iterate on the migration until green. Do NOT mark `tests_passed: true` while this gate is red — downstream steps will inherit a wrong schema (see F-00079 post-mortem).

## Project Conventions

Read the project's `CLAUDE.md` for:

- SQLAlchemy 2.0 `Mapped[]` declarative style — match `WorkItem`'s existing fields exactly.
- psycopg v3 driver — never psycopg2.
- `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` are raw DDL — don't disturb the existing FTS triggers.
- Composite PK `(project_id, id)` on `work_items` — preserve it.
- Append-only tables (`step_runs`, `fix_cycles`, …) — `work_items` is NOT append-only; UPDATEs are allowed.

## TDD Requirement

Database steps are exempt from the strict RED-first contract because the canonical verification is the migration round-trip gate. Use:

`tdd_red_evidence: "n/a — schema/migration only; verified by make migration-check round-trip"`

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting completion, run in order:

1. `make format` — auto-fix and re-stage.
2. `make typecheck` — zero errors on touched files.
3. `make lint` — zero errors.

Record results in `preflight` in the result contract.

## Test Verification (NON-NEGOTIABLE)

Run **only** `make migration-check` — that is the targeted verification for this step. Do not run the full unit or integration suites.

## Migration Verification (Database steps only — NON-NEGOTIABLE)

`make migration-check` MUST be green before reporting `tests_passed: true`. See design doc AC1 and Invariant 7.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_f_00090_regression_link_fields.py",
    "docs/IW_AI_Core_Database_Schema.md"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "make migration-check: PASS (round-trip OK, no model↔migration drift)",
  "tdd_red_evidence": "n/a — schema/migration only; verified by make migration-check round-trip",
  "blockers": [],
  "notes": ""
}
```
