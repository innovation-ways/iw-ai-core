# CR-00078_S08_Frontend_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S08
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
No migration work.

## Input Files

- `ai-dev/active/CR-00078/CR-00078_CR_Design.md` (§2, §3, frontend changes)
- `dashboard/templates/fragments/batch_overlap_modal.html` (introduced by CR-00077 — extend it; do NOT replace)
- `dashboard/static/styles.css` (already has CR-00077 modal CSS; append new rules)

## Output Files

- `dashboard/templates/fragments/batch_overlap_modal.html` (modified)
- `dashboard/static/styles.css` (modified)
- `ai-dev/active/CR-00078/reports/CR-00078_S08_Frontend_report.md`

## Requirements

### 1. Per-row Ignore button

Inside the existing `{% for section in sections %}` ... `{% for glob in section.globs %}` loop, change the `<li>` markup from CR-00077 to:

```jinja
<li class="iw-modal-file-row">
  <code>{{ glob }}</code>
  <button type="button"
          class="iw-modal-ignore-btn"
          hx-post="/project/{{ project_id }}/batch/{{ batch_id }}/overlap/{{ held_item_id }}/ignore"
          hx-vals='{"blocking_item_id": "{{ section.blocking_item_id }}", "file_pattern": "{{ glob }}"}'
          hx-target="closest .iw-modal-file-row"
          hx-swap="outerHTML">Ignore</button>
</li>
```

Note: CR-00077 did NOT pass `batch_id` to the template — you must update CR-00077's GET endpoint context to include it (this is a small fix in CR-00078 scope because the endpoint URL needs it for both POST endpoints). Add `"batch_id": batch_id` to the template context in `dashboard/routers/batches.py`'s overlap GET endpoint as part of S08's frontend deliverable (this is a one-line dict addition — not a daemon change, not a model change, well within scope).

### 2. Master "Ignore all & start" button

After the `{% endfor %}` of the sections loop, inside `.iw-modal-body` but at the bottom, add:

```jinja
{% if sections %}
<footer class="iw-modal-footer">
  <button type="button"
          class="iw-modal-ignore-all-btn"
          hx-post="/project/{{ project_id }}/batch/{{ batch_id }}/overlap/{{ held_item_id }}/ignore-all"
          hx-target="#overlap-modal-root"
          hx-swap="innerHTML"
          hx-confirm="Ignore every remaining overlap for {{ held_item_id }} in this batch and let it start?">
    Ignore all &amp; start
  </button>
</footer>
{% endif %}
```

The `{% if sections %}` guard prevents the master button from rendering on the 404/empty path (CR-00077 renders an empty body in that case).

### 3. CSS

Append to `dashboard/static/styles.css`:

```css
/* CR-00078: ignore controls */
.iw-modal-file-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--border, #e5e7eb);
}
.iw-modal-file-row:last-child { border-bottom: none; }
.iw-modal-file-row code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  word-break: break-all;
  flex: 1 1 auto;
}
.iw-modal-ignore-btn {
  background: var(--secondary, #f3f4f6);
  color: var(--secondary-foreground, #111);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 4px;
  font-size: 0.75rem;
  padding: 2px 8px;
  cursor: pointer;
  white-space: nowrap;
}
.iw-modal-ignore-btn:hover { background: var(--muted, #e5e7eb); }
.iw-modal-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border, #e5e7eb);
  display: flex;
  justify-content: flex-end;
  background: var(--muted, #fafafa);
}
.iw-modal-ignore-all-btn {
  background: var(--primary, #2563eb);
  color: var(--primary-foreground, #fff);
  border: none;
  border-radius: 4px;
  font-size: 0.85rem;
  padding: 6px 14px;
  cursor: pointer;
  font-weight: 600;
}
.iw-modal-ignore-all-btn:hover { opacity: 0.9; }
```

The existing CR-00077 `.iw-modal-file-list li { padding: 4px 0; border-bottom: ... }` rule MAY conflict with `.iw-modal-file-row` if CR-00077 chose `<li>`-level borders. Inspect the existing CSS; if there's a conflict, **add a more-specific selector** (e.g., `.iw-modal-file-list .iw-modal-file-row { ... }`) rather than editing CR-00077's rule.

### 4. Do NOT touch

- The script tag at the bottom of `batch_overlap_modal.html` (Esc handler from CR-00077) — it still works.
- The `{% if empty %}` branch — the master button should not appear there (the `{% if sections %}` guard handles this).
- `dashboard/templates/fragments/batch_items_rows.html` — the pill trigger is CR-00077's; this CR does not change it.
- `dashboard/templates/pages/project/queue.html` — same.
- `dashboard/static/styles.tailwind.css` — never.

## Project Conventions

- Read `dashboard/CLAUDE.md` plain-CSS-fallback rule. Plain CSS only — no Tailwind recompile.
- htmx form-encoded fields via `hx-vals` ship as application/x-www-form-urlencoded by default — S06's endpoints handle this.

## TDD Requirement

`tdd_red_evidence`: `"n/a — template + CSS edits; behaviour tested by S10 dashboard tests + S19 browser_verification."`

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck` (only if your one-line context change in batches.py touches typed code)
3. `make lint` (includes `scripts/check_templates.py`)

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "frontend-impl",
  "work_item": "CR-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/batch_overlap_modal.html",
    "dashboard/static/styles.css",
    "dashboard/routers/batches.py (one-line context addition: batch_id passed to the modal template)"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "make lint passed (incl. scripts/check_templates.py)",
  "tdd_red_evidence": "n/a — template + CSS edits; behaviour tested by S10 + S19",
  "blockers": [],
  "notes": "Confirmed no Tailwind input edit; added batch_id to GET overlap template context."
}
```
