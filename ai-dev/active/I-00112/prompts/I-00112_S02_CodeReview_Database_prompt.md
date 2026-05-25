# I-00112_S02_CodeReview_Database_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step Being Reviewed**: S01 (Database)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker state-change command. Testcontainers spun up by pytest fixtures are the only exception. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB. Your job here is to READ S01's revision file and verify it is correct, not to apply it. `alembic history/current/show` is allowed (read-only). Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00112 --json`.
- `ai-dev/active/I-00112/I-00112_Issue_Design.md` — design document (read **Database Changes**, **AC5**, **Notes**).
- `ai-dev/active/I-00112/reports/I-00112_S01_Database_report.md` — S01 step report.
- All files listed in S01's `files_changed`.

## Output Files

- `ai-dev/active/I-00112/reports/I-00112_S02_CodeReview_report.md` — review report.

## Context

You are reviewing S01 (Database). The step generated an Alembic revision adding four nullable columns (`stdout`, `stderr`, `elapsed_ms`, `returncode`) to `keep_alive_runs` and extended the `KeepAliveRun` ORM model to match.

## Read the Design Document FIRST

Before opening any code, read:
- `## Acceptance Criteria` (especially **AC5**: migration round-trips cleanly).
- `## Database Changes` — exact column names, types, nullability.
- `## Notes` — the explicit "no backfill, NULL is the sentinel for legacy rows" decision.

Note: the design doc names no test files for S01 (this is a schema/ORM step). If S01's `files_changed` includes any test file, that is a CRITICAL scope violation.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation in S01's `files_changed` is a CRITICAL finding (`"category": "conventions"`, with file/line and the violation code).

## Review Checklist

### 1. Schema correctness

- The migration adds exactly four columns: `stdout TEXT`, `stderr TEXT`, `elapsed_ms INTEGER`, `returncode INTEGER`, all `nullable=True`. Any extra `add_column`, `alter_column`, index creation, or table touch is a HIGH finding (autogenerate noise that should have been stripped).
- The `downgrade()` body drops the four columns in reverse order. Missing drops are CRITICAL.
- `down_revision` points at a real existing revision in `orch/db/migrations/versions/`. A `down_revision = None` or a typo is CRITICAL.
- Revision file name follows `<rev>_i00112_keep_alive_runs_capture_cli_output.py`.

### 2. ORM ↔ migration agreement

- `KeepAliveRun` in `orch/db/models.py` declares four new `Mapped[…]` attributes whose names AND types match the migration exactly. Mismatch → `make migration-check` will fail at the `metadata.create_all()` comparison → CRITICAL.
- New attributes use `Mapped[str | None]` / `Mapped[int | None]` (declarative style consistent with the file).
- No defaults on the new columns (`server_default`, `default` would both shift the design-intended NULL sentinel).

### 3. Scope adherence

- S01's `files_changed` MUST contain exactly two paths: the new revision file and `orch/db/models.py`. Any other file (service, poller, template, test) is a CRITICAL scope violation — that work belongs to S03 / S05 / S07.

### 4. Migration round-trip

- Re-run `make migration-check` yourself. If it fails, the failure is a CRITICAL finding even if S01's report claimed PASS. Capture the exact error.

### 5. Project conventions

- psycopg v3 only (no `psycopg2` import).
- SQLAlchemy 2.0 `Mapped[]` style.
- Migration body uses `sa.Text()` and `sa.Integer()` from the standard alembic op vocabulary (not custom types).

## Test Verification (NON-NEGOTIABLE)

Run `make migration-check`. Report PASS/FAIL accurately. Do NOT run `make test-unit` or `make test-integration` — those are downstream gates.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Migration broken, schema↔ORM mismatch, scope violation, downgrade missing, round-trip failing |
| **HIGH** | Autogenerate noise not stripped, extra unintended touches, naming convention drift |
| **MEDIUM (fixable)** | Style / comment inconsistencies that should be cleaned up |
| **MEDIUM (suggestion)** | Optional improvements |
| **LOW** | Nitpicks |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00112",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make migration-check: PASS",
  "notes": ""
}
```

`verdict: pass` only if zero CRITICAL/HIGH/MEDIUM-fixable findings.

## Lifecycle Commands

```bash
uv run iw step-start I-00112 --step S02
# work
uv run iw step-done I-00112 --step S02 --report ai-dev/active/I-00112/reports/I-00112_S02_CodeReview_report.md
```
