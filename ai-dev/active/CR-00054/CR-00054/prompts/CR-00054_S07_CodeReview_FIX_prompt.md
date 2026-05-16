# CR-00054_S07_CodeReview_FIX_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S07
**Agent**: code-review-fix-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds NO migrations.

## Input Files

- `ai-dev/active/CR-00054/reports/CR-00054_S06_CodeReview_report.md` — findings list
- `ai-dev/active/CR-00054/CR-00054_CR_Design.md` — design contract
- All files touched by S01–S05

## Output Files

- Modified source files (limited to `scope.allowed_paths` from `workflow-manifest.json`)
- `ai-dev/active/CR-00054/reports/CR-00054_S07_CodeReviewFix_report.md`

## Context

You are applying the CRITICAL and HIGH fixes from S06's findings. MEDIUM and LOW are recorded but **not** addressed in this step (the operator decides whether to handle them in S09 or punt to a follow-up).

## Requirements

1. For every finding with severity `CRITICAL` or `HIGH`:
   - Read the offending file at the reported line.
   - Apply the fix described in the "Fix" column.
   - Re-run the targeted tests for files touched by the fix:
     ```bash
     uv run pytest tests/integration/test_e2e_opencode_stub.py -v
     ```
   - Confirm the test still passes (or now passes if the fix is for a test bug).
2. Do NOT run `make test-integration` or `make test-unit` — those are S15/S14 jobs.
3. Stay within `scope.allowed_paths`. Any cross-cutting fix that requires modifying a path outside that list is a blocker — raise it in `blockers` and stop. Do NOT silently widen scope.
4. Do NOT address MEDIUM/LOW findings unless explicitly safe and trivial — note in `notes` if you choose to.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`

## Report

Write a fix-report:

```markdown
# CR-00054 S07 CodeReview Fix Report

## Findings Addressed

| Finding ID | Severity | File:Line | Fix Applied | Test Result |
|------------|----------|-----------|-------------|-------------|
| F1 | CRITICAL | ... | ... | pass |
| ... | ... | ... | ... | ... |

## Findings Deferred

| Finding ID | Severity | Reason |
|------------|----------|--------|
| F8 | MEDIUM | Not in this step's scope |
```

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-fix-impl",
  "work_item": "CR-00054",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — fixes for review findings; targeted tests already exist",
  "blockers": [],
  "notes": ""
}
```
