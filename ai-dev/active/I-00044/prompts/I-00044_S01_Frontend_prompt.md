# I-00044_S01_Frontend_prompt

**Work Item**: I-00044 — Code View Chat Panel — Ugly Collapse State and Viewport Drift
**Step**: S01
**Agent**: Frontend

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers spun up by pytest, read-only introspection, `./ai-core.sh` / `make` targets.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No database changes in this step. Do NOT run any alembic commands against port 5433.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00044/I-00044_Issue_Design.md` — full root cause analysis and fix plan
- `dashboard/templates/chat/panel.html` — current collapse toggle (to be redesigned)
- `dashboard/static/chat/panel.js` — `applyCollapsedState()` (to be updated)
- `dashboard/static/chat.css` — chat panel CSS (to be extended)
- `dashboard/templates/project_code.html` — `#page-body` grid (one-class fix)
- `dashboard/CLAUDE.md` — dashboard architecture and conventions

## Output Files

- `dashboard/templates/chat/panel.html` — redesigned collapse toggle (Bug 1 fix)
- `dashboard/static/chat/panel.js` — updated `applyCollapsedState()` (Bug 1 fix)
- `dashboard/static/chat.css` — slide-out tab styles (Bug 1 fix)
- `dashboard/templates/project_code.html` — `lg:grid-rows-[1fr]` added (Bug 2 fix)
- `dashboard/static/styles.css` — rebuilt by `make css`
- `ai-dev/active/I-00044/reports/I-00044_S01_Frontend_report.md` — step report

## Context

This step fixes two UX defects in the code view chat panel (`/project/{id}/code`).

**Bug 1**: When the panel is collapsed, only a bare `<` chevron is visible in a 48 px strip.
There is no label, icon, or tooltip, making the collapsed state unrecognisable.

**Bug 2**: The chat panel shares the page scroll container (`<main class="overflow-y-auto">`).
When a long module is selected, the page scrolls and the chat panel is pushed above the fold.
The user must scroll to reach the composer, then scroll back to read the response.

Read the full root cause analysis in the design document before touching any file.

---

## Requirements

### 1. Fix Bug 2 — Grid row height constraint (one line)

In `dashboard/templates/project_code.html`, find the `#page-body` grid (line 106):

```html
<div id="page-body"
     class="grid gap-0 lg:gap-4 grid-cols-1 lg:grid-cols-[1fr_var(--chat-width)] lg:h-[calc(100vh-12rem)]">
```

Add `lg:grid-rows-[1fr]` to the class list:

```html
<div id="page-body"
     class="grid gap-0 lg:gap-4 grid-cols-1 lg:grid-cols-[1fr_var(--chat-width)]
            lg:h-[calc(100vh-12rem)] lg:grid-rows-[1fr]">
```

**Why**: `grid-template-rows: 1fr` forces the single grid row to consume exactly
`calc(100vh-12rem)`, matching the container height. Grid items are constrained to this
height. Content taller than the row scrolls inside the left column's existing
`overflow-y-auto` wrapper card (in `code_architecture_view.html`) rather than overflowing
into `<main>`. The chat panel no longer scrolls with the page.

Do NOT touch `base.html`, `code_architecture_view.html`, or the `scrollIntoView()` calls
— the `scrollIntoView()` calls will now scroll within the left column's scroll container
(the architecture card has `overflow-y-auto`), which is the correct behavior.

### 2. Fix Bug 1 — Slide-out toggle tab (Option C)

Replace the in-header collapse button with a persistent slide-out toggle tab that always
stays visible on the left edge of `#chat-panel-slot`, providing a clear visual affordance
in both expanded and collapsed states.

#### 2a. Design specification for the toggle tab

**Expanded state**:
- A narrow vertical button/tab is attached to the LEFT edge of `#chat-panel-slot`.
- It shows a minimal collapse icon (e.g. `›` / right-pointing chevron, or a `»` double
  chevron) and has `aria-label="Collapse chat panel (Cmd+\)"`.
- The existing `#chat-collapse-btn` inside the panel header MUST be replaced or repurposed;
  remove the collapse button from the header so the header cleanly shows only the context label.

**Collapsed state** (panel width = `--chat-width` = 48 px):
- The toggle tab expands visually to show:
  1. A chat bubble SVG icon (recognisable symbol)
  2. A rotated "Chat" text label (rotated 90° counter-clockwise, readable bottom-up)
  3. An expand icon (e.g. `‹` / left-pointing chevron, or `«` double chevron)
- `aria-label` changes to `"Expand chat panel (Cmd+\)"`.
- The collapsed strip is no longer a meaningless gray sliver — the toggle tab
  IS the collapsed strip and fills it with a recognisable identity.

**Positioning**:
Place the toggle tab INSIDE `#chat-panel-slot` on its left edge. Two acceptable patterns:

  - **Pattern A** (preferred): The toggle tab is a `<button>` with
    `position: absolute; left: 0; top: 50%; transform: translateY(-50%)` inside
    `#chat-panel-slot` (which must be `position: relative`). The button visually
    "sticks out" to the left of the chat panel content area.

  - **Pattern B**: A dedicated left-edge strip column within `#chat-panel-slot`
    (use a flex row layout inside the slot, left strip + panel content).

Choose whichever pattern produces cleaner HTML and CSS. The requirement is that the
toggle is ALWAYS visible and clearly communicates the chat panel identity when collapsed.

#### 2b. Update `panel.html`

- Remove (or repurpose) `#chat-collapse-btn` from the `<header>` inside `#chat-panel`.
- Add the new toggle tab button element (id: `#chat-toggle-tab`) with the correct
  SVG icon, "Chat" label, and aria-label.
- Keyboard shortcut hint `(Cmd+\)` must remain in the aria-label.
- The toggle tab must be keyboard-accessible (focusable `<button>` with aria-label).
- Keep the existing `#chat-close-btn` (mobile drawer close) and mobile drawer button
  unchanged.

#### 2c. Update `panel.js`

In `applyCollapsedState(collapsed)`:
- Wire the new `#chat-toggle-tab` button to `togglePanel()`.
- When `collapsed=true`: update `aria-label` of `#chat-toggle-tab` to
  `"Expand chat panel (Cmd+\\)"` and set a `data-collapsed="true"` attribute (or CSS class)
  on the tab so CSS can show the expanded tab appearance.
- When `collapsed=false`: update `aria-label` to `"Collapse chat panel (Cmd+\\)"` and
  clear the collapsed state attribute/class on the tab.
- Remove the old `#chat-collapse-btn` references from the JS; update the SVG rotation
  logic if you kept any of it.
- The resize handle and keyboard shortcut handling must remain unchanged.

#### 2d. Update `chat.css`

Add styles for the toggle tab. Use CSS custom properties and the existing `--chat-width`
variable where possible. Key rules:

```css
#chat-toggle-tab {
  /* Positioned on the left edge; always visible */
}
#chat-toggle-tab .chat-tab-label {
  writing-mode: vertical-rl;
  transform: rotate(180deg);   /* bottom-up text */
}
/* Collapsed state: show the full tab identity */
#chat-panel[data-collapsed="true"] + * #chat-toggle-tab .chat-tab-icon,
#chat-panel[data-collapsed="true"] + * #chat-toggle-tab .chat-tab-label {
  display: flex;   /* or block, as appropriate */
}
```

Adapt selectors to match the actual DOM structure you choose. Keep the existing
`min-height: 44px` and `min-width: 44px` touch-target rules on all interactive elements.

### 3. Run `make css`

After all template/JS/CSS edits, run:

```bash
make css
```

This regenerates `dashboard/static/styles.css` from the updated templates and JS files.
The rebuilt file MUST be committed. If `make css` fails, STOP and raise a blocker.

---

## Project Conventions

Read `dashboard/CLAUDE.md`. Key rules for this step:

- Routers are thin — no business logic changes needed here.
- Tailwind CSS is pre-built via `make css` — run it after any template class additions.
- Avoid dynamic class construction that breaks JIT purging.
- Use `lg:` prefix for desktop-only rules (breakpoint ≥ 1024 px).
- Touch targets must be at least 44 × 44 px (existing `tap` class or inline min-h/min-w).
- The chat panel is mobile-aware: the `#chat-drawer-open` FAB and `#chat-drawer-backdrop`
  serve mobile users — do not touch mobile-specific behavior.

## TDD Requirement

This is a template/CSS/JS fix, not a Python backend change. The TDD cycle is:

1. **RED** (before coding): Run `make test-unit` — the tests in S03 will be written to
   fail against the pre-fix code. For S01, confirm those tests would fail.
2. **GREEN**: Implement the fixes so the template structure satisfies the assertions.
3. **REFACTOR**: Clean up any redundant CSS rules.

You do NOT write the tests in this step — that is S03. But you MUST ensure your implementation
produces HTML/CSS that will satisfy the assertions listed in the design document's
"Test to Reproduce" section.

Specifically, after your changes:
- `re.search(r'<div[^>]+id="page-body"[^>]*>', html).group(0)` must contain `lg:grid-rows-[1fr]`
- `"Chat"` must appear in the rendered HTML of `chat/panel.html`
- An `aria-label` attribute referencing "chat" must be present on the toggle element

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order:

1. `make format` — auto-fixes formatting drift (Python files only; JS/HTML not covered)
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors (includes `make lint-js` which checks JS files)
4. `make test-unit` — all unit tests pass

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00044",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/project_code.html",
    "dashboard/templates/chat/panel.html",
    "dashboard/static/chat/panel.js",
    "dashboard/static/chat.css",
    "dashboard/static/styles.css"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
