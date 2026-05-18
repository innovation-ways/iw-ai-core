# I-00097_S01_Frontend_prompt

**Work Item**: I-00097 — Auto-merge polish — token cost formatting & entity_id linkification
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies — `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00097 --json`
- `ai-dev/active/I-00097/I-00097_Issue_Design.md`
- `ai-dev/active/I-00097/I-00097_Functional.md`
- `dashboard/templates/fragments/auto_merge_rollup.html`
- `dashboard/templates/fragments/auto_merge_event_row.html`
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00097/reports/I-00097_S01_Frontend_report.md`

## Context

Two small polish changes — smart zero formatting for the token cost
total + linkified entity_id when it's a recognisable work-item ID.

## Requirements

### 1. Smart $0 formatting

In `dashboard/templates/fragments/auto_merge_rollup.html:22`,
replace:

```jinja
${{ "%.6f"|format(token_cost_rollup.total_cost_usd) }}
```

with a conditional render that avoids trailing-zero noise:

```jinja
{% set _cost = token_cost_rollup.total_cost_usd %}
{% if _cost == 0 %}
$0
{% else %}
${{ ("%.6f"|format(_cost)).rstrip('0').rstrip('.') }}
{% endif %}
```

Or, equivalently as a one-liner using Jinja2 ternary:

```jinja
${{ '0' if token_cost_rollup.total_cost_usd == 0 else (("%.6f"|format(token_cost_rollup.total_cost_usd)).rstrip('0').rstrip('.')) }}
```

Pick whichever is more readable. AC1 requires `$0` for exact zero;
AC2 requires `$0.000123` (no trailing zeros) for `0.000123`.

### 2. Linkify entity_id for work-item IDs

In `dashboard/templates/fragments/auto_merge_event_row.html:5`,
replace:

```jinja
<td class="px-3 py-2 text-xs font-mono">{{ row.entity_id or '—' }}</td>
```

with a conditional that renders an `<a>` when `entity_id` matches
the work-item pattern `^(F|I|CR)-\d{5}$`:

```jinja
{% set _eid = row.entity_id %}
<td class="px-3 py-2 text-xs font-mono">
  {% if _eid and (_eid is match('^(F|I|CR)-\\d{5}$')) %}
    <a href="/project/{{ request.path_params.project_id }}/item/{{ _eid }}" class="text-primary hover:underline">{{ _eid }}</a>
  {% elif _eid %}
    {{ _eid }}
  {% else %}
    —
  {% endif %}
</td>
```

Note: Jinja2's built-in test `is match(...)` works if the Jinja2
env has it; otherwise use a Python helper exposed as a filter, e.g.
add to `dashboard/utils/template_filters.py`:

```python
import re
_WORK_ITEM_RE = re.compile(r"^(F|I|CR)-\d{5}$")

def is_work_item_id(value: str | None) -> bool:
    return bool(value and _WORK_ITEM_RE.match(value))
```

and register it via `env.filters['is_work_item_id'] = is_work_item_id`
(or a `tests['work_item_id']` test). Pick whichever fits the existing
filter-registration pattern in the project.

Check for existing helpers first:

```bash
grep -rn "is_work_item\|work_item_id_re\|F-00\|CR-00" dashboard/utils/ orch/ 2>/dev/null
```

If a helper exists, REUSE it. Otherwise add a small one.

### 3. Use existing dashboard URL conventions

The item-detail URL pattern in this dashboard is
**`/project/{project_id}/item/{item_id}`** (singular `item`) — confirmed
by `dashboard/routers/items.py:1124` (`@router.get("/item/{item_id}")`
under the prefix `/project/{project_id}`) and by existing template
hrefs in `queue.html`, `history.html`, `worktree_table.html`, and
`batch_items_rows.html`.

Re-verify before writing the href:

```bash
grep -rn '/item/' dashboard/routers/items.py dashboard/templates/pages/ | grep -v test_ | head
```

If the grep no longer matches (the route has been renamed), use
whatever the dashboard already uses. **Do NOT use the plural form
`/items/<id>`** — the only place that pattern appears in the codebase
is `containers_table.html:121`, which is a pre-existing bug (out of
scope for this incident).

### 4. Preserve the `—` rendering when entity_id is null

AC5: null entity_id still renders as `—` plain text.

### 5. Do NOT touch other fragments

`auto_merge_settings.html`, `auto_merge_status_chip.html`,
`auto_merge_event_detail.html`, `auto_merge_events_table.html`,
`auto_merge_refuse_list.html` are not in scope.

## Project Conventions

- `dashboard/CLAUDE.md`: htmx + Jinja2; Tailwind classes are JIT-purged
  — `text-primary` and `hover:underline` are both safe (used elsewhere
  in the dashboard).
- Jinja2 `format` filter must remain `%`-style (I-00075).

## TDD Requirement

Frontend step — `tdd_red_evidence = "n/a — template-only polish"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint` (includes template validator)

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
  "work_item": "I-00097",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/auto_merge_rollup.html",
    "dashboard/templates/fragments/auto_merge_event_row.html"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — template-only polish",
  "blockers": [],
  "notes": "Note the URL pattern used for items (singular vs plural) and whether a new Jinja2 filter was added or an existing helper reused."
}
```
