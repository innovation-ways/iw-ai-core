# F-00087 — S04 Frontend Implementation Report

**Work item**: F-00087 — Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S04 (Frontend)
**Agent**: frontend-impl
**Status**: complete

---

## Summary

Extended the AI Assistant create-tab modal and chat.js to offer Pi as a second
selectable runtime, wire the model dropdown to re-fetch from
`GET /api/chat/config?runtime=<selected>` on runtime change, restrict per-tab model
dropdowns to the active tab's runtime, handle the empty-model-list edge case, and
add `data-runtime` to tab strip DOM elements.

## What Was Done (per requirement)

### Requirement 1: Runtime dropdown gains "Pi" option

`dashboard/templates/chat_assistant/create_tab_modal.html` — the runtime `<select>`
(id `chat-assistant-create-tab-runtime`) now has two options:

```html
<option value="opencode" selected>OpenCode</option>
<option value="pi">Pi</option>
```

Matched the existing `<select>` pattern: same `id`/`class` conventions, no htmx
attributes (the dropdown is handled purely by chat.js). The `selected` attribute is
explicit on the default option.

### Requirement 2: Re-fetch model list on runtime change

Added a `document.addEventListener('change', ...)` listener in the `DOMContentLoaded`
block that targets `#chat-assistant-create-tab-runtime`. On change, it:
- Updates `_modalRuntime` sentinel.
- Clears `_modalModels`/`_modalDefaultModel`.
- Calls `_fetchModelsForModal(selectedRuntime)`.

The new `_fetchModelsForModal(runtime)` function (replacing the old
`_fetchModelsForModal()` that ignored runtime):
- Builds `GET /api/chat/config?project_id=X&runtime=<runtime>` using `URLSearchParams`.
- Uses the existing `fetch` pattern (no new HTTP library).
- Includes a stale-fetch guard: if `_modalRuntime !== selectedRuntime` when the
  response arrives, the result is discarded (handles rapid user switching).
- On 503 or non-200: calls `_showCreateTabError('Could not load models: ...')` and
  disables the Create button.
- On success with models: calls `_populateCreateTabModelDropdown()` and hides any
  prior error.

`_populateCreateTabModelDropdown()` now reads from `_modalModels`/`_modalDefaultModel`
(modal-local) instead of the global `_availableModels`/`_defaultModel` (which are
reserved for the per-tab bar). This prevents the modal and the per-tab bar from
accidentally sharing the same model cache from different runtimes.

`_openCreateTabModal()` now:
- Resets the runtime dropdown to `opencode` every time the modal opens.
- Sets `_modalRuntime = 'opencode'` and triggers `_fetchModelsForModal('opencode')`
  always on open (so a fresh fetch happens even if models were previously cached for
  this runtime, ensuring we see current Pi model availability).

### Requirement 3: Per-tab model dropdown is runtime-scoped

`_refreshModels()` (called on every `_activateTab()`) now resolves the active tab's
runtime from `_tabs` and appends `runtime=<activeRuntime>` to the config fetch URL.
This means:
- Pi tab activated → fetches `?runtime=pi` → `_availableModels` populated with Pi
  models only → `_populateTabModelDropdown()` renders only Pi models.
- OpenCode tab activated → fetches `?runtime=opencode` → only OpenCode models shown.

`_populateTabModelDropdown()` has a tooltip added to the dropdown container:
`dd.title = 'Switching runtime requires creating a new tab.'`

### Requirement 4: Empty model list handling

In `_fetchModelsForModal`, when `data.models` is empty after a successful fetch:
- The model `<select>` is cleared and a descriptive `<option>` is inserted:
  - Pi runtime: "No Pi models configured for this project. See docs/IW_AI_Core_AI_Assistant_Models.md."
  - Other runtimes: "No models available."
- The Create button is disabled (`submitBtn.disabled = true`).
- `_showCreateTabError()` is called with the same message.

When the user switches back to a runtime that has models, `_hideCreateTabError()` is
called and the button is re-enabled.

### Requirement 5: Tab strip indicator

`_buildTabButton(tab)` now sets `data-runtime="<opencode|pi>"` on the tab `<button>`
element, alongside the existing `data-tab-id`. This attribute is set from
`tab.runtime || 'opencode'`. No new visual styling was added (the existing model badge
implicitly differentiates runtimes by model name; the `data-runtime` attribute
satisfies the minimum requirement and is queryable by tests).

### Requirement 6: CSS strategy

`make css` reported "Nothing to be done" (I-00067 Tailwind toolchain issue in
worktrees). No new CSS rules were required for this step: all new behavior uses
existing Tailwind utility classes from the template (which are unchanged), JavaScript
DOM manipulation for the modal, and plain attribute-setting for `data-runtime`. The
CSS mitigation path (append to `dashboard/static/styles.css`) was **not needed** —
no new selectors or animations were introduced.

**CSS strategy used**: `make-css` attempted → "Nothing to be done" → no CSS changes
required → no plain-CSS-fallback needed.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/chat_assistant/create_tab_modal.html` | Added `<option value="pi">Pi</option>` to the runtime `<select>`; added `selected` to the opencode option. |
| `dashboard/static/chat_assistant/chat.js` | (1) Added `_modalModels`, `_modalDefaultModel`, `_modalRuntime` variables. (2) `_buildTabButton`: adds `data-runtime` attribute. (3) `_refreshModels`: appends `runtime=<activeTabRuntime>` to the fetch URL. (4) `_populateTabModelDropdown`: adds `title` tooltip. (5) `_openCreateTabModal`: resets runtime dropdown, triggers fresh model fetch. (6) `_populateCreateTabModelDropdown`: reads from `_modalModels`/`_modalDefaultModel`. (7) `_fetchModelsForModal(runtime)`: runtime-aware, stale-guard, error/empty handling, disables Create on error. (8) `DOMContentLoaded`: adds `change` event listener on `#chat-assistant-create-tab-runtime`. |

## Quality Gates Run

| Gate | Command | Result | Notes |
|------|---------|--------|-------|
| CSS build | `make css` | "Nothing to be done" | Per I-00067 — expected in worktree |
| Lint | `make lint` | PASS ("All checks passed!") | Includes ruff (Python) + check_templates.py (Jinja2) |
| Format | skipped | n/a | No Python files modified |
| Typecheck | skipped | n/a | No Python files modified |

## Manual Smoke Description

The following behaviors are expected (S13 owns browser verification):

1. **Modal opens**: Runtime dropdown shows "OpenCode" (selected, default) and "Pi".
   Model dropdown shows "Loading…" while the OpenCode model list is fetched from
   `GET /api/chat/config?project_id=X&runtime=opencode`. On success, models populate
   and Create button is enabled.

2. **User selects Pi**: The `change` event fires, `_fetchModelsForModal('pi')` is
   called with `GET /api/chat/config?project_id=X&runtime=pi`. If Pi models are
   configured (e.g., `pi/minimax/MiniMax-M2.7`), they populate the dropdown. If none
   are configured, the dropdown shows the "No Pi models configured..." message and the
   Create button is disabled.

3. **User switches back to OpenCode**: Model list re-fetches with `runtime=opencode`,
   error is cleared, Create button re-enabled.

4. **Pi tab activated**: `_refreshModels` fetches `?runtime=pi`; the per-tab model
   bar above the composer shows only Pi models. Hovering over the model dropdown
   shows "Switching runtime requires creating a new tab."

5. **OpenCode tab activated**: `_refreshModels` fetches `?runtime=opencode`; only
   OpenCode models appear in the per-tab bar.

6. **Tab strip buttons**: Each tab button has `data-runtime="opencode"` or
   `data-runtime="pi"` set, queryable by `querySelector('[data-runtime="pi"]')`.

## Deviations, Blockers, and Follow-ups

- No deviations from the design spec.
- No blockers encountered.
- S05 (tests-impl) should add a unit/integration test for the runtime-change model
  re-fetch flow (verifying the `change` event triggers the correct API call) and for
  the `data-runtime` attribute on tab buttons.
- S13 (qv-browser) owns end-to-end browser verification of the dropdown behavior.
