# CR-00002 S04: Code Review — Frontend sortable headers

## Review Scope

Review ALL changes made in S03 (template changes in `dashboard/templates/pages/project/history.html`).

## Review Checklist

1. **Correctness**: Do all 6 headers link to the correct `sort_by` value? Does direction toggle work?
2. **Sort indicator**: Is ▲/▼ shown only on the active sort column?
3. **Param preservation**: Do all pagination links include `sort_by` and `sort_dir`?
4. **Filter form**: Are hidden inputs for sort params present inside the `<form>`?
5. **Page reset**: Do header sort links always go to `page=1`?
6. **URL encoding**: Are filter values properly escaped in URLs?
7. **Accessibility**: Are links navigable via keyboard? Do they have meaningful text?
8. **Visual consistency**: Do headers match the existing Tailwind theme (dark mode compatible)?
9. **DRY**: Is a Jinja2 macro used to avoid repeating header logic 6 times?
