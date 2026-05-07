# F-00080 S04 — CodeReview Report

## What was done

Reviewed S03 (frontend-impl) implementation for F-00080: First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness).

**Review scope**: License compliance, accessibility, help fragment shape, JS quality, CSS quality, base.html changes, and convention checks.

## Pre-Review Gate Results

```
make lint          ✓ PASS  (after removing unused pytest import from test_help_js_smoke.py)
node --check       ✓ CLEAN (help.js and tours.js — no syntax errors)
make format        ✓ CLEAN (all 629 files formatted)
```

## Files Changed by S03

```
dashboard/static/vendor/driver/driver.js.iife.js   (new, vendored IIFE)
dashboard/static/vendor/driver/driver.css          (new, vendored CSS)
dashboard/static/vendor/driver/LICENSE             (new, MIT license verbatim)
dashboard/static/help/help.js                      (new, popover + tour glue)
dashboard/static/help/tours.js                     (new, tour definitions)
dashboard/templates/macros/help_button.html       (new, macro)
dashboard/templates/macros/empty_state.html       (new, macro)
dashboard/templates/_partials/help/*.html         (×22, help fragments)
dashboard/templates/base.html                     (modified, added slot + scripts)
dashboard/static/styles.css                       (modified, appended CSS)
THIRD_PARTY_LICENSES.md                           (modified, appended entry)
tests/dashboard/test_help_js_smoke.py             (new, 8 smoke tests — fixed unused import)
```

## Review Findings

### 1. License Compliance — PASS ✓

| Check | Result |
|-------|--------|
| `dashboard/static/vendor/driver/LICENSE` exists and contains verbatim MIT text | ✓ Kamran Ahmed, MIT |
| `driver.js.iife.js` retains upstream MIT header comment at top | ✓ `/*! Driver.js v1.4.0 ... Licensed under MIT */` |
| `THIRD_PARTY_LICENSES.md` has Driver.js entry with version, copyright, license, source URL, and full MIT text | ✓ lines 798–827 |
| No Shepherd.js / Intro.js / Hopscotch / AGPL library added | ✓ confirmed via grep |
| No CDN `<script src="https://...">` for Driver.js | ✓ Only local `/static/vendor/driver/driver.js.iife.js` |

### 2. Accessibility — PASS ✓ (with reduced-motion noted)

| Check | Result |
|-------|--------|
| `?` button is `<button>` with `aria-label="Help for this page"`, `aria-haspopup="dialog"`, `aria-expanded` toggling | ✓ `help_button.html` line 3–8 |
| Popover container has `role="dialog" aria-modal="true" aria-label="Page help"` | ✓ `help_button.html` line 12 |
| ESC dismisses popover; focus returns to `?` button | ✓ `help.js` lines 144–151 |
| Background click closes popover | ✓ `help.js` lines 155–164 |
| Driver.js options include `allowKeyboardControl: true` | ✓ `help.js` line 231 |
| Reduced-motion users get instantaneous transitions | ✓ `styles.css` lines 65–73: `prefers-reduced-motion: no-preference` guard |
| Focus-visible ring implemented in CSS | ✓ `styles.css` lines 267–271 |
| WCAG 1.4.13 (dismissible, hoverable, persistent) | ✓ Popover is fixed-position, dismissible via × button, ESC, and background click |
| **Focus trap** while popover is open | ⚠ NOT implemented — popover does not trap focus |

**Focus trap gap**: The popover itself is not a focus trap. While Driver.js tour (when active) provides its own focus management, the **help popover** (before a tour starts) does not implement a focus trap. A keyboard user can Tab outside the open popover into background page content. This is a MEDIUM issue for the popover, but Driver.js itself handles focus trapping during active tours.

### 3. Help Fragment Shape — PASS ✓

All 22 fragments verified with correct structure:
- Heading 1: "What is this page?"
- Heading 2: "What can I do here?"
- Heading 3: "Vocabulary"
- Footer with "Take the 30-second tour →" + "Open full docs →"

No missing headings found across all 22 slugs.

### 4. JS Quality — PASS ✓

| Check | Result |
|-------|--------|
| Event delegation on `document` (not direct per-button listeners) | ✓ `help.js` lines 168–179 (`document.addEventListener("click", ...)`) |
| No use of `eval`, `new Function`, or `innerHTML` from untrusted sources | ✓ Popover HTML comes from same-origin `/_help/{slug}` endpoint |
| `localStorage` access wrapped in try/catch | ✓ `help.js` lines 25–39 |
| Driver.js lazy-loaded (CSS injected once on first mount; JS bundle once) | ✓ `help.js` lines 43–70 |
| Only one popover open at a time | ✓ `closeOpenPopover()` called before `openPopover()` (line 95) |
| If no tour defined for slug, "Take tour" button is hidden | ✓ `help.js` lines 205–207 |

### 5. CSS Quality — PASS ✓

| Check | Result |
|-------|--------|
| All rules go to `dashboard/static/styles.css` (plain CSS) | ✓ No Tailwind classes introduced |
| Theme-aware (`--ring`, `--background`, `--foreground` variables) | ✓ Uses `var(--popover)`, `var(--border)`, `var(--foreground)`, `var(--ring)` |
| No `!important` | ✓ None found in appended CSS |
| Tour-seen indicator is subtle | ✓ `.help-trigger__seen` only visible when `data-tour-seen="true"` (lines 44–48) |

### 6. base.html Changes — PASS ✓

| Check | Result |
|-------|--------|
| `{% block page_help_slug %}` exists | ✓ Line 8 |
| Help button mount is **inside** the existing header bar (same div as hamburger + search) | ✓ Lines 189–193, inside `#global-header` flex container |
| No JavaScript DOM-walking to position button next to `<h1>` | ✓ No `.page-help-mount` placeholder or `position: relative` hack |
| `tours.js` and `help.js` loaded with `defer` | ✓ Lines 34–35 |
| Driver.js bundle NOT eagerly loaded | ✓ Lazy-loaded on first `[data-tour-start]` click |
| No new Tailwind class names on the `?` button | ✓ Button uses `class="help-trigger"` (plain CSS); only existing Tailwind classes `ml-auto flex-shrink-0` on the wrapper div |

### 7. Convention Checks — PASS ✓

| Check | Result |
|-------|--------|
| Vendored asset directory follows `static/vendor/htmx/` pattern | ✓ `static/vendor/driver/` |
| Macros live under `templates/macros/` | ✓ `macros/help_button.html`, `macros/empty_state.html` |
| Help fragments live under `templates/_partials/help/` (not `fragments/`) | ✓ Correct — `_partials/help/` |
| Directory structure consistent | ✓ All conventions followed |

## Test Results

```
Smoke tests (tests/dashboard/test_help_js_smoke.py):
  8 passed in 0.03s ✓

make test-unit:
  2680 passed, 3 failed (pre-existing skill-file sync failures unrelated to F-00080)
  Coverage: 52.52% (required 46.0%) ✓
  The 3 failures are in test_skills_sync_is_byte_identical — unrelated to help system
```

The 3 pre-existing failures are in `tests/unit/test_skill_files.py` testing byte-identity of skill files and are not related to F-00080 changes.

## Fixes Applied During Review

1. **CRITICAL**: Removed unused `import pytest` from `tests/dashboard/test_help_js_smoke.py` (caused `make lint` failure — F401 unused import). Applied `ruff --fix` and formatted with `ruff format`.

## Mandatory Fix Count

**0** — The lint violation was fixed during review. No blocking issues remain.

## Notes for Subsequent Steps

- **Focus trap for popover** (MEDIUM): The help popover does not implement a focus trap. While Driver.js manages focus during active tours, the popover itself allows Tab-navigating out. Consider adding a `tabindex="-1"` on the popover and trapping Tab/Shift-Tab within it while open. Not blocking S05.
- **CSS transition**: Popover uses `prefers-reduced-motion: no-preference` guard for transitions (line 65 of styles.css) — this correctly applies transitions only when user hasn't requested reduced motion.
- **S05**: Needs to add `{% block page_help_slug %}«slug»{% endblock %}` to each of the 22 page templates and add `data-tour="..."` attributes to elements referenced in `tours.js`.

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00080",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "8 smoke tests passed; 2680/2683 unit tests passed (3 pre-existing skill-file failures unrelated to F-00080). All 22 fragments verified. Lint cleaned.",
  "notes": "Removed unused pytest import from test_help_js_smoke.py during review. No blocking issues remain. Focus trap for popover (non-blocking MEDIUM) noted for future consideration."
}
```