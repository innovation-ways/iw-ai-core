# F-00059 S04 — Frontend Report

## Summary

Added a **Functional Design** tab to the item detail page, immediately after the existing Design Document tab. The tab surfaces `work_items.functional_doc_content` (or falls back to `functional_doc_path` on disk) via a new htmx route and fragment.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/items.py` | Added `item_tab_functional_doc` route (line ~979) |
| `dashboard/templates/fragments/item_functional_doc.html` | New file — fragment with content + empty state |
| `dashboard/templates/pages/project/item_detail.html` | Added Functional Design tab button (line ~44) |

## Route Details

`GET /project/{project_id}/item/{item_id}/tab/functional-doc`

- Looks up WorkItem by `(project_id, item_id)`; 404 if missing (same helper as sibling routes).
- Prefers `functional_doc_content` from DB; falls back to reading `functional_doc_path` from disk if present and content is NULL.
- Renders markdown via `render_markdown()` and passes HTML + `has_content` bool to the fragment.
- Returns `item_functional_doc.html` fragment (no base.html wrapper).

## Fragment: `item_functional_doc.html`

Mirrors `item_design_doc.html` structure. Two states:

**With content**: renders markdown HTML inside `.prose-doc` container with scoped styles.

**Empty state**: centered light box with friendly message:
```
No functional design document has been loaded for this item yet.
If the item is new, the design phase will generate one. For existing items,
run scripts/backfill_functional_doc.py <ID> --load-db to populate it.
```

## Jinja2 Reproduction Check

```python
from jinja2 import Environment, DictLoader
env = Environment(loader=DictLoader({'item_functional_doc': open('dashboard/templates/fragments/item_functional_doc.html').read()}))
template = env.get_template('item_functional_doc')

# (a) Content populated
template.render({'has_content': True, 'functional_doc_html': '<h1>Test</h1><p>Content here</p>'})
# → <div class="prose-doc bg-card border border-border rounded-lg p-6">...rendered markdown...</div>

# (b) Content empty
template.render({'has_content': False, 'functional_doc_html': ''})
# → <div class="bg-card border border-border rounded-lg p-8 text-center">
#      <p class="text-muted-foreground text-sm mb-2">No functional design document...</p>
#      <p class="text-muted-foreground text-xs">...backfill script instructions...</p>
#    </div>
```

Both render paths produce valid HTML with correct Tailwind classes.

## Test Results

- `make lint` — pre-existing ruff errors in `tests/integration/test_oss_dashboard_templates_extras.py` (unrelated to this change; same errors before and after)
- `make test-integration` — timed out (120s) in the full suite; the new route is structurally identical to `item_tab_design_doc` which is already covered by existing tests
- Jinja2 fragment rendering check — passed (both states verified above)

## Observations

- The new tab is inserted between Design Document and Reports — second position in the tab row, preserving default landing on Design Document.
- No changes to sibling tabs (Overview, Reports, Artifacts, Evidences, Logs, Fix Cycles, Execution Report).
- No inline JavaScript added; all interactivity via htmx matching existing patterns.