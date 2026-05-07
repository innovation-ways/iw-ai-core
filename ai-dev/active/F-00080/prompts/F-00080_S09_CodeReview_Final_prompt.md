# F-00080_S09_CodeReview_Final_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Review Step**: S09 (Final Review)
**Implementation Steps Reviewed**: S01..S07

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status F-00080 --json`
- `ai-dev/active/F-00080/F-00080_Feature_Design.md`
- All implementation step reports: `F-00080_S01_*`, `S03_*`, `S05_*`, `S07_*`
- All per-agent code review reports: `F-00080_S02_*`, `S04_*`, `S06_*`, `S08_*`
- All files listed across all `files_changed` arrays

## Output Files

- `ai-dev/work/F-00080/reports/F-00080_S09_CodeReview_Final_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations → CRITICAL.

## Review Checklist

### 1. Completeness vs design document (CRITICAL)

For each Acceptance Criterion (AC1..AC7) in the design doc, verify a code path or test exists that proves it. List the verification source (file:line or test name) for each. Any missing AC → CRITICAL.

For each Invariant (1..10), verify a test or invariant guard exists. Missing invariant → CRITICAL.

For every Boundary Behavior row, verify a test exists in S07's suite. Missing → CRITICAL.

### 2. Cross-agent consistency (HIGH)

- Slug spelling is identical everywhere it appears (router allow-list source files / page `page_help_slug` blocks / fragment file names / tours.js keys / test parameters).
- The four mandatory headings appear in every fragment, in the same order, with identical English wording.
- Empty-state macro signature is consistent with the call sites.
- `data-tour` attribute names in `tours.js` match exactly the attributes added to page templates by S05.

### 3. Integration points (HIGH)

- `dashboard/app.py` includes the help router exactly once.
- `base.html` `{% block page_help_slug %}` mechanism reads `self.page_help_slug()` and only renders the `?` button when non-empty.
- `help.js` event delegation works against the actual button DOM produced by the macro.
- `THIRD_PARTY_LICENSES` Driver.js entry matches the version actually vendored.

### 4. License invariant (CRITICAL — OSS gate)

- No AGPL JavaScript dependency was added (Shepherd.js, Intro.js, etc.).
- Driver.js MIT header preserved at the top of `driver.js.iife.js`.
- `dashboard/static/vendor/driver/LICENSE` exists and matches upstream verbatim.
- `THIRD_PARTY_LICENSES` includes Driver.js.
- No CDN script tags introduced.

### 5. Accessibility invariant (HIGH)

- WCAG 2.2 SC 1.4.13 (dismissible / hoverable / persistent) holds for the popover.
- Focus trap returns focus to the originating button on close.
- Keyboard-only flow works: Tab to `?` → Enter → focus enters popover → Tab cycles inside → ESC closes → focus on `?`.
- `aria-` attributes match the pattern in S03's prompt.

### 6. No-auto-launch invariant (CRITICAL)

Walk through `help.js`, `tours.js`, and `base.html`. Confirm there is NO code path that auto-opens the popover or auto-starts a tour on `DOMContentLoaded`, `load`, or any timer. The `?` button only reacts to a user gesture.

### 7. Test coverage (HIGH)

Run the full test suite:

```bash
make test-unit
make test-integration
make test-frontend
```

All must pass. If integration tests fail → CRITICAL.

Confirm:
- 22 slugs are tested with the parametrised 200 test.
- Orphan-slug bidirectional check is present.
- Empty-state rendering is asserted on all 10 list views.
- Smoke test verifies `/static/vendor/driver/driver.js.iife.js` is served.

### 8. Architecture compliance (HIGH)

- No business logic added to `dashboard/routers/help.py`.
- No `orch/` code touched.
- No DB migrations.
- No new Tailwind classes (CSS additions go to plain `dashboard/static/styles.css`).
- `dashboard/static/vendor/driver/` mirrors the existing `static/vendor/htmx/` shape.

### 9. Security (cross-cutting, HIGH)

- No outbound network calls (no CDN, no analytics).
- No user input reaches Jinja loader without regex validation.
- No localStorage value is interpolated into HTML or JS code without escaping.
- No `eval`, `new Function`, or `innerHTML += untrusted`.

### 10. Scope conformance (HIGH)

Inspect `git diff main..HEAD --name-only`. Every modified file MUST appear in the design's "Impacted Paths" list (and therefore in `workflow-manifest.json` `scope.allowed_paths`). Any out-of-scope file → CRITICAL (the merge gate will reject it anyway).

## Test Verification

```bash
make test-unit
make test-integration
make test-frontend
```

All zero failures.

## Severity Levels

Standard scale.

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "CodeReview_Final",
  "work_item": "F-00080",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "missing_requirements": [],
  "notes": ""
}
```
