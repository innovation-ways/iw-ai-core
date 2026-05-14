# F-00083_S04_Frontend_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S04
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — Design (Sections: Frontend Changes, AC1–AC10, Boundary Behavior, Invariants 1, 5, 9, 10)
- `ai-dev/work/F-00083/reports/F-00083_S03_API_report.md` — S03 (endpoint contracts)
- `dashboard/CLAUDE.md` — htmx + EventSource + Tailwind-prebuilt conventions; **the rule about appending plain CSS to styles.css when `make css` reports "Nothing to be done" applies here**.
- `dashboard/templates/chat/panel.html` — **existing right-side Code Q&A chat — DO NOT EDIT.** Use as a structural reference only.
- `dashboard/templates/base.html` — base layout to extend.
- `dashboard/static/clipboard.js` — note the project's "use the shared helper, don't call `navigator.clipboard.writeText(...)` directly" rule.

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_S04_Frontend_report.md`
- `dashboard/templates/chat_assistant/panel.html` (new — left-sidebar slide-out)
- `dashboard/templates/chat_assistant/composer.html` (new)
- `dashboard/templates/chat_assistant/message.html` (new)
- `dashboard/templates/chat_assistant/approval.html` (new)
- `dashboard/templates/chat_assistant/skills_tray.html` (new)
- `dashboard/templates/chat_assistant/history_dropdown.html` (new)
- `dashboard/templates/base.html` (modified — include + Ctrl+/ wiring)
- `dashboard/static/chat_assistant/chat.js` (new)
- `dashboard/static/chat_assistant/chat.css` (new — referenced from styles.css)
- `dashboard/static/styles.css` (modified — `@import` or appended rules per the dashboard/CLAUDE.md rule)
- `.opencode/config.json` (new or modified — add the 6-line `permission` block from R-00074 §5 verbatim)
- 7 page templates modified to call `window.iwChat.setContext({...})`:
  - `dashboard/templates/pages/project/item_detail.html`
  - `dashboard/templates/pages/project/batch_detail.html`
  - `dashboard/templates/research_detail.html`
  - `dashboard/templates/research_library.html`
  - `dashboard/templates/docs_detail.html`
  - `dashboard/templates/docs_library.html`
  - `dashboard/templates/project_code.html`

## Context

You are implementing the entire frontend surface for the Dashboard AI Assistant. **Hard regression-guard rule: zero edits to `dashboard/templates/chat/**` and `dashboard/static/chat/**` (the existing Code Q&A chat).** Verify with `git diff --stat` at the end of the step.

## Requirements

### 1. Panel templates under `dashboard/templates/chat_assistant/`

All DOM ids prefixed with `chat-assistant-`. All Jinja2 templates extend `base.html` ONLY if they are top-level pages; the panel itself is an **include**, not a page.

- `panel.html`: left-sidebar slide-out container. Collapsed by default (`data-collapsed="true"`). Uses Tailwind classes that already exist in the prebuilt `styles.css` (greppable). Width 360px expanded, 40px rail collapsed. Same `<style>` pattern as the existing `chat/panel.html` for collapsed-hide rules. Header includes: title "AI Assistant", model selector (`<select id="chat-assistant-model">`), context % indicator (`<span id="chat-assistant-context-pct">`), "?" tray toggle, history dropdown toggle, "New chat" button, collapse button.
- `composer.html`: form with textarea (`#chat-assistant-input`), slash-menu div (`#chat-assistant-slash-menu`), chip container (`#chat-assistant-chips`), Send + Abort buttons.
- `message.html`: card template with role-specific styling for user / assistant / tool-call / tool-result.
- `approval.html`: modal fragment rendered when a `permission.asked` event arrives. Shows the bash command / file path / agent rationale, Allow + Deny + (optional) "Remember for this session" buttons.
- `skills_tray.html`: collapsible list populated by `GET /api/chat/skills`. Two sections: "Skills" and "Commands". Each entry shows `name` (monospace) + `description` (small text).
- `history_dropdown.html`: dropdown populated by `GET /api/chat/sessions`. Each entry shows session-id + created-at.

### 2. Static JS: `dashboard/static/chat_assistant/chat.js`

Exposes `window.iwChat`:

```javascript
window.iwChat = {
  open()                          { /* slides panel in */ },
  close()                         { /* slides panel out */ },
  toggle()                        { /* flips */ },
  setContext({ type, id, title })  { /* called by per-page scripts; renders chip */ },
  clearContext()                  { /* removes chip */ },
  openWith(prefilledText)         { /* opens + pre-fills composer + focuses */ },
  newSession()                    { /* hits POST /api/chat/sessions */ },
  switchSession(sid)              { /* loads past session by id */ },
};
```

Behaviour:

- **Tab-id generation**: on page load, `sessionStorage.getItem("iw-chat-tab-id")` — if absent, generate via `crypto.randomUUID()` and store. The tab-id is what's used to look up the OpenCode session-id (kept in memory; the backend re-creates as needed).
- **EventSource wiring** when a session is active:
  - `const es = new EventSource("/api/chat/sessions/${sid}/stream");`
  - Track `lastEventId` from each `MessageEvent` so the browser sends `Last-Event-ID` on auto-reconnect.
  - **Client-side message-id dedup**: maintain a `Set<string>` of recent ids; skip duplicates.
  - **Gap detection**: on reconnect, compare the first received id to the last-seen id; if > +1 gap, render a small warning chip "some events may have been missed."
- **Ctrl+/ keybinding**: a single `keydown` listener on `document`; when `e.ctrlKey && e.key === "/"`, call `iwChat.toggle()` and `e.preventDefault()`. **Verify this does NOT collide with the existing Cmd+\ handler** in `dashboard/static/chat/*.js` — different modifier + different key, but visually check.
- **Cookie persistence**: when panel open/closed state changes, write `iw-chat-assistant-open=1|0` cookie (path=/, no expiry override needed).
- **Composer behaviours**:
  - Send button (and `Cmd/Ctrl+Enter`) posts to `/api/chat/sessions/${sid}/prompt` with `{text, model, context}` (where `context` is the active chip if not dismissed).
  - `/` keypress at start of an empty line opens the slash-menu populated from `/api/chat/skills`. Filter as the user types.
  - Abort button posts to `/api/chat/sessions/${sid}/abort`.
  - On streaming, disable Send and enable Abort.
- **Approval modal**: when an SSE event with `event: "permission.asked"` arrives, render `approval.html`'s contents via `fetch("/api/chat/sessions/${sid}/permissions/<rid>", ...)` semantics. Allow + Deny + Remember.
- **Context % polling**: while streaming, poll `GET /api/chat/sessions/${sid}` every 5 s, read the reported context size from the response, update `#chat-assistant-context-pct`. Stop polling within 5 s of receiving `event: "session.idle"`.
- **Model selector**: on panel open (and on every 30 s thereafter for refresh), GET `/api/chat/config`, populate the `<select>` with the model list. Changing the selection updates the per-session default model for the next prompt — does NOT abort or interrupt an in-flight run.

### 3. `dashboard/templates/base.html`

- Include the panel: `{% include "chat_assistant/panel.html" %}` placed in the body — note that `base.html` may already include the existing right-side Code chat at some point. Place the Dashboard AI Assistant include **before** (left side) the existing one to avoid layout collisions.
- Add the chat.js script: `<script src="/static/chat_assistant/chat.js" defer></script>`.
- Add the chat.css link or rely on `styles.css` import — pick one per project convention.
- Add a nav button or icon that calls `window.iwChat.toggle()` — placed at the top-left of the nav, with title "AI Assistant (Ctrl+/)".

### 4. `.opencode/config.json` — the entire safeguard layer

Create or merge into `.opencode/config.json` (at repo root) the following permission block:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "*": "ask",
    "read": "allow",
    "glob": "allow",
    "grep": "allow",
    "webfetch": "allow",
    "websearch": "allow",
    "external_directory": "deny"
  }
}
```

If the file already exists with other keys, merge — preserve every key that's not in the `permission` block. If a `permission` block already exists, **ASK** in your step report whether to overwrite (raise a blocker) — do not silently replace existing rules.

### 5. Per-page `setContext` wiring (7 templates)

In each of the 7 listed templates, add a small `<script>` block (placed before `{% endblock %}` of the page-specific block, or in a `{% block scripts %}` if the base layout has one). Each call uses the page's Jinja2 context variables:

| Template | Call |
|----------|------|
| `pages/project/item_detail.html` | `window.iwChat.setContext({type: "{{ item.type }}", id: "{{ item.id }}", title: {{ item.title | tojson }}});` |
| `pages/project/batch_detail.html` | `window.iwChat.setContext({type: "batch", id: "{{ batch.id }}", title: {{ batch.title | tojson }}});` |
| `research_detail.html` | `window.iwChat.setContext({type: "research", id: "{{ doc.id }}", title: {{ doc.title | tojson }}});` |
| `research_library.html` | `window.iwChat.setContext({type: "research_library", id: "{{ project_id }}", title: "Research library"});` |
| `docs_detail.html` | `window.iwChat.setContext({type: "doc", id: "{{ doc.id }}", title: {{ doc.title | tojson }}});` |
| `docs_library.html` | `window.iwChat.setContext({type: "docs_library", id: "{{ project_id }}", title: "Docs library"});` |
| `project_code.html` | `window.iwChat.setContext({type: "code", id: "{{ project_id }}", title: "Code view"});` |

The Research view's existing "Create new research" button (in `research_library.html`) gets a one-line `onclick` change to call `window.iwChat.openWith("/iw-research ")`.

### 6. CSS

Per `dashboard/CLAUDE.md` rule: prefer appending plain CSS to `dashboard/static/styles.css` (which is served as-is) if `make css` reports "Nothing to be done" or the Tailwind CLI fails. New chat-assistant-specific rules can also live in a separate `chat_assistant/chat.css` linked from `base.html`.

## Project Conventions

Read `dashboard/CLAUDE.md`:
- **NEVER** call `navigator.clipboard.writeText(...)` directly — use `window.iwClipboard.copy(...)`.
- Tailwind prebuilt; avoid dynamic class construction that breaks JIT purging. Stick to classes already in the codebase OR append plain CSS to `styles.css`.
- Fragment templates under `templates/fragments/` MUST NOT extend `base.html`; the chat_assistant component templates are "includes," so they follow the same rule.

## TDD Requirement

This is a Frontend step. There is no Python TDD here, but the prompt is "RED-equivalent" via S05's tests checking the SSE wiring and the S18 browser verification step. Use `tdd_red_evidence: "n/a — frontend step, behavioural tests in S05 (Python) and S18 (browser)"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` (won't touch HTML/JS but won't hurt)
2. `make typecheck` (Python-only; should pass — this step adds no Python)
3. `make lint` — **note: includes `node --check` on dashboard JS and `scripts/check_templates.py` on Jinja2**. Both must pass. Common Jinja2 trap per CLAUDE.md: use `%`-style format-filter calls (`"%dm%02ds"|format(m, s)`), never `{}`-style.

## Test Verification

Targeted: none — this step has no Python tests. Manual smoke test: run `make css` if needed, start the dashboard, visit each of the 7 listed pages, confirm `console.log(window.iwChat)` shows the API. Document the smoke results in the step report.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "frontend-impl",
  "work_item": "F-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat_assistant/panel.html",
    "dashboard/templates/chat_assistant/composer.html",
    "dashboard/templates/chat_assistant/message.html",
    "dashboard/templates/chat_assistant/approval.html",
    "dashboard/templates/chat_assistant/skills_tray.html",
    "dashboard/templates/chat_assistant/history_dropdown.html",
    "dashboard/templates/base.html",
    "dashboard/static/chat_assistant/chat.js",
    "dashboard/static/chat_assistant/chat.css",
    "dashboard/static/styles.css",
    ".opencode/config.json",
    "dashboard/templates/pages/project/item_detail.html",
    "dashboard/templates/pages/project/batch_detail.html",
    "dashboard/templates/research_detail.html",
    "dashboard/templates/research_library.html",
    "dashboard/templates/docs_detail.html",
    "dashboard/templates/docs_library.html",
    "dashboard/templates/project_code.html"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "manual smoke: window.iwChat API present on 7 pages; Ctrl+/ toggles panel; existing Code Q&A chat unaffected (cmd+\\ still works on Code view)",
  "tdd_red_evidence": "n/a — frontend step, behavioural tests in S05 (Python) and S18 (browser)",
  "blockers": [],
  "notes": "Regression-guard verified via `git diff --stat dashboard/templates/chat/ dashboard/static/chat/` — zero lines changed. .opencode/config.json: {created fresh|merged into existing|raised blocker for existing permission block}."
}
```
