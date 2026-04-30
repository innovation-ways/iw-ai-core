# F-00074_S05_Frontend_prompt

**Work Item**: F-00074 — Keep-Alive Scheduler
**Step**: S05
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. This step does not touch alembic.

## Input Files

- `ai-dev/active/F-00074/F-00074_Feature_Design.md` — read first
- `ai-dev/active/F-00074/reports/F-00074_S03_CodeReview_report.md`
- `dashboard/templates/base.html` — base layout; `system_links` array at line ~106
- `dashboard/templates/pages/system/status.html` — System page to model after visually
- `dashboard/templates/pages/system/coverage.html` — example with timeline-like width math
- `dashboard/static/styles.css` — Tailwind output; existing utility classes
- `dashboard/CLAUDE.md` — htmx + Jinja conventions

## Output Files

- New: `dashboard/templates/pages/system/keep_alive.html`
- New: `dashboard/templates/fragments/keep_alive_slots.html`
- New: `dashboard/templates/fragments/keep_alive_slot_row.html`
- New: `dashboard/templates/fragments/keep_alive_timeline.html`
- New: `dashboard/templates/fragments/keep_alive_runs.html`
- Modified: `dashboard/templates/base.html` (add nav entry)
- `ai-dev/active/F-00074/reports/F-00074_S05_Frontend_report.md`

## Context

Implement all Jinja2 templates for the Keep-Alive Scheduler System page. htmx handles all slot add/delete/toggle actions and timeline refreshes — no full page reloads. The visual centrepiece is a 24-hour CSS timeline bar showing coverage blocks, built with pure Tailwind utility classes (no inline styles, no JS charting library).

## Requirements

### 1. Add nav entry to `base.html`

Locate the `system_links` list (around line 106). Add `('/system/keep-alive', 'Keep-Alive')` between `('/system/coverage', 'Test Coverage')` and `('/system/all-active', 'All Active Work')`. Match indentation exactly.

### 2. Create `dashboard/templates/pages/system/keep_alive.html`

Full-page template extending `base.html`. Context variables provided by the API:
- `config`: `KeepAliveConfig` object
- `slots`: `list[KeepAliveSlot]`
- `runs`: `list[KeepAliveRun]` (last 10)
- `available_models`: `["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"]`
- `available_durations`: `[3, 4, 5, 6]`

Page structure (top to bottom):

#### A. Page header
```
h1: Keep-Alive Scheduler
p (subtitle): Automatically maintains Claude Max usage windows by sending scheduled messages.
```

#### B. Config card
A bordered card with a form that POSTs to `/api/keep-alive/config` via htmx.

```html
<form hx-post="/api/keep-alive/config"
      hx-target="#config-form"
      hx-swap="outerHTML"
      id="config-form">
  <!-- Model selector -->
  <label>Claude Model</label>
  <select name="model">
    {% for m in available_models %}
      <option value="{{ m }}" {% if m == config.model %}selected{% endif %}>{{ m }}</option>
    {% endfor %}
  </select>

  <!-- Window duration selector -->
  <label>Usage Window Duration</label>
  <select name="window_duration_hours">
    {% for h in available_durations %}
      <option value="{{ h }}" {% if h == config.window_duration_hours %}selected{% endif %}>{{ h }} hours</option>
    {% endfor %}
  </select>

  <button type="submit">Save Config</button>
</form>
```

The form must serialize as JSON to match the `ConfigPayload` Pydantic model. Use `hx-ext="json-enc"` or send as `application/x-www-form-urlencoded` with the router accepting form data (coordinate with S04 — if S04 uses `BaseModel` for JSON, use `hx-headers='{"Content-Type": "application/json"}'` and `hx-vals` pattern).

> **Note**: Check the S04 report for whether config POST expects JSON or form data. Match what S04 implemented. If S04 used Pydantic BaseModel (JSON), use `hx-ext="json-enc"` (already available in htmx CDN used by the dashboard).

#### C. 24-hour Timeline card

A horizontal bar representing 00:00–23:59 divided into coverage blocks.

**Structure**:
```html
<div id="timeline-container">
  <div class="text-sm font-medium mb-2">Coverage Timeline</div>

  <!-- Hour labels: 00 06 12 18 24 -->
  <div class="relative flex justify-between text-xs text-muted-foreground mb-1">
    <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
  </div>

  <!-- Timeline bar -->
  <div class="relative h-8 rounded bg-red-100 dark:bg-red-900/30 overflow-hidden" id="timeline-bar">
    {% include "fragments/keep_alive_timeline.html" %}
  </div>
</div>
```

The red background represents uncovered time (gap). Green blocks overlay it for covered periods.

The timeline refreshes automatically via **htmx OOB swap** — the slot mutation routes (POST/DELETE/PATCH) return the timeline fragment as an `hx-swap-oob="innerHTML"` element targeting `#timeline-bar` (see S04). No extra `hx-get` on the timeline container is needed; the primary slot-list response already carries the OOB update.

#### D. Slots section

```html
<div class="flex items-center justify-between">
  <h2>Scheduled Slots</h2>
  <!-- Add slot form — use json-enc so SlotPayload(BaseModel) receives JSON body -->
  <form hx-post="/api/keep-alive/slots"
        hx-ext="json-enc"
        hx-target="#slot-list"
        hx-swap="outerHTML">
    <input type="text" name="time_hhmm" placeholder="HH:MM" pattern="\d{2}:\d{2}"
           title="24-hour time, e.g. 05:00" required>
    <button type="submit">Add Slot</button>
  </form>
</div>

<div id="slot-list">
  {% include "fragments/keep_alive_slots.html" %}
</div>
```

#### E. Last 10 Runs table

```html
<div id="runs-section">
  <h2>Recent Executions</h2>
  <div id="runs-table"
       hx-get="/api/keep-alive/runs"
       hx-trigger="every 60s"
       hx-swap="innerHTML">
    {% include "fragments/keep_alive_runs.html" %}
  </div>
</div>
```

### 3. Create `dashboard/templates/fragments/keep_alive_timeline.html`

Renders green coverage blocks inside the timeline bar. This fragment is included in the page AND returned by htmx slot mutations.

Context: `slots` (list[KeepAliveSlot]), `config` (KeepAliveConfig).

**Algorithm** (implement as Jinja2 template logic):

For each enabled slot:
- Parse `slot.time_hhmm` → `hh`, `mm`
- `start_minutes = hh * 60 + mm`
- `duration_minutes = config.window_duration_hours * 60`
- `end_minutes = start_minutes + duration_minutes`

If `end_minutes <= 1440` (no midnight wrap):
- Render one block: `left% = start_minutes / 1440 * 100`, `width% = duration_minutes / 1440 * 100`

If `end_minutes > 1440` (crosses midnight):
- Block 1 (from start to midnight): `left% = start_minutes / 1440 * 100`, `width% = (1440 - start_minutes) / 1440 * 100`
- Block 2 (midnight to end): `left% = 0`, `width% = (end_minutes - 1440) / 1440 * 100`

Each block:
```html
<div class="absolute top-0 h-full bg-green-400 dark:bg-green-600 opacity-80 rounded"
     style="left: {{ left_pct }}%; width: {{ width_pct }}%"
     title="{{ slot.time_hhmm }} + {{ config.window_duration_hours }}h"></div>
```

**Implementation note**: Jinja2 doesn't have `.split(':')` on integers. Use the `time_hhmm` string split:
```jinja
{% set parts = slot.time_hhmm.split(':') %}
{% set hh = parts[0] | int %}
{% set mm = parts[1] | int %}
```

Show an empty-state message if no enabled slots exist:
```html
{% if not slots or not slots | selectattr("enabled") | list %}
  <span class="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">No active slots</span>
{% endif %}
```

### 4. Create `dashboard/templates/fragments/keep_alive_slots.html`

Renders the full slot list table. Context: `slots` (list[KeepAliveSlot]), `config`.

```html
<div id="slot-list">
  {% if not slots %}
    <p class="text-sm text-muted-foreground py-4">No slots configured. Add a time above.</p>
  {% else %}
    <table class="w-full text-sm">
      <thead class="bg-muted/40 text-left">
        <tr>
          <th class="px-4 py-2">Time</th>
          <th class="px-4 py-2">Status</th>
          <th class="px-4 py-2">Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for slot in slots %}
          {% include "fragments/keep_alive_slot_row.html" %}
        {% endfor %}
      </tbody>
    </table>
  {% endif %}
</div>
```

### 5. Create `dashboard/templates/fragments/keep_alive_slot_row.html`

Renders a single slot `<tr>`. Context: `slot` (KeepAliveSlot).

```html
<tr id="slot-row-{{ slot.id }}" class="border-t">
  <td class="px-4 py-3 font-mono font-medium">{{ slot.time_hhmm }}</td>
  <td class="px-4 py-3">
    {% if slot.enabled %}
      <span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Active</span>
    {% else %}
      <span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground">Disabled</span>
    {% endif %}
  </td>
  <td class="px-4 py-3 flex gap-2">
    <!-- Toggle button -->
    <button hx-patch="/api/keep-alive/slots/{{ slot.id }}/toggle"
            hx-target="#slot-row-{{ slot.id }}"
            hx-swap="outerHTML"
            class="text-xs px-2 py-1 rounded border hover:bg-muted transition-colors">
      {% if slot.enabled %}Disable{% else %}Enable{% endif %}
    </button>
    <!-- Delete button -->
    <button hx-delete="/api/keep-alive/slots/{{ slot.id }}"
            hx-target="#slot-list"
            hx-swap="outerHTML"
            hx-confirm="Delete slot {{ slot.time_hhmm }}?"
            class="text-xs px-2 py-1 rounded border border-destructive text-destructive hover:bg-destructive/10 transition-colors">
      Delete
    </button>
  </td>
</tr>
```

### 6. Create `dashboard/templates/fragments/keep_alive_runs.html`

Renders the last-10-runs table body. Context: `runs` (list[KeepAliveRun]).

Status badge colours:
- `success` → green
- `retried_success` → amber
- `failed` → red
- `retried_failed` → red

```html
{% if not runs %}
  <p class="text-sm text-muted-foreground py-4">No executions yet.</p>
{% else %}
  <table class="w-full text-sm">
    <thead class="bg-muted/40 text-left">
      <tr>
        <th class="px-4 py-2">Fired At</th>
        <th class="px-4 py-2">Slot</th>
        <th class="px-4 py-2">Status</th>
      </tr>
    </thead>
    <tbody>
      {% for run in runs %}
        <tr class="border-t">
          <td class="px-4 py-2 font-mono text-xs">{{ run.fired_at.strftime('%Y-%m-%d %H:%M:%S') }}</td>
          <td class="px-4 py-2">{{ run.slot_time }}</td>
          <td class="px-4 py-2">
            {% set badge = {
              'success': ('bg-green-100 text-green-800', 'Success'),
              'retried_success': ('bg-amber-100 text-amber-800', 'Retry OK'),
              'failed': ('bg-red-100 text-red-800', 'Failed'),
              'retried_failed': ('bg-red-100 text-red-800', 'Failed (retry)'),
            } %}
            {% set cls, label = badge.get(run.status, ('bg-muted text-muted-foreground', run.status)) %}
            <span class="inline-block px-2 py-0.5 rounded text-xs font-medium {{ cls }}">{{ label }}</span>
          </td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
{% endif %}
```

### 7. Run `make css`

After all templates are created, run:
```bash
make css
```
Confirm `dashboard/static/styles.css` is updated. Commit the updated file.

## Project Conventions

- htmx-only — no client-side JS framework.
- Tailwind only — no inline `style=` attributes (the timeline blocks are an exception: `left` and `width` percentages MUST use `style=` because Tailwind cannot construct dynamic percentage classes safely).
- Fragment templates MUST NOT extend `base.html`.
- Match the visual language of `pages/system/status.html` (rounded cards, muted borders, Tailwind utility classes).

## Pre-flight Quality Gates

1. `make format` (auto-fix)
2. `make lint`
3. `make css` — no new errors
4. `make typecheck`
5. Visual check: open `/system/keep-alive` in a running dashboard and verify page renders with no Jinja errors.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "F-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/pages/system/keep_alive.html",
    "dashboard/templates/fragments/keep_alive_slots.html",
    "dashboard/templates/fragments/keep_alive_slot_row.html",
    "dashboard/templates/fragments/keep_alive_timeline.html",
    "dashboard/templates/fragments/keep_alive_runs.html",
    "dashboard/templates/base.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {"format": "ok", "lint": "ok", "css": "ok", "typecheck": "ok"},
  "tests_passed": true,
  "test_summary": "no new tests in this step; existing suite unchanged",
  "blockers": [],
  "notes": ""
}
```
