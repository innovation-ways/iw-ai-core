# CR-00056_S02_CodeReview_Database_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection only.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade` against the live DB. `alembic history` / `current` / `show` are fine. Round-trip via `make migration-check` is fine (testcontainer).

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — Design document (focus on `Impact Analysis → Affected Components` and `Acceptance Criteria → AC1`)
- `ai-dev/work/CR-00056/reports/CR-00056_S01_Database_report.md` — Implementation report
- All files listed in the implementation report's `files_changed`

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S02_CodeReview_report.md` — Review report

## Context

You are reviewing the schema half of CR-00056. S01 added two TEXT NULL columns (`prompt_text`, `fix_prompt_text`) to the `step_runs` table via both the SQLAlchemy ORM model and a new alembic migration. The columns are written by the daemon at step launch (subsequent step S04) and read by the dashboard (S06/S08).

## Read the Design Document FIRST

Specifically:
- `Acceptance Criteria → AC1` — schema additions.
- `Impact Analysis → Affected Components` table — row for `orch/db/models.py` (StepRun) and `orch/db/migrations/versions/`.
- `Rollback Plan` — confirms the migration is reversible (downgrade drops both columns).
- `TDD Approach → Unit tests` — the test that proves column existence lives in S11 (not S01); confirm S01's TDD evidence uses the `n/a` form correctly.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files listed in `files_changed`:

```bash
make lint
make format
```

NEW violations on the changed files → **CRITICAL** with `"category": "conventions"`.

## Review Checklist

### 1. Architecture Compliance

- Columns added to the **right model**: `StepRun` (line ~778), NOT `WorkflowStep` or `FixCycle`.
- Match SQLAlchemy 2.0 `Mapped[]` declarative style with `mapped_column(Text, nullable=True, comment=...)`.
- Append-only invariant on `step_runs` is preserved — these columns are written **once** at row creation, never UPDATEd. Confirm no UPDATE path was added.

### 2. Schema correctness

- Both columns are TEXT (not VARCHAR(N)), nullable, no server_default. Prompts can be many KB — TEXT is correct.
- No index added (display-only field; index would be wasted bytes).
- Column comments are present and informative; they match the migration comments.

### 3. Migration quality

- `upgrade()` adds exactly two columns; `downgrade()` drops exactly those two (in reverse order).
- `down_revision` points at the prior head (run `alembic history` to confirm).
- No extraneous DDL (no trigger drops, no FTS column changes, no unrelated table modifications). If autogenerate emitted noise, the implementer should have manually cleaned it. If you find leftover noise, flag CRITICAL.
- The migration is **not** applied to the live DB on port 5433 — confirm by running `uv run iw db-identity check` is unaffected and the live DB still shows the prior head (`alembic current` against a testcontainer is OK).

### 4. Project Conventions

- psycopg v3 (not psycopg2) usage throughout — no change expected here since `alembic` driver is project-configured, but verify the migration file has no hardcoded psycopg2 anywhere.
- ORM model comments worded consistently with the migration column comments (they show up in `\d+ step_runs`).

### 5. Testing

- The ORM-level unit test for column existence is in S11 — not S01. That is correct per the design. Do NOT flag absence of a unit test in S01 as a finding; the design splits implementation and coverage by convention.
- `make migration-check` must have passed in S01. If the report says it was skipped or red, that's CRITICAL.

### 5a. TDD RED Evidence

For Database steps: confirm `tdd_red_evidence` in the report uses the `"n/a — <one-line reason>"` form (e.g., `"n/a — schema-only column addition, behaviour exercised by daemon-snapshot integration test in S11"`). If it claims to have RED evidence inline, verify the evidence is plausible; if it's missing entirely, that's a HIGH finding.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_migrations_round_trip.py -v
make migration-check
```

Both must pass before submitting the review. Report results accurately.

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Migration drift, unsafe DDL, applied to live DB, irreversible downgrade |
| HIGH | Wrong nullable/type, missing `comment`, missing TDD evidence field |
| MEDIUM (fixable) | Comment quality, naming inconsistencies, downgrade order wrong |
| MEDIUM (suggestion) | Style preferences |
| LOW | Nitpicks |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00056",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "migration-check passed",
  "notes": ""
}
```
