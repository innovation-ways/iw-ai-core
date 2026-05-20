# CR-00065_S05_Frontend_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S05
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No schema changes in this step.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00065 --json`
- `ai-dev/active/CR-00065/CR-00065_CR_Design.md` — Design document
- `dashboard/templates/fragments/item_steps_table.html` — step table template (add Logs column)
- `dashboard/routers/items.py` — new session-log endpoint added in S04
- `dashboard/CLAUDE.md` — dashboard conventions
- `dashboard/static/styles.css` — for any new CSS (append plain CSS here; do NOT run `make css`)

## Task

Add the Logs icon column and its popup modal to the item steps table.

---

### 1. Update `dashboard/templates/fragments/item_steps_table.html`

**Add column header** — immediately after the `<th>Status</th>` header (currently line 13):

```html
<th class="px-4 py-2 text-left font-medium text-muted-foreground">Logs</th>
```

**Add column cell** — in each `<tr>` row (after the Status `<td>`), add a Logs cell:

```html
<td class="px-4 py-2">
  {% if not step.is_synthetic and step.run_count > 0 %}
  <button
    class="session-log-trigger p-1 rounded hover:bg-muted/60 transition-colors text-muted-foreground hover:text-foreground"
    aria-label="View logs for step {{ step.step_id }}"
    hx-get="/project/{{ item.project_id }}/api/item/{{ item.id }}/step/{{ step.step_id }}/session-log"
    hx-target="#session-log-modal-body"
    hx-trigger="click"
    hx-on::after-request="document.getElementById('session-log-modal').classList.remove('hidden')"
  >
    <!-- terminal / log icon -->
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h10M4 14h8M4 18h6"/>
    </svg>
  </button>
  {% else %}
  <span class="text-muted-foreground/30">—</span>
  {% endif %}
</td>
```

**Add modal overlay** — once, outside the `<table>` element, at the bottom of the fragment:

```html
<!-- CR-00065: Session log modal -->
<div id="session-log-modal"
     class="hidden fixed inset-0 z-50 flex items-center justify-center bg-black/50"
     role="dialog"
     aria-modal="true"
     aria-labelledby="session-log-modal-title">
  <div class="bg-card border border-border rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col mx-4">
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <h2 id="session-log-modal-title" class="text-sm font-semibold">Agent Session Log</h2>
      <button
        class="p-1 rounded hover:bg-muted/60 transition-colors text-muted-foreground"
        aria-label="Close log viewer"
        onclick="document.getElementById('session-log-modal').classList.add('hidden')"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>
    <div id="session-log-modal-body" class="overflow-y-auto flex-1 p-4 text-xs font-mono">
      <span class="text-muted-foreground">Select a step to view its log.</span>
    </div>
  </div>
</div>
<script>
// Close modal on Escape key or backdrop click
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') document.getElementById('session-log-modal').classList.add('hidden');
});
document.getElementById('session-log-modal').addEventListener('click', function(e) {
  if (e.target === this) this.classList.add('hidden');
});
</script>
```

---

### 2. Create `dashboard/templates/fragments/session_log_popup_content.html`

This is the htmx fragment returned by the S04 API endpoint and injected into `#session-log-modal-body`.

```html
{% if is_live %}
<div hx-get="/project/{{ project_id }}/api/item/{{ item_id }}/step/{{ step_id }}/session-log"
     hx-target="#session-log-modal-body"
     hx-trigger="every 3s"
     hx-swap="innerHTML">
{% endif %}

<div class="mb-2 flex items-center gap-2 text-muted-foreground border-b border-border pb-2">
  <span class="font-semibold text-foreground">{{ step_id }}</span>
  <span>run #{{ run_number }}</span>
  {% if cli_tool %}<span class="px-1.5 py-0.5 rounded bg-muted text-xs">{{ cli_tool }}</span>{% endif %}
  {% if is_live %}<span class="text-xs text-primary animate-pulse">● live</span>{% endif %}
</div>

{% if segments %}
  {% for seg in segments %}
    {% if seg.type == "compaction" %}
      <div class="my-2 border-t border-dashed border-border text-center text-muted-foreground text-xs py-1">{{ seg.text }}</div>
    {% elif seg.type == "assistant" %}
      <div class="mb-2">
        <span class="text-xs font-semibold text-primary">assistant</span>
        <pre class="mt-0.5 whitespace-pre-wrap text-foreground">{{ seg.text }}</pre>
      </div>
    {% elif seg.type == "thinking" %}
      <details class="mb-2 text-muted-foreground">
        <summary class="cursor-pointer text-xs font-semibold hover:text-foreground">thinking (click to expand)</summary>
        <pre class="mt-1 whitespace-pre-wrap text-xs">{{ seg.text }}</pre>
      </details>
    {% elif seg.type == "tool_call" %}
      <div class="mb-1 px-2 py-1 rounded bg-muted/50 border-l-2 border-primary/50">
        <span class="text-xs font-semibold text-primary">tool </span>
        <span class="text-xs">{{ seg.text }}</span>
      </div>
    {% elif seg.type == "tool_result" %}
      <details class="mb-2">
        <summary class="cursor-pointer text-xs text-muted-foreground hover:text-foreground">result (click to expand)</summary>
        <pre class="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">{{ seg.text }}</pre>
      </details>
    {% elif seg.type == "error" %}
      <div class="mb-2 px-2 py-1 rounded bg-destructive/10 border border-destructive/30 text-destructive text-xs">
        <span class="font-semibold">error: </span>{{ seg.text }}
      </div>
    {% elif seg.type == "log" %}
      <pre class="whitespace-pre-wrap text-foreground text-xs">{{ seg.text }}</pre>
    {% endif %}
  {% endfor %}
{% else %}
  <p class="text-muted-foreground text-xs">
    {% if error_message %}
      Step ended with: {{ error_message }}
    {% else %}
      No log content available yet.
    {% endif %}
  </p>
{% endif %}

{% if is_live %}</div>{% endif %}
```

---

### 3. CSS additions (`dashboard/static/styles.css`)

Append these rules directly (do NOT run `make css`):

```css
/* CR-00065: session log modal */
#session-log-modal pre {
  max-height: 200px;
  overflow-y: auto;
}
#session-log-modal details[open] pre {
  max-height: 400px;
}
```

---

### Quality gates

```bash
make lint
```

(The lint gate runs `scripts/check_templates.py` to catch Jinja2 format-filter issues. Ensure no `"{}"|format(...)` patterns are introduced — use `"%s"|format(...)` style.)

## Output Files

- `dashboard/templates/fragments/item_steps_table.html` — Logs column added
- `dashboard/templates/fragments/session_log_popup_content.html` — new popup content fragment
- `dashboard/static/styles.css` — appended CSS rules

## Subagent Result Contract

```bash
uv run iw step-done CR-00065 --step S05 \
  --report ai-dev/work/CR-00065/reports/CR-00065_S05_Frontend_report.md
```

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "CR-00065",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/templates/fragments/item_steps_table.html",
    "dashboard/templates/fragments/session_log_popup_content.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "lint passed",
  "blockers": [],
  "notes": ""
}
```
