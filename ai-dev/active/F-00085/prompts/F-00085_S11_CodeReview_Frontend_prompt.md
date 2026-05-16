# F-00085_S11_CodeReview_Frontend_prompt

**Work Item**: F-00085
**Step**: S11 (Per-agent review of S10)
**Agent**: code-review-impl

---

## Inputs

- F-00085 Feature Design (ACs, Invariants, Boundary table)
- S10 report + diff of `files_changed`

## Output

- `ai-dev/active/F-00085/reports/F-00085_S11_CodeReview_report.md`

## Review Checklist

### Chip visibility (Inv 6)

- [ ] `auto_merge_status_chip.html` is HIDDEN via Jinja `{% if %}`, NOT via CSS `display:none`.
- [ ] Chip is rendered only when `status.config.phase >= 1`.
- [ ] Browser-test (S24) can assert the DOM element is absent in phase=0 fixture.

### Settings panel (Inv 5)

- [ ] Phase dropdown lists ONLY 0 and 1.
- [ ] "Use global default" radio sends `phase=null` to the API.
- [ ] Runtime picker `<option>` list is built from `enabled=True` rows only (defence in depth — API also re-validates).
- [ ] No `<option>` for disabled runtimes anywhere in the rendered HTML.

### Diff viewer

- [ ] Uses server-rendered `difflib.HtmlDiff` output (no client-side diff lib).
- [ ] "(file no longer exists on main)" placeholder when right pane is None.
- [ ] Multi-file events handled (tabs OR sequential per-file diffs).

### Verdict widgets

- [ ] Inline (in events table row) AND modal both POST to the same endpoint.
- [ ] Active verdict is visually distinct (button state, not just colour).
- [ ] Notes textarea is in modal only (inline widget is verdict-only).

### htmx hygiene

- [ ] All dynamic regions use htmx attributes; no inline `<script>` blocks.
- [ ] `hx-target` and `hx-swap` are explicit; no surprise full-page replacements.
- [ ] Fragment endpoints return fragments only (S08 already ensures this; verify the template consumer side).
- [ ] Rollup widget refreshes via htmx with window selector (7d / 30d).

### Jinja `format` filter (CLAUDE.md rule)

- [ ] All `format` filter calls use `%`-style: `"%d events"|format(n)`, NOT `"{} events"|format(n)`.
- [ ] `scripts/check_templates.py` lint gate passes (`make lint`).

### base.html edits

- [ ] One include of the compact status chip inside the header.
- [ ] One sidebar nav row tuple addition (`('/auto-merge', 'Auto-Merge')`).
- [ ] Chip include is gated on phase>=1 via Jinja conditional.
- [ ] No structural change to existing nav layout.

### CSS additions

- [ ] Plain CSS rules appended to `dashboard/static/styles.css` (CR-00033 fallback).
- [ ] No new files under `dashboard/static/`.
- [ ] Existing CSS rules untouched.
- [ ] No `!important` usage (would conflict with future Tailwind layer).

### Empty / boundary states

- [ ] AC1 empty state ("No auto-merge events yet") rendered when 0 events.
- [ ] AC7 refuse-list widget hidden when total count is 0.
- [ ] AC6 phase=0 hides events table + chip + rollups; Settings panel still visible.

### Out-of-scope guard

- [ ] No new Python files.
- [ ] No new routes / API changes (S08).
- [ ] No daemon-side changes (S04/S06).
- [ ] No alembic migration.

### Accessibility / UX

- [ ] Verdict buttons have accessible labels (aria-label or visible text).
- [ ] Modal can be dismissed via Escape key (htmx supports this — verify).
- [ ] Diff viewer is keyboard-scrollable.
- [ ] No colour-only signals (health icon uses both colour + glyph).

## Severity Mapping

- **CRITICAL** — chip rendered when phase=0 (Inv 6 violated); phase 2/3 selectable in dropdown; disabled runtime visible in picker; format filter uses `{}` style (template will crash at runtime).
- **HIGH** — missing htmx targets; verdict POST swap wrong; multi-file diff missing.
- **MEDIUM** — accessibility nits; CSS specificity issues.
- **LOW** — style.

## Result Contract

Standard code-review JSON.
