# CR-00002 S03: Frontend — Sortable column headers in History template

## Context

Read `CLAUDE.md` for project conventions. The backend (S01) has added `sort_by` and `sort_dir` to the template context. Now update the template to render sortable column headers.

## What to Change

**File**: `dashboard/templates/pages/project/history.html`

### 1. Replace static `<th>` headers with sortable links

Each column header becomes a clickable `<a>` tag that navigates to the same page with `sort_by` and `sort_dir` query params.

Column-to-sort_by mapping:
- ID → `id`
- Type → `type`
- Title → `title`
- Status → `status`
- Date → `created_at`
- Duration → `duration`

For each header:
- If this column is the currently active sort (`sort_by == column_key`), clicking toggles direction (asc↔desc)
- If this column is NOT the active sort, clicking sorts ascending
- The active column shows a direction indicator: `▲` for asc, `▼` for desc

Example header markup:
```html
<th class="px-4 py-2 text-left font-medium text-muted-foreground">
  <a href="?sort_by=id&sort_dir={{ 'desc' if sort_by == 'id' and sort_dir == 'asc' else 'asc' }}{% if type_filter %}&type={{ type_filter }}{% endif %}{% if status_filter %}&status={{ status_filter }}{% endif %}{% if date_from %}&date_from={{ date_from }}{% endif %}{% if date_to %}&date_to={{ date_to }}{% endif %}&page=1"
     class="hover:text-foreground transition-colors inline-flex items-center gap-1">
    ID
    {% if sort_by == 'id' %}
      <span class="text-primary">{{ '▲' if sort_dir == 'asc' else '▼' }}</span>
    {% endif %}
  </a>
</th>
```

Consider using a Jinja2 macro to avoid repeating the link logic 6 times:
```html
{% macro sort_header(label, key) %}
  ... 
{% endmacro %}
```

### 2. Preserve sort params in pagination links

All pagination links (`← Prev`, page numbers, `Next →`) must include `&sort_by={{ sort_by }}&sort_dir={{ sort_dir }}` alongside the existing filter params.

### 3. Preserve sort params in the filter form

Add hidden inputs inside the `<form>` so that applying a filter preserves the current sort:
```html
<input type="hidden" name="sort_by" value="{{ sort_by }}">
<input type="hidden" name="sort_dir" value="{{ sort_dir }}">
```

### 4. Reset to page 1 when sort changes

When a column header is clicked, always navigate to `page=1` since the sort order changes the page contents.

## Styling Guidelines

- Use the same Tailwind classes as existing headers: `px-4 py-2 text-left font-medium text-muted-foreground`
- Sort indicator: small text, use `text-primary` color class
- Hover state on header links: `hover:text-foreground transition-colors`
- No additional CSS files or JavaScript needed — this is pure server-side rendering with `<a>` links

## Files to Modify

- `dashboard/templates/pages/project/history.html`

## Acceptance Criteria

- All 6 column headers are clickable links
- Clicking a header sorts by that column, clicking again toggles direction
- Active sort column shows ▲ or ▼ indicator
- Sort state is preserved across pagination and filter changes
- Page resets to 1 when sort column or direction changes
- Visual style is consistent with the existing dashboard theme
