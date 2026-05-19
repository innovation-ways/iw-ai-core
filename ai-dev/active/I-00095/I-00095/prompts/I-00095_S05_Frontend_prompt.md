# I-00095_S05_Frontend_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step**: S05
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00095 --json`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/I-00095_Functional.md`
- `ai-dev/active/I-00095/reports/I-00095_S01_Backend_report.md`
- `ai-dev/active/I-00095/reports/I-00095_S03_Api_report.md`
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/static/styles.css`
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S05_Frontend_report.md`

## Context

S03 added `sort` + `dir` query params to the route and passes them
into the template context. You convert the four sortable column
headers into clickable sort controls with chevron indicators.

## Requirements

### 1. Replace static `<th>` with sortable buttons

In `dashboard/templates/fragments/auto_merge_events_table.html`,
replace the `<thead>` block (lines 25-28). For each sortable column
(`created_at` rendered as "timestamp", `event_type`, `entity_id`,
`verdict`), render:

```jinja
{% set columns = [
  ('created_at', 'timestamp', True),
  ('event_type', 'event_type', True),
  ('entity_id', 'entity_id', True),
  ('message', 'message', False),
  ('verdict', 'verdict', True),
  (None, 'actions', False),
] %}

<thead>
  <tr class="border-b border-border bg-muted/30 text-xs text-muted-foreground">
    {% for col_key, label, sortable in columns %}
      {% if sortable %}
        {% set _is_active = (sort == col_key) %}
        {% set next_dir = ('asc' if _is_active and direction == 'desc' else 'desc') %}
        {% set chevron = '↓' if _is_active and direction == 'desc' else ('↑' if _is_active and direction == 'asc' else '') %}
        <th class="px-3 py-2 text-left"
            {% if _is_active %}aria-sort="{{ 'ascending' if direction == 'asc' else 'descending' }}"{% endif %}>
          <button type="button"
                  hx-get="/project/{{ request.path_params.project_id }}/auto-merge/events?page=0&page_size={{ page_size }}&sort={{ col_key }}&dir={{ next_dir }}{% if request.query_params.get('type') %}&type={{ request.query_params.get('type') }}{% endif %}"
                  hx-target="#auto-merge-events"
                  hx-swap="innerHTML"
                  class="auto-merge-sortable {% if _is_active %}auto-merge-sortable--active{% endif %}">
            {{ label }}{% if chevron %} <span aria-hidden="true">{{ chevron }}</span>{% endif %}
          </button>
        </th>
      {% else %}
        <th class="px-3 py-2 text-left">{{ label }}</th>
      {% endif %}
    {% endfor %}
  </tr>
</thead>
```

Notes:
- `request.path_params.project_id`, `request.query_params.get('type')`,
  `sort`, `direction`, `page_size` are all already in context (after
  S03's update).
- The default `next_dir` for an inactive column is `desc` (per AC3).
- The chevron is a small visual cue; screen readers read `aria-sort`
  instead.

### 2. Preserve the filter chip section above the table

Don't touch lines 1-21 (filter chips) — they're owned by I-00092.

### 3. CSS (optional)

Append to `dashboard/static/styles.css`:

```css
.auto-merge-sortable{display:inline-flex;align-items:center;gap:.25rem;background:transparent;border:0;font:inherit;color:inherit;padding:0;cursor:pointer}
.auto-merge-sortable:hover{color:var(--foreground)}
.auto-merge-sortable--active{color:var(--foreground);font-weight:600}
```

### 4. Preserve filter+sort interop in pagination links

Lines 44-49 contain pagination links/buttons. After this change they
must ALSO carry `&sort={{ sort }}&dir={{ direction }}` so a Prev/Next
click preserves the sort. Update those URLs accordingly.

### 5. No new JavaScript

The htmx `hx-get` swap handles everything.

## Project Conventions

`dashboard/CLAUDE.md`; Jinja2 `format`-filter must be `%`-style
(I-00075); plain CSS goes to `styles.css`.

## TDD Requirement

Frontend step — behavioural tests in S07. Targeted run:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint` (incl. template validator)

## Test Verification (NON-NEGOTIABLE)

Targeted only.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "I-00095",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/auto_merge_events_table.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — template change; behavioural tests in S07",
  "blockers": [],
  "notes": ""
}
```
