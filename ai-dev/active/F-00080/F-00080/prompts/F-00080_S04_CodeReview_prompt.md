# F-00080_S04_CodeReview_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status F-00080 --json`
- Design doc + S03 report + every file in S03's `files_changed`

## Output Files

- `ai-dev/work/F-00080/reports/F-00080_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate

```bash
make lint   # includes node --check on dashboard/static/**/*.js
make format
```

NEW violations → CRITICAL.

Also run `node --check dashboard/static/help/help.js dashboard/static/help/tours.js` explicitly and report any syntax errors as CRITICAL.

## Review Checklist

### 1. License compliance (CRITICAL — this is the OSS gate)
- `dashboard/static/vendor/driver/LICENSE` exists and contains the verbatim upstream MIT text.
- `dashboard/static/vendor/driver/driver.js.iife.js` retains the upstream MIT header comment at the top.
- `THIRD_PARTY_LICENSES` has a Driver.js entry with version, copyright, license name, source URL, and full license text.
- No Shepherd.js, Intro.js, or any other AGPL onboarding library was added.
- No CDN `<script src="https://...">` was introduced — Driver.js must be served from `/static/`.

### 2. Accessibility (CRITICAL on a11y, HIGH otherwise)
- The `?` button is a real `<button>` with `aria-label="Help for this page"`, `aria-haspopup="dialog"`, and `aria-expanded` toggling.
- The popover container has `role="dialog" aria-modal="true" aria-label="Page help"`.
- Focus trap is implemented while the popover is open; ESC dismisses; focus returns to the originating button.
- Driver.js options include `allowKeyboardControl: true`. `keyboardNavigation` is NOT disabled.
- Reduced-motion users get instantaneous popovers / transitions.
- Focus-visible ring is implemented in CSS.
- WCAG 2.2 SC 1.4.13: tooltip/popover content is dismissible, hoverable, persistent.

### 3. Help fragment shape (HIGH)
For each of the 22 fragments, verify the four mandatory headings appear in order: "What is this page?", "What can I do here?", "Vocabulary", and the footer with "Take the 30-second tour →" + "Open full docs →". Any missing heading → CRITICAL (the orphan-check test in S07 asserts this).

### 4. JS quality (HIGH)
- Event delegation on `document` (not direct `addEventListener` per button) so clicks before JS load still fire.
- No use of `eval`, `new Function`, or `innerHTML` from untrusted sources. The popover is filled via the response from a same-origin endpoint that returns server-rendered Jinja — that's acceptable.
- `localStorage` access wrapped in try/catch (private mode does not break the page).
- Driver.js lazy-loaded (CSS injected once on first tour mount; JS bundle loaded once).
- Only one popover open at a time.
- If `tours.js` does not define a tour for the current slug, the "Take the tour" button is hidden.

### 5. CSS quality (MEDIUM)
- All rules go to `dashboard/static/styles.css` (plain CSS), not Tailwind classes that need `make css`.
- Theme-aware (uses `--ring`, `--background`, `--foreground` variables from `theme.css`).
- No `!important` unless absolutely required.
- ✓ tour-seen indicator is subtle, not loud.

### 6. base.html changes (HIGH)
- The `{% block page_help_slug %}` mechanism auto-renders the `?` button only when the block is non-empty (use `self.page_help_slug()`).
- The help-button mount lives **inside the existing global header bar** (the same `<div>` that contains the hamburger + search input). It is rendered server-side via the macro at a fixed `ml-auto flex-shrink-0` slot — there is **no** JavaScript that walks the DOM to position the `?` next to an `<h1>`, no `<div class="page-help-mount">` placeholder, no `position: relative` hack. Flag any such code as MEDIUM_FIXABLE.
- `tours.js` and `help.js` are loaded with `defer`.
- Driver.js bundle is NOT loaded eagerly; `driver.css` is NOT preloaded.
- No new Tailwind class names introduced beyond utility classes that already exist on `base.html` (`ml-auto`, `flex-shrink-0` are already used). The `?` button itself is styled by plain CSS in `styles.css` — verify no Tailwind class is required on the button.

### 7. Convention checks (MEDIUM)
- Vendored asset directory follows the same pattern as `static/vendor/htmx/`.
- Macros live under `templates/macros/`.
- Help fragments live under `templates/_partials/help/` (not `templates/fragments/help/` — fragments/ is for htmx swaps that already exist).

## Test Verification

Run `make test-unit` and the smoke test created in S03.

## Severity Levels

Standard scale.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00080",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
