# CR-00077 S03 Frontend Report — Overlap details popup (read-only)

## What was done

Implemented all frontend changes for CR-00077 — the clickable Held pill, modal root mount point, modal fragment, and plain CSS — completing the frontend-impl role for step S03.

## Files changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/batch_items_rows.html` | Wrapped the `held` branch pill in a `<button type="button">` with `hx-get`, `hx-target="#overlap-modal-root"`, `hx-swap="innerHTML"`. Moved `title` and `aria-label` from the `<td>` to the button. `policy_allowed` branch left unchanged. |
| `dashboard/templates/fragments/batch_overlap_modal.html` | Full rewrite from S01 stub to the production modal fragment — includes backdrop, container, header, close button, `{% if empty %}` branch, `{% else %}` branch with per-section grouping, and an IIFE JS block for Esc/backdrop/close dismissal. Does NOT extend `base.html`. |
| `dashboard/templates/pages/project/batch_detail.html` | Added `<div id="overlap-modal-root"></div>` as the htmx swap target, placed between the existing `#confirm-dialog` and the existing `#overlap-modal-overlay` (CR-00078). |
| `dashboard/static/styles.css` | Appended plain CSS for all modal classes: `.iw-modal-backdrop`, `.iw-modal-container`, `.iw-modal-header`, `.iw-modal-close`, `.iw-modal-body`, `.iw-modal-section`, `.iw-modal-section-header`, `.iw-modal-file-list`, `.iw-modal-empty`, plus `.iw-overlap-pill-trigger` and its `:focus-visible` style. |

## Implementation notes

- **`{{ batch.id }}` in trigger URL** — S01 added `batch` to the `batch_items_fragment` context, so `{{ batch.id }}` resolves correctly on both the initial page load and after each htmx live-refresh of the Items tab.
- **JS IIFE re-binds on every htmx swap** — the `htmx:afterSwap` handler in `batch_detail.html` (`detail.target.id === 'overlap-modal-inner'`) shows the existing CR-00078 overlay wrapper. The IIFE inside `batch_overlap_modal.html` handles dismissal independently; it cleans up its own Esc listener via `removeEventListener` on close.
- **Existing CR-00078 overlay is preserved** — `batch_detail.html` already had `#overlap-modal-overlay` (a full-page overlay with `#overlap-modal-inner` as the content div). The S03 `#overlap-modal-root` div is positioned before this overlay, and htmx swaps content into it. The CR-00078 JS listens for `detail.target.id === 'overlap-modal-inner'` — this does NOT conflict with S03's `#overlap-modal-root` swap target.
- **CSS selector discipline** — `.iw-modal-*` classes follow the same naming convention as CR-00078's pre-existing `.iw-modal-*` classes already at the bottom of `styles.css`, so both CRs share the same namespace (intentional per the design doc: "CR-00078 adds Ignore controls to the `<li>` file rows without rewriting the layout").

## Pre-flight quality gates

| Gate | Result |
|------|--------|
| `make format` | ✅ 866 files already formatted |
| `make lint` | ✅ All checks passed (incl. `scripts/check_templates.py` — no `str.format`-style `format` filter misuse) |
| `make typecheck` | ✅ Success: no issues in 275 source files |
| `make quality` | ✅ Passed (runs format-check + lint + typecheck) |

## TDD evidence

`n/a — template + CSS edits only, no behavioural production logic. Behaviour is tested by S05 (dashboard + browser tests).`

## Notes

- Modal partial is designed for CR-00078 extension: the `{% for glob in section.globs %}` loop produces `<li>` elements that CR-00078 can extend via Jinja2 block inheritance to inject per-row Ignore buttons.
- The Queue-page `Held` pill (`queue.html`) is intentionally untouched per the design doc Notes.
- `tailwind.config.js` and `dashboard/static/styles.tailwind.css` were not modified.