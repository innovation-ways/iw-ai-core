# CR-00053_S08_CodeReview_FIX_Final_prompt

**Work Item**: CR-00053 -- Idempotent `iw next-id` via `--idempotency-key` flag
**Step**: S08
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/CR-00053/CR-00053_CR_Design.md` -- Design
- `ai-dev/work/CR-00053/reports/CR-00053_S07_CodeReview_Final_report.md` -- S07 cross-agent findings (drives this step)
- All prior step reports + source files

## Output Files

- `ai-dev/work/CR-00053/reports/CR-00053_S08_CodeReview_FIX_Final_report.md` -- Step report
- Updated source files as needed

## Context

Apply fixes for any CRITICAL/HIGH findings from S07's cross-agent review. If S07 reported "no CRITICAL/HIGH findings," this step is effectively a no-op — write a brief report stating so and pass through.

## Requirements

1. For each CRITICAL/HIGH finding from S07: apply the minimum fix; re-run any tests the fix touches.
2. If S07 reported any scope-creep file (touched outside `scope.allowed_paths`), revert that file to its main-branch state unless the design clearly intended it (rare; document the decision either way).
3. If your changes touched the migration file, **re-run `make migration-check`**.
4. Re-run the CR's own targeted tests:
   ```bash
   uv run pytest tests/unit/test_id_allocations.py tests/integration/test_idempotency_key_cli.py -v
   ```
   Must be green before reporting completion.
5. Run the standard pre-flight gates.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00053",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "..."
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "N passed, 0 failed (targeted reruns)",
  "tdd_red_evidence": "n/a — final fix step",
  "blockers": [],
  "notes": "Addressed X CRITICAL, Y HIGH from S07. Or: S07 reported clean — no changes required."
}
```
