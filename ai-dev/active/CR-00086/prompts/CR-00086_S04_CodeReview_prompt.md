# CR-00086_S04_CodeReview_prompt

**Work Item**: CR-00086 -- Self-dashboarding of test health
**Steps Being Reviewed**: S01 (database-impl) and S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Same policy as the implementation prompts. You may run `docker ps` / `docker inspect` / `docker logs` for read-only investigation, plus `make` and `./ai-core.sh` targets. Anything else is forbidden.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB. Read-only `alembic history/current/show` is allowed. Verifying the migration round-trips happens via the testcontainer fixtures or the dedicated S02 `make migration-check` gate.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00086 --json`.
- `ai-dev/active/CR-00086/CR-00086_CR_Design.md` -- Design document (read AC1, AC2, AC3, and the **TDD Approach** section in full)
- `ai-dev/work/CR-00086/reports/CR-00086_S01_Database_report.md` -- S01 implementation report
- `ai-dev/work/CR-00086/reports/CR-00086_S03_Backend_report.md` -- S03 implementation report
- All files listed in those reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00086/reports/CR-00086_S04_CodeReview_report.md` -- Review report

## Context

You are reviewing the **Database (S01)** and **Backend (S03)** implementation work for CR-00086. Read the design FIRST so you know which test files the TDD Approach names by path — every one of them must appear in some implementation step's `files_changed`. A missing one is CRITICAL.

## Read the Design Document FIRST

- `## Acceptance Criteria` section — AC1, AC2, AC3 are in scope for this review (AC4–AC6 belong to S06/S08).
- `## TDD Approach` — note every test file path the design names. Cross-check against `files_changed` of S01 + S03 reports.
- `## Notes` — flags the mutation-JSON shape adapter and the missing-source-graceful-degradation contract. Both are mandatory checks.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files listed in S01 + S03 `files_changed`:

```bash
make lint
make format
```

Report any NEW violations as **CRITICAL** findings with `category: conventions`. Do NOT auto-fix.

## Review Checklist

### 1. Architecture Compliance

- S01: migration follows the project's Alembic style; `downgrade()` is implemented; index ordering is `(project_id, metric, ts DESC)` (not ASC).
- S01: model uses `Mapped` / `mapped_column` and carries `doc=` strings on EVERY column.
- S03: service module never raises on a missing source — verify by reading each parser's exception handling.
- S03: the mutation-JSON adapter handles BOTH the CR-00080 new shape AND the CR-00059 legacy shape (look for a dispatch helper; absence of one is a HIGH finding because the design Notes called this out).
- S03: coverage reading goes through `orch/coverage_service.py`, not a parallel reimplementation.

### 2. Code Quality

- Idempotency: `tests/integration/test_test_health_service.py::test_idempotent_within_minute` exists and asserts row count == 1 after two captures within the same minute. If the test is missing OR weak (asserts only that the second call exits 0), raise CRITICAL.
- The CLI command's JSON summary shape matches the design's AC2 description: `{"project": ..., "captured": [...], "skipped": [...]}`.
- Logging: missing-source warnings go through the project logger; `print` calls are not used in service code (CLI command may print its JSON summary to stdout — that's fine).

### 3. Project Conventions

- `tests/CLAUDE.md` — testcontainer rules followed; no test connects to port 5433.
- `event_metadata` vs `metadata` — N/A for this CR (column is named `meta`), but verify the SQLAlchemy reserved-name trap is not tripped elsewhere by accident.
- Typer command registration follows the existing pattern.

### 4. Security

- No hardcoded secrets, paths, or credentials. The artefact-source paths SHOULD come from `orch/config.py` or sensible defaults — flag literal hardcoded absolute paths as a HIGH finding.
- The `meta` JSONB is bounded: assert that the parser does not stuff unbounded raw payloads into `meta` (a CR-00080 mutation JSON can be tens of MB — keep `meta` small: commit SHA, file path, top-line counts only).

### 5. Testing (TDD section anchor)

- Cross-check every test file named in the design's TDD Approach against S01 + S03 `files_changed`. Missing entries are CRITICAL.
- All four `test_read_*` unit tests for the parser adapter are present.
- The integration tests cover: capture-writes-four, idempotency-within-minute, latest+trend ordering, missing-source-skips.

### 5a. TDD RED Evidence

- S01 and S03 are behaviour-implementing steps; both reports MUST carry `tdd_red_evidence` with a plausible failure snippet (NOT `ImportError` or collection error).
- For at least one new behavioural test in S03, reason about whether it would actually fail against the pre-change code. A test that would pass without the new service is **not** RED-first — HIGH finding.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_test_health_service.py tests/unit/test_test_health_service.py tests/integration/data_layer/test_migration_round_trip.py -v
```

Any failure here is a CRITICAL finding.

## Severity Levels

Standard table — CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00086",
  "step_reviewed": "S01,S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL + HIGH + MEDIUM-fixable findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM-fixable.
