# I003_S01_Frontend_prompt

**Work Item**: I003 — History Page Sorting Broken — Replace with Client-Side JS Sorting
**Step**: S01
**Agent**: Frontend

---

## Input Files

- `ai-dev/design/active/I003/I003_Issue_Design.md` — Design document

## Output Files

- `ai-dev/design/active/I003/reports/I003_S01_Frontend_report.md` — Step report

## Context

You are fixing a broken sorting mechanism on the History page. The current implementation uses server-side sorting via `<a>` links that trigger full page reloads. You must replace it with client-side JavaScript sorting, using the **exact same pattern** as the working Batches page.

Read the design document first, then read `CLAUDE.md` for project conventions.

**Reference implementation**: `dashboard/templates/pages/project/batches.html` (lines 106-154) — this is the working sorting pattern to replicate.

## Requirements

### 1. Replace `sort_header` macro with client-side sortable headers

**File**: `dashboard/templates/pages/project/history.html`

Remove the `sort_header` Jinja2 macro (lines 4-16) and replace the `<thead>` section with sortable `<th>` elements using the batches pattern:

```html
<th class="px-4 py-2 text-left font-medium text-muted-foreground cursor-pointer
           select-none hover:text-foreground transition-colors"
    data-sort-key="<key>"
    onclick="sortTable('<key>')">
  <span class="inline-flex items-center gap-1">
    {{ label }}
    <svg class="w-3 h-3 sort-icon opacity-0 transition-opacity" viewBox="0 0 10 6"
         fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
      <path d="M1 1 L5 5 L9 1"/>
    </svg>
  </span>
</th>
```

Columns to make sortable: ID (`id`), Type (`type`), Title (`title`), Status (`status`), Date (`created_at`), Duration (`duration`).

### 2. Add `data-sort-*` attributes to each `<tr>`

On each item row in `<tbody>`, add data attributes for sorting:

```html
<tr ... 
    data-sort-id="{{ item.id }}"
    data-sort-type="{{ item.type }}"
    data-sort-title="{{ item.title }}"
    data-sort-status="{{ item.status }}"
    data-sort-created_at="{{ item.created_at.isoformat() }}"
    data-sort-duration="{{ item.duration_secs if item.duration_secs is not none else -1 }}">
```

### 3. Add inline `sortTable()` JavaScript

Add a `<script>` block at the end of the template (before `{% endblock %}`) with the same sorting logic as `batches.html:106-154`. Key points:

- Table ID: add `id="history-table"` to the `<table>` element
- `isNumeric(key)` should return `true` for `duration` 
- `sortTable(key)` toggles direction on repeated clicks
- Sort indicators: SVG chevron opacity and rotation
- Use `#history-table` selector (not `#batches-table`)

### 4. Remove pagination UI

Remove the entire pagination section (current lines 137-173). All items will be loaded at once.

### 5. Remove sort-related hidden inputs and URL params from filter form

- Remove the hidden inputs for `sort_by` and `sort_dir` (current lines 28-29)
- Remove `sort_by`/`sort_dir` from the "Clear" link URL (current line 75)
- The filter form should only submit type, status, date_from, date_to

### 6. Update results count

Change the "Showing X–Y of Z items" text to just "{{ total }} items" (no pagination range).

### 7. Remove the empty-row "No history found" handling

Keep the empty state message but update the `<td colspan>` to match the column count (6 columns). Mark the empty row with `class="empty-row"` so `sortTable` can exclude it (same as batches pattern):

```html
{% if not items %}
  <tr class="empty-row">
    <td colspan="6" ...>No history found...</td>
  </tr>
{% endif %}
```

## Project Conventions

Read the project's `CLAUDE.md` for:
- Dashboard uses FastAPI + Jinja2 + htmx + Tailwind CDN
- No build step for frontend
- Follow existing patterns in the codebase

## TDD Requirement

This is a template change — TDD applies at the integration level. The Tests agent (S05) will write the formal tests. Focus on making the template work correctly.

## Test Verification (NON-NEGOTIABLE)

After implementation:
1. Run `make lint` and `make format-check`
2. Verify the template renders without Jinja2 errors by checking the dashboard starts
3. Do **NOT** report `tests_passed: true` unless checks pass

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Frontend",
  "work_item": "I003",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
