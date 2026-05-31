# F-00092_S05_Backend_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S05
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Same as S03: `docker run --rm postgres:15-alpine` to obtain pg client binaries is
allowed; no persistent container/volume changes; never restore over the live 5433
DB during development.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this step.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md` — **Scope**, **Boundary
  Behavior**, **Invariants** 3, 4 (restore-target), AC5.
- `ai-dev/active/F-00092/reports/F-00092_S03_Backend_report.md` — engine public API.
- `orch/db/identity.py` — `iw db-identity check` programmatic entry / how identity
  is verified.

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S05_Backend_report.md`.

## Context

Add the two backup-lifecycle operations on top of the S03 engine: **retention/prune**
and the **guided restore helper**. Both live in `orch/backup/` and are callable by
the CLI (S09).

## Requirements

### 1. Retention / prune (`orch/backup/retention.py` or similar)

- Delete backup sets whose `backup_type=scheduled` and age `> IW_CORE_BACKUP_RETENTION_DAYS`.
- **Never** delete `backup_type=manual` sets, regardless of age (Invariant 3).
- Deletes both the on-disk set and reconciles the `DbBackupJob` rows (mark
  deleted/removed per the model — coordinate with S01's columns).
- Make the age boundary rule explicit and documented (e.g. strictly older than N
  days). Pure decision logic should take an injected "now" so it is unit-testable
  without real time.

### 2. Guided restore helper (`orch/backup/restore.py` or similar)

- `restore(config, *, backup_set, target, allow_prod=False) -> result`.
- **Default target is a SAFE non-prod target** (a fresh database name and/or a
  throwaway `postgres:15-alpine` container) — NOT the live 5433 DB. If `target`
  resolves to the live prod DB and `allow_prod` is not explicitly set, **refuse**
  with a clear error (Invariant 4, Boundary "Restore target = prod (guard)").
- Restore order: **globals first** (`psql -f globals.sql`), then
  `pg_restore --clean --if-exists -d <db>` of the archive.
- After restore, run the identity check against the restored target and print row
  counts for projects/batches/work_items (AC5).
- Surface clear, copy-pasteable errors on failure.

Do NOT implement the daemon scheduler, CLI wiring, or docs here (S06/S09/S10).

## Project Conventions

Read `CLAUDE.md`. Keep these as service-layer functions (no FastAPI/daemon imports).

## TDD Requirement (RED first)

Write failing unit tests first for: the prune rule (manual-exempt; boundary at
exactly N days, using injected now), and the restore-target safety guard (refuses
prod without `allow_prod`). Capture RED, then implement. The full restore
round-trip against a testcontainer is S11.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — zero new errors.

## Test Verification (NON-NEGOTIABLE)

Targeted unit tests only. Not the full suite.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "files_changed": ["orch/backup/retention.py", "orch/backup/restore.py", "tests/unit/..."],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted)",
  "tdd_red_evidence": "tests/unit/.../test_retention.py::test_manual_exempt — AssertionError ... // RED",
  "blockers": [],
  "notes": "Document restore() + prune() signatures for the CLI."
}
```
