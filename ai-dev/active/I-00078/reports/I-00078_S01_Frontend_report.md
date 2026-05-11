# I-00078 S01 Frontend-impl Report

## Summary

Implemented all four dashboard-chrome fixes for I-00078:

1. **Dark-mode scrollbar contrast (AC1)** — `theme.css`
2. **Pipeline strip scrollbar spacing (AC2)** — `styles.css`
3. **Single vertical scrollbar + dynamic viewport (AC3)** — `base.html` + `styles.css`
4. **Full-width footer with theme toggle inside (AC4)** — `base.html`

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/static/theme.css` | Added `--scrollbar-thumb` / `--scrollbar-thumb-hover` CSS vars to `:root` and `.dark`; repainted `::-webkit-scrollbar-thumb` using the new vars; added `::-webkit-scrollbar-thumb:hover`; added Firefox `scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb) transparent;` fallback on `*`; added `overflow: hidden` to `html, body`. |
| `dashboard/static/styles.css` | Added `.h-dvh { height: 100dvh; }` utility (dynamic viewport unit, not in prebuilt Tailwind); added `padding-bottom: 0.5rem` to `.iw-pipeline-strip`. |
| `dashboard/templates/base.html` | Restructured body into a `flex flex-col h-dvh` shell: stale-banner (`flex-shrink-0`) at top, `[sidebar + content]` row in middle, new `<footer class="w-full">` below as a full-width sibling of the sidebar; moved theme toggle from sidebar bottom into footer (left side); moved htmx poll from `<footer>` to an inner `<div class="flex-1">` so the poll's `innerHTML` swap doesn't clobber the toggle button. |
| `dashboard/templates/fragments/llm_usage_footer.html` | No changes needed — fragment already renders only the meters; layout adjustments (`ml-auto` version label) were already correct for the wider footer. |
| `tests/dashboard/test_i00078_layout.py` | New file with 5 tests (footer-full-width, theme-toggle-in-footer, dynamic-viewport, pipeline-padding, dark-scrollbar). |

---

## Test Results

```
tests/dashboard/test_i00078_layout.py::test_i00078_footer_is_full_width_sibling_of_sidebar PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_theme_toggle_lives_in_footer_not_sidebar PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_shell_uses_dynamic_viewport_height PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_pipeline_strip_has_scrollbar_spacing PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_dark_scrollbar_uses_high_contrast_thumb PASSED
======================== 5 passed in 6.06s =========================
```

---

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | `ruff format` auto-fixed the test file; no other files changed |
| `make typecheck` | `Success: no issues found in 240 source files` |
| `make lint` | All checks passed (including `scripts/check_templates.py` and `node --check`) |

---

## Key Implementation Notes

### Scrollbar colours
- Light mode thumb: `#c4c4c8` / hover: `#a8a8ad` — mid-grey, visible but not jarring against `--background: #fbfbfb`
- Dark mode thumb: `#5c5d65` / hover: `#74757d` — clearly lighter than `--background: #323339` (dark bg) while staying muted
- Both are in the existing palette family and consistent with `--muted-foreground` range

### Dynamic viewport
- `.h-dvh { height: 100dvh; }` appended as plain CSS to `styles.css` since Tailwind CLI is broken in worktrees
- `html, body { height: 100%; overflow: hidden; }` in `theme.css` — body never scrolls; only `<main>` does

### Footer / htmx swap
- The `hx-get` / `hx-trigger` / `hx-swap="innerHTML"` moved from `<footer>` to an inner `<div class="flex-1 flex items-center gap-3 sm:gap-4">` so htmx refreshes only the meters, not the theme-toggle button
- The fragment `llm_usage_footer.html` renders only the meters — unchanged

### Sidebar behaviour
- `toggleSidebar()` JS and mobile backdrop/transform behaviour preserved — `<aside id="sidebar">` keeps its `fixed … lg:static` classes inside the `[sidebar + content]` row
