# CR-00068_S03_CodeReviewFix_prompt

**Work Item**: CR-00068 — AI Assistant — Remove Per-Tab Model Bar
**Step**: S03
**Agent**: code-review-fix-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00068 --json`
- `ai-dev/active/CR-00068/CR-00068_CR_Design.md` — Design document
- `ai-dev/work/CR-00068/reports/CR-00068_S02_CodeReview_report.md` — review findings
- All files in S01's `files_changed`

## Output Files

- Modified source files (as needed to resolve findings)
- `ai-dev/work/CR-00068/reports/CR-00068_S03_CodeReviewFix_report.md`

## Task

Resolve every CRITICAL, HIGH, and MEDIUM_FIXABLE finding from the S02 review
report. For each finding:

1. Apply the fix in the relevant file.
2. Stay within the design's **Impacted Paths** — `panel.html`, `chat.js`,
   `chat.css`, `tests/dashboard/**`. Do NOT expand scope.
3. Record in the report: finding id, what changed, and why.

MEDIUM_SUGGESTION and LOW findings are optional — address them only if trivial
and clearly correct. Note any deliberately skipped findings with a reason.

If the S02 verdict was `pass` with zero mandatory findings, make no code changes
and record "no mandatory findings — nothing to fix" in the report.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
```

Both must pass with no new violations in changed files.

## Subagent Result Contract

```bash
uv run iw step-done CR-00068 --step S03 \
  --report ai-dev/work/CR-00068/reports/CR-00068_S03_CodeReviewFix_report.md
```

```json
{
  "step": "S03",
  "agent": "code-review-fix-impl",
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
