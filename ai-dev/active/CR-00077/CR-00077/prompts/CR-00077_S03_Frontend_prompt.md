# CR-00077_S03_Frontend_prompt

**Work Item**: CR-00077 -- Overlap details popup (read-only)
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
This CR adds no migrations.

## Input Files

- `ai-dev/active/CR-00077/CR-00077_CR_Design.md`
- `ai-dev/active/CR-00077/reports/CR-00077_S01_API_report.md`
- `dashboard/templates/fragments/batch_items_rows.html` (current Held pill)
- `dashboard/templates/pages/project/batch_detail.html` (parent page — modal root mount point)
- `dashboard/static/styles.css` (target for the appended CSS rules)

## Output Files

- `ai-dev/active/CR-00077/reports/CR-00077_S03_Frontend_report.md`
- Code: see Requirements.

## Requirements

### 1. Convert the Held pill into a clickable trigger

In `dashboard/templates/fragments/batch_items_rows.html` (line 43-49, the `held` branch of `scope_status.status`), wrap the existing pill markup in a `<button type="button">` with these htmx attributes:

```html
<button type="button"
        hx-get="/project/{{ current_project.id }}/batch/{{ batch.id }}/overlap/{{ row.item_id }}"
        hx-target="#overlap-modal-root"
        hx-swap="innerHTML"
        class="iw-overlap-pill-trigger inline-flex items-center gap-1 text-xs text-warning font-medium"
        title="{{ row.scope_status.pill_tooltip }}"
        aria-label="{{ row.scope_status.pill_text }}">
  <!-- existing SVG icon -->
  {{ row.scope_status.pill_text }}
</button>
```

For the `policy_allowed` branch, leave the markup unchanged — only the `held` branch becomes a trigger.

> **`{{ batch.id }}` is safe in both render paths.** `batch_items_rows.html` is
> rendered on the initial `batch_detail.html` page load **and** on every htmx
> Items-tab live refresh via `batch_items_fragment`. S01 adds `batch` to the
> `batch_items_fragment` context, so `{{ batch.id }}` resolves correctly after
> each refresh. Use `{{ batch.id }}` exactly as shown — do NOT hardcode the id
> and do NOT fall back to a value parsed from the row.

In `batch_items_rows.html` the `title` and `aria-label` attributes currently sit on the wrapping `<td>` (lines 40-42), not on the inner `<span>`. Move them onto the new `<button>` (as shown above) so the tooltip and accessible label stay on the interactive element. Preserve the existing icon SVG and spacing classes.

The project Queue page (`queue.html`) also renders this pill, but the Queue-page trigger is **out of scope** for this CR (see the design doc Notes) — do NOT modify `queue.html`.

### 2. Add the modal root

`batch_items_rows.html` is a `<tr>`-only fragment that the Items tab re-polls via htmx (`batch_detail.html:125`), so the modal mount point CANNOT live inside it. Add the swap target **once** to the parent page `dashboard/templates/pages/project/batch_detail.html`, outside the polled items fragment:

```html
<div id="overlap-modal-root"></div>
```

The id is the htmx swap target referenced by the trigger button's `hx-target`.

### 3. Create the modal fragment

Create `dashboard/templates/fragments/batch_overlap_modal.html`. It MUST NOT extend `base.html`.

Structure (Jinja pseudocode):

```jinja
{% if empty %}
<div class="iw-modal-backdrop" data-iw-modal-root>
  <div class="iw-modal-container" role="dialog" aria-modal="true" aria-labelledby="iw-modal-title">
    <header class="iw-modal-header">
      <h2 id="iw-modal-title">Overlap details — {{ held_item_id }}</h2>
      <button type="button" class="iw-modal-close" aria-label="Close">×</button>
    </header>
    <div class="iw-modal-empty">No overlap details available — the item may have been released since this page rendered.</div>
  </div>
</div>
{% else %}
<div class="iw-modal-backdrop" data-iw-modal-root>
  <div class="iw-modal-container" role="dialog" aria-modal="true" aria-labelledby="iw-modal-title">
    <header class="iw-modal-header">
      <h2 id="iw-modal-title">Overlap details — {{ held_item_id }}</h2>
      <button type="button" class="iw-modal-close" aria-label="Close">×</button>
    </header>
    <div class="iw-modal-body">
      {% for section in sections %}
      <section class="iw-modal-section">
        <h3 class="iw-modal-section-header">
          <a href="/project/{{ project_id }}/item/{{ section.blocking_item_id }}">
            {{ section.blocking_item_id }} — {{ section.blocking_item_title }}
          </a>
        </h3>
        <ul class="iw-modal-file-list">
          {% for glob in section.globs %}
          <li><code>{{ glob }}</code></li>
          {% endfor %}
        </ul>
      </section>
      {% endfor %}
    </div>
  </div>
</div>
{% endif %}
<script>
  (function(){
    const root = document.getElementById('overlap-modal-root');
    if (!root) return;
    const backdrop = root.querySelector('[data-iw-modal-root]');
    if (!backdrop) return;
    function close() { root.innerHTML = ''; document.removeEventListener('keydown', onKey); }
    function onKey(e) { if (e.key === 'Escape') close(); }
    backdrop.addEventListener('click', function(e) { if (e.target === backdrop) close(); });
    backdrop.querySelector('.iw-modal-close').addEventListener('click', close);
    document.addEventListener('keydown', onKey);
  })();
</script>
```

The IIFE re-binds itself each time htmx swaps the fragment in. The `removeEventListener` on close prevents stale Esc handlers from accumulating across opens.

### 4. Append plain CSS

Append to `dashboard/static/styles.css` (per `CLAUDE.md`'s plain-CSS-fallback rule — do NOT modify the Tailwind input file, do NOT run `make css`):

```css
/* CR-00077: Overlap details modal */
.iw-modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.45);
  z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.iw-modal-container {
  background: var(--background, #fff);
  color: var(--foreground, #111);
  border-radius: 8px;
  max-width: 680px; width: 90%;
  max-height: 80vh;
  display: flex; flex-direction: column;
  box-shadow: 0 10px 40px rgba(0,0,0,0.25);
}
.iw-modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border, #e5e7eb);
}
.iw-modal-header h2 { font-size: 0.95rem; font-weight: 600; margin: 0; }
.iw-modal-close {
  background: none; border: none; cursor: pointer;
  font-size: 1.25rem; line-height: 1; padding: 4px 8px;
  color: var(--muted-foreground, #6b7280);
}
.iw-modal-close:hover { color: var(--foreground, #111); }
.iw-modal-body { padding: 12px 16px; overflow-y: auto; }
.iw-modal-section + .iw-modal-section { margin-top: 16px; }
.iw-modal-section-header {
  font-size: 0.85rem; font-weight: 600; margin: 0 0 6px 0;
}
.iw-modal-section-header a { color: var(--primary, #2563eb); text-decoration: none; }
.iw-modal-section-header a:hover { text-decoration: underline; }
.iw-modal-file-list { list-style: none; padding: 0; margin: 0; }
.iw-modal-file-list li {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  padding: 4px 0;
  border-bottom: 1px dashed var(--border, #e5e7eb);
}
.iw-modal-file-list li:last-child { border-bottom: none; }
.iw-modal-empty {
  padding: 24px 16px;
  text-align: center;
  color: var(--muted-foreground, #6b7280);
  font-size: 0.85rem;
}
.iw-overlap-pill-trigger {
  background: none; border: none; padding: 0;
  cursor: pointer;
}
.iw-overlap-pill-trigger:focus-visible {
  outline: 2px solid var(--primary, #2563eb); outline-offset: 2px;
}
```

### 5. NEVER touch

- `dashboard/static/styles.tailwind.css` (Tailwind input) — leave alone.
- `tailwind.config.js` — leave alone.
- `dashboard/templates/pages/project/queue.html` — Queue-page trigger is out of scope.
- Any `orch/`, `executor/`, `tests/` file.

## Project Conventions

Read `dashboard/CLAUDE.md` for fragment / htmx / Tailwind rules. Read root `CLAUDE.md` for the plain-CSS-fallback rule and the prohibition on direct `navigator.clipboard.writeText` (not relevant here — no clipboard in this CR).

## TDD Requirement

`tdd_red_evidence`: `"n/a — template + CSS edits only, no behavioural production logic. Behaviour is tested by S05 (dashboard + browser tests)."`

## Pre-flight Quality Gates

1. `make format` — auto-fix formatting drift.
2. `make typecheck` — must report zero errors on touched Python files (there should be none from this step).
3. `make lint` — must report zero errors. `make lint` runs `scripts/check_templates.py` which catches `%`-format-filter misuse in Jinja2 (see root `CLAUDE.md`). Verify your new template does not introduce a `str.format`-style `format` filter.

## Test Verification

`make lint` and the template check are sufficient. Do not run `make test-unit` or `make test-integration` here — S05 owns tests.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "CR-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/batch_items_rows.html",
    "dashboard/templates/fragments/batch_overlap_modal.html",
    "dashboard/templates/pages/project/batch_detail.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "make lint passed (incl. scripts/check_templates.py)",
  "tdd_red_evidence": "n/a — template + CSS edits only, behaviour tested by S05",
  "blockers": [],
  "notes": "Modal partial structured so CR-00078 can add Ignore controls to the <li> file rows without rewriting the layout."
}
```
