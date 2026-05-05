# I-00068_S03_Frontend_prompt

**Work Item**: I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Input Files

- `uv run iw item-status I-00068 --json` — runtime step state
- `ai-dev/active/I-00068/I-00068_Issue_Design.md` — Design document
- `ai-dev/active/I-00068/reports/I-00068_S01_Backend_report.md` — S01 report
- `dashboard/templates/pages/project/dashboard.html` — Template containing the buggy fallback (current lines 115-119)
- `dashboard/CLAUDE.md` — Dashboard conventions
- `tests/integration/test_dashboard_pages.py` — Existing dashboard tests for reference

## Output Files

- `ai-dev/active/I-00068/reports/I-00068_S03_Frontend_report.md`

## Context

You are implementing the template-side hardening of the I-00068 fix. Even after S01 ensures new archive events carry `entity_type="batch"`, historical rows in production already have `entity_type=None`. The dashboard's current fallback unconditionally routes any unclassified `entity_id` to `/item/`, which generates a known-broken URL for `BATCH-` IDs.

Add a defensive prefix check in the fallback so any `entity_id` starting with `BATCH-` routes to `/batch/` even when `entity_type` is missing.

## Requirements

### 1. Update the Recent Activity fallback

In `dashboard/templates/pages/project/dashboard.html`, locate the elif chain in the Recent Activity loop (currently at lines 100-120 in the rendered template). The chain currently looks like:

```jinja
{% if event.entity_id and event.entity_type == 'batch' %}
  <a href="/project/{{ current_project.id }}/batch/{{ event.entity_id }}" ...>
{% elif event.entity_id and event.entity_type == 'doc_job' %}
  <a href="/project/{{ current_project.id }}/jobs/doc/{{ event.entity_id }}" ...>
{% elif event.entity_id and event.entity_type == 'work_item' %}
  <a href="/project/{{ current_project.id }}/item/{{ event.entity_id }}" ...>
{% elif event.entity_id %}
  <a href="/project/{{ current_project.id }}/item/{{ event.entity_id }}" ...>
{% endif %}
```

Modify the final `{% elif event.entity_id %}` branch to detect a `BATCH-` prefix (case-sensitive) on `entity_id` and route to `/batch/` in that case; otherwise keep the existing `/item/` fallback. Recommended structure:

```jinja
{% elif event.entity_id and event.entity_id.startswith('BATCH-') %}
  <a href="/project/{{ current_project.id }}/batch/{{ event.entity_id }}"
     class="font-mono text-xs font-semibold text-primary hover:underline mr-1">
    {{ event.entity_id }}
  </a>
{% elif event.entity_id %}
  <a href="/project/{{ current_project.id }}/item/{{ event.entity_id }}"
     class="font-mono text-xs font-semibold text-primary hover:underline mr-1">
    {{ event.entity_id }}
  </a>
{% endif %}
```

### 2. Do NOT modify the explicit `entity_type` branches

The `'batch'`, `'doc_job'`, and `'work_item'` branches must remain byte-identical. Only the final fallback elif is split.

### 3. Case-sensitive prefix check

Use `event.entity_id.startswith('BATCH-')` exactly. Do NOT lower-case, do NOT trim, do NOT compare against just `BATCH` (without the dash) — the dash is what guarantees we are matching the ID prefix and not, e.g., a free-form string that happens to begin with the letters BATCH.

### 4. Do NOT bypass autoescape

`{{ event.entity_id }}` is rendered through Jinja2's default autoescape. Do NOT add `|safe` or `Markup(...)`. Do NOT call `event.entity_id.startswith(...)` on a raw, unescaped value AND then try to render it raw.

### 5. No JS changes

This step does NOT touch any JavaScript. Pure Jinja2 conditional change.

### 6. Tailwind CSS

No new Tailwind utility classes are needed. You should NOT need to run `make css`.

## Project Conventions

Read `dashboard/CLAUDE.md` and `CLAUDE.md` for:

- Jinja2 + htmx + prebuilt Tailwind
- Templates are thin (no business logic)
- Static asset pipeline (`make css`) only when classes change

## TDD Requirement

Follow TDD:

1. **RED**: A test in `tests/integration/test_i00068_batch_link_routing.py` (S05 will write the full suite — for this step, you may add a focused integration test that asserts `BATCH-99999` with `entity_type=None` routes to `/batch/`). It MUST FAIL on the pre-fix template.
2. **GREEN**: Make the template change.
3. **REFACTOR**: Clean up.

## Pre-flight Quality Gates

```bash
make format
make typecheck
make lint
```

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration` and confirm:

1. The new test for the prefix-fallback passes.
2. No existing dashboard tests regress, especially:
   - `test_recent_activity_batch_event_links_to_batch_route`
   - `test_recent_activity_doc_job_event_links_to_doc_job_route`
   - `test_recent_activity_work_item_event_links_to_item_route`
   - `test_recent_activity_unknown_entity_type_falls_back_to_item_route`
   - `test_recent_activity_no_link_renders_when_entity_id_is_null`

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "I-00068",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/pages/project/dashboard.html",
    "tests/integration/test_i00068_batch_link_routing.py"
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
