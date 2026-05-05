# I-00065_S01_Frontend_prompt

**Work Item**: I-00065 -- Code-view chat panel — "+ New" visible when collapsed and duplicates greeting
**Step**: S01
**Agent**: frontend-impl

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
infrastructure containers are outside your scope.

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does not require any database migration. Do NOT run
`alembic upgrade`, `alembic downgrade`, `alembic stamp`, or any other
state-changing alembic command.

Allowed for agents (read-only): `alembic history / current / show`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00065 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/I-00065/I-00065_Issue_Design.md` -- Design document
- `dashboard/templates/chat/panel.html` -- file to modify (Bug 1)
- `dashboard/static/chat/panel.js` -- file to modify (Bug 2)
- `dashboard/CLAUDE.md` -- dashboard layer conventions

## Output Files

- `ai-dev/active/I-00065/reports/I-00065_S01_Frontend_report.md` -- Step report

## Context

You are fixing two small frontend defects in the chat panel of the project Code view. Read `ai-dev/active/I-00065/I-00065_Issue_Design.md` first to understand both bugs, then `dashboard/CLAUDE.md` for the dashboard layer's conventions (FastAPI + Jinja2 + htmx + prebuilt Tailwind, no JS framework).

## Requirements

### 1. Bug 1 — Hide "+ New" button when chat panel is collapsed

**File**: `dashboard/templates/chat/panel.html` (lines 1-8)

The `<style>` block at the top of the file lists every header element that should be hidden when `#chat-panel` has `data-collapsed="true"`. The list currently is:

```css
#chat-panel[data-collapsed="true"] #chat-context-label,
#chat-panel[data-collapsed="true"] #chat-messages,
#chat-panel[data-collapsed="true"] #chat-scroll-to-bottom-wrap,
#chat-panel[data-collapsed="true"] #chat-composer,
#chat-panel[data-collapsed="true"] #chat-collapse-btn { display: none; }
```

`#chat-new-btn` (defined at lines 24-31 of the same template) is missing. Add a `#chat-panel[data-collapsed="true"] #chat-new-btn,` clause to this selector list so the button is hidden in the collapsed rail. Place it next to `#chat-collapse-btn` to keep header-button entries grouped.

Do NOT add any new Tailwind utility class. Do NOT modify any other CSS. Do NOT touch the rest of the template.

### 2. Bug 2 — `showEmptyState` must not duplicate the greeting

**File**: `dashboard/static/chat/panel.js` (lines 175-189, function `showEmptyState`)

The current implementation removes all `<article>` chat bubbles and then unconditionally creates a fresh `<div id="chat-empty-state">` and inserts it before `#chat-scroll-anchor`. It never removes any pre-existing `#chat-empty-state`, so each call to `showEmptyState` (triggered by clicking "+ New") leaves the previous greeting in the DOM and inserts another sibling with the same `id`.

Fix: at the top of `showEmptyState` (after the `messages` null-check), look up any existing `#chat-empty-state` element via `document.getElementById('chat-empty-state')` and call `.remove()` on it before the rest of the function runs. The rest of the function is unchanged.

Reference fix shape (do not copy verbatim — match existing code style in the file: `var`, semicolons, no `const`/`let`):

```javascript
function showEmptyState() {
  var messages = document.getElementById('chat-messages');
  if (!messages) return;
  // Remove any pre-existing empty-state block so clicking "+ New"
  // multiple times never stacks duplicate greetings.
  var existingEmpty = document.getElementById('chat-empty-state');
  if (existingEmpty) existingEmpty.remove();
  // Remove all article bubbles but keep the scroll anchor
  var articles = messages.querySelectorAll('article');
  articles.forEach(function (a) { a.remove(); });
  var anchor = document.getElementById('chat-scroll-anchor');
  // ... rest unchanged ...
}
```

Do NOT change the greeting copy. Do NOT change the class names. Do NOT change the insertion point. Do NOT refactor the function. Do NOT introduce a Jinja2 macro to share the markup with `panel.html`. The fix is two new lines.

### 3. Hard scope limits

This incident's `scope.allowed_paths` allows you to touch ONLY these files:

- `dashboard/templates/chat/panel.html`
- `dashboard/static/chat/panel.js`
- `tests/dashboard/test_chat_panel_template.py` (S03 will create)
- `tests/dashboard/test_chat_panel_empty_state.py` (S03 will create)

Do NOT touch any other file. Do NOT run `make css` (no new Tailwind classes are introduced; `dashboard/static/styles.css` would only need regeneration if you added a new utility class to a template). Do NOT touch any other chat template or JS module.

## Project Conventions

Read `dashboard/CLAUDE.md` for:

- Dashboard stack (FastAPI + Jinja2 + htmx + prebuilt Tailwind)
- Why `dashboard/static/**/*.js` is plain JS (no bundler), and why `make lint` runs `node --check` on it — your edit must keep the file syntactically valid as plain ES5/ES2015.
- The "no docker, no migrations from dashboard" rules.

Read the project root `CLAUDE.md` for the broader hard rules.

Match the existing code style of `panel.js`: `var` declarations, semicolons after every statement, no arrow functions in places where the file uses `function`.

## TDD Requirement

S03 (Tests) writes the reproduction and regression tests. For your step (S01) you should:

1. **RED phase**: After the design doc is read, manually verify the bugs would be caught by the tests described in the design's "Test to Reproduce" section (you do NOT need to write the tests yourself — that is S03's job).
2. **GREEN phase**: Apply the two-file fix described above.
3. **REFACTOR phase**: There is nothing to refactor; the fix is minimal by design.

If for any reason S03 has already run before you (out-of-order execution), run those tests once after your fix — they must pass.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift. (Will not touch `panel.html` or `panel.js` unless they have unrelated drift; if so, report.)
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors. Note: `make lint` includes `node --check` on every `dashboard/static/**/*.js` file, so any JS syntax error in your edit will be caught here.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-frontend` (alias of `make test-dashboard`) to ensure no dashboard test regressed.
2. Do **NOT** report `tests_passed: true` unless ALL dashboard tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00065",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat/panel.html",
    "dashboard/static/chat/panel.js"
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
