# I-00094_S01_Frontend_prompt

**Work Item**: I-00094 — Auto-merge htmx-only `<a>` tags render with text cursor and bad accessibility
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies — see `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00094 --json`
- `ai-dev/active/I-00094/I-00094_Issue_Design.md`
- `ai-dev/active/I-00094/I-00094_Functional.md`
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/templates/fragments/auto_merge_event_row.html`
- `dashboard/templates/fragments/auto_merge_rollup.html`
- `dashboard/static/styles.css`
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00094/reports/I-00094_S01_Frontend_report.md`

## Context

Every `<a hx-get="…">` anchor without an `href` attribute defaults to
`cursor: auto` and is announced as `generic` by screen readers. Convert
them all to `<button type="button" hx-get="…">` — htmx behaves the
same and `<button>` carries the right cursor, focus ring, and `role`.

## Requirements

### 1. Replace `<a hx-get>` with `<button type="button" hx-get>` everywhere

In each of the three fragment templates, locate every `<a>` that:

- Has an `hx-get` attribute, AND
- Has NO `href` attribute.

Replace with `<button type="button" …>` — keep:

- All Tailwind / utility classes verbatim.
- All `hx-*` attributes verbatim (`hx-get`, `hx-target`, `hx-swap`,
  `hx-ext`, etc.).
- All ARIA attributes added by sibling incident I-00092 if it has
  landed (e.g. `aria-pressed`, `title`). If I-00092 hasn't landed
  before this fix, do NOT add those attributes here — that is
  I-00092's scope.
- The element's body text unchanged.

Specific spots to change:

1. `auto_merge_events_table.html`:
   - The filter-chip loop (lines ~13-21).
   - The Prev/Next pagination links (lines ~44-49).
2. `auto_merge_event_row.html`:
   - The `(view)` link at line ~25.
3. `auto_merge_rollup.html`:
   - The 7d/30d window toggles at line ~10.

### 2. Preserve `<a>` elements that legitimately have `href`

Do NOT touch `<a href="…">` elements (real links). The conversion is
specifically for `<a hx-get>` without `href`. Audit with:

```bash
grep -rn '<a\b[^>]*\bhx-get=' dashboard/templates/fragments/auto_merge_*.html
```

After your changes, that grep should return no matches.

### 3. CSS adjustment (only if needed)

Tailwind's preflight reset normalises `<button>` styling, BUT
appending one safety rule to `dashboard/static/styles.css` is cheap
insurance — only add if your initial visual check shows a regression
(unexpected background, padding, border, or font):

```css
/* Normalise the chip-style buttons so they look identical to the
   former <a> elements after the I-00094 conversion. */
.auto-merge-chip-btn,.auto-merge-events-table button[hx-get],.auto-merge-events-table button[hx-post],
.auto-merge-rollup button[hx-get],.auto-merge-event-row button[hx-get]{
  background:transparent;color:inherit;font:inherit;line-height:inherit;cursor:pointer;
}
```

(Use any single class hook that makes sense; the actual selectors can
be tighter if you add a wrapper class to each modified template.)

### 4. Do NOT change the JSON-encoding form for verdict pills

`auto_merge_event_row.html` lines 11-18 already use `<button …>` for
the verdict pills (`pending`, `correct`, …). No conversion needed
there.

`auto_merge_event_detail.html` is not in scope for this incident
(I-00093 owns it).

### 5. Preserve I-00092's `_is_active` block

If I-00092 has landed first, the chip's `class` expression includes
the per-chip `_is_active` ternary. Carry that over unchanged — the
expression doesn't depend on the element tag.

## Project Conventions

- `dashboard/CLAUDE.md`: htmx fragments + Tailwind classes; `make css`
  is broken in worktrees so plain CSS rules go to `styles.css`.
- Jinja2 `format` filter must remain `%`-style (I-00075). You probably
  don't touch any `format` call here, but be aware.

## TDD Requirement

Frontend step — behavioural tests in S03. For your own
pre-completion run:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint` (includes `scripts/check_templates.py`)

## Test Verification (NON-NEGOTIABLE)

Targeted only — see above. Do NOT run the full suite.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00094",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/auto_merge_events_table.html",
    "dashboard/templates/fragments/auto_merge_event_row.html",
    "dashboard/templates/fragments/auto_merge_rollup.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — template-only edits; behavioural tests live in S03",
  "blockers": [],
  "notes": "List of <a hx-get>-without-href instances converted. Note any CSS rule added or skipped."
}
```
