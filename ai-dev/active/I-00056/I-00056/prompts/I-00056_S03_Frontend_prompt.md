# I-00056_S03_Frontend_prompt

**Work Item**: I-00056 -- Code page lands on a wall of prose — components hidden, hard to scan
**Step**: S03
**Agent**: Frontend

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00056 --json`.
- `ai-dev/active/I-00056/I-00056_Issue_Design.md`
- `ai-dev/active/I-00056/reports/I-00056_S01_Backend_report.md`
- `dashboard/templates/fragments/code_module_cards.html` — the existing cards template (reference for htmx targets and styling)
- `dashboard/templates/fragments/code_architecture_view.html` — must be edited to insert chip strip
- `dashboard/CLAUDE.md` — htmx + Tailwind conventions

## Output Files

- `ai-dev/active/I-00056/reports/I-00056_S03_Frontend_report.md`
- `dashboard/templates/fragments/code_module_chips.html` (new)
- Edits to `dashboard/templates/fragments/code_architecture_view.html`
- `dashboard/static/styles.css` may regenerate via `make css`

## Context

Read the design document first. Read `dashboard/CLAUDE.md` (Tailwind prebuilt, htmx fragments, no dynamic class construction).

S01 added a backend endpoint `GET /api/projects/{id}/code/modules/chips` that renders the new `fragments/code_module_chips.html` template. Your job:

1. Author that template.
2. Insert the chip strip ABOVE the prose body in `code_architecture_view.html` so the chip strip is the first interactive surface on the Code page.
3. Run `make css` so any new Tailwind classes you introduce are JIT-purged into `dashboard/static/styles.css`.

## Requirements

### 1. New fragment: `dashboard/templates/fragments/code_module_chips.html`

Render a single horizontal row of chips. Each chip shows the module name (bold) and the path (monospace, muted). The chip is a link/htmx trigger to load module detail in `#code-detail-panel`.

Constraints:

- ID on the wrapper: `id="code-component-chips"` — the dashboard tests assert this exact ID.
- Empty-state: when `modules` is empty, render nothing (or a tiny muted "no components detected" — your call, but keep total height ≤ 1 row).
- Chip is a `<a>` with both `href` (server-side fallback) AND `hx-get` to `/api/projects/{{ project_id }}/code/modules/{{ m.slug }}`, `hx-target="#code-detail-panel"`, `hx-swap="innerHTML"` — match the cards template's behavior so chip and card click do exactly the same thing.
- Use Tailwind utility classes (no inline `style=`). Recommended shape:
  - Wrapper: `flex flex-wrap gap-2 px-4 py-3 border-b border-border bg-muted/30`
  - Chip: `inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-card border border-border hover:border-primary hover:text-primary transition-colors`
  - Path: `font-mono text-[11px] text-muted-foreground`
- Accessible: chip's accessible name should include both the module name AND the path. Use `aria-label` if needed.

Example shape (adapt to repo conventions; don't paste verbatim if the repo style differs):

```html
{% if modules %}
<div id="code-component-chips" class="flex flex-wrap gap-2 px-4 py-3 border-b border-border bg-muted/30" aria-label="Code components">
  {% for m in modules %}
  <a href="/api/projects/{{ project_id }}/code/modules/{{ m.slug }}"
     hx-get="/api/projects/{{ project_id }}/code/modules/{{ m.slug }}"
     hx-target="#code-detail-panel"
     hx-swap="innerHTML"
     aria-label="{{ m.name }} ({{ m.path }})"
     class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-card border border-border hover:border-primary hover:text-primary transition-colors">
    <span class="font-medium">{{ m.name }}</span>
    <code class="font-mono text-[11px] text-muted-foreground">{{ m.path }}</code>
  </a>
  {% endfor %}
</div>
{% endif %}
```

Adjust class names if the existing card template uses a different design-system token (e.g. `text-foreground` vs `text-primary`).

### 2. Insert chip strip into `code_architecture_view.html`

Open `dashboard/templates/fragments/code_architecture_view.html`. The current top of the panel is:

```html
<div class="bg-card border border-border rounded-lg h-full overflow-y-auto">
  <div class="px-4 py-2 border-b border-border">
    <h2 class="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Architecture</h2>
  </div>
  <div class="p-8">
    <div class="prose-doc max-w-4xl mx-auto">
      ...
      {{ content_html | safe }}
```

Add an htmx-loaded chip strip immediately after the "Architecture" header and BEFORE the `<div class="p-8">` prose container:

```html
<div id="code-component-chips-slot"
     hx-get="/api/projects/{{ project_id }}/code/modules/chips"
     hx-trigger="load"
     hx-swap="innerHTML"></div>
```

Rationale: the strip loads via htmx (same pattern as the existing `#code-components-section` cards), so the architecture page server-renders fast and the chip strip arrives shortly after.

The endpoint returns the actual `<div id="code-component-chips" ...>...` element (from your new fragment), which replaces the slot's children. Tests assert that `id="code-component-chips"` appears BEFORE `class="prose-doc` in the response HTML — but note that the chip strip arrives via a separate htmx request, so the **dashboard test asserts on the slot order** (`code-component-chips-slot` precedes `prose-doc`), not on the chips themselves. Coordinate with S05 — the test file `tests/dashboard/test_code_module_chips.py` should assert on the slot id (`code-component-chips-slot`) for the page-level test, AND a separate test should hit the chips endpoint and assert it returns `id="code-component-chips"` with a `<a>` per parsed module.

### 3. Run `make css`

```bash
make css
```

This regenerates `dashboard/static/styles.css` with any new Tailwind classes you introduced. Stage the regenerated file in your commit. CI (`make lint`) will run `node --check` on JS but won't rebuild CSS — your responsibility.

### 4. Do not touch

- `dashboard/templates/fragments/code_module_cards.html` — leave the cards rendering as-is.
- The components cards section (`#code-components-section`) — it stays where it is, BELOW the prose. The chip strip is the new top-of-page surface; cards remain the detailed grid.
- Any chat-related template — that's I-00057's territory.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- No `docker compose up` commands from dashboard code or tests.
- Tailwind classes prebuilt — no dynamic class construction that breaks JIT purging (e.g. `class="text-{{ color }}-500"` is forbidden; build the full class statically).
- Fragments under `templates/fragments/` MUST NOT extend `base.html`.
- htmx POSTs/GETs return HTML fragments — no JSON.

## TDD Requirement

1. **RED**: S05 will write a dashboard test asserting `id="code-component-chips-slot"` appears in the rendered Code page response BEFORE `class="prose-doc`. Run a quick local check: spin up the dashboard and visit the Code page; observe the chip strip appears above the prose.
2. **GREEN**: Insert the slot + create the fragment.
3. **REFACTOR**: Tighten Tailwind classes; ensure no class is dynamically composed.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck
make lint
make css        # if you added new Tailwind classes
```

## Test Verification

```bash
make test-unit
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Frontend",
  "work_item": "I-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/code_module_chips.html",
    "dashboard/templates/fragments/code_architecture_view.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
