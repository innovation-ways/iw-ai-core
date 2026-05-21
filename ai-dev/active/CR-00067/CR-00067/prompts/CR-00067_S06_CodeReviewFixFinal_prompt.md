# CR-00067_S06_CodeReviewFixFinal_prompt

**Work Item**: CR-00067 — AI Assistant — Context Usage Percentage Indicator
**Step**: S06
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00067 --json`
- `ai-dev/active/CR-00067/CR-00067_CR_Design.md` — Design document
- `ai-dev/work/CR-00067/reports/CR-00067_S05_CodeReviewFinal_report.md` — final review findings
- All files changed across S01, S02, and S04

## Output Files

- Modified source files (as needed to resolve findings)
- `ai-dev/work/CR-00067/reports/CR-00067_S06_CodeReviewFixFinal_report.md`

## Task

Resolve every CRITICAL, HIGH, and MEDIUM_FIXABLE finding from the S05 final
review report. For each finding:

1. Apply the fix in the relevant file.
2. Stay within the design's **Impacted Paths** — `orch/chat/context_usage.py`,
   `dashboard/routers/chat.py`, `composer.html`, `chat.css`, `chat.js`,
   `tests/unit/**`, `tests/integration/**`, `tests/dashboard/**`.
3. Record in the report: finding id, what changed, and why.

If the S05 verdict was `pass` with zero mandatory findings, make no code changes
and record "no mandatory findings — nothing to fix" in the report.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
```

Re-run the targeted test files for any area you changed. Do NOT run
`make test-integration` / `make test-unit` at large — the full suites are owned
by the S07 / S08 QV gates. All gates must pass with no new violations in changed
files.

## Subagent Result Contract

```bash
uv run iw step-done CR-00067 --step S06 \
  --report ai-dev/work/CR-00067/reports/CR-00067_S06_CodeReviewFixFinal_report.md
```

```json
{
  "step": "S06",
  "agent": "code-review-fix-final-impl",
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
