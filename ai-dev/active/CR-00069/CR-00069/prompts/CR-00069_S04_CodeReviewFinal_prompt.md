# CR-00069_S04_CodeReviewFinal_prompt

**Work Item**: CR-00069 — AI Assistant — Remove Clear Button Confirmation Dialog
**Step**: S04
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00069 --json`
- `ai-dev/active/CR-00069/CR-00069_CR_Design.md` — Design document
- All reports in `ai-dev/work/CR-00069/reports/`
- All files changed across S01 and S03

## Output Files

- `ai-dev/work/CR-00069/reports/CR-00069_S04_CodeReviewFinal_report.md`

## Task

Perform a global, cross-step review of the complete CR-00069 change. Verify the
change is correct, consistent, and complete as one unit.

### Final Review Checklist

- **Acceptance criteria** — all of AC1–AC4 in the design are satisfied by the
  combined S01 + S03 output.
- **Source ↔ test consistency** — `_clearChat()` in `chat.js` no longer
  references `window.confirm`, and the inverted test in
  `test_chat_clear_button.py` asserts exactly that. The test would now FAIL if
  the confirm line were reintroduced.
- **Guards intact** — `_clearChat()` still returns early on no active tab / no
  history; the Clear button is still `disabled` when there is no history.
- **Post-clear behaviour intact** — `/clear` POST, SSE/streaming reset, DOM
  clear, button-state update, stream reconnect, "Chat cleared." message all
  unchanged.
- **Minimal change** — no unrelated refactor of `_clearChat()`; no commented-out
  dead code; the other tests in `test_chat_clear_button.py` are unchanged.
- **Scope** — every changed file is within the design's Impacted Paths.
- **Conventions** — `dashboard/CLAUDE.md` honoured.

## Pre-Review Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
uv run pytest tests/dashboard/test_chat_clear_button.py -v
```

Any new violation in a changed file, or any failing test, = CRITICAL finding.

## Subagent Result Contract

```bash
uv run iw step-done CR-00069 --step S04 \
  --report ai-dev/work/CR-00069/reports/CR-00069_S04_CodeReviewFinal_report.md
```

```json
{
  "step": "S04",
  "agent": "code-review-final-impl",
  "work_item": "CR-00069",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check + test_chat_clear_button.py passed",
  "notes": ""
}
```
