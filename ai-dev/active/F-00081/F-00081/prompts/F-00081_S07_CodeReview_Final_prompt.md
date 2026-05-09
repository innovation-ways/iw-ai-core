# F-00081_S07_CodeReview_Final_prompt

**Work Item**: F-00081 -- Per-Item / Per-Step Agent + Model Override
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection is allowed; testcontainer fixtures are exempt.

## ⛔ Migrations: agents generate, daemon applies

Do NOT mutate alembic state. Read-only `alembic history|current|show` is allowed.

## Input Files

- `uv run iw item-status F-00081 --json` for runtime step state.
- `ai-dev/active/F-00081/F-00081_Feature_Design.md`.
- All implementation reports: `ai-dev/active/F-00081/reports/F-00081_S0[1-6]_*_report.md`.
- All per-agent code review reports: `ai-dev/active/F-00081/reports/F-00081_S03_CodeReview_report.md` (S02 was the only impl step that had a per-agent review).
- All files listed in the implementation reports' `files_changed`.

## Output Files

- `ai-dev/active/F-00081/reports/F-00081_S07_CodeReview_Final_report.md`.

## Context

You are performing the final cross-agent review for **F-00081**. Per-agent review (S03) covered S02's backend layer in isolation. Your job is to catch cross-cutting issues that S03 could not see — places where S01's schema, S02's Python, S04's API, S05's frontend, and S06's tests must agree.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

`make lint` and `make format` (or `make format-check`) on every file in every implementation report's `files_changed`. Any new violation is a CRITICAL `category: conventions` finding.

## Review Checklist

### 1. Completeness vs Design Document

For each acceptance criterion (AC1–AC8), point to the implementation file(s) and the test in S06's coverage table that exercises it. Any AC without an implementation or without a test is a CRITICAL finding (`missing_requirements`).

For each Boundary Behavior row, verify a test exists. Each Invariant likewise.

### 2. Cross-Agent Consistency

- The form-field name on the API endpoints (S04) is `option_id`. Verify S05's templates submit exactly that name.
- The endpoint paths the frontend (S05) calls match exactly what S04 registers in the FastAPI router.
- The catalogue row shape returned by `GET /runtime-options` matches what the frontend expects (`cli_label`, `model_label`, `display_name`, `is_default`).
- The DaemonEvent metadata shape S02 emits matches the assertions S06 makes.
- The `ProjectConfig` field name (`model`) is consistent across S02's project_registry and any code that destructures it.
- The launch-command form S02 builds (`opencode run … --model <m>`) matches what S06 asserts in the cascade tests.

### 3. Integration Points

- The new `orch/agent_runtime/` package does NOT import from `orch/daemon/`.
- The new `dashboard/routers/runtime_overrides.py` is registered in `dashboard/app.py`.
- The migration's seed rows have IDs (or natural-key lookups) that S06's tests use to construct overrides — confirm the test fixtures look up rows by `(cli_tool, model)` not by hardcoded ID.
- The frontend's "Apply to all remaining" interaction calls the bulk endpoint, not multiple single-step endpoints (else AC6 fails — multiple DaemonEvents).

### 4. Test Coverage (Holistic)

- The test gap-coverage table in S06's report should map every AC, Invariant, and Boundary row to a test. Read it. Verify the named tests actually exist and contain the assertions claimed.
- Are the integration tests touching the testcontainer DB (not mocked)?
- Does the suite catch regression on existing items registered before this feature (the "Pre-feature item shape" boundary row)?

### 5. Architecture Compliance

- Read `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`. Verify layer boundaries, the "PostgreSQL is the sole source of truth" principle (catalogue lives in DB), and the "thin routers" rule for the dashboard.
- Verify no new psycopg2 references; the project uses psycopg v3 only.

### 6. Security (Cross-Cutting)

- The `model` field used in shell-command construction comes from a controlled catalogue. Verify S02's command-building code does not interpolate raw user input. Even though the catalogue is operator-controlled, defence-in-depth (e.g., validating the model string against `[a-zA-Z0-9._/-]+`) is appropriate; flag absence as MEDIUM if not present.
- No hardcoded credentials anywhere.
- The PATCH endpoints use the same auth posture as existing `actions.py` endpoints — no privilege escalation introduced.

### 7. Frontend Quality

- AC8 width budget — verify a test asserts segment count and class-based width semantics.
- Plain CSS in `dashboard/static/styles.css` follows the I-00067 mitigation; no Tailwind classes are dynamically constructed.
- The compressed strip preserves accessibility — segments still have `title` attributes.

## Test Verification (NON-NEGOTIABLE)

Run the full suite: `make test-unit`, `make test-integration`, `make test-frontend`. Any failure is a CRITICAL finding.

## Severity Levels

| Severity | Action |
|---|---|
| CRITICAL / HIGH | Must fix before merge |
| MEDIUM (fixable) | Must fix in fix cycle |
| MEDIUM (suggestion) / LOW | Informational |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00081",
  "steps_reviewed": ["S01","S02","S03","S04","S05","S06"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "missing_requirements": [],
  "notes": ""
}
```
