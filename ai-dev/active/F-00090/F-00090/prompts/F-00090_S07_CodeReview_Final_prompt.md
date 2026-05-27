# F-00090_S07_CodeReview_Final_prompt

**Work Item**: F-00090 -- Regression-rate tracking
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S05

---

## ⛔ Docker is off-limits

Standard policy applies. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does not modify migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00090 --json`.
- `ai-dev/active/F-00090/F-00090_Feature_Design.md` -- Design document
- All implementation step reports: `ai-dev/active/F-00090/reports/F-00090_S0{1..5}_*_report.md`
- Per-agent code review report: `ai-dev/active/F-00090/reports/F-00090_S06_CodeReview_report.md`
- All files listed in implementation reports' `files_changed`

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_S07_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **F-00090 — Regression-rate tracking**.

This review looks at the complete picture: how the database fields (S01), the service + CLI (S02), the classification form (S03), the KPI section + badge (S04), and the backfill + docs (S05) fit together. The per-agent review (S06) covered each step in isolation; your job is to catch cross-cutting issues that surface only when all steps are read as one.

## Read the Design Document FIRST

Same anchor as S06 plus:

- Confirm AC1..AC8 each map to concrete code paths across the merged change set. Any AC with no matching code = missing requirement = CRITICAL.
- The four TDD-named test files must appear in `files_changed` across S02..S05 (`test_regression_link_service.py` from S02, `test_regression_classification_form.py` from S03, `test_quality_kpis_section.py` from S04, `test_backfill_regression_classification.py` from S05). Missing any one = CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violations on changed files → CRITICAL, category `conventions`.

## Review Checklist

### 1. Completeness vs Design Document

- AC1..AC8 each have implementing code AND a test? Use the design's `## Acceptance Criteria` block as the checklist.
- Any TODO comments or placeholder implementations left behind?
- Are the new ENUM values (`regression`, `pre_existing`, `unknown`) consistently used across model, migration, service, CLI, form, and tests? Watch for spelling drift (`pre-existing` vs `pre_existing`).

### 2. Cross-Agent Consistency

- The `classified_by` value flows through service, CLI, htmx route, and badge UI. Verify the format is consistent: `operator:USER` from UI, `heuristic:auto` from CLI accept path. No third format snuck in.
- The `regression_link_service.suggest_introducer()` is called from THREE places: the CLI (S02), the `GET /regression-suggestions` htmx route (S03), and the backfill script (S05). Verify the call sites pass consistent arguments (especially `repo_path`).
- The KPI computation in S04 reads `WorkItem.classified_at` and `WorkItem.regression_classification` — confirm those exact column names match S01's migration.

### 3. Integration Points

- Does the htmx form's POST endpoint correctly serialise the form fields into the service's keyword arguments? Watch for `pre-existing` (form) vs `pre_existing` (ENUM) mismatch.
- Does the badge count query (S04) match the form's write path (S03)? Both must read/write the same `introduced_by_work_item_id` column.
- Does the per-project home actually mount the new section, or did S04 only ship a dedicated page?
- Does the `iw regression-classify` command get registered in `orch/cli/main.py` so `uv run iw regression-classify --help` works?

### 4. Test Coverage (Holistic)

- End-to-end coverage: a single integration scenario `(classify → render KPI section → render badge → revisit page sees the same numbers)` would be valuable. Flag MEDIUM_SUGGESTION if absent.
- All Boundary rows from the design covered somewhere? Cross-check the table against `tests/integration/test_regression_link_service.py`, `tests/integration/test_backfill_regression_classification.py`, `tests/dashboard/test_regression_classification_form.py`, `tests/dashboard/test_quality_kpis_section.py`.

### 5. Architecture Compliance

- Read `CLAUDE.md`. Sync SQLAlchemy 2.0, psycopg v3, composite PKs, append-only tables — all respected.
- New routes are project-namespaced.
- No new file outside `scope.allowed_paths` modified (Invariant 8).

### 6. Security (Cross-Cutting)

- `classified_by` derived from session, never from form input.
- `introduced_by_commit_sha` server-side re-validated.
- No hardcoded secrets, ports, or URLs in any changed file (`localhost:5173`, `localhost:9900`, etc.).
- `subprocess.run` in the service uses argument-list form, never `shell=True`.

## Test Verification (NON-NEGOTIABLE)

Run only the unit suite for cross-agent regression detection:

```bash
make test-unit
```

Do **NOT** run `make test-integration` from this review step — the integration
suite is owned by the S15 `integration-tests` QV gate (which uses
`make allure-integration`). Duplicating the full integration run here causes
multi-minute thrash on the critical path (see the rule "any *-impl step: never
make test-integration"). If the cross-agent review needs to confirm a specific
integration behaviour, run the targeted test file instead, e.g.:

```bash
uv run pytest tests/integration/test_regression_link_service.py -v
```

If `make test-unit` is red on `main` already, note the baseline so the QV
gates aren't blamed for pre-existing failures.

## Severity Levels

Same as S06.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00090",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05"],
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
