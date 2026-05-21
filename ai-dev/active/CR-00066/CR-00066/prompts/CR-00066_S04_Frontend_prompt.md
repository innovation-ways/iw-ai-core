# CR-00066_S04_Frontend_prompt

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S04
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00066 --json`
- `ai-dev/active/CR-00066/CR-00066_CR_Design.md` — Design document
- `dashboard/routers/items.py` — items router, `StepInfo` dataclass, `_build_step_data()`
- `dashboard/templates/fragments/item_steps_table.html` — step table (Logs column added by CR-00065)
- `orch/db/models.py` — `StepRun.context_tokens_peak`, `StepRun.context_tokens_last`, `AgentRuntimeOption.context_window_tokens`
- `dashboard/CLAUDE.md` — conventions
- `dashboard/static/styles.css` — append plain CSS here; do NOT run `make css`

## Task

Extend the items router to pass context token data to the template, then add the Context column with a color-coded progress bar.

---

### 1. Extend `dashboard/routers/items.py`

**In the `StepInfo` dataclass** (find the class that holds per-step display data), add:

```python
context_tokens_peak: int | None = None
context_tokens_last: int | None = None
context_window_tokens: int | None = None
```

**In `_build_step_data()` or the equivalent query function**, extend the `last_run_map` query to also fetch `StepRun.context_tokens_peak` and `StepRun.context_tokens_last` from the last StepRun row. Then, for each step, resolve `context_window_tokens` from `AgentRuntimeOption.context_window_tokens` via the step's `agent_runtime_option_id` (already loaded in `runtime_options`).

The `runtime_options` list is already available — look up by `step.runtime_option_id`:

```python
opt = next((o for o in runtime_options if o.id == step.runtime_option_id), None)
context_window_tokens = opt.context_window_tokens if opt else None
```

Populate the three new `StepInfo` fields accordingly.

---

### 2. Add a Jinja2 helper (or inline logic) for context display

In the template, compute:

```jinja2
{% set ctx_peak = step.context_tokens_peak %}
{% set ctx_window = step.context_window_tokens %}
{% if ctx_peak and ctx_window %}
  {% set ctx_pct = (ctx_peak / ctx_window * 100) | round(0) | int %}
  {% set ctx_color = "ctx-bar-green" if ctx_pct <= 60 else ("ctx-bar-yellow" if ctx_pct <= 85 else "ctx-bar-red") %}
{% elif ctx_peak %}
  {% set ctx_pct = none %}
  {% set ctx_color = "ctx-bar-green" %}
{% endif %}
```

---

### 3. Update `dashboard/templates/fragments/item_steps_table.html`

**Add column header** — immediately after the "Logs" `<th>` (added by CR-00065):

```html
<th class="px-4 py-2 text-left font-medium text-muted-foreground">Context</th>
```

**Add column cell** — after the Logs `<td>`, add:

```html
<td class="px-4 py-2 min-w-[90px]">
  {% set ctx_peak = step.context_tokens_peak %}
  {% set ctx_window = step.context_window_tokens %}
  {% if ctx_peak is not none %}
    {% if ctx_window %}
      {% set ctx_pct = (ctx_peak / ctx_window * 100) | round(0) | int %}
      {% if ctx_pct <= 60 %}{% set ctx_color_class = "ctx-bar-green" %}
      {% elif ctx_pct <= 85 %}{% set ctx_color_class = "ctx-bar-yellow" %}
      {% else %}{% set ctx_color_class = "ctx-bar-red" %}{% endif %}
      <div class="text-xs text-muted-foreground whitespace-nowrap">
        {{ (ctx_peak / 1000) | round(0) | int }}K / {{ (ctx_window / 1000) | round(0) | int }}K
      </div>
      <div class="ctx-bar-track mt-0.5">
        <div class="ctx-bar-fill {{ ctx_color_class }}" style="width: {{ [ctx_pct, 100] | min }}%"></div>
      </div>
      <div class="text-xs text-muted-foreground">{{ ctx_pct }}%</div>
    {% else %}
      <div class="text-xs text-muted-foreground">{{ (ctx_peak / 1000) | round(0) | int }}K</div>
    {% endif %}
  {% else %}
    <span class="text-muted-foreground/30">—</span>
  {% endif %}
</td>
```

**Note on Jinja2 `min` filter**: The `| min` filter in Jinja2 applies to iterables. Use `{% if ctx_pct > 100 %}{% set ctx_pct = 100 %}{% endif %}` instead of `[ctx_pct, 100] | min` to cap at 100%.

---

### 4. CSS additions (`dashboard/static/styles.css`)

Append these rules (do NOT run `make css`):

```css
/* CR-00066: context window progress bar */
.ctx-bar-track {
  height: 4px;
  width: 100%;
  background-color: var(--muted);
  border-radius: 2px;
  overflow: hidden;
}
.ctx-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}
.ctx-bar-green  { background-color: #22c55e; }
.ctx-bar-yellow { background-color: #f59e0b; }
.ctx-bar-red    { background-color: #ef4444; }
```

---

### Quality gates

```bash
make lint
make format-check
make typecheck
```

The `scripts/check_templates.py` lint check validates Jinja2 format filters. Ensure no `"{}"|format(...)` patterns in the template (use `"%s"|format(...)` or string concatenation instead).

## Output Files

- `dashboard/routers/items.py` — StepInfo extended; context data loaded
- `dashboard/templates/fragments/item_steps_table.html` — Context column added
- `dashboard/static/styles.css` — progress bar CSS appended

## Subagent Result Contract

```bash
uv run iw step-done CR-00066 --step S04 \
  --report ai-dev/work/CR-00066/reports/CR-00066_S04_Frontend_report.md
```

```json
{
  "step": "S04",
  "agent": "frontend-impl",
  "work_item": "CR-00066",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/routers/items.py",
    "dashboard/templates/fragments/item_steps_table.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "lint passed",
  "blockers": [],
  "notes": ""
}
```
