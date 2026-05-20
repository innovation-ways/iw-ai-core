# CR-00065_S07_CodeReviewFix_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S07
**Agent**: code-review-fix-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00065 --json`
- `ai-dev/active/CR-00065/CR-00065_CR_Design.md` — Design document
- `ai-dev/work/CR-00065/reports/CR-00065_S06_CodeReview_report.md` — Review findings
- All files listed in the review's `files_changed`

## Task

Fix all **CRITICAL**, **HIGH**, and **MEDIUM_FIXABLE** findings from the S06 code review report. Do not change scope — only fix what was flagged.

For each finding fixed:
1. Apply the minimal change that resolves the finding.
2. Re-run the relevant quality gate to confirm the fix:
   ```bash
   make lint
   make format-check
   make typecheck
   make test-unit
   ```

If any finding is not fixable as described (e.g., requires architectural change beyond scope), raise it as a blocker in the result contract.

## Output Files

- Modified files as needed per findings
- `ai-dev/work/CR-00065/reports/CR-00065_S07_CodeReviewFix_report.md`

## Subagent Result Contract

```bash
uv run iw step-done CR-00065 --step S07 \
  --report ai-dev/work/CR-00065/reports/CR-00065_S07_CodeReviewFix_report.md
```

```json
{
  "step": "S07",
  "agent": "code-review-fix-impl",
  "work_item": "CR-00065",
  "completion_status": "complete",
  "findings_fixed": [],
  "files_changed": [],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
