# CR-00068_S04_CodeReviewFinal_prompt

**Work Item**: CR-00068 — AI Assistant — Remove Per-Tab Model Bar
**Step**: S04
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00068 --json`
- `ai-dev/active/CR-00068/CR-00068_CR_Design.md` — Design document
- All reports in `ai-dev/work/CR-00068/reports/`
- All files changed across S01 and S03

## Output Files

- `ai-dev/work/CR-00068/reports/CR-00068_S04_CodeReviewFinal_report.md`

## Task

Perform a global, cross-step review of the complete CR-00068 change. Verify the
change is correct, consistent, and complete as one unit.

### Final Review Checklist

- **Acceptance criteria** — all of AC1–AC4 in the design are satisfied by the
  combined S01 + S03 output.
- **Regression test** — `tests/dashboard/test_cr00068_model_bar_removed.py`
  exists, asserts the model-bar ids/markup are gone from `panel.html` and
  `chat.js`, and would fail if the bar were reintroduced. It does not assert
  the kept `.chat-assistant-tab-model-badge` CSS class is absent.
- **Complete removal** — no element id, function, listener, or variable that
  belonged only to the model bar remains. Re-grep `chat.js` and `panel.html`
  for `chat-assistant-tab-model-bar`, `chat-assistant-tab-model-dropdown`,
  `chat-assistant-tab-model-label`, `_updateTabModelBar`, `_hideTabModelBar`,
  `_populateTabModelDropdown`, `_selectTabModel`, `_availableModels` — all zero.
- **Nothing over-removed** — `_defaultModel`, `_refreshModels`,
  `_scheduleModelRefresh`, the tab-strip badge code, and the
  `.chat-assistant-tab-model-badge` CSS rules are all still present.
- **Template validity** — the collapsed-state `<style>` selector list in
  `panel.html` is still syntactically valid after the selector removal.
- **No regression** — the settings panel still PATCHes the model; the tab
  strip still renders per-tab model badges; tab switching, the skills tray,
  history dropdown, and composer are unaffected.
- **No dead code** — no commented-out blocks left behind.
- **Scope** — every changed file is within the design's Impacted Paths. No
  Python / router / API changes.
- **Conventions** — `dashboard/CLAUDE.md` honoured.

## Pre-Review Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in a changed file = CRITICAL finding.

## Subagent Result Contract

```bash
uv run iw step-done CR-00068 --step S04 \
  --report ai-dev/work/CR-00068/reports/CR-00068_S04_CodeReviewFinal_report.md
```

```json
{
  "step": "S04",
  "agent": "code-review-final-impl",
  "work_item": "CR-00068",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check passed",
  "notes": ""
}
```
