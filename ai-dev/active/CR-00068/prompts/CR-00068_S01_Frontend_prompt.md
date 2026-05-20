# CR-00068_S01_Frontend_prompt

**Work Item**: CR-00068 — AI Assistant — Remove Per-Tab Model Bar
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step writes no migrations. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00068 --json`
- `ai-dev/active/CR-00068/CR-00068_CR_Design.md` — Design document
- `dashboard/CLAUDE.md` — dashboard conventions
- `dashboard/templates/chat_assistant/panel.html` — panel template (target)
- `dashboard/static/chat_assistant/chat.js` — AI Assistant JS (target)
- `dashboard/static/chat_assistant/chat.css` — AI Assistant CSS (reference only — do NOT modify)

## Output Files

- `dashboard/templates/chat_assistant/panel.html` — modified
- `dashboard/static/chat_assistant/chat.js` — modified
- `tests/dashboard/test_cr00068_model_bar_removed.py` — new regression test
- `ai-dev/work/CR-00068/reports/CR-00068_S01_Frontend_report.md` — report

## Context

The AI Assistant panel shows a per-tab model bar (`#chat-assistant-tab-model-bar`)
— a clickable model badge and drop-down model picker — above the message area.
It is redundant with the model picker in the settings panel. This step removes
the bar and all JavaScript that exists only to drive it. The small model badge
on each **tab-strip button** is a separate element and MUST be kept.

## Task

### 1. `panel.html` — remove the model bar

In `dashboard/templates/chat_assistant/panel.html`:

- Remove the entire `<div id="chat-assistant-tab-model-bar"> … </div>` block
  (the bar, the `#chat-assistant-tab-model-badge` button, the
  `#chat-assistant-tab-model-label` span, and the
  `#chat-assistant-tab-model-dropdown` list — currently around lines 80–103,
  including the `<!-- Per-tab model bar … -->` comment).
- In the `<style>` block at the top of the file, remove the
  `#chat-assistant-panel[data-collapsed="true"] #chat-assistant-tab-model-bar,`
  selector line (it is one selector in a comma-separated list that hides panel
  chrome when collapsed — remove just that one line, keep the rest of the list
  valid: the line before it must still end with a comma and the list must still
  terminate correctly).

Do NOT touch the tab strip include, the skills tray, the history dropdown, the
messages area, or the composer.

### 2. `chat.js` — remove dead model-bar code

In `dashboard/static/chat_assistant/chat.js`, remove everything that exists
only to drive the now-deleted bar:

**Functions to delete entirely:**
- `_updateTabModelBar()`
- `_hideTabModelBar()`
- `_populateTabModelDropdown()`
- `_selectTabModel()`

**Call sites to remove** (the lines that call the deleted functions):
- The `_updateTabModelBar()` call after a tab is activated.
- The `if (tabId === _activeTabId) _updateTabModelBar();` call.
- The `_hideTabModelBar()` call(s).
- The `_updateTabModelBar()` call after a tab PATCH.
- Any other call to the four deleted functions — grep to be exhaustive.

**Event listeners to remove:**
- The `#chat-assistant-tab-model-badge` click listener that toggles the model
  dropdown.
- The model-dropdown branch inside the document-level outside-click handler
  (the block that looks up `chat-assistant-tab-model-dropdown` /
  `chat-assistant-tab-model-badge` and hides the dropdown on outside click).
  Keep the other branches of that handler (tab context menu, closed-tabs
  dropdown, settings panel) intact.

**Dead state to remove:**
- The `_availableModels` variable — it is used **only** by the deleted
  `_populateTabModelDropdown()`. Remove its declaration, the
  `_availableModels = data.models || [];` assignment inside `_refreshModels()`,
  and the `_availableModels = [];` reset inside `_scheduleModelRefresh()`.

**MUST keep (do NOT remove):**
- `_defaultModel` — `_instantCreateTab()` uses it to choose a new tab's default
  model.
- `_refreshModels()` and `_scheduleModelRefresh()` and `_modelRefreshTimer` —
  they keep `_defaultModel` current. Inside `_refreshModels()`, after removing
  the `_availableModels` assignment, also remove the now-dangling
  `_populateTabModelDropdown()` call; keep the `_defaultModel` assignment and
  the `project_directory` handling.
- The tab-strip model badge: the `.chat-assistant-tab-model-badge` element
  created during tab-button rendering (the `modelBadge` in the tab-strip render
  code) and `_updateTabButtonLabel` — these style/update the per-tab badge that
  is being kept.
- The **create-tab modal** model subsystem — `_populateCreateTabModelDropdown`,
  `_fetchModelsForModal`, `_modalModels`, `_modalDefaultModel` — is a separate
  feature unrelated to the removed bar. Do NOT touch it. Note its function
  `_populateCreateTabModelDropdown` is deliberately distinct from the deleted
  `_populateTabModelDropdown` — delete only the latter.

### 3. `chat.css` — no change expected

The model bar used inline Tailwind classes; it has no dedicated rules in
`chat.css`. The `.chat-assistant-tab-model-badge` and
`.chat-assistant-tab-btn-active .chat-assistant-tab-model-badge` rules style the
**tab-strip badge** that is kept — do NOT remove them. Only touch `chat.css` if
you find a rule that *exclusively* targeted the removed bar (none is expected).

### 4. Add a regression test

Create `tests/dashboard/test_cr00068_model_bar_removed.py` — a fast,
no-database test (follow the file-read pattern of
`tests/dashboard/test_chat_panel_template.py`: read the file directly, assert on
its content). It MUST assert:

- `dashboard/templates/chat_assistant/panel.html` no longer contains
  `id="chat-assistant-tab-model-bar"`, `id="chat-assistant-tab-model-dropdown"`,
  or `id="chat-assistant-tab-model-label"`.
- The collapsed-state `<style>` block in `panel.html` no longer lists
  `#chat-assistant-tab-model-bar`, and that block still terminates with
  `{ display: none; }` (the selector list is still syntactically valid).
- `dashboard/static/chat_assistant/chat.js` no longer references the removed
  element ids `chat-assistant-tab-model-bar`,
  `chat-assistant-tab-model-dropdown`, or `chat-assistant-tab-model-label`.

Every assertion must be one that would **fail if the model bar were
reintroduced** — do not assert on anything that passes regardless. Do NOT
assert that the `chat-assistant-tab-model-badge` CSS class is absent: that class
styles the kept tab-strip badge and must survive.

If any existing `tests/dashboard/` test asserts on the model bar's *presence*,
update it. A design-time grep found none — confirm with a grep and proceed.

## Constraints

- Pure removal / cleanup. Do NOT modify any Python, router, or API. The
  settings-panel model-change path (`PATCH /api/chat/tabs/{id}`) stays as-is.
- After editing, grep `chat.js` for each removed identifier —
  `chat-assistant-tab-model-bar`, `chat-assistant-tab-model-dropdown`,
  `chat-assistant-tab-model-label`, `_updateTabModelBar`, `_hideTabModelBar`,
  `_populateTabModelDropdown`, `_selectTabModel`, `_availableModels` — and
  confirm **zero** remaining references. The string `chat-assistant-tab-model-badge`
  may still appear as a CSS class for the tab-strip badge — that is correct;
  only its use as the **bar's element id** is removed.
- Do NOT leave commented-out dead code — delete it.
- Keep all other DOM ids and the `chat-assistant-` prefix convention intact.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
uv run pytest tests/dashboard/test_cr00068_model_bar_removed.py -q
```

All three must pass with no new violations in changed files. `make lint`
includes `node --check` on dashboard JS and `scripts/check_templates.py` on
Jinja2. Run **only** the new regression test file here — do NOT run
`make test-integration` or `make test-unit`; the full integration suite is the
S06 QV gate's job.

## Subagent Result Contract

```bash
uv run iw step-done CR-00068 --step S01 \
  --report ai-dev/work/CR-00068/reports/CR-00068_S01_Frontend_report.md
```

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "CR-00068",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat_assistant/panel.html",
    "dashboard/static/chat_assistant/chat.js",
    "tests/dashboard/test_cr00068_model_bar_removed.py"
  ],
  "tests_passed": true,
  "test_summary": "lint + format-check + regression test passed",
  "blockers": [],
  "notes": ""
}
```
