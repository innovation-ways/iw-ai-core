# I-00046_S01_Frontend_prompt

**Work Item**: I-00046 — Code view chat panel — toggle button clipped and viewport drift on module select
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations are needed for this fix.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00046 --json`
- `ai-dev/active/I-00046/I-00046_Issue_Design.md` — design document (read first)
- `dashboard/templates/project_code.html` — main code view page template
- `dashboard/templates/chat/panel.html` — chat panel template (included by project_code.html)
- `dashboard/static/chat/panel.js` — chat panel JS (read-only; understand before touching templates)
- `dashboard/static/styles.css` — prebuilt Tailwind CSS (check if new classes need `make css`)

## Output Files

- `ai-dev/active/I-00046/reports/I-00046_S01_Frontend_report.md` — step report

## Context

You are fixing a **post-merge regression** in the Code view chat panel introduced by I-00044.

Two bugs are present:

**Bug (a)**: The collapse/expand toggle button (`#chat-toggle-tab`) is invisible and
unclickable. Root cause: `dashboard/templates/project_code.html` line 123 has
`<aside id="chat-panel-slot" class="... lg:overflow-hidden">`. The toggle button is
absolutely positioned at `style="left: -48px"` inside the inner wrapper div in
`panel.html` — it extends 48px to the left of the aside, which `overflow-hidden` clips.

**Bug (c)**: When a long module detail loads, the page grows beyond the viewport and the
chat panel scrolls off-screen. Root cause: `#code-content-root` in `project_code.html`
line 108 has no `min-h-0`, so the CSS Grid item's default `min-height: min-content` lets
the column grow the `1fr` row beyond the viewport height.

**Side issue**: `panel.html` line 9 introduced `<div id="chat-panel-slot">` which
duplicates the ID already on the outer `<aside>`. Remove the duplicate ID.

Read the design document (`I-00046_Issue_Design.md`) for the full root cause and fix
specification before making any changes.

## Requirements

### 1. Fix Bug (a): Remove overflow-hidden from aside, eliminate duplicate ID

**In `dashboard/templates/project_code.html`** (line 123):

Change:
```html
<aside id="chat-panel-slot"
       class="lg:border-l lg:border-border flex flex-col lg:overflow-hidden"
       aria-label="Code module chat">
```

To:
```html
<aside id="chat-panel-slot"
       class="lg:border-l lg:border-border flex flex-col lg:min-h-0"
       aria-label="Code module chat">
```

- Remove `lg:overflow-hidden` — this was clipping the toggle button at `left: -48px`
- Add `lg:min-h-0` — prevents the aside from growing the grid row (also fixes bug c for
  the chat column)
- Do NOT add `relative` to the aside — the inner wrapper div in `panel.html` remains
  the positioning context for the toggle button

**In `dashboard/templates/chat/panel.html`** (line 9):

Change:
```html
<div id="chat-panel-slot" class="relative lg:overflow-visible">
```

To:
```html
<div class="relative flex-1 min-h-0">
```

- Remove `id="chat-panel-slot"` — eliminates the duplicate ID; the outer `<aside>` is
  the sole `chat-panel-slot`
- Remove `lg:overflow-visible` — the aside no longer has `overflow-hidden`, so this is
  redundant and can be dropped
- Add `flex-1` — makes the inner wrapper fill available height in the aside's flex-col
  layout so `#chat-panel`'s `h-full` has a definite height context
- Keep `relative` — the toggle button at `left: -48px; top: 50%` is positioned relative
  to this wrapper

### 2. Fix Bug (c): Add min-h-0 to the content root grid item

**In `dashboard/templates/project_code.html`** (line 108):

The `#code-content-root` div currently has NO class attribute. Change:
```html
<div id="code-content-root"
   data-context-level="architecture"
```

To:
```html
<div id="code-content-root"
   class="lg:min-h-0"
   data-context-level="architecture"
```

- `lg:min-h-0` overrides the CSS Grid default `min-height: min-content` on the left
  column item, forcing it to respect the `1fr` row size — the architecture card's
  `overflow-y-auto h-full` then properly scrolls instead of expanding the page

### 3. Rebuild CSS if needed

After making the template changes, check whether the new Tailwind classes (`flex-1`,
`min-h-0`, `lg:min-h-0`) already exist in `dashboard/static/styles.css`:

```bash
grep -E "min-h-0|flex-1" dashboard/static/styles.css | head -5
```

If any are absent, run:
```bash
make css
```

This regenerates `dashboard/static/styles.css` from all templates and JS files.
The generated file is committed — stage it along with the template changes.

### 4. Scope

**Do NOT**:
- Touch `dashboard/static/chat/panel.js` (the `panelSlot` dead code is pre-existing,
  out of scope)
- Touch any other template or CSS file
- Refactor other parts of the chat panel
- Change the `applyCollapsedState` logic or any JS behaviour

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run in order:

1. **`make format`** — `uv run ruff format --check .` (Python formatting check; these
   are HTML/CSS changes so expect "no changes")
2. **`make typecheck`** — must report zero mypy errors involving touched files
3. **`make lint`** — `make lint-js` runs Node syntax check on dashboard JS; must pass

Fix any issues before reporting completion.

## Test Verification (NON-NEGOTIABLE)

After making changes:

```bash
make test-unit
```

Specifically, all tests in `tests/dashboard/` must pass. The reproduction tests
(`tests/dashboard/test_chat_panel_layout_i00046.py`) are written in S03 — they will not
exist yet, so no false red from them. The existing tests in
`tests/dashboard/test_code_layout_fixes.py` must remain green (do not regress I-00033).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00046",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/project_code.html",
    "dashboard/templates/chat/panel.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Include whether make css was required and what classes were added/verified"
}
```
