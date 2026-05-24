# I-00104_S02_CodeReview_prompt

**Work Item**: I-00104 -- Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
No migration work in this step.

## Input Files

- `ai-dev/active/I-00104/I-00104_Issue_Design.md`
- `ai-dev/active/I-00104/reports/I-00104_S01_Backend_report.md`
- The S01 diff.

## Output Files

- `ai-dev/active/I-00104/reports/I-00104_S02_CodeReview_report.md`

## Scope of Review

Per-agent review of S01's fix.

### 1. globs_intersect adoption

- `grep '& set(' orch/batch_planner.py` MUST return zero lines. If any plain set-intersection still computes overlap, CRITICAL.
- `grep 'globs_intersect' orch/batch_planner.py` MUST return at least two lines (one per loop — intra and cross-batch). If only one, MAJOR (cross-batch loop missed).
- The import is `from orch.daemon.scope_overlap import globs_intersect` (or equivalent — match repo style). Single import; no shadowing.

### 2. Max Parallel literal

- `grep -n 'generate_execution_plan_md\|generate_drawio\|generate_png' dashboard/routers/actions.py` — confirm each call passes `batch.max_parallel`, not a literal integer.
- `grep -n ', 4)' dashboard/routers/actions.py` — confirm no `, 4)` literal remains around the plan-generation calls.

### 3. Scope discipline

- Diff is confined to `orch/batch_planner.py` and `dashboard/routers/actions.py`. Any other file changed in S01 = CRITICAL (scope violation).
- No new function added in `orch/batch_planner.py` (the fix is in-place replacement).

### 4. Behavioural risk

- The original code stored overlap via `analysis[id_a].overlap_with.append(id_b)` — string IDs, NOT the conflicting globs themselves. S01 must NOT have changed that schema. Confirm.
- The original dependency-injection `if id_a not in analysis[id_b].depends_on:` line is preserved.

### 5. Lint / format / typecheck on the diff

The diff must pass `make lint`, `make format-check`, and `make type-check` cleanly. If S01's report claims pass, sanity-spot-check by running the touched-file typecheck.

## Severity Guide

- CRITICAL: any remaining `& set(` overlap computation; any remaining literal `4` in the three plan-gen calls; scope creep into `orch/daemon/` or other dashboard routers.
- HIGH: cross-batch loop missed (only intra-batch fixed); changed `overlap_with` data shape; changed `depends_on` injection logic.
- MEDIUM: missing import sort; missing docstring update.
- LOW: comment polish.

## Subagent Result Contract

```json
{
  "step": "S02",
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
