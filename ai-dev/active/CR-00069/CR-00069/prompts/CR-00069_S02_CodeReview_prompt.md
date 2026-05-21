# CR-00069_S02_CodeReview_prompt

**Work Item**: CR-00069 — AI Assistant — Remove Clear Button Confirmation Dialog
**Steps Being Reviewed**: S01
**Review Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00069 --json`
- `ai-dev/active/CR-00069/CR-00069_CR_Design.md` — Design document
- Report from S01 in `ai-dev/work/CR-00069/reports/`
- All files in S01's `files_changed`

## Output Files

- `ai-dev/work/CR-00069/reports/CR-00069_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
uv run pytest tests/dashboard/test_chat_clear_button.py -v
```

Any new lint/format violation in a changed file = CRITICAL finding. Any failing
test in `test_chat_clear_button.py` = CRITICAL finding.

## Review Checklist

### 1. `chat.js` — `_clearChat()`

- The `window.confirm('Clear chat history? ...')` line is fully removed — no
  reference to `window.confirm` remains anywhere in the `_clearChat()` body.
- Both early-return guards are still present: `if (!_activeTabId) return;` and
  `if (!_tabHasHistory[_activeTabId]) return;`.
- The `fetch(... '/clear' ...)` POST and its `.then`/`.catch` chain are
  unchanged.
- The SSE/streaming reset, DOM clear (`_clearMessages`), `_updateClearButton`,
  stream reconnect, and `_appendSystemMessage('Chat cleared.', 'info')` calls
  are all intact.
- No commented-out dead code; no unrelated refactor of `_clearChat()`.

### 2. `test_chat_clear_button.py`

- The former `test_clear_calls_confirm` is inverted: it now asserts the
  `_clearChat()` body does NOT reference `window.confirm`.
- The assertion is scoped to the `_clearChat` function body — the test
  extracts the `_clearChat` body and checks that slice, not a blunt whole-file
  string check. (The other tests in this file use whole-file checks; the
  inverted test is deliberately tighter so an unrelated future `window.confirm`
  elsewhere in `chat.js` cannot make it fail spuriously. A whole-file
  `not in` check is acceptable-but-weaker — flag as MEDIUM_FIXABLE, not
  CRITICAL.)
- The module docstring's numbered test list is updated to match the new name
  and intent.
- The other tests (`_clearChat` exists, button disabled-by-default, calls
  `/clear`, removes eid) are unchanged and still pass.

### 3. Scope check

Changed files MUST be a subset of the design's **Impacted Paths**:
`chat.js`, `tests/dashboard/test_chat_clear_button.py` (and `tests/dashboard/**`).
Any router, API, or other Python change is a CRITICAL scope violation.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Breaks functionality, scope violation, failing test |
| HIGH | Significant bug, missing requirement |
| MEDIUM_FIXABLE | Convention violation, weak test assertion |
| MEDIUM_SUGGESTION | Optional improvement |
| LOW | Nitpick |

## Review Result Contract

```bash
uv run iw step-done CR-00069 --step S02 \
  --report ai-dev/work/CR-00069/reports/CR-00069_S02_CodeReview_report.md
```

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00069",
  "steps_reviewed": ["S01"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check + test_chat_clear_button.py passed",
  "notes": ""
}
```
