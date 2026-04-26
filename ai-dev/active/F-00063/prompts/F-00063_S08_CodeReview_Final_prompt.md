# F-00063_S08_CodeReview_Final_prompt

**Work Item**: F-00063 -- Stale Process & Migration Detector
**Review Step**: S08 (Final Review)
**Implementation Steps Reviewed**: S01..S07

---

## ⛔ Docker is off-limits

You MUST NOT execute docker container/volume/network mutating commands. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00063/F-00063_Feature_Design.md`
- All implementation reports: `ai-dev/active/F-00063/reports/F-00063_S0[1-7]_*_report.md`
- All per-agent code review reports: `ai-dev/active/F-00063/reports/F-00063_S0[2,5,6]_CodeReview_report.md`
- All files listed across all `files_changed` lists

## Output Files

- `ai-dev/active/F-00063/reports/F-00063_S08_CodeReview_Final_report.md`

## Context

You are performing the final cross-agent review of all implementation work for F-00063 — Stale Process & Migration Detector. Per-agent reviews already covered each step in isolation. Your job is to look at the whole feature end-to-end: backend + API + frontend + tests + config.

## Review Checklist

### 1. Completeness vs Design Document

- Every In Scope item is implemented.
- Every Acceptance Criterion (AC1–AC6) has corresponding code AND tests.
- Every Boundary Behavior row has a test (cross-check against S07 report).
- Every Invariant is enforceable / tested.
- No TODO comments or placeholders in the new code.

### 2. Cross-Agent Consistency

- The `ProjectStalenessResult` shape produced by `orch/staleness/service.py` (S01) matches what the panel template (S04) consumes.
- Endpoint URLs called from the templates (S04) match exactly the URLs declared in `dashboard/routers/staleness.py` (S03).
- Toast trigger format used by S03 matches what the dashboard's existing JS handler expects.
- The `restart_command` strings in `projects.toml` (S01 seed) match the actual scripts (`./ai-core.sh daemon restart`, `bin/restart-dashboard.sh`).

### 3. Integration

- `bin/restart-dashboard.sh` exists, is executable, and has the shebang.
- `projects.toml` parses cleanly after the seed (try `iw projects list` or equivalent in the test).
- Dashboard starts and the new router is registered (no import errors).
- `make` targets all green: `make lint`, `make format`, `make typecheck`, `make test-unit`, `make allure-integration` (the project's canonical 5-gate set — there is no `frontend/`, `arch-check`, `security-sast`, or `test-frontend` target in this codebase).

### 4. Architecture

- `orch/staleness/` does not import from `dashboard/`.
- No new third-party dependencies introduced.
- No DB schema changes (no new tables, no new migrations under `orch/db/migrations/versions/`).
- Live computation only — no module-level caches that would let a stale read leak across requests.

### 5. Security

- No hardcoded secrets in any new file.
- `db_url_env` value never logged.
- Subprocess invocations use `start_new_session=True` for fire-and-forget restarts.
- `shell=True` usage documented as intentional and justified.

### 6. Testing

- Full suite green: `make test-unit` AND `make test-integration` (this project has no `test-frontend` target — Jinja template tests live in `tests/dashboard/` and run inside `test-unit`).
- No tests skipped without justification.
- Performance smoke (≤500 ms for `compute_project_staleness`) passes.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `make lint`
4. `make typecheck`
5. (Inspect, don't run) — confirm `make allure-integration` would pass; if you can't run it, note it.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Breaks functionality / data loss / security / missing requirement | Must fix |
| HIGH | Significant bug / integration failure / arch violation | Must fix |
| MEDIUM_FIXABLE | Code quality / convention / missing edge case | Must fix |
| MEDIUM_SUGGESTION | Optional improvement | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "F-00063",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06", "S07"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "missing_requirements": [],
  "notes": ""
}
```
