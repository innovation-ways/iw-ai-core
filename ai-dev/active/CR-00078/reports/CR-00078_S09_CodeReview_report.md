# CR-00078 S09 — Code Review (Implementation Review)

**Step**: S09
**Agent**: code-review-impl
**Work Item**: CR-00078 — Per-batch ignore overlap & force-start
**Date**: 2026-05-23

## What Was Reviewed

S08's frontend implementation (CR-00078_S08_Frontend_prompt.md) adds per-file "Ignore" buttons and a master "Ignore all & start" button to the overlap modal, with the required CSS.

Files changed by S08 (per the contract):
- `dashboard/templates/fragments/overlap_modal.html` — modified
- `dashboard/static/styles.css` — modified
- `dashboard/routers/batches.py` — one-line context addition

Additional implementation files in the worktree (from earlier steps):
- `dashboard/routers/actions.py` — POST /ignore and /ignore-all endpoints
- `orch/daemon/batch_manager.py` — overlap filter integration
- `orch/daemon/scope_overlap.py` — overlap detection logic
- `orch/db/models.py` — `BatchOverlapIgnore` model
- `orch/db/migrations/versions/3a3dfec7bfbd_cr_00078_add_batch_overlap_ignore.py`
- `tests/unit/test_daemon_overlap_filter.py`

---

## Review: 8-Point Scope Checklist

### 1. `hx-target="closest .iw-modal-file-row"` — ✅ CORRECT

Template line 19:
```html
hx-target="closest .iw-modal-file-row"
```
This is a scoped selector relative to the button. On a row-by-row "Ignore" click, only the nearest `.iw-modal-file-row` (the `<li>`) is removed — no global selector risk.

### 2. Master button gated by `{% if sections %}` — ✅ CORRECT

The `<footer class="iw-modal-footer">` with the "Ignore all & start" button is wrapped in `{% if sections %}` (lines 27–37). The `{% else %}` branch (lines 39–45) renders only an empty-message `<div>` with no footer. The master button is never rendered in the empty-state path.

### 3. `batch_id` in template context — ✅ PRESENT

The `overlap_modal()` GET endpoint (batches.py lines 854–862) explicitly passes `"batch_id": batch_id` in the context dict. URL construction `/batch/{{ batch_id }}/overlap/...` will resolve correctly.

### 4. CSS prefix `iw-modal-*` — ✅ CORRECT

All new classes use the `iw-modal-` prefix: `.iw-modal-file-row`, `.iw-modal-ignore-btn`, `.iw-modal-footer`, `.iw-modal-ignore-all-btn`. No collision with existing dashboard classes.

### 5. CSS cascade: `.iw-modal-file-list li` vs `.iw-modal-file-row` — ✅ NO CONFLICT

- The existing `.iw-modal-file-list` rule (`list-style: none; padding: 0; margin: 0;`) is inherited by child `<li>` elements — this is a container style, not a per-row style.
- The new `.iw-modal-file-row` rule explicitly sets `display: flex; align-items: center; justify-content: space-between; gap: 12px;` on the `<li>` elements.
- These are **complementary**: the container resets list styles while the row element applies flex layout. No CSS specificity conflicts. The merged result is the intended layout.

### 6. No enclosing `<form>` — ✅ CORRECT

The "Ignore" button has `hx-post` directly on the `<button type="button">` element with `hx-vals='{"blocking_item_id": "...", "file_pattern": "..."}'` for form-encoded field passing. No `<form>` element was introduced. The "Ignore all" button also POSTs directly.

### 7. `hx-confirm` text is meaningful — ✅ PRESENT

```html
hx-confirm="Ignore every remaining overlap for {{ held_item_id }} in this batch and let it start?"
```
The `held_item_id` interpolation is direct Jinja2 variable substitution. No escaping issues in the confirmation string. The text clearly describes the action and its consequence.

### 8. No `str.format`-style `format` filter — ✅ VERIFIED

Ran `make lint` → `scripts/check_templates.py`: **zero errors**. Jinja2 templates use only `%`-style format filters (`"%dm%02ds"|format(m, s)` in batch_items_rows.html) and the new template contains no `str.format`-style patterns.

---

## Additional Observations

- **Autoescape is enabled** (Jinja2 `select_autoescape`) for the templates directory. Attributes in `hx-vals` use double-quoted JSON string values — HTML entities in `held_item_id` would be escaped but this is safe for the use case (item IDs are alphanumeric).
- **POST endpoint correctness** — `ignore_single_overlap` in `actions.py` correctly uses `hx-swap="outerHTML"` returning an empty response, which htmx interprets as removing the target row. `ignore_all_overlaps` uses `hx-swap="innerHTML"` on `#overlap-modal-root` returning empty, which htmx replaces the modal content with nothing (effectively closing it).
- **Idempotency** — Both endpoints use `INSERT ... ON CONFLICT DO NOTHING` via `pg_insert` — repeated POSTs are safely no-ops.
- **Scope consistency** — `_get_item_scope_events` in actions.py uses the same 300-second window as `_get_scope_statuses` in batches.py, ensuring ignore-all operates on the same event data as the modal display.
- **Security consideration** — `project_id` in the htmx URLs comes from the URL path (route parameter), not from template data. The `project_id` variable in the template context is consistent with the URL path (both from `current_project.id`). No path traversal or URL injection risk.

---

## Pre-flight Results

| Gate | Result |
|------|--------|
| `make format` | ✅ 851 files already formatted |
| `make typecheck` | ✅ Success: no issues in 275 source files |
| `make lint` | ✅ All checks passed |

---

## Verdict

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |

**No issues found.** All 8 review points pass. Pre-flight gates green. The S08 frontend implementation is clean.