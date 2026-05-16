# CR-00056_S08_Frontend_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step**: S08
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — focus on `AC4–AC8`
- `dashboard/templates/fragments/item_steps_table.html` — the table you're modifying
- `dashboard/templates/fragments/activity_text_modal.html` — the reference modal pattern (a11y, focus trap, Escape, backdrop dismiss)
- `dashboard/static/styles.css` — read existing `.activity-modal-*` rules (search for `activity-modal`); add parallel `.prompt-modal-*` rules if needed
- `dashboard/static/clipboard.js` — the `window.iwClipboard.copy(text, button)` helper
- `dashboard/templates/fragments/prompt_text_modal.html` — placeholder from S06; you'll flesh it out
- `dashboard/CLAUDE.md` — clipboard helper rule, fragment template rule, Tailwind fallback rule
- Pre-state screenshot: `ai-dev/active/CR-00056/evidences/pre/CR-00056_before_no_prompt_column.png`

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S08_Frontend_report.md`

## Context

You're building the visible half of CR-00056: a new **Prompt** column in the steps table that opens an accessible modal with the prompt text.

The route to call (`/project/{pid}/item/{iid}/step/{step_id}/prompt-modal`) was built in S06 and returns the modal HTML fragment. Your job:

1. Add the new column header and cell to the steps-table template.
2. Replace the placeholder fragment template with the production-quality modal.
3. Add CSS to style it.
4. Add JS for focus trap, Escape, backdrop dismiss, copy-to-clipboard.

Read `dashboard/CLAUDE.md` first.

## Requirements

### 1. Add the Prompt column to `dashboard/templates/fragments/item_steps_table.html`

Between the `Model` header (line 11) and the `Status` header (line 12), insert:

```jinja
<th class="px-4 py-2 text-left font-medium text-muted-foreground">Prompt</th>
```

Between the Model cell (closing `</td>` at line 94) and the Status cell (line 95), insert a new cell:

```jinja
<td class="px-4 py-2">
  {% if step.is_synthetic or not step.has_prompt %}
    <span class="text-xs text-muted-foreground">—</span>
  {% else %}
    <button
      type="button"
      class="prompt-view-trigger text-xs px-2 py-0.5 rounded border border-border bg-background hover:bg-muted/40 transition-colors"
      aria-label="View prompt for step {{ step.step_id }}"
      hx-get="/project/{{ item.project_id }}/item/{{ item.id }}/step/{{ step.step_id }}/prompt-modal"
      hx-target="#prompt-modal-mount"
      hx-swap="innerHTML">
      View
    </button>
  {% endif %}
</td>
```

Also update the `colspan` on the "No steps found" empty-state row (currently `colspan="8"` at line 157) to match the new column count.

Add a mount point near the end of the file (inside the wrapping div, after the table), or in `dashboard/templates/pages/...` wherever this fragment is included from. The simplest approach: append `<div id="prompt-modal-mount"></div>` to the bottom of `item_steps_table.html` so the modal lives in the same fragment.

### 2. Build the production `dashboard/templates/fragments/prompt_text_modal.html`

Replace the S06 placeholder with the full modal, modeled on `activity_text_modal.html`:

```jinja
{# Modal fragment returned by /item/{item_id}/step/{step_id}/prompt-modal — adapted from activity_text_modal.html #}
<div id="prompt-modal-overlay" class="prompt-modal-backdrop" aria-hidden="false"></div>
<div id="prompt-modal" class="prompt-modal" role="dialog" aria-modal="true" aria-labelledby="prompt-modal-title" aria-hidden="false" tabindex="-1">
  <div class="prompt-modal-inner">
    <header class="prompt-modal-header">
      <div>
        <h3 id="prompt-modal-title" class="prompt-modal-title">
          Step {{ step.step_id }} · {{ step.agent_label }}
        </h3>
        {% if prompt_file_display %}
          <p class="prompt-modal-subtitle text-xs text-muted-foreground">{{ prompt_file_display }}</p>
        {% endif %}
      </div>
      <button type="button" class="modal-close" aria-label="Close modal">×</button>
    </header>
    <div class="prompt-modal-body">
      {% for section in sections %}
        <section class="prompt-modal-section">
          <div class="prompt-modal-section-header">
            <h4 class="prompt-modal-section-title">{{ section.label }}</h4>
            <button
              type="button"
              class="prompt-modal-copy text-xs px-2 py-0.5 rounded border border-border bg-background hover:bg-muted/40"
              data-prompt-copy-section="{{ loop.index0 }}">
              Copy
            </button>
          </div>
          <pre class="prompt-modal-pre" data-prompt-section-body="{{ loop.index0 }}">{{ section.text }}</pre>
        </section>
      {% endfor %}
    </div>
  </div>
</div>
<script>
  (function () {
    if (window.__promptModalInit) { window.__promptModalInit(); return; }
  })();
</script>
```

**Notes**:

- The trailing `<script>` block calls a singleton init function defined in the external `dashboard/static/prompt_modal.js` file (see step 4). This pattern keeps the JS shippable once and re-init-able when htmx swaps a new modal in.
- `{{ section.text }}` is escaped by Jinja autoescape — DO NOT use `|safe`. Prompts may contain `<script>` literals.
- The modal opens immediately when swapped in (`aria-hidden="false"`). The trigger button is the only thing that needs to "open" it; htmx swapping a fresh fragment into `#prompt-modal-mount` IS the open action.

### 3. Add CSS to `dashboard/static/styles.css`

Per `CLAUDE.md`, when `make css` reports "Nothing to be done" or the Tailwind CLI fails, append plain CSS rules directly to `dashboard/static/styles.css`. Either reuse the existing `.activity-modal-*` rules (rename selectors in the template above to match) OR add parallel `.prompt-modal-*` rules. The styling goal:

- Backdrop: `position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 50;`
- Modal: `position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; z-index: 51;`
- Modal inner: `max-width: 64rem; width: 90vw; max-height: 85vh; display: flex; flex-direction: column;` — wider than activity modal because prompts are long.
- Modal body: `overflow-y: auto; padding: 1rem;`
- `.prompt-modal-pre`: `white-space: pre-wrap; word-break: break-word; font-family: monospace; font-size: 0.8125rem; max-height: 50vh; overflow-y: auto; padding: 0.75rem; background: var(--muted); border-radius: 0.375rem;`
- `.prompt-modal-section + .prompt-modal-section { margin-top: 1rem; }`
- `.prompt-modal-section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }`

Match variable names (`var(--muted)`, `var(--border)`, etc.) used elsewhere in `styles.css`.

If you prefer to **reuse** `.activity-modal-*` instead of adding parallel rules, change the template selectors accordingly. Either approach is acceptable; document the choice in the report.

### 4. Add JS at `dashboard/static/prompt_modal.js`

Implement an init function that:

- Locates `#prompt-modal-mount` and observes for child insertion (MutationObserver) OR uses htmx's `htmx:afterSwap` event listener for that target.
- When a fresh modal appears:
  - Save the currently-focused element (`document.activeElement`) for later restore.
  - Apply a focus trap inside `#prompt-modal` (Tab loops within focusable elements, Shift+Tab in reverse).
  - Focus the first focusable element (probably the close button).
  - Disable body scroll (`document.body.style.overflow = 'hidden'`).
- On dismiss (close button click, backdrop click, or Escape key):
  - Clear `#prompt-modal-mount` (`mount.innerHTML = ''`).
  - Restore body scroll.
  - Restore focus to the saved trigger.
- Copy button (`.prompt-modal-copy`):
  - On click, find the matching `data-prompt-section-body` `<pre>` element.
  - Read its `textContent`.
  - Call `window.iwClipboard.copy(text, button)` — the helper handles success/failure feedback ("Copied" / "Copy failed") by mutating the button label.

Reference `dashboard/templates/fragments/activity_text_modal.html` (lines 14-89) for the focus-trap pattern — adapt it but factor it into the external `.js` file so the modal template stays clean.

**Wire it into the base template**: add `<script defer src="/static/prompt_modal.js"></script>` near the existing `clipboard.js` include (find it via `grep -n "clipboard.js" dashboard/templates/base.html` or similar).

### 5. NEVER call `navigator.clipboard.writeText` directly

Per `dashboard/CLAUDE.md`: use `window.iwClipboard.copy(text, button)`. Direct `navigator.clipboard` calls throw silently outside secure contexts (the dev host `iw-dev-01` is HTTP, not HTTPS).

### 6. Jinja format-filter discipline

Per `CLAUDE.md`: Jinja `format` filter must be `%`-style (`"%dm%02ds"|format(m, s)`), never `{}`-style. There's no formatting in this template right now, but if you add any, use `%`-style.

## Project Conventions

Read `dashboard/CLAUDE.md` carefully. Specific re-emphasis:

- Fragment templates MUST NOT extend `base.html`.
- Clipboard buttons MUST use `window.iwClipboard.copy(text, button)`.
- Tailwind: prefer Tailwind classes where possible; fall back to plain CSS in `styles.css` if `make css` fails (CR-00033).

## TDD Requirement

This step has no behaviour beyond DOM/CSS — testing it via unit tests is awkward. Use `tdd_red_evidence` with `"n/a — frontend template + CSS + JS only; behavioural verification is the qv-browser step S22"`.

The S11 (tests-impl) step will add a TestClient assertion that the rendered table HTML contains the new column header — that covers the static-render side.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck
make lint
```

Note: lint includes `scripts/check_templates.py` which catches Jinja `format`-filter misuse.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_prompt_modal_route.py -v
```

Visually verify in a browser if your worktree has an isolated stack — otherwise rely on S22.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "frontend-impl",
  "work_item": "CR-00056",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/templates/fragments/item_steps_table.html",
    "dashboard/templates/fragments/prompt_text_modal.html",
    "dashboard/static/styles.css",
    "dashboard/static/prompt_modal.js",
    "dashboard/templates/base.html"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed",
  "tdd_red_evidence": "n/a — frontend template + CSS + JS only; behavioural verification is the qv-browser step S22",
  "blockers": [],
  "notes": "Chose <reuse | new> .prompt-modal CSS; copy uses iwClipboard helper."
}
```
