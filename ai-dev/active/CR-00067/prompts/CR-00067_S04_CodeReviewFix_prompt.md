# CR-00067_S04_CodeReviewFix_prompt

**Work Item**: CR-00067 — AI Assistant — Context Usage Percentage Indicator
**Step**: S04
**Agent**: code-review-fix-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00067 --json`
- `ai-dev/active/CR-00067/CR-00067_CR_Design.md` — Design document
- `ai-dev/work/CR-00067/reports/CR-00067_S03_CodeReview_report.md` — review findings
- All files in S01's and S02's `files_changed`

## Output Files

- Modified source files (as needed to resolve findings)
- `ai-dev/work/CR-00067/reports/CR-00067_S04_CodeReviewFix_report.md`

## Task

Resolve every CRITICAL, HIGH, and MEDIUM_FIXABLE finding from the S03 review
report. For each finding:

1. Apply the fix in the relevant file.
2. Stay within the design's **Impacted Paths** — `orch/chat/context_usage.py`,
   `dashboard/routers/chat.py`, `composer.html`, `chat.css`, `chat.js`,
   `tests/unit/**`, `tests/integration/**`, `tests/dashboard/**`. Do NOT expand
   scope.
3. Record in the report: finding id, what changed, and why.

MEDIUM_SUGGESTION and LOW findings are optional — address them only if trivial
and clearly correct. Note any deliberately skipped findings with a reason.

If the S03 verdict was `pass` with zero mandatory findings, make no code changes
and record "no mandatory findings — nothing to fix" in the report.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
```

Re-run the targeted test files for any area you changed (e.g.
`uv run pytest tests/unit/test_context_usage.py`,
`uv run pytest tests/dashboard/test_chat_context_pct_template.py`). Do NOT run
`make test-integration` / `make test-unit` at large — the full suites are owned
by the S07 / S08 QV gates. All gates must pass with no new violations in changed
files.

## Subagent Result Contract

```bash
uv run iw step-done CR-00067 --step S04 \
  --report ai-dev/work/CR-00067/reports/CR-00067_S04_CodeReviewFix_report.md
```

```json
{
  "step": "S04",
  "agent": "code-review-fix-impl",
  "work_item": "CR-00067",
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
