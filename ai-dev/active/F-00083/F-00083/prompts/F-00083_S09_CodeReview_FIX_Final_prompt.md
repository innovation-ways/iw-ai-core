# F-00083_S09_CodeReview_FIX_Final_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S09
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — Design
- `ai-dev/work/F-00083/reports/F-00083_S08_CodeReview_Final_report.md` — cross-agent findings (drives this step)
- All prior step reports + source files

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_S09_CodeReview_FIX_Final_report.md`
- Updated source files as needed

## Context

Apply fixes for any CRITICAL/HIGH findings from S08's cross-agent review. If S08 reported "no CRITICAL/HIGH findings," this step is effectively a no-op — write a brief report stating so.

## Requirements

1. For each CRITICAL/HIGH finding from S08: apply the minimum fix; re-run any tests the fix touches.
2. If S08 reported any scope-creep file (touched outside `scope.allowed_paths`), revert that file to its main-branch state unless the design clearly intended it (rare; document the decision).
3. Re-run the F-00083 targeted tests:
   ```bash
   uv run pytest tests/unit/test_chat_*.py tests/dashboard/test_chat_*.py tests/integration/test_chat_*.py -v
   ```
   Must be green before reporting completion.
4. Run the standard pre-flight gates.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Targeted reruns only.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-fix-final-impl",
  "work_item": "F-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "N passed, 0 failed (targeted reruns)",
  "tdd_red_evidence": "n/a — final fix step",
  "blockers": [],
  "notes": "Addressed X CRITICAL, Y HIGH from S08. Or: S08 was clean — no changes required. Regression-guard post-fix: PASS."
}
```
