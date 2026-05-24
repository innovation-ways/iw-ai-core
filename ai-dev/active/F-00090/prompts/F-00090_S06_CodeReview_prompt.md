# F-00090_S06_CodeReview_prompt

**Work Item**: F-00090 -- Regression-rate tracking
**Step Being Reviewed**: S01..S05 (all implementation steps)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy applies. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does not modify migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00090 --json` is the source of truth for current step list.
- `ai-dev/active/F-00090/F-00090_Feature_Design.md` -- Design document
- `ai-dev/active/F-00090/reports/F-00090_S0{1..5}_*_report.md` -- All implementation step reports
- All files listed in those reports' `files_changed`

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_S06_CodeReview_report.md` -- Per-agent review report covering S01..S05

## Context

You are reviewing the implementation work done in steps S01 (database-impl), S02 (backend-impl), S03 (frontend-impl), S04 (frontend-impl), and S05 (backend-impl) for **F-00090 — Regression-rate tracking**.

Read the design document to understand what was intended. Read each implementation report to understand what was done. Then review all changed files.

This is the **per-agent review** layer. S07 (CodeReview_Final) is the cross-agent layer; do not duplicate its scope here.

## Read the Design Document FIRST

Read the design **before** running the lint/format gate and **before** opening any changed files. Specifically:

- Read the `## Acceptance Criteria` section in full — AC1..AC8 are all mandatory checks.
- Read the `## TDD Approach` section — three test files are named by path: `tests/integration/test_regression_link_service.py`, `tests/dashboard/test_regression_classification_form.py`, `tests/dashboard/test_quality_kpis_section.py`. **All three must appear in some implementation step's `files_changed`** — missing test files = CRITICAL.
- Read the `## Boundary Behavior` table — every row is a mandatory test case. Confirm each row has a covering test.
- Read the `## Invariants` list — Invariant 3 (operator confirmation) and Invariant 6 (rate guard) are especially load-bearing.
- **Distrust "no production code change needed".** The S01 migration introduces five new columns including an ENUM that flow through routes that previously never saw these values. Re-trace the render paths in `dashboard/routers/items.py` and `project_dashboard.py` for the new fields — latent crashes hide in shared templates (I-00075 cost case).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on the files listed in S01..S05 `files_changed`:

```bash
make lint
make format
```

Any NEW violations in changed files (vs `main`) → CRITICAL finding, category `conventions`, with `file` + `line` + the exact violation code/message.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Architecture Compliance

- Does S01 follow the existing SQLAlchemy 2.0 / `Mapped[]` style? Does the ENUM use the same helper-column pattern as `WorkItemStatus`?
- Does S02's service open sessions itself, or take them as arguments (design says argument)?
- Does S03/S04 keep all htmx interactions server-rendered (no client-side JS framework)?
- Does S05's backfill script use `argparse` and stay file-side-effect-free except for stdout?

### 2. Code Quality

- Look for obvious bugs in the heuristic `suggest_introducer()` — especially the `git log -L` parsing and the resolution of commit SHA → work item ID.
- Look for N+1 query patterns in S04's badge rendering on Batches/History (design calls this out).
- Verify the rate guard in S04's KPI computation (Invariant 6) — `merges == 0 → rate == 0.0`, not NaN, not exception.
- Verify error handling in the htmx form — invalid FK should return 422 with the form re-rendered, not 500.

### 3. Project Conventions

- Read `CLAUDE.md`. Jinja2 `format`-filter calls must be `%`-style (I-00075). Grep the new templates for `|format(` and verify.
- Plain CSS in `dashboard/static/styles.css` (I-00067). Reject any new `@apply` or Tailwind-only utility added without a fallback.
- psycopg v3 driver, not psycopg2 (everywhere — service, tests).
- Composite PK `(project_id, id)` preserved on `work_items`.

### 4. Security

- The `introduced_by_commit_sha` is free-text. Verify the form re-validates server-side (not just `pattern` attribute).
- The `classified_by` value should be derived from the authenticated session, not from a form field the operator can spoof.
- No SQL injection risk in the badge-count GROUP BY query — use parameterized SQLAlchemy.

### 5. Testing

- All three test files from the TDD section present in `files_changed`? If any missing → CRITICAL.
- Boundary rows covered:
  - Empty heuristic result → suggestion list empty + UI button hidden.
  - Cross-project FK rejected.
  - Non-merged FK rejected.
  - Zero-merge rate guard.
  - Re-classification overwrites.
  - Pre-existing does not contribute.
  - N==0 → no badge.
  - <12 weeks of history → chart still works.
- Invariants 1, 3, 6 covered by tests.

### 5a. TDD RED Evidence (behaviour-implementing steps only)

Applies to S02, S03, S04 (each adds behavioural tests).

1. Confirm `tdd_red_evidence` is present and plausible (AssertionError, not ImportError/SyntaxError/collection error).
2. For at least one new test, reason about whether it would actually fail against pre-change code. A test that passes without the new code is HIGH severity.
3. S01 and S05 use the `n/a — ...` form; that is acceptable for schema-only and docs-only steps.

## Test Verification (NON-NEGOTIABLE)

Run the unit test command to verify no regressions:

```bash
make test-unit
```

Report results accurately. If unit tests are red on `main` already, note the baseline.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Breaks functionality, data loss, security vuln, missing required test file | Must fix |
| HIGH | Significant bug, missing requirement, architectural violation, missing RED evidence | Must fix |
| MEDIUM (fixable) | Quality issue, missing edge case, convention violation | Should fix |
| MEDIUM (suggestion) | Design improvement, better pattern | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00090",
  "step_reviewed": "S01..S05",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-unit: X passed, 0 failed",
  "notes": ""
}
```

- `verdict: pass` iff zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE.
- `mandatory_fix_count = CRITICAL + HIGH + MEDIUM_FIXABLE`.
