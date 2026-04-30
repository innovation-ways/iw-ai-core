# F-00069_S04_CodeReview_Frontend_prompt

**Work Item**: F-00069 -- Test Execution, Coverage Gate, Reports, and Coverage Dashboard View
**Step Being Reviewed**: S02 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies. S02 does not touch Docker or migrations.)

## Input Files

- `uv run iw item-status F-00069 --json`
- `ai-dev/active/F-00069/F-00069_Feature_Design.md`
- `ai-dev/active/F-00069/reports/F-00069_S02_Frontend_report.md`
- `dashboard/templates/pages/system/coverage.html`
- `dashboard/templates/fragments/coverage_files.html`
- `dashboard/templates/base.html` (diff for nav addition)

## Output Files

- `ai-dev/active/F-00069/reports/F-00069_S04_CodeReview_report.md`

## Review Checklist

### 1. Nav addition (base.html)

- [ ] Exactly one new entry: `('/system/coverage', 'Test Coverage')`.
- [ ] Position: after `'/system/status'`, before `'/system/all-active'`.
- [ ] Indentation matches surrounding rows.
- [ ] No other modifications to base.html.

### 2. Page template

- [ ] Extends `base.html` with `{% block content %}`.
- [ ] Title block set to "Test Coverage — IW AI Core".
- [ ] Empty state path: renders when `view.available` is false; shows hint text and parse-error if present.
- [ ] Available path: renders header card (4 cells), per-package table, per-row drill-down container.
- [ ] Threshold gap displayed correctly with sign (+/-) and units (pp).
- [ ] Color badges use only existing Tailwind utility classes (no new tokens introduced).
- [ ] Package rows have htmx attributes: `hx-get`, `hx-target`, `hx-swap="innerHTML"`.
- [ ] Package rows are keyboard-accessible: `tabindex="0"`, Enter triggers htmx via `hx-trigger="click, keydown[key=='Enter']"` (or equivalent).
- [ ] No inline styles, no `<style>` blocks, no `<script>` blocks.

### 3. Fragment template

- [ ] Pure table fragment — no `<html>`/`<body>`/`{% extends %}` wrappers.
- [ ] Iterates `files` context var.
- [ ] Empty case (no files) renders gracefully with a "No files" row.
- [ ] Same color badge logic as the page.

### 4. Visual consistency

- [ ] Compare with `dashboard/templates/pages/system/status.html` and `pages/system/worktrees.html` — class tokens and spacing match (`bg-card`, `border`, `text-muted-foreground`, etc.).
- [ ] No layout regressions in adjacent pages (System nav still visible on every other page).

### 5. Accessibility

- [ ] Empty state has `role="status"` or equivalent live region.
- [ ] Click targets have keyboard fallback.
- [ ] Color is not the sole signal — badge text (`GREEN/AMBER/RED`) accompanies the color.
- [ ] Tables have `<thead>` with `<th>` cells.

### 6. Conventions

- Read `dashboard/CLAUDE.md`.
- htmx-only (no fetch, no Alpine, no React).
- Tailwind utility classes only.

## Test Verification

- `make lint` — zero errors.
- `make typecheck` — zero new errors (templates aren't typechecked, but base.html / Python touched files must be clean).
- Render check: with the dashboard running locally, hit `/system/coverage` and `/system/coverage/files/orch` and verify HTTP 200 + no template errors.

## Severity Levels

(Standard table.)

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00069",
  "step_reviewed": "S02",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
