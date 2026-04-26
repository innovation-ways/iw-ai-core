# I-00040 S03 — Frontend: stale-DB banner in dashboard base template

You are executing step **S03** for work item **I-00040** ("Alembic-version guard at daemon/dashboard/launch boundaries").

## ⛔ Docker / Migrations off-limits

Standard rules.

## Context

S01 added a backend middleware that sets `request.state.alembic_guard_status`
(a `GuardStatus` dataclass) on every request, plus an
`is_db_stale(request)` helper. Your job is to surface that to the user
with a banner and to disable write-action buttons when the DB is stale.

Read `ai-dev/active/I-00040/I-00040_Issue_Design.md` (Description, Steps
to Reproduce, Acceptance Criteria), and `ai-dev/active/I-00040/reports/I-00040_S01_Backend_report.md` for the helper API.

## Project Context

Read `dashboard/CLAUDE.md` for template conventions, htmx patterns, and
where to put fragments.

## Requirements

### R1 — Global banner in `dashboard/templates/base.html`

Render a banner at the **top of the page**, above the existing nav, when
`is_db_stale(request)` is true. Markup contract:

```html
<div role="alert"
     aria-live="polite"
     class="bg-red-700 text-white px-4 py-3 text-sm flex items-center justify-between"
     id="stale-db-banner">
  <div>
    <strong>Orch DB schema is behind head</strong> —
    current_rev=<code>{{ status.current_rev or 'EMPTY' }}</code>
    head_rev=<code>{{ status.head_rev }}</code>.
    Run <code>make db-migrate</code> to fix.
    Write actions are disabled until then.
  </div>
  <div>
    {{ status.pending|length }} pending revision{{ '' if status.pending|length == 1 else 's' }}
  </div>
</div>
```

The banner MUST:

- Use `role="alert"` for assistive tech.
- Be visually distinct (red background, white text). Use existing
  Tailwind utility classes from `dashboard/static/styles.css` — do
  NOT introduce inline styles.
- Be the FIRST child of `<body>`, BEFORE the nav, so it stays visible
  when scrolling htmx-swapped fragments.
- Contain both revisions and the literal string `make db-migrate`
  (these strings are tested in S05/S13 — do NOT change the wording).
- Contain NO emoji.
- Be skipped entirely (rendered as no markup at all) when the DB is at
  head. Do NOT render an empty `<div>` shell.

### R2 — Disable write-action buttons site-wide

For every button or form element that triggers a state-mutating action
(batch approve, item launch, item approve, batch resume, daemon
start/stop, etc.), conditionally add `disabled` and a `title` tooltip
when `is_db_stale(request)` is true.

Strategy: introduce a Jinja macro in
`dashboard/templates/macros/db_guard.html`:

```jinja
{% macro write_button_attrs(request) -%}
{% if is_db_stale(request) -%}
disabled aria-disabled="true" title="Orch DB schema mismatch — run 'make db-migrate' to fix."
{%- endif %}
{%- endmacro %}
```

Then update each affected template to invoke the macro. Use `Grep` to
find write-action buttons:

```bash
grep -rnE 'hx-post|hx-put|hx-delete|hx-patch|type="submit"' dashboard/templates/
```

Touch each match where the action mutates orch state. Read-only forms
(filters, search) are exempt.

### R3 — Expose `is_db_stale` to Jinja context

Register `is_db_stale` as a Jinja global (or via the existing
template-context-processor pattern in `dashboard/app.py`) so any
template can call it without an import.

### R4 — htmx-swapped fragments

If the user is on a page when the mismatch first appears, the banner
must show on the next htmx swap that returns a full page. For htmx
fragment responses (partial swaps), no special handling is required —
the banner is in `base.html` and full-page reloads will pick it up.
Verify by grepping for `HX-Reswap` / `HX-Trigger` headers and ensure
none of them break the banner.

### R5 — Tailwind regeneration

If you add new utility classes that aren't already in
`dashboard/static/styles.css`, run `make css` and commit the
regenerated file.

## Constraints

1. NO new JavaScript files. The banner is pure HTML/CSS.
2. NO emoji anywhere in the banner.
3. Banner copy is fixed per R1 — tests assert the exact strings.
4. Touch only:
   - `dashboard/templates/base.html`
   - `dashboard/templates/macros/db_guard.html` (new)
   - any templates with write-action buttons (per Grep results)
   - `dashboard/app.py` (only the Jinja global registration line)
   - `dashboard/static/styles.css` (only via `make css`)

## Input Files

- `ai-dev/active/I-00040/I-00040_Issue_Design.md`
- `ai-dev/active/I-00040/reports/I-00040_S01_Backend_report.md`
- `dashboard/templates/base.html`
- `dashboard/CLAUDE.md`

## Output Files

- `dashboard/templates/base.html` — banner block added
- `dashboard/templates/macros/db_guard.html` — new macro file
- `dashboard/app.py` — `is_db_stale` Jinja global registered
- Other templates as needed (write-action buttons updated)
- `dashboard/static/styles.css` — only if `make css` regenerates it
- `ai-dev/active/I-00040/reports/I-00040_S03_Frontend_report.md`

## Lifecycle Commands

```bash
uv run iw step-start I-00040 --step S03
# ... work ...
mkdir -p ai-dev/active/I-00040/reports
uv run iw step-done I-00040 --step S03 --report ai-dev/active/I-00040/reports/I-00040_S03_Frontend_report.md
```
