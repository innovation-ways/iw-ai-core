# CR-00065_S09_CodeReviewFixFinal_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S09
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00065 --json`
- `ai-dev/active/CR-00065/CR-00065_CR_Design.md` — Design document
- `ai-dev/work/CR-00065/reports/CR-00065_S08_CodeReviewFinal_report.md` — Final review findings
- All changed files

## Task

Fix all **CRITICAL**, **HIGH**, and **MEDIUM_FIXABLE** findings from the S08 final review. Apply minimal, targeted fixes only.

```bash
make lint
make format-check
make typecheck
make test-unit
```

All gates must pass after fixes.

## Output Files

- Modified files per findings
- `ai-dev/work/CR-00065/reports/CR-00065_S09_CodeReviewFixFinal_report.md`

## Subagent Result Contract

```bash
uv run iw step-done CR-00065 --step S09 \
  --report ai-dev/work/CR-00065/reports/CR-00065_S09_CodeReviewFixFinal_report.md
```

```json
{
  "step": "S09",
  "agent": "code-review-fix-final-impl",
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
