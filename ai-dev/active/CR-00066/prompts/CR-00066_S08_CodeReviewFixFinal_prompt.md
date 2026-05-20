# CR-00066_S08_CodeReviewFixFinal_prompt

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S08
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00066 --json`
- `ai-dev/active/CR-00066/CR-00066_CR_Design.md` — Design document
- `ai-dev/work/CR-00066/reports/CR-00066_S07_CodeReviewFinal_report.md`
- All changed files

## Task

Fix all CRITICAL, HIGH, and MEDIUM_FIXABLE findings from S07. Minimal targeted changes only.

```bash
make lint && make format-check && make typecheck && make test-unit
```

## Output Files

- Modified files per findings
- `ai-dev/work/CR-00066/reports/CR-00066_S08_CodeReviewFixFinal_report.md`

## Subagent Result Contract

```bash
uv run iw step-done CR-00066 --step S08 \
  --report ai-dev/work/CR-00066/reports/CR-00066_S08_CodeReviewFixFinal_report.md
```

```json
{
  "step": "S08",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00066",
  "completion_status": "complete",
  "findings_fixed": [],
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
