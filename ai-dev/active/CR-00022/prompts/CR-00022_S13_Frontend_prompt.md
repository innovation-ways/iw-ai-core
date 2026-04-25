# CR-00022_S13_Frontend_prompt

**Work Item**: CR-00022
**Step**: S13
**Agent**: frontend-impl (Phase E — per-row Re-run, Mark-accepted, Apply-all-safe preview)

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + reports from S07, S09, S11
- `dashboard/templates/pages/project/oss.html`
- `dashboard/templates/fragments/oss_table.html`, `oss_finding_modal.html`
- `dashboard/routers/oss.py` (S09 endpoints)

## Output Files

- Modified: `dashboard/templates/pages/project/oss.html` (Apply-all-safe button trigger)
- New: `dashboard/templates/fragments/oss_apply_all_safe_modal.html`
- New: `dashboard/templates/fragments/oss_accept_modal.html` (or inline in oss_finding_modal)
- Modified: `dashboard/templates/fragments/oss_table.html` (Re-run icon per row)
- Modified: `dashboard/static/styles.css` (regenerated)
- `ai-dev/active/CR-00022/reports/CR-00022_S13_Frontend_report.md`

## Context

S11 built the table + modal. S13 adds the per-finding action surfaces:
1. A small `↻` icon on each row for Re-run-this-check.
2. A reason input that appears when the user clicks "Mark accepted" in the finding modal.
3. The Apply-all-safe preview dialog with deselectable per-file checkboxes.

## Requirements

### 1. Per-row Re-run icon

In `oss_table.html`, add an icon inside the Details cell beside the `…` button:

```html
<td class="px-3 py-2 text-right">
  <button type="button" class="oss-rerun-btn text-muted-foreground hover:text-foreground"
          data-check-id="{{ finding.check_id }}"
          aria-label="Re-run this check">↻</button>
  <button type="button" class="oss-details-btn text-muted-foreground hover:text-foreground"
          data-check-id="{{ finding.check_id }}"
          aria-label="Details">…</button>
</td>
```

JS handler POSTs to `/project/{id}/oss/recheck/{check_id}`, shows a small spinner on the icon, and updates the row in place when the SSE `row-update` event arrives. If the endpoint returns synchronously (S09 may implement either), patch the row from the response payload directly.

### 2. Mark-accepted reason flow

Two acceptable UX patterns:
- **Inline in modal**: Clicking "Mark accepted" in the finding modal expands an inline section with a `<textarea>` for the reason and a "Confirm" button. Submit POSTs to `/oss/accept/{check_id}` with `{finding_hash, reason}`.
- **Nested modal**: Open a small secondary modal (`oss_accept_modal.html`) over the finding modal with a textarea + Confirm/Cancel.

Recommend inline (simpler, no nested modal complexity). Implementation:

```html
<!-- inside oss_finding_modal.html footer area -->
<div class="oss-accept-form" hidden>
  <label class="block text-xs text-muted-foreground mb-1">
    Reason (required, ≥ 5 chars)
  </label>
  <textarea name="reason" rows="3" class="w-full text-sm border rounded p-2" minlength="5"></textarea>
  <div class="mt-2 flex gap-2 justify-end">
    <button type="button" class="oss-accept-cancel">Cancel</button>
    <button type="button" class="oss-accept-confirm">Confirm acceptance</button>
  </div>
</div>
```

JS: clicking "Mark accepted" reveals `.oss-accept-form`, focuses the textarea. Confirm POSTs to `/oss/accept/{check_id}`. On 200/204, close modal, move row to "Accepted" group, show toast "Accepted: {check_id}".

### 3. Apply-all-safe preview modal — `oss_apply_all_safe_modal.html`

Triggered by the page-level "Apply all safe" button.

1. POST to `/oss/apply-all-safe/preview` → returns array of recipes with target files.
2. Render a modal listing every file each recipe would touch, with a checkbox per file (all checked by default):

```html
<div class="oss-apply-all-modal" role="dialog" aria-modal="true">
  <header>
    <h3>Apply all safe fixes — preview</h3>
    <p class="text-xs text-muted-foreground">
      Writes to your working tree only. No branch is created. No commit is made.
      You can deselect any file before applying.
    </p>
  </header>
  <ul class="oss-apply-list">
    {% for item in items %}
      <li>
        <details>
          <summary>
            <input type="checkbox" name="check_id" value="{{ item.check_id }}" data-files='{{ item.target_files | tojson }}' checked>
            <span class="font-medium">{{ item.check_id }}</span>
            <span class="text-xs text-muted-foreground">— {{ item.target_files | length }} file(s)</span>
          </summary>
          <ul class="ml-6 text-xs">
            {% for path in item.target_files %}
              <li><label><input type="checkbox" name="file" value="{{ path }}" data-check-id="{{ item.check_id }}" checked> {{ path }}</label></li>
            {% endfor %}
          </ul>
          {% if item.notes %}<p class="ml-6 text-xs text-muted-foreground">{{ item.notes }}</p>{% endif %}
        </details>
      </li>
    {% endfor %}
  </ul>
  <footer>
    <button class="oss-apply-cancel">Cancel</button>
    <button class="oss-apply-confirm">Apply selected</button>
  </footer>
</div>
```

JS: on confirm, gather selected `check_id`s (a recipe is selected if at least one of its files is checked; if user unchecks all files for a recipe, omit it). POST to `/oss/apply-all-safe` with `{check_ids: [...]}`. On 200, close modal, refresh table via SSE.

**Per-file granularity caveat**: a recipe writes/patches all of its target files atomically. If the user unchecks individual files within a recipe, the simplest server semantics are "apply the recipe whole or skip it entirely". For v1, treat per-file checkboxes as informational (visual preview), and only honour the recipe-level checkbox at the top of each `<details>`. Document this in the report.

### 4. Toast notifications

After accept / apply / re-run, show a toast (existing pattern: `HX-Trigger: showToast: {message, type}`). Reuse the existing toast infrastructure from elsewhere in the dashboard.

### 5. Tailwind / JS lint

```bash
make css
make lint
```

### 6. Accessibility for the new modals

Same rules as S11: `role="dialog"`, focus trap, ESC closes, backdrop click closes, reason textarea keyboard-accessible.

## Project Conventions

- `dashboard/CLAUDE.md`: htmx-or-vanilla, fragments don't extend base.html, prebuilt Tailwind.
- Reuse existing modal CSS classes from S11 where possible; don't duplicate.

## TDD Requirement

UI tests via playwright-cli post-implementation (S27 covers end-to-end). For S13, take screenshots of:
- A row with the Re-run icon visible
- The accept reason form revealed in the modal
- The Apply-all-safe preview modal with checkboxes

Save under `ai-dev/active/CR-00022/evidences/post/`.

## Output / Report

Report contains:
- Files modified/added with diff summary
- Manual verification: triggered each new action (re-run, accept, apply-all-safe) and observed expected behavior
- Screenshots
- Per-file checkbox UX decision documented (informational vs functional)

End with `iw step-done` / `iw step-fail`.
