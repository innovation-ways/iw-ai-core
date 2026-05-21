# CR-00068_S05_CodeReviewFixFinal_prompt

**Work Item**: CR-00068 — AI Assistant — Remove Per-Tab Model Bar
**Step**: S05
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00068 --json`
- `ai-dev/active/CR-00068/CR-00068_CR_Design.md` — Design document
- `ai-dev/work/CR-00068/reports/CR-00068_S04_CodeReviewFinal_report.md` — final review findings
- All files changed across S01 and S03

## Output Files

- Modified source files (as needed to resolve findings)
- `ai-dev/work/CR-00068/reports/CR-00068_S05_CodeReviewFixFinal_report.md`

## Task

Resolve every CRITICAL, HIGH, and MEDIUM_FIXABLE finding from the S04 final
review report. For each finding:

1. Apply the fix in the relevant file.
2. Stay within the design's **Impacted Paths** — `panel.html`, `chat.js`,
   `chat.css`, `tests/dashboard/**`.
3. Record in the report: finding id, what changed, and why.

If the S04 verdict was `pass` with zero mandatory findings, make no code changes
and record "no mandatory findings — nothing to fix" in the report.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
```

Both must pass with no new violations in changed files.

## Subagent Result Contract

```bash
uv run iw step-done CR-00068 --step S05 \
  --report ai-dev/work/CR-00068/reports/CR-00068_S05_CodeReviewFixFinal_report.md
```

```json
{
  "step": "S05",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00068",
  "completion_status": "complete|partial|blocked",
  "findings_fixed": [],
  "findings_skipped": [],
  "files_changed": [],
  "tests_passed": true,
  "test_summary": "lint + format-check passed",
  "blockers": [],
  "notes": ""
}
```
