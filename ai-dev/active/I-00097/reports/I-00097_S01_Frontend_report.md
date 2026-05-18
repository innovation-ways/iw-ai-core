# I-00097 S01 — Frontend Report

## What was done

Two small Jinja2 template polish changes:

### 1. Smart $0 formatting (auto_merge_rollup.html:22)

Replaced `${{ "%.6f"|format(token_cost_rollup.total_cost_usd) }}` with a conditional that renders `$0` for exact zero, and strips trailing zeros for non-zero values (e.g. `$0.000123` instead of `$0.000123000000`).

### 2. Linkified entity_id (auto_merge_event_row.html:5)

Replaced plain text `{{ row.entity_id or '—' }}` with a conditional that renders an `<a>` tag when `entity_id` matches the pattern `^(F|I|CR)-\d{5}$`, linking to `/project/{project_id}/item/{entity_id}`. Falls back to plain text for non-matching values, and preserves `—` for null.

## Files changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/auto_merge_rollup.html` | Smart $0 formatting (lines 22) |
| `dashboard/templates/fragments/auto_merge_event_row.html` | Conditional linkification (lines 5-14) |
| `dashboard/app.py` | Added `work_item_id` Jinja2 filter (lines 349-360) |

## URL pattern

Used singular `/project/{project_id}/item/{item_id}` — confirmed by `dashboard/routers/items.py:1124` (`@router.get("/item/{item_id}")` under the `/project/{project_id}` prefix). Grep of existing templates confirmed this is the established convention.

## Jinja2 filter approach

Jinja2's built-in `is match(...)` test does NOT exist in jinja2 3.1.6. Instead, added a `work_item_id` filter registered via `templates.env.filters["work_item_id"] = _is_work_item_id` in `app.py`. Template uses `(_eid | work_item_id)` — filter style — which is the correct approach.

## Pre-flight quality gates

- `make format`: ok (750 files already formatted)
- `make typecheck`: ok (no issues in 255 source files)
- `make lint`: ok (all checks passed)

## Test results

```
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
============================= 25 passed in 32.31s ==============================
```

All 25 tests passed. The failure in the first run was due to using `is work_item_id` (Jinja2 test syntax) which doesn't exist — fixed by switching to `| work_item_id` (filter syntax) with the filter properly registered in `app.py`.

## Notes

- No existing `work_item_id` helper was found in the codebase, so a new small filter was added to `app.py` alongside the other template helpers.
- The `_work_item_re` variable name was lowercase to pass `make lint` (N806 — constant names must be lowercase).
- AC5 (null entity_id renders as `—`) is preserved by the explicit `{% else %}—{% endif %}`. The `—` is only rendered when `_eid` is falsy (None or empty string).