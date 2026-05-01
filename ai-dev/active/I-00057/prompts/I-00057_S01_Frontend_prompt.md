# I-00057_S01_Frontend_prompt

**Work Item**: I-00057 -- Chat panel collapse toggle is intrusive and panel starts open
**Step**: S01
**Agent**: Frontend

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00057 --json`.
- `ai-dev/active/I-00057/I-00057_Issue_Design.md`
- `dashboard/templates/chat/panel.html` — current template; see lines 1-82
- `dashboard/static/chat/panel.js` — current JS; see lines 1-130
- `dashboard/CLAUDE.md` — htmx + Tailwind conventions

## Output Files

- `ai-dev/active/I-00057/reports/I-00057_S01_Frontend_report.md`

## Context

Read the design document first. The current chat panel has a floating absolute-positioned toggle tab outside the panel (`#chat-toggle-tab` at `dashboard/templates/chat/panel.html:11-31`), and the panel ships open (`data-collapsed="false"` at line 38). `panel.js` already implements the 48px-rail mechanic via `applyCollapsedState(collapsed)` and persists width in `localStorage["iw_chat_width"]` but does NOT persist the collapsed state.

## Requirements

### 1. Restructure `dashboard/templates/chat/panel.html`

Goal: the chat panel itself contains BOTH the expanded and collapsed presentations. No floating absolute-positioned button outside the panel.

Required structure:

- Top-level wrapper `<div class="relative flex-1 min-h-0">` stays (keeps the existing layout sibling for the mobile drawer button + backdrop at the bottom of the file).
- Inside, `<div id="chat-panel" data-collapsed="true" ...>`.
- Inside `#chat-panel`, two visual modes selected via CSS rules keyed on `[data-collapsed="true"]` vs `:not([data-collapsed="true"])`:
  - **Expanded** (default-not-collapsed): a `<header>` with the title (`Chat — Architecture`) and a small `#chat-collapse-btn` collapse button (chevron pointing right, label "Collapse chat panel (Cmd+\)"). Below the header: messages, scroll-to-bottom, composer (existing markup). The mobile-only `#chat-close-btn` stays inside the header.
  - **Collapsed** (`data-collapsed="true"`): a vertical rail showing a chat icon, a rotated "Chat" label, and an expand button (chevron pointing left → expand). Use a single button `#chat-expand-rail` with the rail content as its children, so clicking anywhere on the rail expands. The expand button's `aria-label` is "Expand chat panel (Cmd+\)".

Critical:

- DELETE the `<button id="chat-toggle-tab" class="absolute top-1/2 -translate-y-1/2 ..." style="left: -48px;">` and all its children. The collapse/expand affordance is now ENTIRELY inside `#chat-panel`.
- The element id `#chat-toggle-tab` must NOT appear anywhere in the new template. The dashboard test asserts the absolute `style="left: -48px;"` pattern is gone.
- KEEP the existing `<style>` block at the top of `panel.html` for shared rules; add new rules to drive the show/hide between the two modes. For example:
  ```css
  #chat-panel[data-collapsed="true"] #chat-context-label,
  #chat-panel[data-collapsed="true"] #chat-messages,
  #chat-panel[data-collapsed="true"] #chat-scroll-to-bottom-wrap,
  #chat-panel[data-collapsed="true"] #chat-composer,
  #chat-panel[data-collapsed="true"] #chat-collapse-btn { display: none; }
  #chat-panel:not([data-collapsed="true"]) #chat-expand-rail { display: none; }
  ```
- KEEP the mobile drawer button (`#chat-drawer-open`) and backdrop (`#chat-drawer-backdrop`) at the bottom of the file unchanged.
- KEEP `#chat-resize-handle`, `#chat-context-label`, `#chat-messages`, `#chat-scroll-anchor`, `#chat-scroll-to-bottom`, `#chat-empty-state`, and the existing `{% include "chat/composer.html" %}` line. Their layout positions inside the expanded view stay the same.
- Set the initial state to `data-collapsed="true"`. The JS will override this on load if a stored preference exists.

The collapsed-rail markup should reuse the existing icons from the old `#chat-toggle-tab`: the `M8 12h12M12 8v8M7 20h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v11a2 2 0 002 2z` chat-bubble path, the rotated "Chat" label (`writing-mode: vertical-rl; transform: rotate(180deg);`), and a chevron. Layout the rail vertically with `flex flex-col items-center justify-center gap-2 p-2 cursor-pointer min-h-[200px]`. The full panel width when collapsed is 48px (driven by the existing `--chat-width: 48px;` rule from `panel.js`), so the rail must not exceed that.

### 2. Update `dashboard/static/chat/panel.js`

Three additions on top of the existing logic:

#### 2a. Wire up the new buttons

Replace `var toggleTab = document.getElementById('chat-toggle-tab');` and its single click listener with:

```js
var collapseBtn = document.getElementById('chat-collapse-btn');
var expandRail = document.getElementById('chat-expand-rail');
if (collapseBtn) collapseBtn.addEventListener('click', togglePanel);
if (expandRail) expandRail.addEventListener('click', togglePanel);
```

Inside `applyCollapsedState(collapsed)`, drop the `toggleTab.setAttribute(...)` lines (the references no longer exist). Keep all the width / `--chat-width` logic intact.

#### 2b. Read collapsed state on load

Near the existing `var chatWidth = parseInt(localStorage.getItem('iw_chat_width') || '400', 10);` block, add:

```js
var storedCollapsed = localStorage.getItem('iw_chat_collapsed');
var initialCollapsed = storedCollapsed === null ? true : storedCollapsed === 'true';
```

Default is `true` when no stored preference exists. Apply on load AFTER the panel element is found:

```js
applyCollapsedState(initialCollapsed);
```

This must happen synchronously on script load — putting it inside a `DOMContentLoaded` listener is fine if the script is loaded with `defer` or at end-of-body.

#### 2c. Persist on every toggle

Wrap or extend `togglePanel`:

```js
function togglePanel() {
  var isCollapsed = panel && panel.dataset.collapsed === 'true';
  var next = !isCollapsed;
  applyCollapsedState(next);
  try {
    localStorage.setItem('iw_chat_collapsed', String(next));
  } catch (_) { /* localStorage unavailable, ignore */ }
}
```

The Cmd+\\ keyboard shortcut path also calls `togglePanel()` so it inherits the persistence automatically — no extra change needed.

### 3. Remove orphan `#chat-toggle-tab` rules from `dashboard/static/chat.css`

Lines 11-27 of `dashboard/static/chat.css` declare visibility rules keyed on `#chat-toggle-tab .chat-tab-icon`, `#chat-toggle-tab .chat-tab-label`, `#chat-toggle-tab .toggle-collapse-icon`, and `#chat-toggle-tab .toggle-expand-icon`. After S01's template change, `#chat-toggle-tab` no longer exists in the DOM, so these rules become dead CSS. Delete the entire block (lines 11-27 inclusive) — keep the surrounding rules (`#chat-messages`, `.tap`, etc.) untouched. If the new collapsed-rail markup needs equivalent visibility rules, prefer adding them to the inline `<style>` block at the top of `panel.html` (where the existing `[data-collapsed]` rules live) rather than spreading them across `chat.css`.

### 4. Run `make css` if you added new Tailwind classes

```bash
make css
```

Stage the regenerated `dashboard/static/styles.css`.

### 5. Do not touch

- `dashboard/templates/chat/composer.html`, `chat/message.html`, or any other chat sub-template.
- The mobile drawer logic (`#chat-drawer-open`, `#chat-drawer-backdrop`, `openDrawer`, `closeDrawer` in panel.js).
- The width-resize logic.
- `dashboard/static/chat/render.js`, `actions.js`, `composer.js`, `stream.js`.

## Project Conventions

Read `dashboard/CLAUDE.md`. Notable:

- Tailwind classes prebuilt — no dynamic class construction.
- Fragments under `templates/fragments/` MUST NOT extend `base.html`; this template (`templates/chat/panel.html`) is included by parent pages — keep it parent-less.
- `node --check` runs in CI on dashboard JS — keep the JS valid Node-parseable.

## TDD Requirement

1. **RED**: S03 will write a server-rendered HTML test asserting `data-collapsed="true"` is in the response and `style="left: -48px;"` is NOT. Run a quick local `curl` against the dev dashboard (or pytest -k) before your edits to confirm the bug — you'll see the inverse on `main`.
2. **GREEN**: Apply the template + JS changes. Re-run; the assertion passes.
3. **REFACTOR**: Tighten CSS; trim dead code referencing `#chat-toggle-tab`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck
make lint        # also runs node --check on dashboard JS
make css         # if you added new Tailwind classes
```

## Test Verification

```bash
make test-unit
```

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Frontend",
  "work_item": "I-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat/panel.html",
    "dashboard/static/chat/panel.js",
    "dashboard/static/chat.css",
    "dashboard/static/styles.css"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
