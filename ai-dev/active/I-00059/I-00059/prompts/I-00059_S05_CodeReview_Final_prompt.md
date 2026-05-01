# I-00059_S05_CodeReview_Final_prompt

**Work Item**: I-00059 -- Doc Generation Job Detail Page Shows No Error Info or Parameters
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00059 --json`
- `ai-dev/active/I-00059/I-00059_Issue_Design.md` — Design document
- `ai-dev/active/I-00059/reports/I-00059_S01_Backend_report.md`
- `ai-dev/active/I-00059/reports/I-00059_S02_CodeReview_Backend_report.md`
- `ai-dev/active/I-00059/reports/I-00059_S03_Tests_report.md`
- `ai-dev/active/I-00059/reports/I-00059_S04_CodeReview_Tests_report.md`
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/active/I-00059/reports/I-00059_S05_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **I-00059: Doc Generation Job Detail Page Shows No Error Info or Parameters**.

The fix is narrow: `_get_doc_generation` in `orch/jobs/aggregator.py` now returns a full `raw` dict matching `_fetch_doc_generation`. Tests were added to verify specific field values and parity between the two paths.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

## Review Checklist

### 1. Completeness vs Design Document

- `_get_doc_generation` raw dict contains all 14+ fields from `_fetch_doc_generation` — verify by side-by-side comparison
- Both `error` and `agent_output` fields are present (both needed by the template)
- `triggered_by` in the `JobRow` uses `job.skill_used or job.trigger_reason` (not just one)
- No changes outside `orch/jobs/aggregator.py` and `tests/integration/` (any other file changes are out of scope)

### 2. Cross-Agent Consistency

- If S01 extracted a `_build_doc_generation_raw` helper, verify S03's tests exercise it via both `get_job` and the list path
- Naming is consistent between the fix and the tests

### 3. Regression Guard

- The parity test (`get_job` raw == list-path raw for same job) exists and would catch future drift
- The parity test uses specific value assertions, not shape checks

### 4. Scope Containment

- Template (`dashboard/templates/pages/project/job_detail.html`) was NOT modified — it was already correct
- Route (`dashboard/routers/jobs_ui.py`) was NOT modified — it was already correct
- Any unexpected changes to other files are a CRITICAL finding

### 5. Test Coverage (Holistic)

- Reproduction test covers: `error`, `skill_used`, `duration_seconds`, `doc_id`, `trigger_reason`
- Additional tests cover: `lint_warnings` (list field), parity between list and detail paths
- All assertions are semantic (specific values), not shape-only

## Test Verification (NON-NEGOTIABLE)

Run the **full test suite**:

```bash
make test-unit
make test-integration
```

Both must pass with zero failures.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00059",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
