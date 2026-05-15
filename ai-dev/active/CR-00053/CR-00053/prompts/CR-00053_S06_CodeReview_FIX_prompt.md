# CR-00053_S06_CodeReview_FIX_prompt

**Work Item**: CR-00053 -- Idempotent `iw next-id` via `--idempotency-key` flag
**Step**: S06
**Agent**: code-review-fix-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/CR-00053/CR-00053_CR_Design.md` -- Design
- `ai-dev/work/CR-00053/reports/CR-00053_S05_CodeReview_report.md` -- S05 findings (drives this step)
- The S01 / S03 / S04 step reports and all files they touched

## Output Files

- `ai-dev/work/CR-00053/reports/CR-00053_S06_CodeReview_FIX_report.md` -- Step report (lists every finding addressed)
- Updated source files as needed

## Context

Apply fixes for all **CRITICAL** and **HIGH** findings from S05. MEDIUM and LOW findings are at-your-discretion in this step — fix them if cheap. Document deferred MEDIUM/LOW items explicitly in the report.

## Requirements

1. For each CRITICAL/HIGH finding from S05:
   - Read the finding's evidence.
   - Apply the minimum fix that addresses the root cause.
   - If a fix requires modifying a test, do so — but also note WHY in your report so S07 can verify the test still asserts the original intent.
   - Re-run any tests the fix touches: `uv run pytest <path> -v`.
2. If a finding is contested (you believe S05 was wrong), do NOT silently skip it. Document the disagreement in your report under a `contested_findings` section with your rationale; the orchestrator decides.
3. Run the standard pre-flight gates (`make format`, `make typecheck`, `make lint`).
4. If your changes touched the migration file, **re-run `make migration-check`**.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Targeted only — the test files exercised by the code you touched. Do NOT run `make test-unit` or `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-fix-impl",
  "work_item": "CR-00053",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/id_commands.py",
    "..."
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "N passed, 0 failed (targeted reruns)",
  "tdd_red_evidence": "n/a — fix step",
  "blockers": [],
  "notes": "Addressed X CRITICAL, Y HIGH. Deferred Z MEDIUM/LOW (documented in report). Contested findings: N."
}
```
