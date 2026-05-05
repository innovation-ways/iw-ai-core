# I-00069_S05_CodeReview_Final_prompt

**Work Item**: I-00069 -- Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Read-only docker introspection only. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This incident does NOT touch migrations. Read-only alembic commands only.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00069 --json`. The `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00069/I-00069_Issue_Design.md` — Design document
- `ai-dev/active/I-00069/I-00069_Functional.md` — Functional design
- All implementation step reports: `ai-dev/active/I-00069/reports/I-00069_S01_*_report.md`, `..._S03_*_report.md`
- All per-agent code review reports: `..._S02_CodeReview_*_report.md`, `..._S04_CodeReview_*_report.md`
- All files listed in implementation reports' `files_changed`:
  - `dashboard/app.py`
  - `tests/dashboard/test_live_db_guard_log_level.py`

## Output Files

- `ai-dev/active/I-00069/reports/I-00069_S05_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of all implementation
work for **I-00069**.

The change is small and self-contained: a narrowed exception handler in
`dashboard/app.py` and a new test file in `tests/dashboard/`. The cross-cutting
question is whether the two pieces actually integrate — i.e., whether the test
file would catch a regression of the dashboard change.

Read the design + functional docs. Read all per-agent reports. Then read
both changed files end-to-end.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in changed files vs `main` are CRITICAL `category: "conventions"` findings.

## Review Checklist

### 1. Completeness vs Design Document

- Are all three Acceptance Criteria (AC1, AC2, AC3) covered by code + tests?
- AC1 (Bug fixed): `dashboard/app.py` no longer logs the refusal at ERROR. Test A asserts this.
- AC2 (Regression test exists): Test A is in the suite.
- AC3 (Behaviour preserved): Both Test A and Test B assert `app.state.alembic_guard_status is None`.

### 2. Cross-Step Integration

- Does Test A actually exercise the code path changed in S01? Set
  `IW_CORE_TEST_CONTEXT=true`, call `create_app()`, capture logs from
  `dashboard.app` — yes.
- Does Test B actually exercise the surviving `except Exception` path?
  Monkey-patch `check_db_at_head` to raise `RuntimeError` — yes.
- Are there any code paths in S01 that S03 does NOT cover? Notably: the
  WARNING branch (non-test context). If S03 has no test for that, flag
  as MEDIUM_FIXABLE — the design's AC1 only covers test-context, but
  good hygiene asks for parity coverage.

### 3. No Other Consumers Regressed

- `dashboard/middlewares/alembic_guard.py:54-58` — still uses
  `contextlib.suppress(Exception)`. Untouched.
- `orch/daemon/main.py:147` — daemon path uses `logger.critical(...)` at
  CRITICAL level for the guard probe. Untouched.
- `orch/db/live_db_guard.py` and `orch/db/alembic_guard.py` — untouched.
- `tests/dashboard/test_alembic_guard_banner.py` — does it depend on the
  banner state shape? Confirm its assertions are unaffected by the new
  log level (it tests the banner UI, not the log output).

### 4. Test Coverage (Holistic)

- Both tests are FALSIFIABLE on pre-S01 code (Test A) or on a
  hypothetical over-correction (Test B).
- The integration point is: `LiveDbConnectionRefusedError` thrown by
  `safe_create_engine` reaches `dashboard/app.py`'s `except` chain in
  the right order.
- Run the full suite (`make test-unit` + `make test-integration`) and
  confirm zero regressions.

### 5. Architecture Compliance

- Read `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, `tests/CLAUDE.md`.
- `dashboard/` importing from `orch.db.live_db_guard` is allowed.
- No new module dependencies introduced.

### 6. Security (Cross-Cutting)

- No new env-var reads beyond the already-pervasive `IW_CORE_TEST_CONTEXT`.
- No hardcoded secrets / credentials.
- No new endpoints / routes.

## Test Verification (NON-NEGOTIABLE)

1. Run **full unit suite**: `make test-unit`. Zero failures.
2. Run **full integration suite**: `make test-integration`. Zero failures.
3. Run the new file in isolation:
   `uv run pytest tests/dashboard/test_live_db_guard_log_level.py -q`. 2 passed.
4. Report results in the contract.

If integration tests fail, this is a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, missing requirement | Must fix |
| **HIGH** | Integration failure, architectural violation | Must fix |
| **MEDIUM (fixable)** | Code quality / convention | Should fix |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00069",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH and zero MEDIUM_FIXABLE; otherwise `fail`.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
- `missing_requirements`: list any AC not covered by code+tests.
- `cross_cutting`: `true` for findings that span S01 + S03.
