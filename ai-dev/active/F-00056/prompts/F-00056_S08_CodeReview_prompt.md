# F-00056_S08_CodeReview_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step Being Reviewed**: S07 (frontend-impl)
**Review Step**: S08

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- **READ the full "Gantt Chart Strategy" section** (normative)
- `ai-dev/active/F-00056/reports/F-00056_S07_Frontend_report.md`
- `dashboard/templates/fragments/item_execution_report.html`
- `dashboard/templates/pages/project/item_execution_report.html`
- `dashboard/templates/pages/project/item_detail.html` (diff the tab-button addition only)
- `dashboard/static/execution_report.css` (if present)

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S08_CodeReview_report.md`

## Review Checklist

### 1. Gantt Spec Compliance (NORMATIVE)

For each rule in the design's Gantt Chart Strategy section, verify the implementation:

- Pure CSS only (no JS chart library imports). Inspect HTML for `<script>` additions; any JS added by S07 is a HIGH finding unless strictly necessary.
- Layout: fixed 220px label column, flex-1 time track.
- Time mapping: percentages computed from `total_duration_secs`; min width 0.5%.
- Retry segments carry `.gantt-bar--retry` for non-final runs; final segment carries status-matched class.
- Fix-marker between retry segments where FixCycle exists.
- QV-gate row tint class.
- Palette matches the 5-entry table in the design doc exactly (hex codes).
- Time-axis header with 4 ticks in `Xm Ys` (or `Xh Ym` if > 3600s).
- Responsive: 720px breakpoint; compact row height.
- Accessibility: each bar has `aria-label`; `<details>/<summary>` semantic accordion.

A single deviation from any of the normative rules is a HIGH finding.

### 2. Fragment Quality

- Renders `data.hotspots` with the exact wording "No retries — clean run." and "final: {final_status}" suffix.
- Timeline `<details>` blocks have `id="timeline-{step_id}"` and Gantt-row anchors use matching hash links.
- Fix-summary block-quote uses the exact "_no fix summary captured (pre-F-00056)_" wording for NULL cases.
- Template respects autoescape; no `|safe` filter used on `error_message`, `fix_summary`, or any user/agent-provided text.

### 3. Tab Button Addition

- Exactly ONE new button added to `item_detail.html`.
- Button's `class=` attributes are copied verbatim from the sibling buttons; no new CSS classes introduced.
- No other changes to `item_detail.html` — diff must show a localized addition, not reformatting.

### 4. Standalone Page

- Extends `base.html` and uses the correct block names from that file.
- Title block renders "Execution Report — {work_item_id}".
- Includes the fragment (not duplicated content).

### 5. CSS Scoping

- If inline `<style>`, the block does not leak selectors that affect unrelated pages (selectors scoped under a container class).
- If external CSS, the stylesheet is linked only on this page/fragment, not globally.

### 6. No-regression (Invariant 7)

- Existing fragments untouched (verify `git diff` limited to the two new files + `item_detail.html`'s tab button region + optional new CSS file).

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check .`
4. Render the fragment template with a seeded `ExecutionReportData` via `jinja2.Environment` and assert it parses without syntax errors; if a sibling fragment has an equivalent smoke test, follow that pattern.
5. Visual inspection by opening `/project/iw-ai-core/item/F-00055/execution-report` in the dashboard after S09 backfill (acceptable to defer to S09/S18 if backfill not yet run).

## Review Result Contract

Standard JSON. `verdict=pass` only if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE.
