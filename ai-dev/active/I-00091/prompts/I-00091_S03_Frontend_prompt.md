# I-00091_S03_Frontend_prompt

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy — see `docs/IW_AI_Core_Agent_Constraints.md`. No docker
commands. Testcontainers in pytest fixtures are exempt.

## ⛔ Migrations: agents generate, daemon applies

N/A — this step does not touch alembic.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00091 --json`.
- `ai-dev/active/I-00091/I-00091_Issue_Design.md` — design document
- `ai-dev/active/I-00091/I-00091_Functional.md` — functional design
- `ai-dev/active/I-00091/reports/I-00091_S01_Backend_report.md` — what
  S01 changed (especially the `.source` back-compat decision)
- `orch/auto_merge_aggregator.py` — read the new
  `ResolvedConfig.phase_source` / `runtime_source` fields S01 added
- `dashboard/templates/fragments/auto_merge_settings.html`
- `dashboard/templates/fragments/auto_merge_status_chip.html`
- `dashboard/routers/auto_merge_ui.py`
- `dashboard/static/styles.css`
- `dashboard/CLAUDE.md` — htmx / fragment / Tailwind rules

## Output Files

- `ai-dev/active/I-00091/reports/I-00091_S03_Frontend_report.md`

## Context

S01 added `phase_source` and `runtime_source` to `ResolvedConfig`. Your
job is to make the two templates and the FastAPI route consume those
fields correctly so:

1. Each settings dropdown is `selected` against the DB-stored value when
   its axis is overridden (regardless of the other axis).
2. Clicking Save swaps the **settings form** in place (not just the
   chip) — and the chip too, via `hx-swap-oob`.
3. The user gets a visible "Saving…" indicator while in flight and a
   transient "Saved" hint after success.
4. The status chip's "Source" line is honest about which axis is
   overridden.

Read the design's **Acceptance Criteria** section in full before
touching code — AC1..AC4 are mandatory checks.

## Requirements

### 1. Per-axis selected logic in `auto_merge_settings.html`

Replace the single `{% set _is_override = … %}` with two independent
booleans:

```jinja
{% set _phase_override = status.config.phase_source == 'per_project_db' %}
{% set _runtime_override = status.config.runtime_source == 'per_project_db' %}
```

Update the Phase dropdown so:
- `Use global default` is `selected` iff `_phase_override` is False.
- `0 — disabled` / `1 — dry-run` are `selected` iff `_phase_override`
  is True AND `status.config.phase` matches the option value.

Update the Runtime dropdown the same way using `_runtime_override`.

Update the footer block:
- Render `Last changed: {{ status.deployed_since | localdt(...) }} by dashboard`
  iff `_phase_override OR _runtime_override`.
- Render `Using global default` iff neither is true.

### 2. Wrap the settings section in a stable id and target it for swap

The current outer `<section class="auto-merge-settings ...">` has no
`id`. Give it `id="auto-merge-settings"`.

Change the form's htmx attributes:

```jinja
<form hx-post="/project/{{ current_project.id }}/auto-merge/config"
      hx-ext="json-enc"
      hx-target="#auto-merge-settings"
      hx-swap="outerHTML"
      hx-indicator="#auto-merge-saving"
      class="space-y-4">
```

Add an indicator element (kept simple — htmx's `htmx-request` class
auto-toggles visibility):

```jinja
<span id="auto-merge-saving" class="auto-merge-save-indicator htmx-indicator">Saving…</span>
```

After a successful response (see Requirement 4), the swapped-in
fragment can carry a short-lived "Saved" badge that fades on its own —
keep it CSS-only, no new JS modules.

### 3. Status chip uses per-axis sources

In `auto_merge_status_chip.html`, replace the single-string
`Source: {{ status.config.source }}{% if status.config.source == 'per_project_db' %} (Per-project override){% endif %}`
with a per-axis description, e.g.:

```jinja
<p class="mt-2 text-xs text-muted-foreground">
  Phase source: {{ status.config.phase_source }}{% if status.config.phase_source == 'per_project_db' %} (Per-project override){% endif %}
  · Runtime source: {{ status.config.runtime_source }}{% if status.config.runtime_source == 'per_project_db' %} (Per-project override){% endif %}
</p>
```

If S01 kept `.source` as a back-compat property, you may either leave
other (non-auto-merge-page) consumers untouched or migrate them — grep
first:

```bash
grep -rn "status\.config\.source\|config\.source" dashboard/templates orch
```

Update each consumer to use the new per-axis fields where the
distinction matters; preserve behaviour where it doesn't.

### 4. Combined fragment response in `auto_merge_set_config`

In `dashboard/routers/auto_merge_ui.py`, the non-JSON branch
(currently lines 377-382) returns only the status-chip fragment.
Change it to return a combined HTML response containing:

1. The full re-rendered `auto_merge_settings.html` fragment as the
   primary response body (this swaps into `#auto-merge-settings`).
2. The `auto_merge_status_chip.html` fragment marked with
   `hx-swap-oob="outerHTML:#auto-merge-status-chip"` so the chip is
   also updated.

You have two equivalent implementation choices — pick whichever fits
the existing helper pattern in this file:

**Option A — render two templates, concatenate**:

```python
status = _load_status(db, project_id)
rows = db.scalars(select(AgentRuntimeOption)...).all()  # mirror the GET handler
runtime_options = ...                                    # same shape

settings_html = templates.TemplateResponse(...,
    "fragments/auto_merge_settings.html",
    {"request": request, "current_project": project, "status": status,
     "runtime_options": runtime_options}).body.decode()
chip_html = templates.TemplateResponse(...,
    "fragments/auto_merge_status_chip.html",
    {"request": request, "status": status, "project_id": project_id, "oob": True}).body.decode()
return HTMLResponse(settings_html + chip_html)
```

In `auto_merge_status_chip.html`, wrap the **rich** chip's outer
`<section>` so that when `oob` is True the element gets
`hx-swap-oob="outerHTML"` on the same `id="auto-merge-status-chip"`
element. (Htmx finds the OOB element by id, so the id must remain.)

**Option B — combined fragment template**: create no new template;
inline the OOB marker in a wrapper string returned by a single
`_render_settings_with_oob_chip(...)` helper. Acceptable as long as
the OOB element retains `id="auto-merge-status-chip"`.

Reuse the existing `_get_project_or_404`, `_load_status`, and
`_render_fragment` helpers; do not duplicate logic.

### 5. CSS: small "Saved" / "Saving…" indicator styling

Append to `dashboard/static/styles.css` (plain CSS — per CLAUDE.md, `make
css` is currently broken in worktrees, so plain rules at the end of the
file are correct):

```css
.auto-merge-save-indicator{display:none;margin-left:.5rem;font-size:.75rem;color:var(--muted-foreground)}
.auto-merge-save-indicator.htmx-request,.htmx-request .auto-merge-save-indicator{display:inline}
.auto-merge-save-indicator--saved{display:inline;color:var(--primary);animation:auto-merge-fade 2s ease-out forwards}
@keyframes auto-merge-fade{0%{opacity:1}80%{opacity:1}100%{opacity:0}}
```

If you decide to render a transient "Saved" badge in the swapped-in
fragment (Requirement 2), emit
`<span class="auto-merge-save-indicator auto-merge-save-indicator--saved">Saved</span>`
inside the form section conditionally — guard it with a
`{% if just_saved %}` flag passed from the route's response context.

### 6. Do NOT introduce new JavaScript modules

The existing `hx-indicator` + CSS animation pattern is enough. Do not
add a new `<script>` block; do not add a new file under
`dashboard/static/scripts/`. See `dashboard/CLAUDE.md` for the no-new-JS
preference.

### 7. JSON branch unchanged

The `_accepts_json(request)` branch returning JSON
(`{"ok": True, ...}`) must continue to work as-is for non-htmx callers
(curl, integration tests). Verify it still returns the same payload
shape.

## Project Conventions

- `dashboard/CLAUDE.md` — fragment templates do NOT extend `base.html`;
  htmx posts return HTML fragments; **append plain CSS rules** to
  `styles.css` because `make css` is broken in worktrees (CLAUDE.md
  global rule).
- Jinja2 `format` filter must stay `%`-style: `"%dm%02ds"|format(m, s)`
  not `"{}m{}s"|format(m, s)` (CLAUDE.md → I-00075). You probably don't
  touch any such call in this step, but be aware.
- Use the shared `window.iwClipboard.copy(...)` helper for any copy
  button (you won't add one in this step).
- No `navigator.clipboard.writeText(...)` direct calls.

## TDD Requirement

This is a Frontend step; the behavioural tests live in S05. Your
RED-evidence obligation is satisfied by the targeted dashboard tests
S05 will run. For your own pre-completion check, run the **existing**
dashboard tests to make sure you haven't broken the current passing
tests:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

Some may legitimately need to be updated for the new
`#auto-merge-settings` id / new chip line — update them only if the
existing assertion is too coupled to the old DOM shape (e.g. asserts
on a literal phrase you renamed). Document each such test edit in your
report's `notes`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint` — note that `scripts/check_templates.py` runs as part of
   `make lint` and validates Jinja2 `format` calls. If it flags a NEW
   template you touched, fix it.

If `make css` is invoked anywhere, expect it to fail
("Nothing to be done" or `postcss-selector-parser` missing) — that is
the known I-00067 state. Plain CSS rules in `styles.css` are served
as-is.

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

Do **NOT** run `make test-unit` or `make test-integration`.

## Migration Verification

N/A.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "I-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/auto_merge_settings.html",
    "dashboard/templates/fragments/auto_merge_status_chip.html",
    "dashboard/routers/auto_merge_ui.py",
    "dashboard/static/styles.css"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — frontend/template + route response shape; behavioural tests written in S05",
  "blockers": [],
  "notes": "Combined-fragment approach used: A|B. List of existing dashboard tests updated for new id/chip line, with one-line justification each."
}
```
