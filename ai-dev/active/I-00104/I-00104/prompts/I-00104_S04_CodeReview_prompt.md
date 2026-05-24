# I-00104_S04_CodeReview_prompt

**Work Item**: I-00104 -- Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
This step is review-only.

## Input Files

- `ai-dev/active/I-00104/I-00104_Issue_Design.md`
- `ai-dev/active/I-00104/reports/I-00104_S03_Tests_report.md`
- The S03 diff (`tests/unit/test_batch_planner_overlap.py`, `tests/dashboard/test_batch_plan_max_parallel.py`).

## Output Files

- `ai-dev/active/I-00104/reports/I-00104_S04_CodeReview_report.md`

## Scope of Review

Per-agent review of S03's tests against the iw-ai-core-testing red-flag checklist.

1. **Semantic assertions** — every assertion compares against a SPECIFIC value:
   - `"B" in analysis["A"].overlap_with` (semantic), not `analysis["A"].overlap_with` (truthy).
   - `"**Max Parallel**: 5" in plan_md` (exact substring with markdown formatting), not `"5" in plan_md` (too loose).
   - The negative assertion `"**Max Parallel**: 4" not in plan_md` is present in the max_parallel test (defends against regressions).

2. **Cross-batch case actually exercises the cross-batch path** — `test_cross_batch_overlap_uses_globs_intersect` passes a non-empty `active_items_data` argument to `analyze_dependencies`. If S03 cheats by reusing intra-batch input, that's a CRITICAL false-positive on AC1.

3. **Disjoint case** — `test_strictly_disjoint_paths_no_overlap` is present and asserts EMPTY overlap_with for both items (defends against a regression where `globs_intersect` matches too aggressively).

4. **Batch-create endpoint URL correct** — S03's dashboard test must POST to `/project/{project_id}/batch/create-from-selection` (the endpoint that renders the plan — there is NO regenerate-plan route). If the test uses a guessed/wrong URL it will 404 and fail for a non-bug reason. Verify against `dashboard/routers/actions.py` (function `create_batch_from_selection`). Also confirm the value-variation case lives in the unit file (`test_execution_plan_md_renders_given_max_parallel`), not the dashboard file — `create-from-selection` hardcodes `max_parallel=5`, so a `max_parallel=3` dashboard test is impossible.

5. **Testcontainer isolation** — `db_session` fixture used in the dashboard test; no `postgresql://...5433` strings anywhere.

6. **tdd_red_evidence** — present for both files. Acceptable forms: real captured `AssertionError`, OR the design-time analytic form (S03 reads pre-fix code and pastes the would-be failure line). Reject if the evidence is missing entirely.

7. **No `xfail` / `skip` on the new tests**. If any test is skipped, MEDIUM finding — require it to either work or be deleted.

## Severity Guide

- CRITICAL: vacuous truthy assertions; cross-batch test doesn't use active_items_data; missing negative assertion on `Max Parallel: 4`; live-DB connection.
- HIGH: wrong batch-create endpoint URL (not `create-from-selection`); missing disjoint-case test.
- MEDIUM: xfail/skip without justification; tdd_red_evidence missing for one file but not the other.
- LOW: naming, ordering.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00104",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "review-only step",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "<count of CRITICAL/HIGH/MEDIUM/LOW findings>"
}
```
