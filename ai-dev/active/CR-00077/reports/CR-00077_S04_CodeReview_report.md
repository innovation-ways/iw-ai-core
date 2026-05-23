# CR-00077 S04 Code Review Report — Overlap details popup (read-only)

**Reviewer**: code-review-impl  
**Step**: S04  
**Files reviewed**:  
- `dashboard/templates/fragments/batch_overlap_modal.html`  
- `dashboard/templates/fragments/batch_items_rows.html`  
- `dashboard/templates/pages/project/batch_detail.html`  
- `dashboard/static/styles.css` (new appended rules, lines 550–690)

---

## Pre-flight quality gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed (incl. `scripts/check_templates.py`) |
| `make format-check` | ✅ 867 files already formatted |
| `make typecheck` | ✅ Success: no issues in 275 source files |
| `make quality` | ✅ Passed |

---

## Findings

### ✅ 1. Single source of truth — PASS (no issues)

`batch_overlap_modal.html` is the sole template that renders the S03 read-only overlap modal. `overlap_modal.html` (added in the same merge by CR-00078) is a **separate template** used by the CR-00078 ignore flow — it renders different markup with different context (per-file `hx-post` ignore buttons, `ignored_set`, `batch_id` in context). No duplication of modal markup.

### ✅ 2. Reuse of pill markup — PASS (no issues)

The S03 trigger button in `batch_items_rows.html` preserves all four no-regression contract items:
- `title="{{ row.scope_status.pill_tooltip }}"` — ✅
- `aria-label="{{ row.scope_status.pill_text }}"` — ✅
- The same SVG lock icon (`<svg>...</svg>`) — ✅
- Visible text: `{{ row.scope_status.pill_text }}` — ✅

No regression.

### ✅ 3. Esc handler scope — PASS (no issues)

The IIFE in `batch_overlap_modal.html` registers `document.addEventListener('keydown', onKey)` and cleans up via `document.removeEventListener('keydown', onKey)` inside the `close()` function. No handler leak.

### ✅ 4. Modal root — PASS (no issues)

`batch_detail.html` has exactly one `<div id="overlap-modal-root"></div>` (line 13), placed outside the polled items fragment. No duplicate IDs. `queue.html` was not modified.

### ✅ 5. CSS append-only — PASS (no issues)

New CR-00078 rules (`/* CR-00078: overlap modal ignore controls */`) and CR-00077 rules (`/* CR-00077: Overlap details modal */`) are appended to `styles.css`. No existing rules were deleted. All class names use `iw-modal-*` and `iw-overlap-pill-*` prefixes. No collision with pre-existing `.modal`, `.dialog`, or `.overlay` classes.

### ✅ 6. Tailwind discipline — PASS (no issues)

No changes to `dashboard/static/styles.tailwind.css` or `tailwind.config.js`. The trigger button uses `class="iw-overlap-pill-trigger inline-flex items-center gap-1 text-xs text-warning font-medium"` — all the `inline-flex` etc. Tailwind utilities are already in the compiled `styles.css` (they're global Tailwind utilities), and `iw-overlap-pill-trigger` is the new plain-CSS class. No new Tailwind classes that require JIT recompile.

### ✅ 7. No read-only contract violations — PASS (no issues)

`batch_overlap_modal.html` contains no `<form>`, `<input>`, `hx-post`, or `hx-delete`. The `{% if empty %}` branch renders the 404 message safely. CR-00078's `overlap_modal.html` does contain POST actions — that is correct and intentional (CR-00078 owns those).

### ✅ 8. Jinja `%`-format-filter rule — PASS (no issues)

The `scripts/check_templates.py` linter ran and passed. No `str.format`-style `"{} ..."|format(...)` pattern found in any template. The `batch_items_rows.html` template uses the correct `"%dm%02ds"|format(mins, secs)` pattern in its existing duration formatting.

### ✅ 9. 404 path — PASS (no issues)

`batch_overlap_modal.html`'s `{% if empty %}` branch renders without any `sections` variable — only `empty`, `held_item_id`, and `current_project` are required. The 404 endpoint (lines 877–882 of `batches.py`) passes `{"empty": True, "held_item_id": held_item_id, "current_project": project}` — all required context is provided.

### ✅ 10. Read-only script tag review — PASS (no issues)

The inline `<script>` block in `batch_overlap_modal.html` only manipulates the modal's own DOM:
- Reads `#overlap-modal-root` — ✅
- Adds Esc listener and backdrop/close handlers — ✅
- Clears modal content on close — ✅
- No fetch, no post, no state write — ✅

### ✅ 11. Trigger URL survives live refresh — PASS (no issues)

The trigger button's `hx-get` embeds `{{ batch.id }}`. S01 correctly added `batch` to the `batch_items_fragment` context (lines 698–709 of `batches.py`). `batch` is resolved in both render paths: initial page load (`batch_detail.html`) and htmx refresh (`batch_items_fragment`). No silent break after Items-tab live refresh.

---

## Summary

| Check | Severity | Result |
|-------|----------|--------|
| Single source of truth | CRITICAL | ✅ PASS |
| Duplicate modal markup | CRITICAL | ✅ PASS |
| Read-only contract (no POST in S03 modal) | CRITICAL | ✅ PASS |
| Jinja `%`-format-filter rule | CRITICAL | ✅ PASS |
| Duplicate `#overlap-modal-root` ID | CRITICAL | ✅ PASS |
| Esc handler leak | HIGH | ✅ PASS |
| Trigger URL survives live refresh | HIGH | ✅ PASS |
| Pill contract (title, aria-label, SVG, text) | MAJOR | ✅ PASS |
| CSS append-only, no collisions | MEDIUM | ✅ PASS |
| Tailwind discipline | MEDIUM | ✅ PASS |
| 404 path without `sections` variable | MEDIUM | ✅ PASS |
| Script read-only scope | MEDIUM | ✅ PASS |

**Finding counts: 0 CRITICAL · 0 HIGH · 0 MEDIUM · 0 LOW**

All 11 review points pass. The S03 template and CSS implementation is clean.

---

## Notes

- `queue.html` (Queue page, out of scope per the design doc Notes) was not touched — confirmed.
- `batch_items_rows.html`'s `{% else %}` branch (empty `items`) is unchanged; it renders `No items in this batch.` with colspan 8 and no `scope_status` — no regression.
- The IIFE in `batch_overlap_modal.html` uses `[data-iw-modal-root]` as a selector for the backdrop — this is the `data-iw-modal-root` attribute on the inner `<div>` inside the backdrop, not the mount div. This is intentional and correct; the close-on-backdrop-click and Esc handlers are correctly scoped to the modal instance.