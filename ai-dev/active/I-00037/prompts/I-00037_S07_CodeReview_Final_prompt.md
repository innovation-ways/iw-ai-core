# I-00037_S07_CodeReview_Final_prompt

**Work Item**: I-00037 -- Per-project dashboard still uses item-level batch progress after I-00036
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01, S03, S05

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker state.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations expected.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00037/I-00037_Issue_Design.md` -- Design document (canonical AC list)
- `ai-dev/active/I-00037/reports/I-00037_S01_Backend_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S02_CodeReview_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S03_Frontend_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S04_CodeReview_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S05_Tests_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S06_CodeReview_report.md`
- All production files touched: `dashboard/utils/batch_progress.py`,
  `dashboard/routers/project_dashboard.py`, `dashboard/routers/batches.py`,
  and the test module(s) from S05
- `ai-dev/active/I-00037/evidences/pre/I-00037-dashboard-home-shows-0pct.png`
- `ai-dev/active/I-00037/evidences/pre/I-00037-batches-view-shows-correct-pct.png`

## Output Files

- `ai-dev/active/I-00037/reports/I-00037_S07_CodeReview_Final_report.md`

## Context

Per-agent reviews (S02, S04, S06) have already validated each step in
isolation. This final pass looks at the **complete picture**: does the system
as a whole meet the acceptance criteria, is there a single source of truth,
and do the three agents' outputs integrate correctly?

The root cause of I-00037 was that I-00036 only fixed one of two duplicated
code paths. The cross-cutting question for your review is: **has I-00037
structurally eliminated the possibility of recurrence?**

## Review Checklist

### 1. Completeness vs Design Document (CRITICAL-class)

Walk each AC from the design doc and point to the code/test that fulfils it:

- [ ] **AC1** — `/project/{id}/` shows step-based progress. Proof: the line
  in `project_dashboard.py:_active_batches()` that assigns `progress_pct`
  reads from `compute_batch_step_progress(...)`.
- [ ] **AC2** — parity between the two views. Proof: both routers call the
  same helper with the same `project_id`, same `batch_ids`, same logic. The
  parity test
  (`test_I00037_dashboard_home_and_batches_view_agree_on_progress`) asserts
  `dash.progress_pct == full.progress_pct` on the same seeded batch.
- [ ] **AC3** — `completed_items` / `total_items` unchanged. Proof: both
  routers still derive those from `BatchItem` counts, not from the helper.
- [ ] **AC4** — regression tests exist for the matrix.
- [ ] **AC5** — zero-step batch renders 0%, no crash. Proof: helper handles
  `total == 0` explicitly; unit test asserts `{batch.id: 0}`.

Any AC without a pointer → **CRITICAL** missing requirement.

### 2. Single Source of Truth (CRITICAL-class)

The entire point of this incident is structural:

- [ ] There is exactly ONE function that computes step-based
  `progress_pct` — `compute_batch_step_progress` in
  `dashboard/utils/batch_progress.py`.
- [ ] `project_dashboard.py:_active_batches()` imports and calls it.
- [ ] `batches.py:_all_batches()` imports and calls it.
- [ ] Neither router contains an inline step-counting loop, `SUM(CASE WHEN)`
  over `WorkflowStep`, or any other path that could compute `progress_pct`
  independently of the helper.
- [ ] No third router/page has been added that renders `batch.progress_pct`
  from its own computation (`grep -rn "progress_pct" dashboard/routers/` must
  show only these two producers).

### 3. Cross-Agent Consistency

- [ ] Helper signature (S01) matches how S03 calls it (same param names,
  same types, same return type).
- [ ] Helper signature (S01) matches how S05 tests it.
- [ ] No agent added a second "utility" path that duplicates the helper's
  work.

### 4. Scope hygiene (HIGH-class)

- [ ] No template files edited across all three implementation steps
  (`dashboard/templates/pages/project/dashboard.html`,
  `.../batches.html`, `.../fragments/batches_table_rows.html`).
- [ ] `BatchSummary` and `BatchRow` dataclasses are unchanged (field names,
  types, ordering).
- [ ] No unrelated refactors, no "while I'm here" changes.
- [ ] No changes to `orch/` — this was intentionally kept in the dashboard
  layer.

### 5. Items-count preservation (per reporting user's instruction)

- [ ] `BatchSummary.total_items` and `completed_items` on
  `/project/{id}/` are item-based (sourced from the `BatchItem` grouped
  query).
- [ ] `BatchRow.total_items` and `completed_items` on
  `/project/{id}/batches` are item-based (sourced from the existing
  `sum(1 for it in items if it.status.value in ("completed", "merged"))`).
- [ ] Tests explicitly assert Items stays item-based (`total_items == 1` with
  10 steps).

### 6. Regression test quality (holistic)

- [ ] The reproduction test IS the bug's proof — mentally revert S03 (put
  the old `pct = int(done / total * 100)` line back) and confirm the test
  would fail.
- [ ] All assertions on `progress_pct` pin specific integers, not shapes.
- [ ] Parity assertion present.
- [ ] Project-scoping test present — protects against the subtle
  cross-project join leak.

### 7. Integration points

- [ ] Imports are tidy — no circular imports between
  `dashboard.utils.batch_progress` and `orch.db.models`.
- [ ] `make lint`, `make typecheck`, `make test-unit`, `make test-integration`
  all pass as a complete suite after the fix.
- [ ] HTTP smoke tests confirm the value reaches the rendered HTML.

### 8. Security (cross-cutting)

- `project_id` is threaded through helper + both routers; no path bypasses
  the scope.
- No hardcoded secrets or credentials introduced.

## Test Verification (NON-NEGOTIABLE)

Before submitting the review:

1. Run the **full test suite**:
   - `make test-unit`
   - `make test-integration`
2. Run `make lint` and `make typecheck`.
3. `grep -rn "progress_pct" dashboard/routers/` — confirm the only producers
   are the two expected routers, each going through the helper.
4. `grep -rn "compute_batch_step_progress" dashboard/` — confirm exactly two
   callers.

Report the exact numbers in the contract's `test_summary`.

## Severity Levels

| Severity | Use when |
|----------|----------|
| CRITICAL | An AC has no corresponding code; a second `progress_pct` computation path exists anywhere; the reproduction test would pass against pre-fix code; `project_id` missing on helper join |
| HIGH | Template edited; dataclass shape changed; Items column accidentally switched to step counts; `make test-integration` fails |
| MEDIUM (fixable) | Missing regression scenario; dead code left behind; unused import in a touched file |
| MEDIUM (suggestion) | Naming, restructuring, alternative placement |
| LOW | Nitpicks |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00037",
  "steps_reviewed": ["S01", "S03", "S05"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "",
      "line": 0,
      "description": "",
      "suggestion": "",
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

- `verdict: pass` requires zero CRITICAL/HIGH/MEDIUM-fixable findings.
- Any `missing_requirements` entry is automatically a CRITICAL finding.
- `cross_cutting: true` on any finding that spans more than one agent's work
  or that touches integration between the helper and its callers.
