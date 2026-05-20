# CR-00068_S02_CodeReview_prompt

**Work Item**: CR-00068 — AI Assistant — Remove Per-Tab Model Bar
**Steps Being Reviewed**: S01
**Review Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00068 --json`
- `ai-dev/active/CR-00068/CR-00068_CR_Design.md` — Design document
- Report from S01 in `ai-dev/work/CR-00068/reports/`
- All files in S01's `files_changed`

## Output Files

- `ai-dev/work/CR-00068/reports/CR-00068_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in a changed file = CRITICAL finding.

## Review Checklist

### 1. `panel.html`

- The entire `#chat-assistant-tab-model-bar` block (bar, badge, label,
  dropdown) is removed.
- The `#chat-assistant-tab-model-bar` selector is removed from the collapsed-
  state `<style>` block, and the remaining comma-separated selector list is
  still syntactically valid (no trailing/leading comma error, list still
  terminates with `{ display: none; }`).
- Tab strip include, skills tray, history dropdown, messages area, and composer
  are untouched.

### 2. `chat.js` — completeness of removal

- Functions `_updateTabModelBar`, `_hideTabModelBar`, `_populateTabModelDropdown`,
  and `_selectTabModel` are deleted entirely.
- Every call site of those four functions is removed.
- The `#chat-assistant-tab-model-badge` click listener is removed.
- The model-dropdown branch of the document outside-click handler is removed;
  the other branches (tab context menu, closed-tabs dropdown, settings panel)
  remain intact.
- `_availableModels` declaration, its assignment in `_refreshModels()`, and its
  reset in `_scheduleModelRefresh()` are removed.
- **No dangling references**: grep the final `chat.js` for
  `chat-assistant-tab-model-bar`, `chat-assistant-tab-model-dropdown`,
  `chat-assistant-tab-model-label`, `_updateTabModelBar`, `_hideTabModelBar`,
  `_populateTabModelDropdown`, `_selectTabModel`, `_availableModels` — all must
  return zero hits.
- No commented-out dead code left behind.

### 3. `chat.js` — what MUST still be present

- `_defaultModel` still declared and still used by `_instantCreateTab()`.
- `_refreshModels()` and `_scheduleModelRefresh()` still exist and still keep
  `_defaultModel` current; `_refreshModels()` no longer calls
  `_populateTabModelDropdown()`.
- The tab-strip badge code (`.chat-assistant-tab-model-badge` element created in
  tab-button rendering, `_updateTabButtonLabel`) is intact.

### 4. `chat.css`

- `.chat-assistant-tab-model-badge` and
  `.chat-assistant-tab-btn-active .chat-assistant-tab-model-badge` rules are
  still present (they style the kept tab-strip badge).
- `chat.css` was ideally not modified at all; if it was, the only acceptable
  change is removal of a rule that exclusively targeted the deleted bar.

### 5. Regression test

- `tests/dashboard/test_cr00068_model_bar_removed.py` exists.
- It asserts the model-bar ids/markup are absent from `panel.html` and
  `chat.js` (`chat-assistant-tab-model-bar`, `-dropdown`, `-label`).
- Every assertion would fail if the model bar were reintroduced — no assertion
  that passes regardless. It does NOT assert the kept
  `.chat-assistant-tab-model-badge` CSS class is absent.
- It is a fast, no-database test (file-read / template-content style).

### 6. Scope check

Changed files MUST be a subset of the design's **Impacted Paths**:
`panel.html`, `chat.js`, `chat.css`, `tests/dashboard/**`. Any Python, router,
or API change is a CRITICAL scope violation.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Breaks functionality, scope violation, dangling reference |
| HIGH | Significant bug, incomplete removal |
| MEDIUM_FIXABLE | Convention violation, leftover dead code |
| MEDIUM_SUGGESTION | Optional improvement |
| LOW | Nitpick |

## Review Result Contract

```bash
uv run iw step-done CR-00068 --step S02 \
  --report ai-dev/work/CR-00068/reports/CR-00068_S02_CodeReview_report.md
```

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00068",
  "steps_reviewed": ["S01"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check passed",
  "notes": ""
}
```
