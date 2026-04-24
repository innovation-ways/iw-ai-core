# F-00060 S06 — Frontend Report

## What Was Done

1. **Added "Re-index Docs" dropdown entry** to `dashboard/templates/project_code.html` — positioned immediately below "Re-index changed files" in the action dropdown. Uses identical CSS classes and htmx attributes as sibling entries (`hx-post`, `hx-target="#code-status-panel"`, `hx-swap="innerHTML"`). Calls `POST /project/{id}/api/code/reindex-docs`.

2. **Parameterised `code_job_status.html` fragment** — changed the hardcoded "Indexing files..." label to `{% if job_type_label %}{{ job_type_label }}{% else %}Indexing files...{% endif %}`. The S05 API endpoint already passes `job_type_label: "Doc indexing"`; code index calls pass no label, so the default is preserved.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/project_code.html` | New dropdown button for `reindex-docs` action |
| `dashboard/templates/fragments/code_job_status.html` | Made phase label template-driven via `job_type_label` |

## Static Checks

```
grep -n 'reindex-docs' dashboard/templates/project_code.html → 1 match (line 65)
grep -n 'Re-index Docs' dashboard/templates/project_code.html → 1 match (line 73)
```

## Fragment Rendering

```python
# With job_type_label="Doc indexing"  → label renders as "Doc indexing"
# Without job_type_label             → label renders as "Indexing files..." (default)
```

## Test Results

- `make typecheck` — Success: no issues found (152 source files)
- `make lint` — 3 pre-existing PT018 errors in unrelated test file `tests/integration/test_oss_dashboard_templates_extras.py`; none in changed files
- `pytest tests/integration/test_reindex_docs_endpoint.py` — **9/9 passed**

## Observations

- S05 API endpoint (`reindex_docs`) already passes `job_type_label: "Doc indexing"` in its template context — this step only needed to wire the label into the fragment.
- The "Re-index Docs" button reuses the same refresh/cycle SVG icon as sibling entries, consistent with the dropdown's index-family grouping.
- No new CSS, JS, or dependencies introduced.
