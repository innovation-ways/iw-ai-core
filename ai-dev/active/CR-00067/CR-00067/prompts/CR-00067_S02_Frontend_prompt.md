# CR-00067_S02_Frontend_prompt

**Work Item**: CR-00067 — AI Assistant — Context Usage Percentage Indicator
**Step**: S02
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step writes no migrations. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00067 --json`
- `ai-dev/active/CR-00067/CR-00067_CR_Design.md` — Design document
- `dashboard/CLAUDE.md` — dashboard conventions
- `ai-dev/work/CR-00067/reports/CR-00067_S01_Backend_report.md` — S01 backend report (confirms `context_pct` is now produced)
- `dashboard/templates/chat_assistant/composer.html` — composer template (target)
- `dashboard/static/chat_assistant/chat.css` — AI Assistant CSS (target)
- `dashboard/static/chat_assistant/chat.js` — AI Assistant JS (target)
- `dashboard/templates/chat_assistant/panel.html` — reference for the amber colour value

## Output Files

- `dashboard/templates/chat_assistant/composer.html` — modified
- `dashboard/static/chat_assistant/chat.css` — modified
- `dashboard/static/chat_assistant/chat.js` — modified
- `tests/dashboard/test_chat_context_pct_template.py` — new template-render test
- `ai-dev/work/CR-00067/reports/CR-00067_S02_Frontend_report.md` — report

## Context

S01 made the backend compute and return `session.context_pct` from
`GET /api/chat/tabs/{id}`. This step renders and styles the indicator.

`chat.js` already has a context-percentage poll, `_startContextPoll()` (around
`chat.js:1917`), which fetches `/api/chat/tabs/{id}` and tries to write
`session.context_pct` into a DOM element with id `chat-assistant-context-pct`.
That element is **never rendered by any template**, so the value is discarded.

**Important — the poll is streaming-scoped, not active-tab-scoped.**
`_startContextPoll()` is invoked only when a response starts streaming
(`_sendPrompt()` at `chat.js:1821`, and the SSE streaming-start handlers around
lines 465 / 483 / 508 / 614 / 664); `_stopContextPoll()` runs on `session.idle`
/ errors / stream teardown. `_activateTab()` (`chat.js:226–279`) does **NOT**
call `_startContextPoll()`. Do **not** try to make the poll run continuously
while idle — context usage only changes while a response is being generated. The
fix for "nothing shows on a freshly activated idle tab" is the immediate fetch
on activation (task 3b below), not a continuous poll.

## Task

### 1. `composer.html` — add the context-% element

In `dashboard/templates/chat_assistant/composer.html`, inside the Send/Abort row
(`<div class="flex items-center gap-2">` that wraps the Clear / Abort / Send
buttons), add a `<span>` **immediately before** the `#chat-assistant-clear`
button so it renders to the **left of "Clear"**:

```html
<span id="chat-assistant-context-pct"
      class="chat-assistant-context-pct hidden"
      aria-label="Context window used"
      title="Context window used"></span>
```

- It MUST start with the `hidden` class (no data until the first fetch resolves).
- It MUST sit before `#chat-assistant-clear` in DOM order.
- Keep it inside the same flex row so it aligns vertically with the buttons.

### 2. `chat.css` — add colour-band styling

Append plain CSS rules to `dashboard/static/chat_assistant/chat.css` (this file
is plain CSS served as-is — no Tailwind recompile needed). Add:

- `.chat-assistant-context-pct` — base style: small font (≈0.7rem), the neutral
  `var(--muted-foreground)` colour, `white-space: nowrap`, vertically centred,
  modest right margin/padding so it does not crowd the Clear button.
- `.chat-assistant-context-pct.is-warn` — amber/warning colour for the 70–89%
  band. Use an amber value consistent with other dashboard warning UI (`#92400e`
  is used for `#chat-assistant-settings-warn` in `chat_assistant/panel.html`).
- `.chat-assistant-context-pct.is-crit` — `var(--destructive)` colour for ≥90%.

The existing `hidden` utility class already exists project-wide (Tailwind) and
sets `display:none` — do not redefine it.

### 3. `chat.js` — colour bands + immediate fetch on tab activation

In `dashboard/static/chat_assistant/chat.js`:

**a. Extract a reusable fetch helper.** The body of the `setInterval` callback in
`_startContextPoll()` currently fetches `/api/chat/tabs/{id}` and updates the
element. Extract that into a named helper, e.g. `_refreshContextPct(tabId)`, that:

- Returns early if `tabId` is falsy.
- Fetches `GET /api/chat/tabs/{encodeURIComponent(tabId)}`.
- Reads `data.session.context_pct`.
- If `context_pct` is a finite number: set the element's `textContent` to
  `Math.round(pct) + '%'`, remove the `hidden` class, and apply the colour band
  (see (c)). Also update the element's `title`/`aria-label` to
  `"Context window used: " + Math.round(pct) + '%'`.
- If `context_pct` is missing / non-numeric: add the `hidden` class back and
  clear `textContent` (do NOT show `0%`).
- Swallows fetch errors silently (matches existing behaviour).

`_startContextPoll()` then just calls `_refreshContextPct(_activeTabId)` inside
its `setInterval`.

**b. Immediate fetch on tab activation.** Add a call to `_refreshContextPct(tabId)`
**inside `_activateTab()`** (`chat.js:226–279`) — a natural spot is near the end,
alongside the `_updateClearButton()` call at line 278. This is the ONLY change
needed for on-activation display; do not add the call to `_startContextPoll()`'s
call sites. After this, switching to or opening a tab shows its context value at
once, without waiting for a message to be sent.

**c. Colour-band logic.** A small helper applied to the element:

- Remove both `is-warn` and `is-crit` classes first.
- `pct >= 90` → add `is-crit`.
- `pct >= 70 && pct < 90` → add `is-warn`.
- `pct < 70` → neither (neutral base style).

**d. Hide on no active tab.** When there is no active tab (e.g. after the last
tab is closed — see `_closeTab` where `_activeTabId` is set to `null`), ensure
the element is returned to the `hidden` state with empty `textContent`. Reuse
`_refreshContextPct` semantics (a falsy `tabId` hides it) or add a tiny
`_hideContextPct()` helper — do not leave a stale percentage on screen.

### 4. `tests/dashboard/` — template-render test

Add `tests/dashboard/test_chat_context_pct_template.py` (FastAPI TestClient,
following the patterns in existing `tests/dashboard/test_chat_*` files). Assert
that the rendered `chat_assistant/composer.html` (or the page including it):

- Contains an element with id `chat-assistant-context-pct`.
- That element appears **before** `#chat-assistant-clear` in document order.
- That element carries the `hidden` class by default.

Read `skills/iw-ai-core-testing/SKILL.md` and `tests/CLAUDE.md` first — note the
rule about importing `dashboard.routers.*` only with a testcontainer `db_session`
in scope.

## Constraints

- Presentation change only. Do NOT modify any application Python (`orch/` or
  `dashboard/routers/`) — the backend `context_pct` computation is delivered by
  S01. The only Python you add is the `tests/dashboard/` test above.
- Do NOT touch the model bar, the Clear button behaviour, or any other composer
  control — those are separate concerns.
- Keep all DOM ids prefixed `chat-assistant-` per the existing convention.
- `Math.round` the percentage — never render a fractional `%`.
- Treat a missing/`null`/`NaN` `context_pct` as "hide", never as `0%`.
- Do NOT duplicate the `fetch` block — the poll and the on-activation call MUST
  share the single `_refreshContextPct` helper.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
uv run pytest tests/dashboard/test_chat_context_pct_template.py
```

Run only the targeted test file above for verification — do NOT run
`make test-integration` / `make test-unit` at large (the full suites are owned
by the S07 / S08 QV gates). `make lint` includes `node --check` on dashboard JS
and `scripts/check_templates.py` on Jinja2. All must pass with no new violations
in changed files.

## Subagent Result Contract

```bash
uv run iw step-done CR-00067 --step S02 \
  --report ai-dev/work/CR-00067/reports/CR-00067_S02_Frontend_report.md
```

```json
{
  "step": "S02",
  "agent": "frontend-impl",
  "work_item": "CR-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat_assistant/composer.html",
    "dashboard/static/chat_assistant/chat.css",
    "dashboard/static/chat_assistant/chat.js",
    "tests/dashboard/test_chat_context_pct_template.py"
  ],
  "tests_passed": true,
  "test_summary": "lint + format-check + dashboard template test passed",
  "blockers": [],
  "notes": ""
}
```
