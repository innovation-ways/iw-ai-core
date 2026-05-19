# F-00086_S07_Frontend_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Step**: S07
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- **Runtime step state** — `uv run iw item-status F-00086 --json`.
- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — design document (read §Scope, §Frontend Changes, §Acceptance Criteria in full)
- `ai-dev/active/F-00086/reports/F-00086_S06_API_report.md` — S06 API surface (paths, schemas, headers)
- Existing UI:
  - `dashboard/templates/chat_assistant/panel.html` (126 lines)
  - `dashboard/templates/chat_assistant/{composer,message,approval,history_dropdown,skills_tray}.html`
  - `dashboard/static/chat_assistant/chat.js` (1116 lines)
  - `dashboard/static/chat_assistant/chat.css`
- Pre-state evidence: `ai-dev/active/F-00086/evidences/pre/F-00086-before-single-session-chat.png`

## Output Files

- `dashboard/templates/chat_assistant/panel.html` — embeds tab strip, modal, dropdown
- `dashboard/templates/chat_assistant/tab_strip.html` — new
- `dashboard/templates/chat_assistant/create_tab_modal.html` — new
- `dashboard/templates/chat_assistant/closed_tabs_dropdown.html` — new
- `dashboard/static/chat_assistant/chat.js` — tab lifecycle, per-tab EventSource, per-tab model dropdown, soft-cap banner
- `dashboard/static/chat_assistant/chat.css` — tab strip styling (or append to `dashboard/static/styles.css` if `make css` is unavailable per CLAUDE.md mitigation)
- `ai-dev/active/F-00086/reports/F-00086_S07_Frontend_report.md`

## Context

You are adding a tab strip to the AI Assistant chat panel and wiring per-tab lifecycle to the tab-scoped API (S06). The existing single-session composer/message/approval templates are preserved and **rendered per-active-tab** — the tab strip selects which tab's content is visible; only the active tab keeps an `EventSource` open.

## Requirements

### 1. Tab strip (`tab_strip.html`)

Horizontal scrollable row above the existing chat content. Each tab is a button with:

- A short title (truncated with ellipsis; full title in `title` attribute)
- A model badge showing the model's short name (e.g., `claude-sonnet-4-7`)
- A close × button (visible on hover or always — match dashboard idiom)
- Active state styling (background color, border)
- Right-click context menu: `Rename`, `Duplicate`, `Close`
- Double-click on title → inline rename (input field replaces span; Enter saves via `PATCH /api/chat/tabs/{tab_id}`; Escape cancels)

Right end of strip:
- "+" button → opens `create_tab_modal`
- "Recent closed" dropdown button → opens `closed_tabs_dropdown`

### 2. Create-tab modal (`create_tab_modal.html`)

Fields:
- **Project**: pre-filled from current page context (`window.IW_CURRENT_PROJECT_ID`); LOCKED (read-only) when launched from a per-project page. Editable dropdown only when launched from the global context.
- **Runtime**: dropdown with exactly one option `"OpenCode"` (selected by default). Show as disabled or single-item — match dashboard idiom for "single-option dropdown that will gain options later".
- **Model**: dropdown populated by `GET /api/chat/config?project_id=X&runtime=opencode` — same model list the existing single-session selector uses. Default to the `default_model` from the response.
- **Title**: text input, optional, default `"New chat"`.

Submit → `POST /api/chat/tabs`. On 201:
- Add the new tab to the local tab list
- Switch to it (activate)
- If `X-Tab-Soft-Cap-Exceeded: true` header present → render the soft-cap banner (§4)

On 400 → display the error inline in the modal; keep the modal open.
On 503 → display "Runtime unavailable; try again later"; keep the modal open.

### 3. Per-tab EventSource lifecycle

Today there is one chat panel with one `EventSource`. Refactor so:

- **Each tab** has a lazy-instantiated `EventSource` to `/api/chat/tabs/{tab_id}/stream`.
- Only the **active** tab keeps its `EventSource` open. Switching tabs → close the previous tab's EventSource, open the new tab's EventSource using its stored `last_event_id` (the highest `event.lastEventId` it has seen).
- Persist the per-tab `last_event_id` in `sessionStorage` keyed by `tab_id` so reload retains it.
- On EventSource error → exponential backoff retry (match existing chat.js retry pattern in `stream.js`).

Events carry a top-level `"tab_id"` field (S03 invariant #2). Use it to:
- Defensive sanity check: ignore any event whose `tab_id` does not match the active tab (logs a console warning).
- Future-proofing for F-B: when Pi tabs are added, the same dispatch shape applies.

### 4. Soft-cap warning banner

When ANY response from `POST /api/chat/tabs` returns `X-Tab-Soft-Cap-Exceeded: true`, render a dismissible info banner ABOVE the tab strip:

> ⚠ 10+ tabs open — consider closing inactive tabs.

Banner persists across tab switches in the current page session. Dismiss button (×) removes it. Re-shows on the next POST that returns the header. Match the dashboard's existing alert/banner styling (see `dashboard/templates/components/` or `dashboard/templates/base.html` for the pattern; if none exists, create a minimal styled `<div role="alert">`).

### 5. Recent-closed dropdown (`closed_tabs_dropdown.html`)

Button at the right of the tab strip. On click → `GET /api/chat/tabs/recent-closed?project_id=X&limit=10` and render a dropdown of items. Each item shows the tab title, model, and "Closed at <relative time>". Click an item → `POST /api/chat/tabs/{tab_id}/reopen` → refresh tab list → switch to reopened tab.

If the list is empty → render "No recently closed tabs."

### 6. Per-tab model dropdown above composer

Above the composer, render the active tab's current model as a clickable badge. Click → dropdown of available models for the runtime (reuses the same `/api/chat/config` data as the create-tab modal). Selecting a different model → `PATCH /api/chat/tabs/{tab_id}` with `{model: "..."}` → update the local tab state and the badge text.

Subsequent prompts in the tab use the new model (the API picks up the model from the tab record; client just needs to update the visible badge).

### 7. Bootstrap-default behaviour

On panel mount, call `GET /api/chat/tabs?project_id=X`. If response is empty, the backend has already triggered `bootstrap_default_tab` server-side — the next read may return a single default tab. Re-fetch once after a short delay (100ms) when the first response is empty, to account for the lazy-bootstrap behaviour.

If still empty after the retry → render empty-state: "No chats yet — click + to create one." (Boundary row "No tabs exist, no prior OpenCode session".)

### 8. Empty-state UI

When no tabs exist (after bootstrap), the panel content area shows the empty-state message + a prominent "+" CTA. No composer is rendered until at least one tab is active.

### 9. Clipboard / safety conventions

- Per `dashboard/CLAUDE.md`: NEVER call `navigator.clipboard.writeText(...)` directly. Use `window.iwClipboard.copy(text, button)` for any copy actions you add.
- Do NOT introduce inline event handlers (`onclick=...`); attach via `addEventListener` in chat.js. Match existing JS style.
- HTMX: use `hx-*` attributes only where the existing chat panel already uses HTMX. For tab CRUD, vanilla `fetch` + JS DOM updates is the established pattern (the chat panel today does not use HTMX for its core flow — verify by reading `chat.js`).

### 10. CSS strategy

Try `make css` first. If it succeeds, you may use Tailwind utility classes in your new templates. If `make css` reports "Nothing to be done" or fails with a missing-postcss-selector-parser-style error (the I-00067 issue), append plain CSS rules directly to `dashboard/static/styles.css` per the CLAUDE.md mitigation rule. Document which path you took in your report.

## Project Conventions

Read `dashboard/CLAUDE.md` (FastAPI + Jinja2 + htmx + Tailwind; clipboard helper; mtime-keyed Tailwind purge). Read the existing `panel.html`, `composer.html`, `message.html` for the established structural patterns — match them.

## TDD Requirement

Frontend changes are exercised by the qv-browser step (S16). The targeted unit/integration tests for tab CRUD are in S08. For S07 alone, `tdd_red_evidence` is `"n/a — UI template/JS; behavioural tests added in S08, browser verification in S16"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — picks up Python file changes if any (dashboard/templates/* are templates; chat.js is JS — run `make lint` for both)
2. `make typecheck`
3. `make lint` — includes `lint-js` and `lint-templates`
4. **Open the dashboard in a browser** to manually verify your tab strip renders without console errors. Even though S16 is the formal browser verification step, a quick smoke test here catches obvious template syntax / JS errors before S08 spends compute running adapted tests.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "frontend-impl",
  "work_item": "F-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat_assistant/panel.html",
    "dashboard/templates/chat_assistant/tab_strip.html",
    "dashboard/templates/chat_assistant/create_tab_modal.html",
    "dashboard/templates/chat_assistant/closed_tabs_dropdown.html",
    "dashboard/static/chat_assistant/chat.js",
    "dashboard/static/chat_assistant/chat.css"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:no-python-changes",
    "typecheck": "ok|skipped:no-python-changes",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "manual smoke: dashboard renders tab strip without console errors",
  "tdd_red_evidence": "n/a — UI template/JS; behavioural tests added in S08, browser verification in S16",
  "blockers": [],
  "notes": "CSS strategy used: <make-css|plain-css-fallback>"
}
```
