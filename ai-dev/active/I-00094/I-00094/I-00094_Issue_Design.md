# I-00094: Auto-merge htmx-only `<a>` tags render with text cursor and bad accessibility

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-17
**Reported By**: sergio (manual UX audit of `/project/iw-ai-core/auto-merge`)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures exempt.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Description

Every clickable element in the auto-merge view that uses
`<a hx-get="...">` without an `href` attribute — filter chips,
pagination Prev/Next, the `(view)` event-detail link, and the
7d/30d rollup window switchers — renders with the **text cursor**
(I-beam) on hover instead of the standard hand pointer, and is
announced to screen readers as a generic element rather than a link.

Confirmed via `getComputedStyle()` on every such anchor:

```json
[{"text": "7d",         "href": null, "cursor": "auto"},
 {"text": "resolved",   "href": null, "cursor": "auto"},
 {"text": "(view)",     "href": null, "cursor": "auto"}, ...]
```

The same elements appear as `generic [ref=eNNN]` in the Playwright
accessibility snapshot, not `link "..."`. Browsers only attach
`cursor: pointer` and the `link` ARIA role to `<a>` elements that
carry an `href` attribute.

## Project Context

Read `CLAUDE.md`, `dashboard/CLAUDE.md`.

## Browser Evidence

- `ai-dev/active/I-00094/evidences/pre/I-00094-page-baseline.png` —
  baseline page; cursor evidence is captured via `getComputedStyle`
  output in the design (above) since cursor doesn't show in static
  screenshots.

## Steps to Reproduce

1. Open `/project/iw-ai-core/auto-merge` in a desktop browser.
2. Hover any filter chip, the `(view)` link, the Prev/Next pagination
   buttons, or the 7d/30d rollup window toggles.

**Expected**: hand pointer cursor on hover; screen reader announces
each as a "link" or "button".

**Actual**: text I-beam cursor; screen reader announces "generic" /
unfocusable / no role.

## Root Cause Analysis

Four templates contain `<a hx-get=…>` anchors without `href`:

1. `dashboard/templates/fragments/auto_merge_events_table.html:15-19`
   (filter chips), `:44-49` (pagination Prev/Next).
2. `dashboard/templates/fragments/auto_merge_event_row.html:25`
   (`(view)` link).
3. `dashboard/templates/fragments/auto_merge_rollup.html:10`
   (7d/30d window toggles).
4. `dashboard/templates/fragments/auto_merge_refuse_list.html` —
   contains only `<span>` chips (no clickable anchors); no change
   needed.

Browsers' default UA stylesheet rule for `a:link, a:visited` is
`cursor: pointer` — but `a:link` matches only anchors with an `href`.
Same for the implicit ARIA role `link` (browsers map `<a>` to role
`link` only when `href` is set).

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/fragments/auto_merge_events_table.html` | Filter chips + Prev/Next look unclickable |
| `dashboard/templates/fragments/auto_merge_event_row.html` | `(view)` action ambiguous |
| `dashboard/templates/fragments/auto_merge_rollup.html` | 7d/30d toggles look like static labels |
| `dashboard/static/styles.css` (optional) | Place to define `.iw-htmx-action { cursor: pointer; }` if we want a single shared class |

## Fix Plan

The cleanest fix is to convert each `<a hx-get>` into a `<button type="button" hx-get>` — `<button>` always has `cursor: pointer`,
gets proper keyboard support (Enter and Space activate it), and an
implicit `role="button"` for screen readers. htmx works the same on
`<button>` as on `<a>`.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `frontend-impl` | Replace `<a hx-get>` → `<button type="button" hx-get>` in the four affected fragment templates; preserve all classes and htmx attributes; preserve the active-chip styling from I-00092 (assumes I-00092 lands first; if not, this fix is independent of that one). Append minimal CSS to ensure `<button>` baseline matches the previous `<a>` look (no border, no padding from UA stylesheet — Tailwind's reset usually handles this; verify). | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `tests-impl` | Dashboard tests: each fragment's clickable elements are `<button>` (not `<a>` without href) and have `cursor-pointer` applicable styling. Also assert that the htmx attributes still point at the right endpoints. | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `code-review-final-impl` | Global review | — |
| S06–S11 | `qv-gate` | lint, format, typecheck, security-sast, unit-tests, integration-tests | — |
| S12 | `qv-browser` | Playwright: snapshot the page; assert filter chips, view link, rollup toggles all appear as `button` not `generic` in the a11y tree | — |
| S13 | `self-assess-impl` | Self-assessment | — |

### Database Changes

None.

### Code Changes

- **Files to modify**:
  - `dashboard/templates/fragments/auto_merge_events_table.html`
  - `dashboard/templates/fragments/auto_merge_event_row.html`
  - `dashboard/templates/fragments/auto_merge_rollup.html`
- **Files to extend (tests)**:
  - `tests/dashboard/test_auto_merge_routes.py`
- **CSS**: a small `auto_merge` ruleset only if needed to normalise
  `<button>` background/border (likely Tailwind already covers it via
  reset).

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00094_Issue_Design.md` | Design | This document |
| `I-00094_Functional.md` | Design | Human summary |
| `workflow-manifest.json` | Manifest | Steps |
| `prompts/I-00094_S01_Frontend_prompt.md` | Prompt | Replace anchors with buttons |
| `prompts/I-00094_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/I-00094_S03_Tests_prompt.md` | Prompt | Tests |
| `prompts/I-00094_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/I-00094_S05_CodeReview_Final_prompt.md` | Prompt | Final review |
| `prompts/I-00094_S12_BrowserVerification_prompt.md` | Prompt | Browser verify |
| `prompts/I-00094_S13_SelfAssess_prompt.md` | Prompt | Self-assess |

## Test to Reproduce

```python
def test_filter_chips_are_buttons_not_hrefless_anchors(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=10"
    )
    html = response.text

    # Every clickable filter chip is a <button>, not <a hx-get … without href>.
    import re
    chip_anchors_without_href = re.findall(
        r'<a\b[^>]*\bhx-get="[^"]*/auto-merge/events[^"]*"[^>]*>',
        html,
    )
    chip_anchors_with_href = [a for a in chip_anchors_without_href if 'href=' in a]
    assert chip_anchors_without_href == chip_anchors_with_href, (
        f"Filter chips must be <button> or <a href=…>, not <a hx-get …> without href.\n"
        f"Offenders:\n{chip_anchors_without_href}"
    )

    chip_buttons = re.findall(
        r'<button\b[^>]*\bhx-get="[^"]*/auto-merge/events[^"]*"',
        html,
    )
    assert len(chip_buttons) >= 7, f"Expected ≥7 filter chip <button>s; got {len(chip_buttons)}"
```

Sibling tests cover the `(view)` link in the event row fragment and
the 7d/30d toggles in the rollup fragment.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge"
playwright-cli snapshot                       # check that chips/view/toggles appear as button refs
```

## Acceptance Criteria

### AC1: Filter chips are `<button>` not href-less `<a>`

```
Given the events table fragment renders
Then every filter chip element is a <button type="button">
 AND no <a> element with hx-get and no href appears in the fragment
```

### AC2: `(view)` link is `<button>` not href-less `<a>`

```
Given a row in the events table
Then the (view) action element is a <button type="button">
```

### AC3: 7d/30d rollup toggles are `<button>`

```
Given the rollup fragment renders
Then the 7d and 30d toggles are <button type="button">
```

### AC4: Pagination Prev/Next are `<button>`

```
Given the events table has more than one page
Then Prev and Next are <button type="button">
```

### AC5: Accessibility — element role

```
Given the page is loaded in a real browser
When Playwright captures the accessibility snapshot
Then each former-<a> element appears with role "button" and is in the tab order
```

### AC6: Regression tests exist

```
The four named tests pass.
```

## Regression Prevention

- A custom lint rule that scans fragment templates under
  `dashboard/templates/fragments/` for `<a … hx-get … >` without
  `href` would prevent this class of bug from recurring. Add a one-off
  helper in `scripts/check_templates.py` if straightforward — otherwise
  document the rule in `dashboard/CLAUDE.md` (future addition; not
  required by this incident).

## Dependencies

- **Depends on**: None
- **Blocks**: None
- **Conflicts with**: I-00091, I-00092, I-00093, I-00095, I-00096, I-00097 (overlapping auto-merge fragments); run sequentially.

## Impacted Paths

- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/templates/fragments/auto_merge_event_row.html`
- `dashboard/templates/fragments/auto_merge_rollup.html`
- `dashboard/static/styles.css`
- `tests/dashboard/test_auto_merge_routes.py`

## TDD Approach

- Reproducing tests:
  - `tests/dashboard/test_auto_merge_routes.py::test_filter_chips_are_buttons_not_hrefless_anchors`
  - `tests/dashboard/test_auto_merge_routes.py::test_view_link_is_button_not_hrefless_anchor`
  - `tests/dashboard/test_auto_merge_routes.py::test_rollup_window_toggles_are_buttons`
  - `tests/dashboard/test_auto_merge_routes.py::test_pagination_links_are_buttons`
- Assertions target the actual element tag, not just the text "button"
  (which appears in many places).

## Notes

- 4 of 7 audit incidents.
- htmx works the same on `<button>` as on `<a>`; no JS changes
  required.
- Tailwind's preflight reset normalises `<button>` styling — minimal
  CSS adjustments expected.
