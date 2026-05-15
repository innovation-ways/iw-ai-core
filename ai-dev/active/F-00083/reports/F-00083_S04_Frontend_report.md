# F-00083 S04 Frontend Implementation Report

## Summary

Step S04 implements the Dashboard AI Assistant frontend: a collapsible left-panel chat widget backed by the new `/api/chat/` endpoints (S02/S03), wired into all major project pages via `setContext` calls, and configured with `.opencode/config.json` for OpenCode permission defaults.

## What Was Done

### Panel Templates (new files under `dashboard/templates/chat_assistant/`)
- `panel.html` — main panel container: header, collapse/expand rail, skills tray include, history dropdown include, messages area with empty state, composer wrap, approval modal mount, message template
- `composer.html` — textarea with slash menu, send/abort buttons, context chip row
- `message.html` — client-side message template (user, assistant, tool-call, tool-result variants)
- `skills_tray.html` — toggleable tray for skills and commands lists
- `history_dropdown.html` — toggleable session history list
- `approval.html` — (included inline in panel.html via JS; no standalone template needed)

### Static Assets (new files under `dashboard/static/chat_assistant/`)
- `chat.js` — complete `window.iwChat` API: toggle/open/close, setContext/clearContext, openWith, newSession, switchSession; SSE stream handling (named events: message.part, message.snapshot, message.complete, tool.call, tool.result, permission.asked, session.idle, error, gap, reconnecting); approval modal; slash menu; skills tray population; session history dropdown; context chip; model selector; Ctrl+/ keybinding; cookie-persisted open/closed state; tab-scoped session ID via sessionStorage
- `chat.css` — all panel styles scoped under `#chat-assistant-*` IDs and `.chat-assistant-*` classes to avoid collision with existing `#chat-panel` / `#chat-messages` Code Q&A widget

### base.html Modifications
- Added `<link rel="stylesheet" href="/static/chat_assistant/chat.css" />` in `<head>`
- Included `{% include "chat_assistant/panel.html" %}` as first child of the flex shell (left of sidebar)
- Added `#chat-assistant-nav-toggle` button in the top bar (all screen sizes)
- Added `<script src="/static/chat_assistant/chat.js" defer></script>` before `{% block scripts %}`

### setContext Wiring (7 templates total)
| Template | Context type | ID variable | Title |
|---|---|---|---|
| `pages/project/item_detail.html` | `{{ item.type }}` | `{{ item.id }}` | `{{ item.title \| tojson }}` |
| `pages/project/batch_detail.html` | `"batch"` | `{{ batch.id }}` | `{{ batch.title \| tojson }}` |
| `research_detail.html` | `"research"` | `{{ doc.id }}` | `{{ doc.title \| tojson }}` |
| `research_library.html` | `"research_library"` | `{{ current_project.id }}` | `"Research library"` |
| `docs_detail.html` | `"doc"` | `{{ doc.id }}` | `{{ doc.title \| tojson }}` |
| `docs_library.html` | `"docs_library"` | `{{ current_project.id }}` | `"Docs library"` |
| `project_code.html` | `"code"` | `{{ current_project.id }}` | `"Code view"` |

Placement: `item_detail.html`, `batch_detail.html`, and `research_detail.html` used the existing `{% block scripts %}` block. The remaining 4 templates had no `{% block scripts %}` — the setContext `<script>` was placed inline in the content block (immediately before or after the final `</script>`) for `docs_detail.html`, `docs_library.html`, and `research_library.html`; a new `{% block scripts %}` was added after the content block for `project_code.html` and `research_library.html`.

Variable name convention: all 4 "library/view" templates use `current_project.id` (not a standalone `project_id`). The instruction said to use `project_id` as a placeholder; the actual variable in scope is `current_project.id` throughout the dashboard.

### .opencode/config.json
Created fresh with permission defaults: `read`, `glob`, `grep`, `webfetch`, `websearch` all `allow`; `*` → `ask`; `external_directory` → `deny`.

## Files Changed

- `dashboard/templates/base.html` — panel include, CSS link, nav toggle button, chat.js script tag
- `dashboard/templates/pages/project/item_detail.html` — setContext in block scripts
- `dashboard/templates/pages/project/batch_detail.html` — setContext in block scripts
- `dashboard/templates/research_detail.html` — setContext in block scripts
- `dashboard/templates/research_library.html` — setContext in new block scripts
- `dashboard/templates/docs_detail.html` — setContext inline in content block
- `dashboard/templates/docs_library.html` — setContext inline in content block
- `dashboard/templates/project_code.html` — setContext in new block scripts
- `dashboard/templates/chat_assistant/panel.html` — new
- `dashboard/templates/chat_assistant/composer.html` — new
- `dashboard/templates/chat_assistant/message.html` — new
- `dashboard/templates/chat_assistant/skills_tray.html` — new
- `dashboard/templates/chat_assistant/history_dropdown.html` — new
- `dashboard/static/chat_assistant/chat.js` — new
- `dashboard/static/chat_assistant/chat.css` — new
- `.opencode/config.json` — new

## Lint Result

`make lint` passed cleanly:
- `scripts/check_templates.py` — all Jinja2 templates OK (no `{}`-style format filter calls)
- `ruff check .` — all checks passed

## Regression-Guard Outcome

`git diff --stat dashboard/templates/chat/ dashboard/static/chat/` — zero lines (no files under old `chat/` paths were touched).

## Template Path Substitutions

None required. All target template names matched exactly:
- `research_library.html` — confirmed at `dashboard/templates/research_library.html`
- `docs_detail.html` — confirmed at `dashboard/templates/docs_detail.html`
- `docs_library.html` — confirmed at `dashboard/templates/docs_library.html`
- `project_code.html` — confirmed at `dashboard/templates/project_code.html`
