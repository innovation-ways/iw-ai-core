# CR-00062_S07_CodeReviewFix_prompt

**Work Item**: CR-00062 — Add Pi (pi.dev) as a third agent runtime
**Step**: S07
**Agent**: code-review-fix-impl

---

## ⛔ Docker is off-limits

Same policy as the earlier implementation steps. Testcontainers exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

If S06 identified a migration issue and the fix requires a new revision, write a new revision file (do not edit S01's merged-pending revision unless it's still un-merged in this batch — in which case edit it in place is correct). Do NOT run `alembic upgrade / downgrade / stamp` against the live orch DB.

## Input Files

- S06 report: `ai-dev/active/CR-00062/reports/CR-00062_S06_CodeReview_report.md`
- All S01/S03/S04/S05 input files (design doc, etc.)
- Project conventions: `CLAUDE.md`, `orch/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- Edits to any of the files originally touched by S01/S03/S04/S05
- `ai-dev/active/CR-00062/reports/CR-00062_S07_CodeReviewFix_report.md`

## Context

You are applying fixes for the CRITICAL and HIGH findings reported by S06. MEDIUM and LOW findings are recorded in the report but you may defer them to a follow-up if time-bounded; CRITICAL and HIGH must all be addressed in this step.

## Requirements

### 1. Read every CRITICAL and HIGH finding in `S06_CodeReview_report.md`

For each finding, the report should name: severity, step, file, summary, recommended fix. If a recommended fix is missing or ambiguous, use your judgement guided by the design doc and project conventions, and document the choice in your S07 report.

### 2. Apply the fixes

Edit only the files named in S06 findings. Do not introduce out-of-scope changes — if you spot something during the fix work that's outside the finding, file it as a `<!-- TODO(CR-00062-followup): -->` comment but do not fix it in this step.

### 3. Re-run targeted verification

For each file you edit, re-run the affected unit test:

```bash
uv run pytest tests/unit/<affected_test_file>.py -v
```

If a HIGH finding required adding a new test (rare — usually S05 covered that), add it now.

### 4. Re-run preflight gates

After all fixes are applied, run:

1. `make format`
2. `make typecheck`
3. `make lint`

All three must report clean for files you touched.

### 5. Migration-check re-run (only if S07 touched the migration or model file)

If S07 modified the S01 migration or `orch/db/models.py`, run `make migration-check` again. Must report green.

## TDD Requirement

Each fix that changes behaviour should have an associated test (added in S05 or now). `tdd_red_evidence` records the test id(s) you used to verify each fix. If a fix is non-behavioural (e.g., a renamed identifier, a comment correction, a frontmatter-only change), use `"n/a — non-behavioural fix; verified by lint/format/typecheck only"`.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-fix-impl",
  "work_item": "CR-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "<path>"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "X passed",
  "tdd_red_evidence": "<test id list> or n/a — non-behavioural",
  "findings_addressed": [
    {"id": "F1", "severity": "CRITICAL|HIGH", "status": "fixed|deferred-to-followup", "notes": ""}
  ],
  "blockers": [],
  "notes": "any MEDIUM/LOW findings deferred and the rationale"
}
```
