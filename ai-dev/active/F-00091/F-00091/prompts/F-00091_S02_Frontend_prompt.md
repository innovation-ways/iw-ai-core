# F-00091_S02_Frontend_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Step**: S02
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. This step touches no Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step adds no migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00091 --json`
- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — Design (read Scope → S02, AC1, all Invariants 1–2, and Boundary rows 1–6)
- `ai-dev/active/F-00091/evidences/pre/` — three "before" screenshots showing the current URL-driven swap
- `dashboard/templates/chat_assistant/panel.html` — Panel header where the dropdown lives
- `dashboard/static/chat_assistant/chat.js` — `_currentProjectId()` defined at line 87; 10 call sites at lines 163, 1026, 1077, 1142, 1197, 1254, 1340, 1446, 1916, 1945 (run grep to confirm before editing)
- `dashboard/static/chat_assistant/chat.css` — CSS source for new selector styles
- S01 report (if available): `ai-dev/work/F-00091/reports/F-00091_S01_API_report.md` — confirms the new endpoint shape

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_S02_Frontend_report.md`

## Context

You are removing the URL coupling that makes the Assistant swap projects on every page navigation. After this step the Assistant's project is governed by an in-panel dropdown only; the URL is consulted ONCE on first ever open (when the localStorage key is unset).

Read the design doc Sections **Scope → S02**, **AC1**, **Invariants 1 and 2**, and Boundary rows 1–6 in full before touching code. Then read `dashboard/CLAUDE.md` and the top-level `CLAUDE.md`.

## Requirements

### 1. Add the project selector to `panel.html`

In `dashboard/templates/chat_assistant/panel.html`, modify the header `<header id="chat-assistant-header">` block:

- Replace the static `<span id="chat-assistant-title">AI Assistant</span>` with a flex layout that contains:
  1. A small `<select id="chat-assistant-project-select">` styled to fit the 360px panel width. It uses `class="text-xs bg-input border border-border rounded px-2 py-1 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"` to match the existing settings-panel dropdowns.
  2. The select's initial `<option>` is `<option value="">Loading…</option>`. The chat.js bootstrap replaces it with the real list.
- Keep the existing `data-collapsed="true"` rules — when the panel is collapsed the select is hidden via the existing `display: none` CSS for `#chat-assistant-title`. Add `#chat-assistant-project-select` to the same selector list at the top of the file's `<style>` block so it hides when collapsed.
- Do NOT remove the `id="chat-assistant-title"` element entirely — keep a small visually-hidden span with that id so existing test selectors and `aria-label` references don't break.

### 2. New JS accessors in `chat.js`

In `dashboard/static/chat_assistant/chat.js`:

- Add `_assistantProjectId()` that returns `localStorage.getItem('iw-chat-assistant-project') || null`, wrapped in a try/catch so private-browsing quota errors yield `null` (Boundary row 6).
- Add `_setAssistantProjectId(projectId)` that writes the value, wrapped in try/catch. After writing, it ALSO updates the `<select>` element's value if the element exists.
- Add `_seedAssistantProjectId()` that runs ONCE during first bootstrap:
  1. If `localStorage` already has a value AND that value matches a project_id returned by `/api/chat/projects`, do nothing.
  2. Else if `/api/chat/projects` is empty, set to `null`.
  3. Else if the current URL parses as `/project/<id>/` AND `<id>` matches a returned project, set to `<id>`.
  4. Else, set to the first project's id (alphabetical → already sorted by the API).
- Add `_loadAssistantProjects()` that fetches `/api/chat/projects`, populates the `<select>` (preserving the currently selected value if still valid), and returns the list as a Promise.

### 3. Replace ALL `_currentProjectId()` call sites

Search `chat.js` for `_currentProjectId(` and replace EVERY occurrence with `_assistantProjectId(`. Current hits (verify with grep before touching — line numbers may shift after S02 edits):

- `chat.js:163` inside `_bootstrapTabs()`
- `chat.js:1026` inside `_duplicateTab()` (falls back to `tab.project_id` — keep the `|| tab.project_id` fallback)
- `chat.js:1077` inside `_instantCreateTab()`
- `chat.js:1142` inside `_fetchModelsForSettings()`
- `chat.js:1197` inside the runtime-change handler (falls back to `tab.project_id` — keep the fallback)
- `chat.js:1254` prefilling the create-tab modal project input
- `chat.js:1340` inside `_fetchModelsForModal()`
- `chat.js:1446` inside `_loadRecentClosedTabs()`
- `chat.js:1916` inside `_refreshModels()`
- `chat.js:1945` inside `_scheduleModelRefresh()`

After this step, `chat.js` must contain ZERO references to `window.location.pathname` for project derivation. The ONLY remaining place that touches the URL for project is `_seedAssistantProjectId()` (the one-time seed). Per Invariant 1, the symbol `_currentProjectId` must not appear in `chat.js` at all.

### 4. Wire the dropdown's change handler

When the user selects a different project in the dropdown:

1. Call `_setAssistantProjectId(newId)`.
2. Close any open EventSources for the previous project's tabs (use the existing per-tab cleanup paths so streams aren't orphaned).
3. Re-call `_bootstrapTabs()` to load the new project's tabs.
4. The model refresh and context-pct poll restart naturally inside `_activateTab(...)`, which `_bootstrapTabs()` triggers.

Do NOT do a full page reload. The whole point of this step is to make project switching cheap.

### 5. Initial state and empty-projects state

- During DOM-ready setup, call `_loadAssistantProjects().then(_seedAssistantProjectId).then(_bootstrapTabs)` only when the panel is open (preserve current laziness).
- When the projects list is empty: render the dropdown with one disabled option "No projects available", disable the composer (`textarea`, Send button), and hide the empty-state CTA "New Chat" button (no tabs can exist without a project).

### 6. CSS

Append the new selector styles to `dashboard/static/chat_assistant/chat.css` (NOT to `styles.css` — that file is the Tailwind output and is regenerated). Per the project's known toolchain limitation (I-00067), plain CSS appended here is served as-is.

### 7. TDD

Add `tests/dashboard/test_assistant_project_decoupling.py`:

- A Playwright-driven dashboard test is NOT in scope here (that's S19). Use the existing test harness pattern: hit the dashboard route, parse the HTML, assert the `<select id="chat-assistant-project-select">` exists with the expected initial structure.
- Verify the page no longer contains a `_currentProjectId` reference in the served `chat.js`.

Capture the RED run (test fails because the selector is missing), then implement, then GREEN.

### 8. Out of scope for this step

- The per-project active-tab restoration. That is S03. Today's sessionStorage behaviour is fine in this step.
- The progress bar UI. That is S07.
- The context-pct payload changes. That is S06.

## Project Conventions

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md`. Specifically:

- Tailwind CSS is prebuilt; new CSS goes into `chat_assistant/chat.css`.
- Jinja2 templates: keep `format` filter calls in `%`-style.
- No `navigator.clipboard.writeText` (not relevant here, but worth noting).
- `chat.js` uses the ES5 IIFE style — match it. No `const`/`let`/arrow functions for state declarations.

## TDD Requirement

Standard RED → GREEN → REFACTOR. Record the failing assertion in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Run before reporting completion:

1. `make format`
2. `make typecheck`
3. `make lint` (this includes `scripts/check_templates.py` — your template edits must pass)

## Test Verification (NON-NEGOTIABLE)

Run only the test file(s) you wrote:

```bash
uv run pytest tests/dashboard/test_assistant_project_decoupling.py -v
```

Do NOT run the whole dashboard or integration suite.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "frontend-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat_assistant/panel.html",
    "dashboard/static/chat_assistant/chat.js",
    "dashboard/static/chat_assistant/chat.css",
    "tests/dashboard/test_assistant_project_decoupling.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_assistant_project_decoupling.py::test_dropdown_renders — AssertionError: '<select id=\"chat-assistant-project-select\"' not in served HTML",
  "blockers": [],
  "notes": ""
}
```
