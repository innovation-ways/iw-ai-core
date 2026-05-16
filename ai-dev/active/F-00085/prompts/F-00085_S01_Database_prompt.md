# F-00085_S01_Database_prompt

**Work Item**: F-00085 — Auto-Merge Resolver Observability + Per-Project Control
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

You write the migration FILE. The daemon applies it during the pre-merge phase. **NEVER** run `alembic upgrade head` against the live orchestration DB (port 5433).

You MAY use:
- `uv run alembic revision --autogenerate -m "F-00085: …"` — writes the file
- Testcontainer fixtures (via `make migration-check` in S03)
- `alembic history / current / show` (read-only)

## Input Files

- `uv run iw item-status F-00085 --json`
- `ai-dev/active/F-00085/F-00085_Feature_Design.md`
- Canonical reference: `ai-dev/active/AUTO_MERGE_RESOLUTION.md` §5b
- Existing precedents:
  - `orch/db/models.py` — `AgentRuntimeOption` (~line 55), `DaemonEvent` (~line 1271), composite-PK examples
  - `orch/db/migrations/versions/d1e2f3gpt53c_*.py` — recent migration file structure
- ORM conventions: `orch/CLAUDE.md` (SQLAlchemy 2.0 `Mapped[]` declarative style, sync, psycopg v3)

## Output Files

- `ai-dev/active/F-00085/reports/F-00085_S01_Database_report.md`

## Context

You are creating the schema layer for F-00085. Two NEW tables, NO modifications to existing tables (daemon_events remains append-only — Invariant 1).

## Requirements

### 1. New table `merge_auto_verdicts`

| Column | Type | Constraints |
|--------|------|-------------|
| `project_id` | TEXT | NOT NULL, part of PK, FK `projects(id)` ON DELETE CASCADE |
| `daemon_event_id` | BIGINT | NOT NULL, part of PK, FK `daemon_events(id)` ON DELETE CASCADE |
| `verdict` | TEXT | NOT NULL, CHECK (`verdict IN ('pending','correct','wrong','partial')`) |
| `verdict_notes` | TEXT | NOT NULL DEFAULT '' (≤ 8192 chars enforced at API layer, not DB) |
| `verdicted_by` | TEXT | NULL (operator id or "dashboard" sentinel) |
| `verdicted_at` | TIMESTAMPTZ | NOT NULL DEFAULT `now()` |

- Composite PK: `(project_id, daemon_event_id)`.
- ORM class: `MergeAutoVerdict` in `orch/db/models.py`.
- This table IS mutable on UPDATE (operator changes verdict). Use `ON CONFLICT (project_id, daemon_event_id) DO UPDATE` at the API layer (S08). Do NOT add this to the append-only-tables list in `orch/CLAUDE.md`.

### 2. New table `auto_merge_project_config`

| Column | Type | Constraints |
|--------|------|-------------|
| `project_id` | TEXT | PK, FK `projects(id)` ON DELETE CASCADE |
| `phase` | INT | NULL (NULL → use TOML default), CHECK (`phase IS NULL OR phase IN (0, 1)`) |
| `runtime_option_id` | INT | NULL, FK `agent_runtime_options(id)` ON DELETE SET NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT `now()` |
| `updated_by` | TEXT | NULL |

- Single-column PK on `project_id`.
- ORM class: `AutoMergeProjectConfig` in `orch/db/models.py`.
- CHECK constraint MUST enforce phase ∈ {NULL, 0, 1} — Phase 2/3 are reserved (Invariant 5).
- This table is also mutable (operator changes the config). API layer (S08) uses `ON CONFLICT (project_id) DO UPDATE`.

### 3. Alembic migration file

- One file under `orch/db/migrations/versions/<hash>_f00085_observability_and_control.py`.
- `down_revision` = current head as of the worktree's state (find via `alembic history`).
- Forward migration creates both tables in one transaction.
- `downgrade()` drops both tables.
- File must round-trip cleanly (S03 runs `make migration-check` to verify).

### 4. ORM models in `orch/db/models.py`

- Use SQLAlchemy 2.0 `Mapped[]` declarative style consistent with neighbouring models.
- Reuse the `_TIMESTAMPTZ` and `_TIMESTAMP` aliases already defined in the file.
- Add type-hint imports as needed (`Literal` for verdict if you want; otherwise plain `str`).
- Place new classes after `DaemonEvent` (line ~1271) — group with other auxiliary tables.

### 5. Document new event types as constants (NOT a migration, but in the models module)

After F-00084 introduced event_type STRINGS, this Feature adds two more:

- `auto_merge_health_probe` — emitted by daemon health task
- `auto_merge_config_updated` — emitted by POST `/<project>/auto-merge/config`

These are TEXT values, NOT enum members. The convention in F-00084 was module-level string constants in `orch/daemon/auto_merge.py`. Add these two there (or in `orch/auto_merge_aggregator.py` — pick whichever S06 will use; document the choice in your report).

Actually — don't add these here in S01. Just note in your report that S04/S06 should define them. S01's responsibility ends at the schema + ORM models.

## Project Conventions

- Read `orch/CLAUDE.md` for orch package rules.
- Composite PKs use SQLAlchemy 2.0 `__table_args__ = (PrimaryKeyConstraint("project_id", "daemon_event_id"),)` style — see existing examples.
- All NEW timestamp columns are `TIMESTAMPTZ` with `server_default=func.now()`.
- Migration message string: lowercase, descriptive, ≤ 70 chars: e.g., `"F-00085 auto merge verdicts and project config"`.

## TDD Requirement

Database steps are NOT behavioural — no RED test for schema. Use `tdd_red_evidence: "n/a — schema-only step; behavioural tests live in S13"`.

After writing the migration:
1. Run `make migration-check` LOCALLY in your worktree to confirm round-trip works.
2. Capture the output in your report.
3. S03 will re-run it in CI as the gate.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix.
2. `make typecheck` — zero errors on `orch/db/models.py` involving your new classes.
3. `make lint` — zero errors.

## Migration Verification (NON-NEGOTIABLE)

**You MUST run `make migration-check` and confirm it passes before reporting completion.** This is the single most important gate for a Database step — it catches model↔migration drift (the F-00079 cost case).

## Test Verification

- Targeted: `uv run pytest tests/integration/test_migrations_round_trip.py -v` if it exists.
- Do NOT run `make test-integration` (full suite).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00085",
  "completion_status": "complete",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<hash>_f00085_observability_and_control.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "make migration-check: PASS (round-trip + drift check green)",
  "tdd_red_evidence": "n/a — schema-only step; behavioural tests live in S13",
  "blockers": [],
  "notes": "New event types auto_merge_health_probe and auto_merge_config_updated are TEXT strings to be defined as module constants by S04 (TOML loader) and S06 (aggregator) respectively. S01 does not introduce them yet."
}
```
