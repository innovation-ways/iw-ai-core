# CR-00039_S01_Frontend_prompt

**Work Item**: CR-00039 — Step Pipeline: Labeled Pill Redesign with Fix-Cycle Expansion
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. Do not run docker commands.

## ⛔ Migrations: agents generate, daemon applies

This CR makes no database changes. Do not touch migrations.

---

## Input Files

- `CLAUDE.md` (root) — architecture, CSS rules, hard constraints
- `dashboard/CLAUDE.md` — dashboard conventions
- `dashboard/templates/components/step_pipeline.html` — file to replace
- `dashboard/templates/fragments/item_overview.html` — file to update (remove duration row)
- `dashboard/static/styles.css` — file to extend with new pill CSS

## Output Files

- `dashboard/templates/components/step_pipeline.html` — redesigned pill macro
- `dashboard/templates/fragments/item_overview.html` — duration row removed
- `dashboard/static/styles.css` — new `.iw-pipeline-*` classes appended

---

## Context

Read `CLAUDE.md` (root) and `dashboard/CLAUDE.md` before starting. Key points:

- Dashboard is FastAPI + Jinja2 + htmx + Tailwind (prebuilt). Plain CSS rules must be
  appended directly to `dashboard/static/styles.css` — `make css` may report "Nothing to
  be done" in worktrees (I-00067). Plain CSS is served as-is, no recompile needed.
- Step pipeline template: `dashboard/templates/components/step_pipeline.html`
- Item overview fragment: `dashboard/templates/fragments/item_overview.html`
- CSS: `dashboard/static/styles.css`

---

## Objective

Replace the unreadable 6×14 px green square strip + broken duration row with a horizontal
strip of labeled fixed-width pills. Fix-cycle reruns must be visually expanded as separate
amber pills labelled `↺SXX`. No Python/backend changes — pure Jinja2 template + CSS.

---

## Current State (what you are replacing)

### `dashboard/templates/components/step_pipeline.html` (entire file)

```jinja2
{% macro step_pipeline(steps) %}
  <div class="iw-step-strip" data-step-count="{{ steps | length }}">
    {% for step in steps %}
      {% if step.status == 'completed' %}
        <div class="iw-step-seg iw-step-seg--completed"
             title="{{ step.step_id }} {{ step.agent_label }}: completed{{ ' ' ~ step.duration if step.duration else '' }}"></div>
      ...
    {% endfor %}
  </div>
{% endmacro %}
```

### `dashboard/templates/fragments/item_overview.html` (lines 10–36)

```html
<div class="mb-6">
  <h3 ...>Step Pipeline</h3>
  <div class="bg-card border border-border rounded-lg p-4 overflow-x-auto">
    {% if steps %}
      {{ step_pipeline(steps) }}
      <!-- Duration row — BROKEN: w-8 columns don't align with 6px segments -->
      <div class="flex items-center gap-1 mt-2">
        {% for step in steps %}
          <div class="w-8 text-center">
            <span class="text-xs text-muted-foreground font-mono">
              {% if step.duration_secs is not none %}
                {% set m = (step.duration_secs // 60)|int %}
                {% set s = (step.duration_secs % 60)|int %}
                {% if m > 0 %}{{ m }}m{% endif %}{{ s }}s
              {% endif %}
            </span>
          </div>
          {% if not loop.last %}
            <div class="w-4"></div>
          {% endif %}
        {% endfor %}
      </div>
    {% else %}
      <p class="text-muted-foreground text-sm">No steps defined.</p>
    {% endif %}
  </div>
</div>
```

### `dashboard/static/styles.css` (lines 352–358)

```css
.iw-step-strip { display: flex; gap: 1px; align-items: center; }
.iw-step-seg   { width: 6px; height: 14px; border-radius: 1px; flex-shrink: 0; }
.iw-step-seg--completed   { background: var(--success); }
.iw-step-seg--in-progress { background: var(--primary); animation: pulse 1.4s ease-in-out infinite; }
.iw-step-seg--failed      { background: var(--destructive); }
.iw-step-seg--skipped     { background: var(--muted); }
.iw-step-seg--pending     { background: var(--secondary); }
```

---

## Data Available in the Template

`steps` is a `list[StepDetail]` (one entry per WorkflowStep + synthetic S00/MERGE).
Each `step` has:

| Field | Type | Notes |
|-------|------|-------|
| `step.step_id` | `str` | `"S00"`, `"S01"`, …, `"MERGE"` |
| `step.agent_label` | `str` | Human-readable agent name |
| `step.status` | `str` | `"completed"`, `"in_progress"`, `"failed"`, `"skipped"`, `"pending"`, `"needs_fix"` |
| `step.duration_secs` | `float \| None` | Aggregate duration in seconds |
| `step.run_count` | `int` | Total runs (including fix-cycle reruns) |
| `step.fix_cycle_count` | `int` | Number of fix-cycle reruns (0 for steps that ran once cleanly) |
| `step.is_synthetic` | `bool` | True for S00 and MERGE steps |

**Key insight**: `fix_cycle_count` counts how many extra reruns happened due to fix cycles.
A step with `fix_cycle_count=2` ran 3 times total (1 original + 2 fix-cycle reruns).
Use `{% for i in range(step.fix_cycle_count) %}` to emit that many extra pills.

---

## Required Changes

### 1. `dashboard/templates/components/step_pipeline.html` — full replacement

Replace the entire macro with the new pill-based design:

- Outer container: preserve `data-step-count="{{ steps | length }}"` (tests assert this).
  Use class `iw-pipeline-strip`.
- For each step, render:
  1. **Main pill** (`iw-pipeline-pill iw-pipeline-pill--{status}`):
     - First line: step ID in monospace bold (e.g. `S01`)
     - Second line: formatted duration if `step.duration_secs is not none`
       Use `{% set m = (step.duration_secs // 60)|int %}{% set s = (step.duration_secs % 60)|int %}` then render `{% if m > 0 %}{{ m }}m{% endif %}{{ s }}s`
     - `title` tooltip: `"{{ step.step_id }} {{ step.agent_label }}: {{ step.status }}{% if step.duration_secs is not none %} {{ dur }}{% endif %}"`
  2. After the main pill, if `step.fix_cycle_count > 0`, render N **fix-cycle rerun pills**
     (`iw-pipeline-pill iw-pipeline-pill--fixcycle`) each labelled `↺{{ step.step_id }}`.
     No duration label on fix-cycle pills (we don't have per-run data).
     `title` tooltip: `"↺{{ step.step_id }}: fix cycle {{ loop.index }}"`
  3. A **connector** div (`iw-pipeline-connector`) between every pair of adjacent pills
     (between main pill and fix-cycle pill: `iw-pipeline-connector--fixcycle`; between
     normal sequential pills: `iw-pipeline-connector`). Do NOT render a connector after
     the last pill overall.

**Status → CSS modifier mapping:**

| status | modifier |
|--------|----------|
| `completed` | `iw-pipeline-pill--completed` |
| `in_progress` | `iw-pipeline-pill--in-progress` |
| `failed` | `iw-pipeline-pill--failed` |
| `needs_fix` | `iw-pipeline-pill--failed` (same red) |
| `skipped` | `iw-pipeline-pill--skipped` |
| `pending` | `iw-pipeline-pill--pending` |
| anything else | `iw-pipeline-pill--pending` |

### 2. `dashboard/templates/fragments/item_overview.html` — remove the broken duration row

In the Step Pipeline `<div class="mb-6">` block (lines 10–36), remove the entire
`<!-- Duration row -->` div (the `<div class="flex items-center gap-1 mt-2">` block
and all its children). Keep everything else (the `h3`, the outer card div, the macro
call, and the `{% else %}` no-steps paragraph).

### 3. `dashboard/static/styles.css` — append new CSS rules

Append the following at the end of the file (do NOT replace the old `.iw-step-*` rules —
leave them in place to avoid breaking any cached reference):

```css
/* CR-00039: Step Pipeline pill redesign */
.iw-pipeline-strip {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 0;
  overflow-x: auto;
}

.iw-pipeline-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 52px;
  min-height: 42px;
  border-radius: 4px;
  padding: 3px 4px;
  flex-shrink: 0;
  cursor: default;
}

.iw-pipeline-pill-id {
  font-size: 10px;
  font-weight: 700;
  font-family: ui-monospace, monospace;
  line-height: 1.3;
  text-align: center;
}

.iw-pipeline-pill-dur {
  font-size: 9px;
  font-family: ui-monospace, monospace;
  line-height: 1.3;
  text-align: center;
  opacity: 0.85;
}

.iw-pipeline-pill--completed   { background: var(--success); color: #fff; }
.iw-pipeline-pill--in-progress { background: var(--primary); color: #fff; animation: pulse 1.4s ease-in-out infinite; }
.iw-pipeline-pill--failed      { background: var(--destructive); color: #fff; }
.iw-pipeline-pill--skipped     { background: var(--muted); color: var(--muted-foreground); }
.iw-pipeline-pill--pending     { background: var(--secondary); color: var(--secondary-foreground); }
.iw-pipeline-pill--fixcycle    { background: var(--warning, #f59e0b); color: var(--warning-foreground, #fff); }

.iw-pipeline-connector {
  width: 12px;
  height: 2px;
  background: var(--border);
  flex-shrink: 0;
  align-self: center;
}

.iw-pipeline-connector--fixcycle {
  background: repeating-linear-gradient(
    90deg,
    var(--warning, #f59e0b) 0px,
    var(--warning, #f59e0b) 3px,
    transparent 3px,
    transparent 6px
  );
}
```

---

## Verification

After implementing, verify with:

```bash
make lint
make format-check
make type-check
make test-unit
```

All must pass. If `make css` reports "Nothing to be done", that is expected — plain CSS
rules in `styles.css` do not require a Tailwind recompile.

Then visually check by opening the item detail page (e.g., an item in the iw-ai-core
project with fix cycles) and confirming:
1. Each step shows its ID (S01, S02, …) in a readable pill
2. Steps with `fix_cycle_count > 0` show additional amber `↺SXX` pills
3. Duration appears inside each pill (where available)
4. No broken duration row below the strip
5. `data-step-count` attribute is present on the outer container

---

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "CR-00039",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/components/step_pipeline.html",
    "dashboard/templates/fragments/item_overview.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {
    "format": "ok|fail",
    "typecheck": "ok|fail",
    "lint": "ok|fail"
  },
  "tests_passed": true,
  "test_summary": "make test-unit: N passed",
  "blockers": [],
  "notes": ""
}
```
