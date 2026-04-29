# F-00069_S02_Frontend_prompt

**Work Item**: F-00069 -- Test Execution, Coverage Gate, Reports, and Coverage Dashboard View
**Step**: S02
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

(Standard Docker policy applies — see Implementation_Prompt_Template / agent constraints. This step does not require Docker.)

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch alembic.

## Input Files

- `ai-dev/active/F-00069/F-00069_Feature_Design.md`
- S01 report (when available): `ai-dev/active/F-00069/reports/F-00069_S01_Backend_report.md`
- `dashboard/services/coverage_service.py` — produced by S01; defines `CoverageView`, `PackageRow`, `FileRow`
- `dashboard/templates/base.html` — has the System nav block (look for `{% set system_links = [...] %}`)
- `dashboard/templates/pages/system/status.html` — example System page to model after
- `dashboard/static/styles.css` — Tailwind output; existing utility classes
- `dashboard/CLAUDE.md` — htmx + Jinja conventions

## Output Files

- New: `dashboard/templates/pages/system/coverage.html`
- New: `dashboard/templates/fragments/coverage_files.html`
- Modified: `dashboard/templates/base.html` (add one nav entry)
- `ai-dev/active/F-00069/reports/F-00069_S02_Frontend_report.md`

## Context

You are implementing the **frontend templates** for the new
`/system/coverage` page that visualises coverage data on the dashboard.
S01 has already created the FastAPI router and the
`coverage_service.load_coverage()` function that returns a typed
`CoverageView`. Your job is purely Jinja templating + a base.html nav
addition.

## Requirements

### 1. Add nav entry to `base.html`

Locate the `system_links` list in `dashboard/templates/base.html`. It currently looks like:

```jinja
{% set system_links = [
  ('/system/running', 'Running Tasks'),
  ('/system/worktrees', 'Worktree Health'),
  ('/system/containers', 'Container Health'),
  ('/system/status', 'System Status'),
  ('/system/all-active', 'All Active Work'),
  ('/system/config', 'Configuration'),
] %}
```

Insert `('/system/coverage', 'Test Coverage')` between `'/system/status'` and `'/system/all-active'`. Match the indentation of surrounding rows exactly.

### 2. Create `dashboard/templates/pages/system/coverage.html`

Extend `base.html` (`{% extends "base.html" %}`). The page receives `view: CoverageView` as context.

Structure (Tailwind classes; reuse what exists in `pages/system/status.html`):

```jinja
{% extends "base.html" %}
{% block title %}Test Coverage — IW AI Core{% endblock %}

{% block content %}
<div class="p-6 space-y-6">
  <h1 class="text-2xl font-bold">Test Coverage</h1>

  {% if not view.available %}
    {# Empty state #}
    <div class="rounded-lg border border-dashed p-8 text-center bg-card">
      <p class="text-lg font-medium">No coverage data yet</p>
      <p class="text-sm text-muted-foreground mt-2">
        Run <code class="bg-muted px-1.5 py-0.5 rounded">make test-unit</code>
        or <code class="bg-muted px-1.5 py-0.5 rounded">make test-parallel</code>
        to generate coverage data.
      </p>
      {% if view.error %}
        <p class="text-xs text-destructive mt-4">Parse error: {{ view.error }}</p>
      {% endif %}
      {% if view.mtime_iso %}
        <p class="text-xs text-muted-foreground mt-2">
          Last seen: {{ view.mtime_iso }}
        </p>
      {% endif %}
    </div>
  {% else %}
    {# Header card #}
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="rounded-lg border bg-card p-4">
        <p class="text-xs text-muted-foreground uppercase">Overall Lines</p>
        <p class="text-3xl font-bold">{{ "%.1f"|format(view.overall_line_pct) }}%</p>
      </div>
      <div class="rounded-lg border bg-card p-4">
        <p class="text-xs text-muted-foreground uppercase">Overall Branches</p>
        <p class="text-3xl font-bold">
          {% if view.overall_branch_pct is not none %}{{ "%.1f"|format(view.overall_branch_pct) }}%{% else %}—{% endif %}
        </p>
      </div>
      <div class="rounded-lg border bg-card p-4">
        <p class="text-xs text-muted-foreground uppercase">Threshold</p>
        <p class="text-3xl font-bold">{{ view.threshold }}%</p>
        <p class="text-xs {% if view.gap_pct is not none and view.gap_pct < 0 %}text-destructive{% else %}text-muted-foreground{% endif %} mt-1">
          {% if view.gap_pct is none %}n/a{% elif view.gap_pct >= 0 %}+{{ "%.1f"|format(view.gap_pct) }} pp above{% else %}{{ "%.1f"|format(view.gap_pct) }} pp below{% endif %}
        </p>
      </div>
      <div class="rounded-lg border bg-card p-4">
        <p class="text-xs text-muted-foreground uppercase">Last Run</p>
        <p class="text-sm font-medium">{{ view.mtime_iso or "—" }}</p>
        {% if view.test_count is not none %}
          <p class="text-xs text-muted-foreground mt-1">{{ view.test_count }} statements</p>
        {% endif %}
      </div>
    </div>

    {# Per-package table #}
    <div class="rounded-lg border bg-card">
      <table class="w-full text-sm">
        <thead class="bg-muted/40 text-left">
          <tr>
            <th class="px-4 py-2 font-medium">Package</th>
            <th class="px-4 py-2 font-medium">Lines</th>
            <th class="px-4 py-2 font-medium">Branches</th>
            <th class="px-4 py-2 font-medium">Missing</th>
            <th class="px-4 py-2 font-medium">Status</th>
            <th class="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {% for pkg in view.packages %}
            <tr class="border-t cursor-pointer hover:bg-muted/30"
                hx-get="/system/coverage/files/{{ pkg.name }}"
                hx-target="#files-{{ pkg.name }}"
                hx-swap="innerHTML">
              <td class="px-4 py-3 font-medium">{{ pkg.name }}</td>
              <td class="px-4 py-3">{{ "%.1f"|format(pkg.line_pct) }}%</td>
              <td class="px-4 py-3">
                {% if pkg.branch_pct is not none %}{{ "%.1f"|format(pkg.branch_pct) }}%{% else %}—{% endif %}
              </td>
              <td class="px-4 py-3">{{ pkg.missing_lines }}</td>
              <td class="px-4 py-3">
                {% set badge_class = {'green': 'bg-green-100 text-green-800', 'amber': 'bg-amber-100 text-amber-800', 'red': 'bg-red-100 text-red-800'}[pkg.badge] %}
                <span class="inline-block px-2 py-0.5 rounded text-xs font-medium {{ badge_class }}">
                  {{ pkg.badge|upper }}
                </span>
              </td>
              <td class="px-4 py-3 text-xs text-muted-foreground">click to expand</td>
            </tr>
            <tr class="border-t bg-muted/10">
              <td colspan="6" class="px-4 py-2">
                <div id="files-{{ pkg.name }}"></div>
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% endif %}
</div>
{% endblock %}
```

Adapt class names if `dashboard/templates/pages/system/status.html` uses different tokens (`bg-sidebar`, `text-foreground`, etc.). Match existing System pages — do not invent a new visual style.

### 3. Create `dashboard/templates/fragments/coverage_files.html`

```jinja
<table class="w-full text-xs">
  <thead class="text-left">
    <tr>
      <th class="px-2 py-1 font-medium">File</th>
      <th class="px-2 py-1 font-medium">Lines</th>
      <th class="px-2 py-1 font-medium">Branches</th>
      <th class="px-2 py-1 font-medium">Missing</th>
      <th class="px-2 py-1 font-medium">Status</th>
    </tr>
  </thead>
  <tbody>
    {% for f in files %}
      <tr class="border-t">
        <td class="px-2 py-1 font-mono">{{ f.path }}</td>
        <td class="px-2 py-1">{{ "%.1f"|format(f.line_pct) }}%</td>
        <td class="px-2 py-1">
          {% if f.branch_pct is not none %}{{ "%.1f"|format(f.branch_pct) }}%{% else %}—{% endif %}
        </td>
        <td class="px-2 py-1">{{ f.missing_lines }}</td>
        <td class="px-2 py-1">
          {% set badge_class = {'green': 'bg-green-100 text-green-800', 'amber': 'bg-amber-100 text-amber-800', 'red': 'bg-red-100 text-red-800'}[f.badge] %}
          <span class="inline-block px-1.5 py-0.5 rounded text-xs font-medium {{ badge_class }}">{{ f.badge|upper }}</span>
        </td>
      </tr>
    {% endfor %}
    {% if not files %}
      <tr><td colspan="5" class="px-2 py-2 text-muted-foreground">No files in this package.</td></tr>
    {% endif %}
  </tbody>
</table>
```

### 4. Tailwind / CSS

Do NOT introduce new utility classes. The existing build (`make css`) already produces `dashboard/static/styles.css` from `tailwind.src.css`. Run `make css` after editing templates if any new utilities are picked up; if the CI fails because of unknown classes, that's a signal you used something not in the existing palette.

### 5. Accessibility

- Package rows are clickable — they MUST also be keyboard-accessible. Add `tabindex="0"` and a `hx-trigger="click, keydown[key=='Enter']"` so Enter triggers the swap.
- Set `role="button"` on package rows. (htmx supports keyboard triggers natively.)
- Empty state must be announced — use `role="status"` on the empty-state container.

## Project Conventions

- Match `dashboard/templates/pages/system/*.html` for visual style.
- htmx-only — no client-side JS framework.
- Tailwind only — no inline styles.
- `dashboard/CLAUDE.md` is authoritative on htmx patterns.

## TDD Requirement

Templates are exercised by S05's dashboard tests. For S02, run the dashboard locally (`make dashboard-start` or hit `/system/coverage` via the running dev server) and verify visually that:
- Page renders with no Jinja errors.
- Empty state appears when `tests/output/coverage/coverage.json` is absent.
- Header card renders when present.

## Pre-flight Quality Gates

1. `make format` — auto-fix
2. `make lint` — zero errors (lint-js will syntax-check JS; templates are not linted but Jinja syntax errors will surface at request time)
3. `make typecheck` — zero new errors

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "frontend-impl",
  "work_item": "F-00069",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/pages/system/coverage.html",
    "dashboard/templates/fragments/coverage_files.html",
    "dashboard/templates/base.html"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "no new tests in this step (S05 owns them); existing suite unchanged",
  "blockers": [],
  "notes": ""
}
```
