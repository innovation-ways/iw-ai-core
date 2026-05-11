# I-00078 S02 Code Review Report

## Reviewed Step: S01 (frontend-impl)

## Summary

S01 implemented all four dashboard layout fixes for I-00078. The implementation is correct and complete. All acceptance criteria are met. One formatting issue was found in the new test file (`ruff format` would reformat it), which is classified as MEDIUM (fixable) and does not block merge.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/base.html` | Restructured body into `flex flex-col h-dvh overflow-hidden` shell; stale-banner gets `flex-shrink-0`; outer shell changed from `flex h-screen overflow-hidden` to `flex flex-1 overflow-hidden`; sidebar theme-toggle removed; `<footer>` moved outside the `[sidebar+content]` flex row as a full-width sibling with `w-full`; `hx-get/hx-trigger/hx-swap` moved from `<footer>` to inner `<div class="flex-1 flex items-center gap-3 sm:gap-4">` (meters container). |
| `dashboard/static/theme.css` | Added `--scrollbar-thumb: #c4c4c8` / `--scrollbar-thumb-hover: #a8a8ad` to `:root`; added `--scrollbar-thumb: #5c5d65` / `--scrollbar-thumb-hover: #74757d` to `.dark`; `::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); }` + hover rule; Firefox fallback `* { scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb) transparent; }`; `html, body { height:100%; overflow:hidden; }`. |
| `dashboard/static/styles.css` | Added `.h-dvh { height: 100dvh; }` utility; added `padding-bottom: 0.5rem` to `.iw-pipeline-strip`. |
| `tests/dashboard/test_i00078_layout.py` | New file with 5 semantic tests covering all four ACs. |

**Not changed** (correctly out of scope): `dashboard/templates/components/step_pipeline.html`, `dashboard/static/theme-toggle.js`, `dashboard/templates/fragments/llm_usage_footer.html`.

---

## Pre-Review Lint & Format Gate

- **`make lint`**: All checks passed (ruff, node --check, scripts/check_templates.py).
- **`make format`**: `ruff format` would reformat `tests/dashboard/test_i00078_layout.py` — 1 file would be reformatted.

This is a **MEDIUM (fixable)** finding (convention: formatting in a new file added by the agent).

---

## Acceptance Criteria Verification

### AC1: Dark-mode scrollbars visible, hover state, Firefox fallback

| Check | Status |
|-------|--------|
| `--scrollbar-thumb` / `--scrollbar-thumb-hover` defined in `:root` | ✅ `#c4c4c8` / `#a8a8ad` |
| `--scrollbar-thumb` / `--scrollbar-thumb-hover` defined in `.dark` | ✅ `#5c5d65` / `#74757d` — contrasts with `#323339` bg |
| `::-webkit-scrollbar-thumb` uses `var(--scrollbar-thumb)` | ✅ (no longer uses `var(--border)`) |
| `::-webkit-scrollbar-thumb:hover` exists | ✅ uses `var(--scrollbar-thumb-hover)` |
| Firefox `scrollbar-width: thin` | ✅ on `*` selector |
| Firefox `scrollbar-color` | ✅ `var(--scrollbar-thumb) transparent` |

### AC2: Pipeline scrollbar separated from pills

`.iw-pipeline-strip` in `styles.css`:
```css
padding-bottom: 0.5rem;
```
✅ Non-zero `padding-bottom` declared.

### AC3: Exactly one vertical scrollbar; footer always visible

Layout structure in `base.html`:
- `<body class="… h-dvh overflow-hidden flex flex-col">` — dvh, body pinned
- Stale banner: `<div … flex-shrink-0>` — won't cause overflow
- Shell: `<div class="flex flex-1 overflow-hidden">` — `flex-1` absorbs available space
- `[sidebar + content]` row inside shell
- `<main class="flex-1 overflow-y-auto">` — the **only** vertical scroller
- `<footer class="flex-shrink-0 w-full">` — below the shell row, always visible

✅ `h-screen` wrapper gone; `html, body { overflow: hidden }` in `theme.css` prevents body scroll; `<main>` is the sole scroller.

### AC4: Full-width footer with theme toggle

| Check | Status |
|-------|--------|
| `<footer class="w-full">` is sibling of `[sidebar+content]` row, not nested inside content column | ✅ footer is outside `div class="flex flex-1 overflow-hidden"` |
| Theme toggle `onclick="toggleDarkMode()"` in `<footer>` | ✅ line 202-207: `<button onclick="toggleDarkMode()" …>` inside `<footer>` |
| `toggleDarkMode()` removed from sidebar | ✅ sidebar theme-toggle block removed (lines 154-162 old location gone) |
| `hx-get/hx-trigger/hx-swap` moved from `<footer>` to inner `<div>` | ✅ htmx attributes are on `<div class="flex-1 flex items-center gap-3 sm:gap-4">` (lines 209-212), not on `<footer>` — first poll will replace only the meters, not the toggle |
| Exactly one `id="theme-icon"` | ✅ `<span id="theme-icon">☾</span>` appears once, in the footer's toggle button |
| `theme-toggle.js` unchanged | ✅ file untouched |

### AC5: Regression test exists

`tests/dashboard/test_i00078_layout.py` exists with 5 tests. All pass (see Test Results below).

---

## Regression Risks

- **Mobile sidebar**: `toggleSidebar()` (lines 224-243 of new base.html), `#sidebar-backdrop`, `-translate-x-full lg:translate-x-0 lg:static` classes — all preserved. ✅
- **Stale-DB banner**: `flex-shrink-0` added to the banner div. Combined with `h-dvh` on body and `overflow:hidden` on `html,body`, the banner now fits without causing double-scroll. ✅
- **`llm_usage_footer.html`**: unchanged — still renders only meters, `ml-auto` pins version label right. ✅
- **`make css`**: S01 did not run `make css`; the `.h-dvh` utility and pipeline padding were added as plain CSS at the end of `styles.css`, which is the correct approach when Tailwind CLI is unavailable (per CLAUDE.md). ✅
- **Jinja2 `format` filter**: `step_pipeline.html` still uses `"%dm%02ds"|format(dur_m, dur_s)` — %-style, correct. ✅

---

## Security

No hardcoded secrets, URLs, or ports introduced. ✅

---

## Test Results

```
tests/dashboard/test_i00078_layout.py::test_i00078_footer_is_full_width_sibling_of_sidebar PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_theme_toggle_lives_in_footer_not_sidebar PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_shell_uses_dynamic_viewport_height PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_pipeline_strip_has_scrollbar_spacing PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_dark_scrollbar_uses_high_contrast_thumb PASSED
======================== 5 passed in 21.23s =========================
```

`make test-unit`: **2741 passed**, 4 skipped, 5 xfailed, 1 xpassed — no regressions.

---

## Findings

### MEDIUM (fixable): test file formatting

- **File**: `tests/dashboard/test_i00078_layout.py`
- **Description**: `make format` reports this file would be reformatted by `ruff format`. The agent ran `make format` which auto-fixed the test file but reported the fix as a change. The unformatted state was the state at `git add` time. This is a minor convention violation in a newly added file.
- **Suggestion**: Run `uv run ruff format tests/dashboard/test_i00078_layout.py` to bring the file into compliance. This is the only issue found.

---

## Verdict

**PASS** — zero CRITICAL findings, zero HIGH findings, one MEDIUM (fixable).

Mandatory fix count: **1** (formatting in the new test file).