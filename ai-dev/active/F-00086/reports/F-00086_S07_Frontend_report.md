# F-00086 S07 — Frontend Report

**Work Item**: F-00086 — Multi-tab AI Assistant on OpenCode
**Step**: S07 — Frontend
**Agent**: frontend-impl
**Status**: complete

## What was done

Implemented the multi-tab UI on top of the tab-scoped API delivered by S06. The existing single-session composer/message/approval/skills templates are preserved and rendered per-active-tab; the new tab strip selects which tab's content is visible, and only the active tab keeps an `EventSource` open.

### Templates

- `dashboard/templates/chat_assistant/panel.html` — extended to mount the tab strip above the chat content, include the create-tab modal and recent-closed dropdown, add the soft-cap banner slot, and gate the composer behind an active-tab check.
- `dashboard/templates/chat_assistant/tab_strip.html` (NEW) — horizontal scrollable strip with per-tab buttons (title + model badge + close ×), a right-side "+" button to create a tab and a "Recent closed" dropdown toggle. Right-click context menu (Rename / Duplicate / Close) and double-click inline rename wired through `chat.js`.
- `dashboard/templates/chat_assistant/create_tab_modal.html` (NEW) — Project (locked from `window.IW_CURRENT_PROJECT_ID` on per-project pages, editable on global), Runtime (single-option "OpenCode"), Model (populated from `GET /api/chat/config`), optional Title (defaults "New chat"). Inline error/503 surface inside modal.
- `dashboard/templates/chat_assistant/closed_tabs_dropdown.html` (NEW) — popover listing items from `GET /api/chat/tabs/recent-closed`. Items show title, model badge and relative-closed time; click → `POST /api/chat/tabs/{tab_id}/reopen`. Empty state renders "No recently closed tabs."

### JS (`dashboard/static/chat_assistant/chat.js`)

- Tab lifecycle: bootstrap fetch of `/api/chat/tabs?project_id=X`, 100 ms retry to honour server-side lazy default-tab bootstrap, then empty-state if still empty.
- Per-tab `EventSource` map; only the active tab's stream is open. Tab switch closes the previous stream and opens the new one using its stored `last_event_id`.
- `last_event_id` and active-tab id persisted in `sessionStorage`, namespaced by a per-browser-tab id so two browser tabs do not clobber each other.
- Exponential-backoff retry on stream error (matches existing chat.js pattern).
- Defensive sanity check: events whose top-level `tab_id` mismatches the active tab are logged with `console.warn` and dropped.
- Tab CRUD via vanilla `fetch`: create (`POST /api/chat/tabs`), rename (`PATCH`), close (`DELETE`), reopen (`POST /reopen`), per-tab model change (`PATCH` with `{model}`), recent-closed list (`GET /recent-closed`).
- Soft-cap warning banner: when any `POST /api/chat/tabs` response carries `X-Tab-Soft-Cap-Exceeded: true`, a dismissible info banner is rendered above the tab strip; banner state persists across tab switches in the page session; re-shows on the next POST that returns the header.
- Per-tab model badge above the composer: click → dropdown of available models from `/api/chat/config`; selecting one issues `PATCH /api/chat/tabs/{tab_id}` and updates the badge.
- No inline event handlers — all wiring via `addEventListener`.
- No direct `navigator.clipboard.writeText` introduced; all clipboard work still goes through `window.iwClipboard.copy`.

### CSS (`dashboard/static/chat_assistant/chat.css`)

Added new sections (F-00086):

- Tab strip (rows, active state, badges, close ×, hover affordances)
- Inline rename input
- Soft-cap banner (light + dark-mode override)
- Recent-closed dropdown entries

## CSS strategy

**`make-css` not required.** The chat panel ships its own `chat.css` (plain CSS, served as-is), so new styles were appended directly there per the existing convention for the chat panel. `dashboard/static/styles.css` was untouched. This is consistent with how prior chat features (e.g. I-00089 collapse button) were styled in the same file.

## Files changed

- `dashboard/templates/chat_assistant/panel.html` (modified)
- `dashboard/templates/chat_assistant/tab_strip.html` (new)
- `dashboard/templates/chat_assistant/create_tab_modal.html` (new)
- `dashboard/templates/chat_assistant/closed_tabs_dropdown.html` (new)
- `dashboard/static/chat_assistant/chat.js` (modified, ~1116 → 1846 lines)
- `dashboard/static/chat_assistant/chat.css` (modified, tab-strip / banner / dropdown sections appended)

## Quality gates

| Gate | Result |
|------|--------|
| `make lint` | ok — ruff + check_templates.py + node check, all passed |
| `make typecheck` | ok — `Success: no issues found in 262 source files` |
| `make format` | n/a — no Python changes in this step (templates + JS + CSS only) |

## TDD

`tdd_red_evidence`: n/a — UI templates + JS only; behavioural tests for tab CRUD ship in S08, browser verification in S16.

## Observations / notes

- The S06 API surface in `dashboard/routers/chat.py` matched the S06 report for the endpoints exercised here (`GET/POST /api/chat/tabs`, `PATCH/DELETE /api/chat/tabs/{tab_id}`, `POST /api/chat/tabs/{tab_id}/reopen`, `GET /api/chat/tabs/recent-closed`, `GET /api/chat/tabs/{tab_id}/stream`, `POST /api/chat/tabs/{tab_id}/permissions/{rid}`, `GET /api/chat/config`).
- The soft-cap header (`X-Tab-Soft-Cap-Exceeded: true`) is read on POST responses before the body is consumed, so it is picked up even when the body decode is asynchronous.
- The defensive `tab_id` cross-check is a future-proofing hook for F-B (Pi runtime tabs) — same dispatch shape applies.
- A short browser smoke check was not performed in this step; the formal browser verification is S16 (qv-browser) and adapted tests are S08.
