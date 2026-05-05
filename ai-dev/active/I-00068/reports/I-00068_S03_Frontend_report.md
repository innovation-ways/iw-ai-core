# I-00068 S03 Frontend Report

## Work Item

I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/

## Step

S03 - Frontend Implementation

## Agent

frontend-impl

## What Was Done

### Template Fix

Modified `dashboard/templates/pages/project/dashboard.html` to add a defensive prefix check in the Recent Activity fallback. Any `entity_id` starting with `BATCH-` now routes to `/batch/` even when `entity_type` is missing (historical data case).

**Change location**: Lines 115-125 in the Recent Activity loop.

**Before**:
```jinja
{% elif event.entity_id %}
  <a href="/project/{{ current_project.id }}/item/{{ event.entity_id }}" ...>
{% endif %}
```

**After**:
```jinja
{% elif event.entity_id and event.entity_id.startswith('BATCH-') %}
  <a href="/project/{{ current_project.id }}/batch/{{ event.entity_id }}" ...>
{% elif event.entity_id %}
  <a href="/project/{{ current_project.id }}/item/{{ event.entity_id }}" ...>
{% endif %}
```

The explicit `entity_type == 'batch'`, `entity_type == 'doc_job'`, and `entity_type == 'work_item'` branches remain byte-identical.

### Test Added

Added `TestRecentActivityBatchPrefixFallback` class to `tests/integration/test_i00068_batch_link_routing.py` with one test:

- `test_batch_id_with_none_entity_type_routes_to_batch_route`: Verifies that a `BATCH-` ID with `entity_type=None` correctly routes to `/batch/BATCH-99999` instead of `/item/BATCH-99999`.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/pages/project/dashboard.html` | Added BATCH- prefix check in fallback |
| `tests/integration/test_i00068_batch_link_routing.py` | Added frontend routing test |

## Test Results

**All 54 tests pass** (50 from `test_dashboard_pages.py` + 3 from `TestBatchArchiverEmitEntityType` + 1 from `TestRecentActivityBatchPrefixFallback`).

Key regression tests verified:
- `test_recent_activity_batch_event_links_to_batch_route` ✅
- `test_recent_activity_doc_job_event_links_to_doc_job_route` ✅
- `test_recent_activity_work_item_event_links_to_item_route` ✅
- `test_recent_activity_unknown_entity_type_falls_back_to_item_route` ✅
- `test_recent_activity_no_link_renders_when_entity_id_is_null` ✅

## Preflight Quality Gates

| Check | Result |
|-------|--------|
| `make format` | Fixed (ruff format applied to test file) |
| `make typecheck` | ok (no issues) |
| `make lint` | ok (no issues in changed files) |

## Notes

- The fix is purely Jinja2 template logic - no JavaScript changes needed.
- No new Tailwind CSS classes introduced.
- The `startswith('BATCH-')` check is case-sensitive as required.
- Autoescape is preserved - `{{ event.entity_id }}` is still rendered through Jinja2's default autoescape.
- The test passes when run alongside other dashboard tests but required fixture setup from the full test suite context.