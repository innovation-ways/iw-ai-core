# I-00054 S01 Frontend Report

## Summary

Fixed the coverage page toggle label bug in `dashboard/templates/pages/system/coverage.html`. The label "click to expand" never changed when a row was expanded, and clicking an expanded row would re-fetch instead of collapse.

## Changes Made

### File: `dashboard/templates/pages/system/coverage.html`

**1. Added toggle state attributes to `<tr>` (lines 73–81)**

```html
<tr class="border-t border-border hover:bg-muted/30 cursor-pointer"
    role="button"
    tabindex="0"
    data-pkg-toggle="{{ pkg.name }}"
    data-expanded="false"
    hx-get="/system/coverage/files/{{ pkg.name }}"
    hx-target="#files-{{ pkg.name }}"
    hx-trigger="click[this.dataset.expanded!='true'], keydown[key=='Enter'][this.dataset.expanded!='true']"
    hx-swap="innerHTML">
```

- `data-pkg-toggle="{{ pkg.name }}"` — identifies the row for the JS collapse handler
- `data-expanded="false"` — tracks expanded/collapsed state
- `hx-trigger` guard condition `this.dataset.expanded!='true'` prevents htmx from firing when already expanded (collapse path is handled by vanilla JS click listener)

**2. Added id to label `<td>` (line 94)**

```html
<td id="expand-label-{{ pkg.name }}" class="px-4 py-3 text-xs text-muted-foreground">click to expand</td>
```

- Gives JS a stable selector to update label text

**3. Added inline `<script>` block at bottom of `{% block content %}` (lines 108–137)**

- Vanilla JS click listener on each toggle row: when `data-expanded === 'true'`, clears the files div and resets state
- `htmx:afterSwap` listener: after htmx injects content, marks row expanded and updates label to "click to collapse"

## How It Works

- **Expand**: htmx fires (because `data-expanded` is `'false'`) → content injected → `htmx:afterSwap` fires → JS sets `data-expanded='true'` and label to "click to collapse"
- **Collapse**: `data-expanded` is `'true'` → htmx trigger guard blocks request → vanilla JS click listener clears div, resets `data-expanded='false'`, resets label to "click to expand"

## Preflight Quality Gates

| Check | Result |
|-------|--------|
| `make format` | ok — 503 files already formatted |
| `make typecheck` | ok — no issues in 210 source files |
| `make lint` | ok — all checks passed |

## Unit Tests

- `make test-unit`: **2 failed, 2197 passed**
- The 2 failures are pre-existing and unrelated to this change:
  - `test_apply_refuses_in_agent_context` and `test_rollback_refuses_in_agent_context` in `tests/unit/test_safe_migrate.py` — these fail due to environment/hostname resolution issues in the test environment, not anything related to this fix

## Files Changed

- `dashboard/templates/pages/system/coverage.html`

## Notes

- This is a template-only fix — no backend, no routes, no service changes
- No new Tailwind classes added → `make css` not needed
- The fix follows existing dashboard conventions (vanilla JS in inline `<script>`, htmx for async content fetch)
- Inline `<script>` blocks are not linted by `node --check` (confirmed by running `make lint`)