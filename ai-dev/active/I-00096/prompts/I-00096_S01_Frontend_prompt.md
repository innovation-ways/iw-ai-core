# I-00096_S01_Frontend_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies — see `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00096 --json`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- `ai-dev/active/I-00096/I-00096_Functional.md`
- `dashboard/templates/base.html`
- `dashboard/templates/pages/project/auto_merge.html`
- `dashboard/templates/fragments/auto_merge_status_chip.html`
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/routers/auto_merge_ui.py` (note `request.state.auto_merge_status_for_chip` at line 93)
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S01_Frontend_report.md`

## Context

Two defects to address: (a) the status chip is rendered twice on the
auto-merge page; (b) the events table fragment needs a "Show all
daemon events" toggle for the new aggregator behaviour from S03.

## Requirements

### 1. Locate the topbar chip render path

Find where the topbar renders the compact auto-merge chip. Typical
locations:

```bash
grep -rn "auto_merge" dashboard/templates/base.html dashboard/templates/components/ 2>/dev/null
grep -rn "auto-merge-chip--compact" dashboard/templates/
```

Identify the conditional that triggers the topbar chip render.
Likely it's something like:

```jinja
{% if request.state.auto_merge_status_for_chip %}
  {% include "fragments/auto_merge_status_chip.html" with compact=true %}
{% endif %}
```

### 2. Suppress topbar chip on the auto-merge page

In the topbar conditional, add a check against the current request
path. Two approaches:

- **Approach A — flag in route handler**: In
  `dashboard/routers/auto_merge_ui.py:auto_merge_page`, set
  `request.state.suppress_topbar_auto_merge_chip = True`. The topbar
  template reads `{% if not request.state.suppress_topbar_auto_merge_chip %}`.
- **Approach B — URL match**: The topbar template checks
  `{% if not request.url.path.endswith('/auto-merge') %}`. Slightly
  more fragile (URL pattern), but no router change needed.

Pick A — it's more explicit. Modify `auto_merge_page` to set the
flag.

Verify the topbar still renders the chip on other project pages
(queue, batches, …).

### 3. Add "Show all daemon events" toggle to events filter row

In `dashboard/templates/fragments/auto_merge_events_table.html`,
above or beside the existing filter chip row, render a separate
toggle button:

```jinja
{% set _show_all = request.query_params.get('all') in ('1', 'true') %}
<div class="flex items-center gap-2 text-xs">
  <button type="button"
          hx-get="/project/{{ request.path_params.project_id }}/auto-merge/events?page=0&page_size={{ page_size }}{% if not _show_all %}&all=1{% endif %}{% if request.query_params.get('type') %}&type={{ request.query_params.get('type') }}{% endif %}"
          hx-target="#auto-merge-events"
          hx-swap="innerHTML"
          class="auto-merge-show-all-toggle {% if _show_all %}is-active{% endif %}"
          aria-pressed="{{ 'true' if _show_all else 'false' }}">
    {% if _show_all %}Auto-merge events only{% else %}Show all daemon events{% endif %}
  </button>
</div>
```

The label flips based on current state — clear affordance for what
clicking will do.

### 4. Propagate the `all` param through filter chip URLs and pagination

When `all=1` is active, the filter chip URLs and pagination
Prev/Next URLs must carry it forward; otherwise clicking a filter
clears the show-all state unintentionally.

Update the filter chip loop to append `&all=1` when `_show_all`.
Same for the pagination Prev/Next URLs at the bottom of the fragment.

### 5. Append small CSS for the toggle

In `dashboard/static/styles.css`:

```css
.auto-merge-show-all-toggle{border:1px solid var(--border);border-radius:.25rem;padding:.2rem .5rem;background:var(--card);cursor:pointer}
.auto-merge-show-all-toggle.is-active{background:var(--primary);color:var(--primary-foreground);border-color:var(--primary)}
```

### 6. Do NOT change the in-page chip include

`dashboard/templates/pages/project/auto_merge.html:13` still
`{% include "fragments/auto_merge_status_chip.html" %}` — the rich
in-page chip is the one we keep.

### 7. Do NOT touch `auto_merge_status_chip.html` itself

The chip fragment is fine as-is; only its render-site count changes.

## Project Conventions

`dashboard/CLAUDE.md`; Jinja2 `format` is `%`-style (I-00075).

## TDD Requirement

Frontend step — `tdd_red_evidence = "n/a — template + minor route flag"`.
Behavioural tests in S07.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00096",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/base.html",
    "dashboard/templates/fragments/auto_merge_events_table.html",
    "dashboard/routers/auto_merge_ui.py",
    "dashboard/static/styles.css"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — template + minor route flag; behavioural tests in S07",
  "blockers": [],
  "notes": "Note Approach A or B chosen for chip suppression."
}
```
