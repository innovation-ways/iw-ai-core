# F-00082_S03_Frontend_prompt

**Work Item**: F-00082 -- Dashboard Cancel Buttons (Batch + Work Item)
**Step**: S03
**Agent**: Frontend (`frontend-impl`)

---

## ⛔ Docker is off-limits

Standard policy. No docker invocations from templates / static / tests.

## ⛔ Migrations: agents generate, daemon applies

No migrations. Pure template + CSS work.

## Input Files

- **Runtime state**: `uv run iw item-status F-00082 --json`.
- `ai-dev/active/F-00082/F-00082_Feature_Design.md` (read in full).
- `ai-dev/active/F-00082/F-00082_Functional.md`.
- S01 report: `ai-dev/active/F-00082/reports/F-00082_S01_API_report.md` — defines the form-field names and endpoint contract you must hit.
- S02 review report (must have OVERALL: PASS or its fixes applied).
- Existing templates to modify:
  - `dashboard/templates/components/confirm_dialog.html`
  - `dashboard/templates/fragments/confirm_action.html` (do NOT break — non-cancel actions still use it)
  - `dashboard/templates/fragments/batch_detail_header.html`
  - `dashboard/templates/pages/project/item_detail.html`
  - `dashboard/templates/pages/project/batches.html`
- New template to create: `dashboard/templates/fragments/confirm_action_form.html`
- Service-layer for visibility rules: `orch/cancel.CANCELLABLE_BATCH_STATUSES`, `orch/cancel.CANCELLABLE_WORK_ITEM_STATUSES`, `orch/cancel._ACTIVE_BATCH_STATUSES`.

## Output Files

- `ai-dev/active/F-00082/reports/F-00082_S03_Frontend_report.md`.

## Context

Read `dashboard/CLAUDE.md` first. Key rules for this step:

- Fragments under `templates/fragments/` MUST NOT extend `base.html`.
- Tailwind is prebuilt — run `make css` after adding new classes; the generated file is committed.
- Use the shared `iwClipboard.copy(...)` helper for any clipboard interaction (not applicable here).
- htmx POSTs return HTML fragments that swap into `hx-target` — no JSON, no JS.

## Requirements

### 1. Extend `components/confirm_dialog.html` to support an optional form

Add a new macro parameter `form_html=""` (default empty string). When set, the macro renders a `<form method="post" action="{{ confirm_url }}">` that wraps the body and the confirm button. The cancel/close button (the secondary) stays outside the form so dismissing doesn't submit.

Importantly: **all existing call sites of `confirm_dialog` must remain byte-equivalent when `form_html` is empty.** The S02-equivalent review for S03 will run a diff on the generated HTML for an existing approve / pause / resume confirm — any byte change there is a regression.

A clean way to do this:

```jinja
{% macro confirm_dialog(title, description, confirm_url, confirm_method='post', confirm_label='Confirm', danger=True, form_html='') %}
<div class="fixed inset-0 …">
  <div class="bg-card …">
    <h3>{{ title }}</h3>
    {% if description %}<p>…</p>{% endif %}
    {% if form_html %}
      <form method="post" action="{{ confirm_url }}" hx-post="{{ confirm_url }}" hx-swap="none" …>
        {{ form_html | safe }}
        <div class="flex gap-3 mt-4 justify-end">
          <button type="button" onclick="…">Cancel</button>
          <button type="submit" class="{{ … }}">{{ confirm_label }}</button>
        </div>
      </form>
    {% else %}
      <div class="flex gap-3 mt-4 justify-end">
        … existing buttons …
      </div>
    {% endif %}
  </div>
</div>
{% endmacro %}
```

### 2. Create `dashboard/templates/fragments/confirm_action_form.html`

This fragment is returned by the confirm-dialog GET endpoint when `action == "cancel"`. It uses the extended macro with a `form_html` string containing:

- `<label>Reason: <textarea name="reason" rows="3">{{ default_reason }}</textarea></label>`
- `<label><input type="checkbox" name="{{ reset_field_name }}" value="true"> {{ reset_field_label }}</label>`

Use Tailwind classes consistent with other modal forms in `dashboard/templates/` (textarea: `w-full mt-2 px-3 py-2 border border-border rounded text-sm bg-background text-foreground`; checkbox container: `mt-3 flex items-center gap-2 text-sm`). After adding classes, run `make css`.

The S01 confirm-dialog handler passes `default_reason`, `reset_field_name`, `reset_field_label` in the context — use those variable names exactly.

### 3. Expand cancel button visibility in `batch_detail_header.html`

The current template only renders a Cancel button for `planning` and `approved`. Extend the conditional to render for every status in `CANCELLABLE_BATCH_STATUSES`:

```
planning, approved, executing, paused, blocked, publish_failed
```

Status is already available as `batch_status` in the template context (verify by reading the file). Use a single `{% if batch_status in ['planning','approved','executing','paused','blocked','publish_failed'] %}` rather than a long if/elif chain.

The button POSTs to `/project/{{ current_project.id }}/api/confirm-batch/cancel/{{ batch.id }}` (GET to fetch the modal), same as today.

For terminal statuses (`completed`, `completed_with_errors`, `publishing`, `published`, `archived`, `cancelled`) — render NO Cancel button.

### 4. Add cancel button to `item_detail.html`

Locate the item-detail header (where Approve / Unapprove / Restart actions live today). Add a Cancel button section:

- If `item.status` is in `CANCELLABLE_WORK_ITEM_STATUSES` (`approved`, `in_progress`, `failed`, `paused`):
  - If the item is in an active batch (`active_batch_id` set with non-terminal status): render a **disabled** button with class `disabled:opacity-50 cursor-not-allowed` and a hint paragraph below: `<p class="text-xs text-muted-foreground">Belongs to active batch <a href="…/batch/{{ active_batch_id }}" class="underline">{{ active_batch_id }}</a> — cancel the batch instead.</p>`.
  - Else: render an enabled htmx button that GETs `…/api/confirm-item/cancel/{{ item.id }}` into `#confirm-dialog`.
- Else: render nothing.

You will need the item's active batch info in the template context. Check whether the existing `items.item_detail` route already exposes it (`grep` for `active_batch` in `dashboard/routers/items.py`). If yes, use it as-is. If no, add it to the route's context dict — minimal addition, document in your report.

### 5. Add per-row quick-cancel to `batches.html`

In the per-row action column, for rows where `batch.status` is in `CANCELLABLE_BATCH_STATUSES`, render a small icon-button:

```html
<button type="button"
        onclick="confirm('Cancel {{ batch.id }}? This is destructive.') && htmx.ajax('POST', '/project/{{ current_project.id }}/api/batch/{{ batch.id }}/cancel', {values:{reason:'cancelled from batches list'}, swap:'none'})"
        class="text-destructive hover:opacity-80 text-sm"
        title="Cancel batch">
  ✕
</button>
```

(Tailwind: use existing classes from neighbouring buttons; the ✕ glyph is one option — match the visual weight of the existing Archive/Pause icons. If the table uses lucide-icons, use `<i data-lucide="x-circle">`.)

For terminal statuses, render nothing in the cancel-icon slot — do NOT render a disabled icon (visual noise on the list view).

### 6. Run `make css`

After adding any new Tailwind classes, run `make css`. Commit the regenerated `dashboard/static/styles.css`.

### 7. Update `dashboard/CLAUDE.md`

The router table entry for `actions.py` already mentions "cancel". Update the **description copy** for that entry to make clear it's the full-teardown variant: replace the existing line with:

```
| `actions.py` | htmx endpoints: approve / unapprove / cancel (full teardown via `orch.cancel`) / pause / resume / restart / restart-merge / full-restart item; batch approve/pause/resume/cancel (full teardown)/archive; create batch from selection |
```

### 8. Tests in this step

S03 is the Frontend implementation step. Write small Jinja2 render anchor tests in `tests/dashboard/` — ≤4 tests:

1. `test_confirm_dialog_macro_renders_form_when_form_html_set` — direct macro render via the Jinja2 environment.
2. `test_confirm_dialog_macro_byte_identical_when_form_html_empty` — render the macro with no form_html and assert it matches an inline-expected snapshot of the existing approve-confirm output (or use `templates.get_template(...).render(...)` and diff against a known string).
3. `test_batch_detail_header_renders_cancel_button_for_executing_batch`.
4. `test_item_detail_renders_disabled_cancel_when_in_active_batch`.

S05 (Tests) extends these with full Boundary coverage and AC matching.

## TDD Requirement

RED first. For each anchor test, write it, see it fail with a real `AssertionError`, then implement. Capture the RED line.

## Pre-flight Quality Gates

Before reporting complete:
1. `make format`.
2. `make typecheck` (no Python files probably touched, but verify).
3. `make lint` — includes the Jinja2 template `%`-style format check (`scripts/check_templates.py`). Pay attention: avoid `"{}m{}s"|format(m,s)` style — use `%`-style.
4. `make css` — committed.

## Test Verification

```bash
uv run pytest tests/dashboard/test_actions_cancel_*.py -v
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Frontend",
  "work_item": "F-00082",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/components/confirm_dialog.html",
    "dashboard/templates/fragments/confirm_action_form.html",
    "dashboard/templates/fragments/batch_detail_header.html",
    "dashboard/templates/pages/project/item_detail.html",
    "dashboard/templates/pages/project/batches.html",
    "dashboard/static/styles.css",
    "dashboard/CLAUDE.md",
    "tests/dashboard/test_confirm_dialog_form.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_confirm_dialog_form.py::test_confirm_dialog_macro_renders_form_when_form_html_set — AssertionError: …",
  "blockers": [],
  "notes": "Confirm with `grep -r 'confirm_dialog' dashboard/templates` that every existing call site still works (snapshot test in S05)."
}
```
