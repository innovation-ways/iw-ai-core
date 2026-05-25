# I-00112_S01_Database_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step**: S01
**Agent**: Database

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network state-change command (`docker kill`, `docker stop`, `docker rm`, `docker restart`, `docker compose up/down/restart`, `docker volume rm/prune`, `docker system/container/image prune`). Testcontainers spun up by pytest fixtures are the only exception; read-only `docker ps/inspect/logs` is fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head|<rev>`, `alembic downgrade <anything>`, or `alembic stamp <anything>` against the live orchestration DB (port 5433). Your job is to WRITE the revision file. The daemon applies it post-merge. `alembic revision --autogenerate -m "..."` is allowed (writes a file only); `alembic history/current/show` is allowed (read-only). If the migration is broken, the daemon refuses to merge the batch. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00112 --json`.
- `ai-dev/active/I-00112/I-00112_Issue_Design.md` — design document (read sections `Description`, `Root Cause Analysis`, `Database Changes`, `Code Changes`).
- `orch/db/models.py` — current `KeepAliveRun` definition.
- `orch/db/migrations/versions/` — read the most recent revision file for naming/style convention.

## Output Files

- `orch/db/migrations/versions/<new-rev>_i00112_keep_alive_runs_capture_cli_output.py` — new Alembic revision.
- `orch/db/models.py` — modified `KeepAliveRun` model.
- `ai-dev/active/I-00112/reports/I-00112_S01_Database_report.md` — step report.

## Context

The bug: `keep_alive_runs` cannot record stdout, stderr, elapsed_ms, or returncode because the schema has no columns for them. The poller and `fire_claude` already discard those values upstream, so even fixing the Python side would have nowhere to write the data. Your step adds those columns and updates the ORM model — nothing else.

Read `ai-dev/active/I-00112/I-00112_Issue_Design.md` first (especially the **Root Cause Analysis**, **Affected Components**, and **AC5: Migration round-trips cleanly** sections). Then read `CLAUDE.md` (root + `orch/CLAUDE.md`) for ORM conventions and migration rules.

## Requirements

### 1. Generate the Alembic revision

Use `uv run alembic revision --autogenerate -m "I-00112 keep_alive_runs capture CLI output"` to seed the file, then hand-edit so the upgrade is exactly:

```python
op.add_column("keep_alive_runs", sa.Column("stdout", sa.Text(), nullable=True))
op.add_column("keep_alive_runs", sa.Column("stderr", sa.Text(), nullable=True))
op.add_column("keep_alive_runs", sa.Column("elapsed_ms", sa.Integer(), nullable=True))
op.add_column("keep_alive_runs", sa.Column("returncode", sa.Integer(), nullable=True))
```

Downgrade drops the four columns in reverse order:

```python
op.drop_column("keep_alive_runs", "returncode")
op.drop_column("keep_alive_runs", "elapsed_ms")
op.drop_column("keep_alive_runs", "stderr")
op.drop_column("keep_alive_runs", "stdout")
```

**All four columns MUST be nullable** so existing rows survive the upgrade with NULL in the new columns (no backfill is in scope — see the design doc's Notes). The autogenerate step often produces extra noise (`alter_column` for unrelated tables, drop-then-create on indexes, etc.); strip every line that isn't an `add_column` on `keep_alive_runs` from the upgrade and the matching mirror from the downgrade.

The revision's `down_revision` MUST be the head revision at the time you run autogenerate. The daemon's pre-merge rebase step (CR-00021) will rewrite this if the head moves before merge — do not pre-emptively guess.

### 2. Extend the `KeepAliveRun` ORM model

In `orch/db/models.py`, add four `Mapped[…]` columns to `KeepAliveRun` matching the migration exactly. Use the same `Mapped[…]` declarative style as the rest of the file. Suggested ordering (after the existing `error` column):

```python
stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
returncode: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Do NOT add defaults. NULL is the design-intended sentinel for "this row predates the new contract."

### 3. Do NOT touch any other file

This step is schema + ORM only. **Do NOT** touch:
- `orch/keep_alive_service.py` (S03's scope)
- `orch/daemon/keep_alive_poller.py` (S03's scope)
- any template or router (S05's scope)
- any test file (S07's scope)

If you find yourself reaching for any of these, STOP — the work belongs to a downstream step.

## Project Conventions

Read `CLAUDE.md` for:
- SQLAlchemy 2.0 `Mapped[]` declarative style (no `Column()` directly on the class body).
- psycopg v3 (`postgresql+psycopg://`) — NOT psycopg2.
- Migration filenames: `<rev>_<short_slug>.py` lowercase snake_case.

When in doubt, match the most-recent file under `orch/db/migrations/versions/` for revision body style.

## TDD Requirement

This step is RED-exempt (schema-only, no behavioural code). Use `tdd_red_evidence: "n/a — schema + ORM only, no behavioural logic; behavioural RED owned by S03"` in your result contract.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fixes formatting drift on touched files.
2. **`make typecheck`** — must report zero errors on `orch/db/models.py` and the new revision file.
3. **`make lint`** — must report zero errors on the same.

If any tool is unavailable, STOP and raise a blocker — do not silently skip.

## Migration Verification (NON-NEGOTIABLE)

You MUST run **`make migration-check`** before reporting completion. It spins a fresh testcontainer, runs `alembic upgrade head` from base, asserts the alembic schema matches `Base.metadata.create_all()` (catches model↔migration drift), and round-trips through `downgrade base → upgrade head`. If it fails, fix the migration or the model and re-run until green. Do not report `tests_passed: true` while this gate is red.

## Test Verification

Run only `make migration-check`. Do NOT run `make test-unit` or `make test-integration` — those are downstream QV gates. The migration round-trip is sufficient evidence that schema + ORM agree.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Database",
  "work_item": "I-00112",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/<rev>_i00112_keep_alive_runs_capture_cli_output.py",
    "orch/db/models.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "make migration-check: PASS",
  "tdd_red_evidence": "n/a — schema + ORM only, no behavioural logic; behavioural RED owned by S03",
  "blockers": [],
  "notes": "Revision file is '<rev>'. Down-revision points at current head '<prev_rev>'. All four columns nullable; no backfill; existing rows now show NULL in the new fields."
}
```

## Lifecycle Commands

```bash
# Start
uv run iw step-start I-00112 --step S01

# On success
mkdir -p ai-dev/active/I-00112/reports
uv run iw step-done I-00112 --step S01 --report ai-dev/active/I-00112/reports/I-00112_S01_Database_report.md

# On failure
uv run iw step-fail I-00112 --step S01 --reason "<short reason>"
```

You MUST call step-done (with --report) or step-fail before exiting.
