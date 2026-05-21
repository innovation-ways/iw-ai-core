# CR-00069_S05_CodeReviewFixFinal_prompt

**Work Item**: CR-00069 — AI Assistant — Remove Clear Button Confirmation Dialog
**Step**: S05
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00069 --json`
- `ai-dev/active/CR-00069/CR-00069_CR_Design.md` — Design document
- `ai-dev/work/CR-00069/reports/CR-00069_S04_CodeReviewFinal_report.md` — final review findings
- All files changed across S01 and S03

## Output Files

- Modified source files (as needed to resolve findings)
- `ai-dev/work/CR-00069/reports/CR-00069_S05_CodeReviewFixFinal_report.md`

## Task

Resolve every CRITICAL, HIGH, and MEDIUM_FIXABLE finding from the S04 final
review report. For each finding:

1. Apply the fix in the relevant file.
2. Stay within the design's **Impacted Paths** — `chat.js`,
   `tests/dashboard/test_chat_clear_button.py` (and `tests/dashboard/**`).
3. Record in the report: finding id, what changed, and why.

If the S04 verdict was `pass` with zero mandatory findings, make no code changes
and record "no mandatory findings — nothing to fix" in the report.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
uv run pytest tests/dashboard/test_chat_clear_button.py -v
```

All must pass with no new violations in changed files.

## Subagent Result Contract

```bash
uv run iw step-done CR-00069 --step S05 \
  --report ai-dev/work/CR-00069/reports/CR-00069_S05_CodeReviewFixFinal_report.md
```

```json
{
  "step": "S05",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00069",
  "completion_status": "complete|partial|blocked",
  "findings_fixed": [],
  "findings_skipped": [],
  "files_changed": [],
  "tests_passed": true,
  "test_summary": "lint + format-check + test_chat_clear_button.py passed",
  "blockers": [],
  "notes": ""
}
```
