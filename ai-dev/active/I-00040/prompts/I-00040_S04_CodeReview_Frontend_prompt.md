# I-00040 S04 — Code review of S03 (frontend banner + button-disable macro)

**Work Item**: I-00040
**Step Being Reviewed**: S03 (frontend-impl — stale-DB banner + write-action disable)
**Review Step**: S04
**Agent**: code-review-impl

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- `ai-dev/active/I-00040/I-00040_Issue_Design.md`
- `ai-dev/active/I-00040/reports/I-00040_S03_Frontend_report.md`
- `dashboard/templates/base.html`
- `dashboard/templates/macros/db_guard.html`
- `dashboard/app.py`
- Any templates updated per the S03 report

## Output Files

- `ai-dev/active/I-00040/reports/I-00040_S04_CodeReview_Frontend_report.md`

## Review Checklist

### 1. Banner markup correctness — CRITICAL

- [ ] Banner is the FIRST child of `<body>` in `base.html`, before the nav.
- [ ] Banner is conditional on `is_db_stale(request)`. When false, NO markup is rendered (no empty wrapper).
- [ ] Banner has `role="alert"` and `aria-live="polite"`.
- [ ] Banner contains `current_rev`, `head_rev`, and the literal string `make db-migrate`.
- [ ] Banner contains the substring `Orch DB schema is behind head`.
- [ ] No emoji.
- [ ] Banner uses Tailwind utilities from `styles.css`; no inline `style="…"`.

### 2. Macro correctness

- [ ] `dashboard/templates/macros/db_guard.html` defines `write_button_attrs(request)`.
- [ ] Macro emits `disabled aria-disabled="true" title="…"` when stale, else nothing.
- [ ] All write-action buttons in the dashboard now invoke the macro (use Grep to confirm).
- [ ] Read-only forms (search, filters) are NOT modified.

### 3. Jinja global registration

- [ ] `is_db_stale` is registered as a Jinja global in `dashboard/app.py` (or via the existing context-processor pattern).
- [ ] No template imports `is_db_stale` — it's available everywhere.

### 4. htmx interaction

- [ ] No htmx fragment response was modified to include the banner inline (would double-render).
- [ ] Full-page htmx swaps (`hx-target="body"` or no `hx-target`) still return `base.html` extending — banner shows.

### 5. Accessibility

- [ ] `role="alert"` present.
- [ ] Disabled buttons keep `aria-disabled="true"` AND the native `disabled` attribute.
- [ ] Visible focus ring on banner not required (banner is informational, not interactive).

### 6. CSS regeneration

- [ ] If new utilities were used, `make css` was run and `styles.css` was committed.
- [ ] If no new utilities were used, `styles.css` is NOT in the diff.

### 7. Scope drift

- [ ] No JavaScript files added or modified.
- [ ] No changes outside the design's File Manifest plus button-bearing templates.

## Output Report

Findings list with severity (CRITICAL / HIGH / MEDIUM / LOW / INFO), file:line, and a one-line verdict per item. End with overall verdict (`PASS` / `NEEDS_FIX` / `BLOCKED`).

## Lifecycle Commands

```bash
uv run iw step-start I-00040 --step S04
# ... review ...
mkdir -p ai-dev/active/I-00040/reports
uv run iw step-done I-00040 --step S04 --report ai-dev/active/I-00040/reports/I-00040_S04_CodeReview_Frontend_report.md
```
