# CR-00067_S05_CodeReviewFinal_prompt

**Work Item**: CR-00067 — AI Assistant — Context Usage Percentage Indicator
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00067 --json`
- `ai-dev/active/CR-00067/CR-00067_CR_Design.md` — Design document
- All reports in `ai-dev/work/CR-00067/reports/`
- All files changed across S01, S02, and S04

## Output Files

- `ai-dev/work/CR-00067/reports/CR-00067_S05_CodeReviewFinal_report.md`

## Task

Perform a global, cross-step review of the complete CR-00067 change. Verify the
backend and frontend together form one correct, consistent, end-to-end feature.

### Final Review Checklist

- **Acceptance criteria** — all of AC1–AC6 in the design are satisfied by the
  combined S01 + S02 + S04 output.
- **End-to-end contract** — the field the backend injects
  (`session.context_pct`) is exactly the field `chat.js` reads
  (`data.session.context_pct`). No name mismatch, no nesting mismatch.
- **Integration** — the `#chat-assistant-context-pct` element id used in
  `composer.html` exactly matches every `getElementById` lookup in `chat.js`.
- **CSS classes** — the class names applied in `chat.js` (`is-warn`, `is-crit`,
  `hidden`, and the base class) exactly match the selectors defined in
  `chat.css`. No typos, no orphan classes.
- **No duplication** — a single shared fetch helper serves both the streaming
  poll and the on-activation fetch.
- **Edge cases** — backend omits `context_pct` when not computable (never `0`);
  frontend hides the label for a missing/`NaN` value and when there is no active
  tab; no `0%` is ever rendered for "no data".
- **No new poll round-trip cost** — the model-limit `/config/providers` lookup
  is cached; `get_tab` does not gain an uncached HTTP call per 5-second poll.
- **Scope** — every changed file is within the design's Impacted Paths. No DB
  schema change, no new/removed endpoints.
- **Regression** — the model bar, Clear, Abort, and Send controls are untouched
  and still laid out correctly in the Send/Abort row; `get_tab` still returns
  `{tab, session, messages}` and never errors because usage could not be
  computed.
- **Conventions** — `dashboard/CLAUDE.md` and `orch/CLAUDE.md` honoured; router
  stays thin; `chat.css` appended (not `styles.css`); ids prefixed
  `chat-assistant-`.

## Pre-Review Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in a changed file = CRITICAL finding.

## Subagent Result Contract

```bash
uv run iw step-done CR-00067 --step S05 \
  --report ai-dev/work/CR-00067/reports/CR-00067_S05_CodeReviewFinal_report.md
```

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "CR-00067",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check passed",
  "notes": ""
}
```
