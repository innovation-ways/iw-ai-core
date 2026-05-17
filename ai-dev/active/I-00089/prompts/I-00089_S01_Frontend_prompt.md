# I-00089_S01_Frontend_prompt

**Work Item**: I-00089 -- AI Assistant panel — in-header collapse button is unusable in both states
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
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live DB.
This incident leaves migrations unchanged — no alembic work at all.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00089 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/I-00089/I-00089_Issue_Design.md` -- Design document (read first)
- `dashboard/templates/chat_assistant/panel.html` -- the file you will modify (lines 1-13 contain the inline `<style>` block; lines 23-72 contain the header)
- `dashboard/static/chat_assistant/chat.css` -- plain CSS file you may extend with supporting rules
- `dashboard/static/chat_assistant/chat.js` -- read-only reference (lines 953-956 wire the collapse button; do NOT modify)
- `ai-dev/active/I-00089/evidences/pre/` -- four pre-fix evidence files (two screenshots + two YAML DOM snapshots) for visual context
- `CLAUDE.md` and `dashboard/CLAUDE.md` -- project conventions

## Output Files

- `ai-dev/active/I-00089/reports/I-00089_S01_Frontend_report.md` -- Step report

## Context

You are implementing the fix for **I-00089: AI Assistant panel — in-header collapse button is unusable in both states**.

The bug has two parts inside the same component (`dashboard/templates/chat_assistant/panel.html`):

- **Bug A** — When the panel is collapsed (`data-collapsed="true"`), the in-header `<` collapse button is still rendered at the top of the 40 px rail. Its click handler calls `close()`, which is a no-op on an already-closed panel. The button should not be visible while collapsed.
- **Bug B** — When the panel is expanded, the `<` collapse button is rendered as the fourth of four 14 px icons clustered next to a model dropdown inside a 360 px panel. It has no visible weight relative to the toggle icons next to it and no `title` tooltip, so users cannot find a click target to collapse the panel.

Read the design document FIRST (`ai-dev/active/I-00089/I-00089_Issue_Design.md`) — it contains the full RCA, ACs, and the exact attributes/classes the regression tests will assert on.

## Requirements

### 1. Bug A — hide the collapse button while collapsed

In `dashboard/templates/chat_assistant/panel.html`, extend the inline `<style>` block at the top of the file so that `#chat-assistant-collapse-btn` is hidden when `#chat-assistant-panel[data-collapsed="true"]`.

Concretely: add `#chat-assistant-panel[data-collapsed="true"] #chat-assistant-collapse-btn` to the existing `display: none` selector list.

**Why not just hide `#chat-assistant-header`?** Hiding the whole header would also work, but the regression test in S03 will assert on the literal presence of the `#chat-assistant-collapse-btn` selector inside the inline `<style>` block — so extending the selector list (rather than hiding the parent) is the chosen approach and is the simplest change.

### 2. Bug B — give the expanded-header collapse button discoverable visual weight

Modify the `<button id="chat-assistant-collapse-btn">` element in `dashboard/templates/chat_assistant/panel.html` (currently lines 65-71) so that:

1. **Tooltip**: the button has a `title="Collapse panel"` attribute (the regression test asserts that a `title` attribute is present on the opening tag).
2. **Distinguishing class marker**: the button carries an additional class that the new CSS rule(s) use to give it visible weight. Choose one of:
   - Add a custom class `chat-assistant-collapse-btn-distinct` (the regression test recognises this exact class name).
   - OR add Tailwind utility class `border-l` (the regression test also recognises Tailwind `border` / `border-l` classes).
   The test accepts either marker — pick whichever fits cleanly with the rest of the header.
3. **Visible separation from the toggle-icon cluster**: a small left margin (`ml-1` or `ml-2`) or a left border (`border-l border-border pl-1`) so the collapse button reads as a distinct affordance, not "another action icon".
4. **Slightly larger tap target**: change the icon from `w-3.5 h-3.5` to `w-4 h-4` (or keep `w-3.5 h-3.5` and add background/border styling — the goal is "visually distinguishable", not "huge"). A `bg-muted hover:bg-muted-foreground/20` or a thin `border border-border rounded` is sufficient.

Preserve the existing `aria-label="Collapse AI Assistant panel (Ctrl+/)"` exactly — do not change it. Do not change the SVG path. Do not change the `tap inline-flex items-center justify-center p-1 rounded hover:bg-muted` baseline classes — you may ADD classes, not remove them.

### 3. Supporting CSS — append to `dashboard/static/chat_assistant/chat.css`

If you introduce a custom class such as `chat-assistant-collapse-btn-distinct`, append the corresponding CSS rule to `dashboard/static/chat_assistant/chat.css`. Plain CSS appended there is served as-is and does NOT require running `make css`.

Example shape (adapt to whichever marker you chose in step 2):

```css
/* ── Collapse button distinct affordance (I-00089) ── */
#chat-assistant-panel:not([data-collapsed="true"]) #chat-assistant-collapse-btn.chat-assistant-collapse-btn-distinct {
  border: 1px solid var(--border);
  background: var(--muted);
}
#chat-assistant-panel:not([data-collapsed="true"]) #chat-assistant-collapse-btn.chat-assistant-collapse-btn-distinct:hover {
  background: var(--muted-foreground);
  color: var(--background);
}
```

If you instead chose the Tailwind-utility path (`border-l border-border pl-1 ml-1`), no `chat.css` change is required because those classes are already in the prebuilt `styles.css`.

### 4. Do NOT change

- The JS click handler in `dashboard/static/chat_assistant/chat.js:953-956`. `close()` is correct; the bug is purely in the template and CSS.
- The expand rail at lines 75-86 of `panel.html` (the collapsed-state ">" affordance is already correct).
- The Ctrl+/ keyboard shortcut handler at `chat.js:937-942`.
- The nav-bar toggle button (`#chat-assistant-nav-toggle`).
- Any other dashboard template or static asset.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for:

- Dashboard tech stack (FastAPI + Jinja2 + htmx + prebuilt Tailwind).
- Plain-CSS fallback policy when `make css` fails (I-00067) — append rules to `dashboard/static/chat_assistant/chat.css` rather than relying on a Tailwind rebuild.
- The clipboard-helper rule (not relevant here but a marker of project's defensive frontend conventions).

Follow all rules defined there exactly. When in doubt, match existing code in `dashboard/templates/chat_assistant/`.

## TDD Requirement

This step is the implementation step. The Tests step (S03) writes the failing reproduction tests AFTER your implementation lands, and the design document already documents the expected RED→GREEN behaviour.

If you want to verify your implementation locally before reporting completion:

```bash
# Render the panel template via a quick smoke test (read-only check).
uv run python -c "
from dashboard.app import create_app
from starlette.testclient import TestClient
client = TestClient(create_app())
r = client.get('/')
assert r.status_code == 200
assert 'chat-assistant-collapse-btn' in r.text
print('OK')
"
```

You do NOT need to write the formal failing test — that is S03's job.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift on Python; HTML/CSS edits are typically untouched, but run it anyway.
2. **`make typecheck`** — must report zero errors for files you touched (you only touched HTML/CSS, so this is informational).
3. **`make lint`** — must report zero errors. Note: `make lint` includes `scripts/check_templates.py`, which catches Jinja2 mistakes; pay attention if it flags `panel.html`.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

In your Subagent Result Contract, populate the `preflight` object recording the result of each command.

## Test Verification (NON-NEGOTIABLE)

Do **NOT** run the full test suite. Full-suite execution is owned by the QV gate steps (S06..S10).

You may run a targeted dashboard smoke test against your change:

```bash
uv run pytest tests/dashboard/ -k chat_assistant -v --no-cov
```

This is informational — there are no existing tests asserting on the collapse-button affordance until S03 lands.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat_assistant/panel.html",
    "dashboard/static/chat_assistant/chat.css"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "n/a — implementation step; failing tests are written in S03",
  "tdd_red_evidence": "n/a — template + CSS edits only, no production logic; behavioural tests added in S03 (tests-impl)",
  "blockers": [],
  "notes": "Note which class-marker variant you chose (chat-assistant-collapse-btn-distinct vs Tailwind border-l) so S03's regression test recognises it."
}
```
