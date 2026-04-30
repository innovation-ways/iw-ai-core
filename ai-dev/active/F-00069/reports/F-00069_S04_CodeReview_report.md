# F-00069 S04 Code Review — Frontend (S02)

## What was done

Reviewed S02 (frontend-impl) implementation of `/system/coverage` page templates, htmx fragment, and nav addition.

## Files reviewed

- `dashboard/templates/base.html`
- `dashboard/templates/pages/system/coverage.html`
- `dashboard/templates/fragments/coverage_files.html`
- `dashboard/routers/coverage.py`
- `dashboard/services/coverage_service.py`

## Checklist results

### 1. Nav addition (base.html) — PASS
- Exactly one entry: `('/system/coverage', 'Test Coverage')` at line 111
- Position: after `('/system/status', ...)` and before `('/system/all-active', ...)` ✓
- Indentation matches surrounding rows ✓
- No other modifications to base.html ✓

### 2. Page template (coverage.html) — PASS
- Extends `base.html` with `{% block content %}` ✓
- Title block: "Test Coverage — IW AI Core" ✓
- Empty state: `role="status"`, hint text, `view.error` shown, `view.mtime_iso` shown when available ✓
- Available path: 4-cell grid header, per-package table with 4 metric columns + Status badge, per-row drill-down container (`#files-<pkg>`) ✓
- Threshold gap: `+N pp above` / `N pp below` — correct sign and "pp" units ✓
- Badge colors: `bg-green-100/amber-100/red-100 text-green-800/amber-800/red-800` — existing Tailwind tokens only ✓
- htmx on package rows: `hx-get`, `hx-target`, `hx-swap="innerHTML"` ✓
- Keyboard accessible: `tabindex="0"` + `hx-trigger="click, keydown[key=='Enter']"` ✓
- No inline styles, no `<style>`/`<script>` blocks ✓

### 3. Fragment template (coverage_files.html) — PASS
- Pure table fragment, no `{% extends %}`/`<html>`/`<body>` wrappers ✓
- Iterates `files` context var ✓
- Empty case: `<tr><td colspan="5">No files in this package.</td></tr>` ✓
- Same badge class pattern as page ✓

### 4. Visual consistency — PASS
- Class tokens (`bg-card`, `border border-border`, `text-muted-foreground`, `bg-muted/40`, `rounded-lg`, `overflow-x-auto`) match `status.html` and `worktrees.html` ✓
- Nav addition in base.html doesn't affect other pages ✓

### 5. Accessibility — PASS
- Empty state has `role="status"` live region ✓
- Click targets have keyboard fallback via `tabindex="0"` + `hx-trigger="click, keydown[key=='Enter']"` ✓
- Color not sole signal: badge text (`GREEN`/`AMBER`/`RED`) accompanies color ✓
- Tables have `<thead>` with `<th>` cells ✓

### 6. Conventions — PASS
- htmx-only pattern (no fetch/Alpine/React) ✓
- Tailwind utility classes only ✓
- `dashboard/CLAUDE.md` patterns followed ✓

## Quality gates

| Check | Result | Notes |
|-------|--------|-------|
| `make lint` | PASS (pre-existing) | 2 errors in `code_qa.py` (ARG001, unrelated to S02) |
| `make typecheck` | PASS (pre-existing) | 4 errors in `orch/daemon/container_info.py`, unrelated to S02 |
| `ruff check` on new Python | PASS | `dashboard/routers/coverage.py` and `dashboard/services/coverage_service.py` clean |

## Test summary

No new tests in S02 (S05 owns dashboard coverage tests). All 10 coverage service unit tests pass (reported in S02 report).

## Notes

- `role="button"` on `<tr>` is unconventional semantically but is a common htmx pattern for interactive table rows; keyboard and htmx behavior is correct.
- The `{% set badge_class = {...}[pkg.badge] %}` dynamic class pattern is used identically in `coverage_files.html`. This is a known Tailwind JIT edge case with Jinja2, but it's consistent with the existing codebase approach and uses hardcoded class strings.
- `coverage_service.py` (S01-owned, reviewed as context) is clean: proper error handling, no DB usage, returns empty-state view-model on missing/malformed JSON.

## Verdict

**PASS** — S02 frontend implementation meets all acceptance criteria in the review checklist.
