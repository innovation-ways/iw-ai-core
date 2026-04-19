# CR-00010 S03 Frontend Report

## Summary

Implemented all dashboard UI changes for CR-00010 (Research items auto-complete without manual approval).

## Files Changed

| File | Changes |
|------|---------|
| `dashboard/routers/actions.py` | Added `WorkItemType` import; `approve_item` and `unapprove_item` now return HTTP 422 with descriptive message when item type is Research |
| `dashboard/routers/project_pages.py` | Added `WorkItem.type != WorkItemType.Research` to `_queue_items()` query so research items are excluded from the approved-items list |
| `dashboard/templates/fragments/item_header.html` | Added `{% elif item_type == 'Research' %}` branch that replaces action buttons with an inline explanatory notice |
| `dashboard/templates/pages/project/queue.html` | Wrapped the drafts table row in `{% if item.type != 'Research' %}` as defense-in-depth; also acts as template-level filter for the batch-queue |

## Audited Templates

All templates containing "approve" or "unapprove" were checked:

| Template | Approve/Unapprove Present? | Action Taken |
|----------|---------------------------|-------------|
| `pages/project/queue.html` | Yes — approve button in draft rows, batch creation from approved rows | Added `{% if item.type != 'Research' %}` guard on draft approve button; batch-queue query already excludes research |
| `fragments/item_header.html` | Yes — approve (draft) and unapprove (approved) buttons | Added `{% elif item_type == 'Research' %}` inline notice branch |
| `pages/project/batch_detail.html` | No — uses "approved" only as a batch status label, not an action | No change |
| `fragments/batch_detail_header.html` | No — "approve" is a batch-level action (not item-level) | No change |
| `components/status_badge.html` | No — only contains CSS class mapping | No change |

## Backend Changes (query filter)

`dashboard/routers/project_pages.py:_queue_items()` — added `WorkItem.type != WorkItemType.Research` to the SQLAlchemy query predicate at line 83. This excludes research items from both `approved` and `draft` result sets in the queue page query. The template iterates over `approved_items` (never contains research after this filter) and `draft_items` (now additionally guarded with `{% if item.type != 'Research' %}`).

## Test Results

- **ruff check**: All checks passed
- **ruff format**: All files already formatted
- **mypy**: No issues found in 2 source files
- **Unit tests**: 818 passed, 5 warnings (no regressions)

## Notes

- `WorkItemType` was already imported in `project_pages.py` (line 22), so no new import needed there
- `WorkItemType` was added to the `actions.py` import block alongside the existing `WorkItemStatus` import
- The approve/unapprove route rejection uses `HTTPException(status_code=422, detail=...)` matching the existing invalid-transition pattern in `actions.py` (lines 460–464)
- The `item_header.html` inline notice uses existing CSS utility classes (`rounded border border-muted bg-muted/20 p-3 text-sm text-muted`) with no new styles added
- `item_type` in `item_header.html` is the pre-computed string already passed by `items.py:814` (`"item_type": item.type.value`), so comparison is against the string `'Research'` without `.value`
- The `queue.html` template's `item.type` refers to the `QueueItem.type` string field (set from `r.type.value` at `project_pages.py:89`), so the comparison `item.type != 'Research'` is correct for that context