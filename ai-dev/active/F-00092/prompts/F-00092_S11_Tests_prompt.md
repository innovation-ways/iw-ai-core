# F-00092_S11_Tests_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S11
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Use **testcontainer** fixtures only (they self-label + self-destruct via Ryuk).
NEVER connect tests to the live DB on 5433. The engine may `docker run --rm` for pg
client tools — in tests, point the engine at the testcontainer DB.

## ⛔ Migrations: agents generate, daemon applies

After `Base.metadata.create_all()` in integration tests, also run
`FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (per `tests/CLAUDE.md`). Remember to replace
`postgresql+psycopg2://` with `postgresql+psycopg://` for the testcontainer URL.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md` — **Boundary Behavior** (every
  row is a mandatory test), **Invariants**, **TDD Approach**, AC1–AC7.
- Reports from S01/S03/S05/S06/S08/S09 — final signatures, columns, CLI shape.
- `tests/CLAUDE.md`, `tests/conftest.py`, an existing `tests/dashboard/` file (for
  the file-local `client` fixture pattern).

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S11_Tests_report.md`.
- New test files under `tests/unit/`, `tests/integration/`, `tests/dashboard/`.

## Context

Add the coverage that proves the backup subsystem works end-to-end. Some unit tests
already exist from S03/S05/S06 (RED-first); this step fills the gaps and adds the
integration round-trip and the dashboard render test.

## Requirements

### 1. Integration: dump → restore round-trip (testcontainer)

- Seed a testcontainer `iw_orch` with known rows (projects/batches/work_items +
  the `iw_core_instance` row).
- Run the engine `create_backup` against it → assert all three artifacts exist and
  the manifest row counts match the seeded data.
- Restore the backup set into a **second fresh** testcontainer (globals first),
  then assert: the `iw_orch` role exists (from globals), the DB restores without
  auth/ownership errors, and row counts match the source (AC3, AC5).

### 2. Unit / logic

- Retention prune: scheduled > N days deleted; **manual never deleted** (Invariant
  3); boundary at exactly N days; injected `now`.
- Scheduler decision: disabled → never; recent scheduled success → not due;
  missed-window → due (catch-up, AC4); injected `now` + last-success.
- Restore-target safety: refuses prod (5433) without `allow_prod` (Invariant 4).
- Integrity-check failure path: a corrupt/garbage archive → backup `failed`, not
  `success` (Invariant 2).
- Mid-dump write failure (Boundary "disk full mid-dump"): a forced write failure →
  backup `failed` and the partial set is cleaned up / not counted as a successful
  scheduled backup (simulate by pointing the set dir at a read-only / unwritable
  location or injecting a write error — do not actually fill the disk).
- Globals secrecy (Boundary "globals file contains role password hashes" / Invariant
  8): after a successful backup, assert the set directory mode is `0700` and the
  `--globals-only` file mode is `0600`.
- Manifest records the PostgreSQL server version (non-empty, matches the source
  server).
- Config: defaults + `.env` overrides; `IW_CORE_BACKUP_ENABLED=false` disables the
  scheduler (AC7).

### 3. Dashboard render test (`tests/dashboard/`)

Using a file-local `client` fixture (copy the pattern from an existing dashboard
test) + the `db_session` testcontainer fixture: seed a `DbBackupJob`, render the
unified jobs view, and assert a backup-job row appears with its status/timestamp
(AC6). Use **semantic** assertions (see below) — assert the specific backup row /
status value renders, not merely that the page is non-empty.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

- BAD: `assert "jobs" in html` / `assert len(rows) > 0` (shape only)
- GOOD: assert the specific backup job's status string / label / id renders, and
  that row counts equal the **specific** seeded numbers (not just "> 0").

## Test Verification (NON-NEGOTIABLE)

Run only the test files you create/modify:

```bash
uv run pytest tests/unit/<...> tests/integration/<...> tests/dashboard/<...> -v
```

Do **NOT** run `make test-unit` / `make test-integration` — those are the S19/S20 QV
gates with their own budgets. Do not report `tests_passed: true` unless your files
pass. Do not perform manual `git checkout`/`git stash` RED reverts.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint`.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "tests-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "files_changed": ["tests/integration/test_backup_roundtrip.py", "tests/unit/...", "tests/dashboard/test_jobs_view_backup.py"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "N passed, 0 failed (targeted)",
  "tdd_red_evidence": "n/a — coverage step (tests-impl); asserts post-implementation behaviour with specific values",
  "blockers": [],
  "notes": "List which Boundary Behavior rows + ACs each test covers."
}
```
