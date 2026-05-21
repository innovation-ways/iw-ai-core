# I-00102_S01_Database_prompt

**Work Item**: I-00102 — iw register silently ignores design-package drift; approve must auto-refresh workflow_steps
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

Your job here is to WRITE the alembic revision file. Do NOT run `alembic upgrade` against the live orch DB. The daemon will apply the migration during the merge pipeline (testcontainer dry-run + post-merge apply). Allowed: `uv run alembic revision --autogenerate -m "..."` (writes a file only), `uv run alembic history` / `current` / `show` (read-only), and migration round-trips inside testcontainer fixtures.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## Input Files

- **Runtime step state** — `uv run iw item-status I-00102 --json` (DB is the source of truth per CR-00023).
- `ai-dev/active/I-00102/I-00102_Issue_Design.md` — design document (read **Description**, **Root Cause Analysis**, **Database Changes**, **Acceptance Criteria** in full).
- `orch/db/models.py` — current `WorkItem` model (you will add one column).
- `orch/db/migrations/versions/` — adjacent example migrations for style.
- `CLAUDE.md` (project root) and `orch/CLAUDE.md` — naming and ORM conventions.

## Output Files

- `orch/db/models.py` — `WorkItem.manifest_digest` column added.
- `orch/db/migrations/versions/<rev>_add_manifest_digest_to_work_items.py` — alembic revision.
- `ai-dev/active/I-00102/reports/I-00102_S01_Database_report.md` — step report.

## Context

This step lays the schema groundwork for I-00102. S02 (Backend) depends on `WorkItem.manifest_digest` existing both in the ORM and in the DB. Keep the scope strictly to the column + migration — no behaviour change in this step.

## Requirements

### 1. ORM column

Add to `WorkItem` in `orch/db/models.py`:

```python
manifest_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- Column type: `Text` (digests are hex strings; we never compare with `LIKE` so no length cap is needed; use `Text` to match adjacent text columns).
- Nullable: True. Existing rows have no digest; the backfill strategy is "approve recomputes on first hit" (see design AC5). Do **not** add a default.
- Place the column in `WorkItem` near other meta columns (e.g., `config`, `impacted_paths`) — match the existing field order/grouping you see in `orch/db/models.py`.
- Add a one-line docstring or inline comment referencing I-00102.

### 2. Alembic migration

Generate via:

```bash
uv run alembic revision --autogenerate -m "add manifest_digest to work_items (I-00102)"
```

Then hand-tune the generated file so:

- `upgrade()` adds the column with `nullable=True`, no default, no server default.
- `downgrade()` drops the column.
- The revision file imports nothing the codebase doesn't already use (compare with neighbours under `orch/db/migrations/versions/`).
- The revision's `down_revision` is the current head (single head — if there are multiple, STOP and raise a blocker; do NOT silently merge heads).

### 3. Migration round-trip verification

After writing the migration, run **`make migration-check`** in your worktree (testcontainer-backed — safe). Required to be green before reporting completion. This runs `tests/integration/test_migrations_round_trip.py`, which asserts:

- `alembic upgrade head` from base succeeds.
- The resulting schema matches `Base.metadata.create_all()` (catches model↔migration drift).
- `downgrade base → upgrade head` round-trips cleanly.

If it fails, fix the migration (or the model) until both halves agree.

### 4. No behaviour change

Do NOT touch `orch/cli/item_commands.py`, the daemon, or anything that reads/writes the column. That is S02's work. This step's purpose is purely additive schema.

## Project Conventions

Read `CLAUDE.md` for ORM style (SQLAlchemy 2.0 `Mapped[]` declarative), the psycopg v3 driver requirement, and the strict-no-live-DB rules. Read `orch/CLAUDE.md` for migration patterns and the "agents generate, daemon applies" boundary.

## TDD Requirement

This step is schema-only (no application behaviour). No new unit/integration test is required from S01 — the behaviour tests live in S03 and exercise the column via the Backend path. Use `tdd_red_evidence: "n/a — schema-only, behaviour tests live in S03"` in the result contract.

The `make migration-check` round-trip serves as the schema-level regression net for this step.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting. If it touches files, inspect the diff.
2. `make typecheck` — zero new errors involving files you touched.
3. `make lint` — zero new errors.
4. `make migration-check` — must be green (see §3 above).

## Test Verification (NON-NEGOTIABLE)

- Run `make migration-check` only — that is this step's targeted verification.
- Do NOT run `make test-integration` or `make test-unit`. Those are S12/S13 QV gates.

## Migration Verification — see §3.

## Subagent Result Contract

When the work is complete:

```bash
mkdir -p ai-dev/active/I-00102/reports
uv run iw step-done I-00102 --step S01 \
  --report ai-dev/active/I-00102/reports/I-00102_S01_Database_report.md
```

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "I-00102",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_add_manifest_digest_to_work_items.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "make migration-check: round-trip + drift check green",
  "tdd_red_evidence": "n/a — schema-only, behaviour tests live in S03",
  "blockers": [],
  "notes": ""
}
```

If the step FAILS:

```bash
uv run iw step-fail I-00102 --step S01 --reason "brief reason"
```

**IMPORTANT**: You MUST call `step-done` (with `--report`) or `step-fail` before exiting.
