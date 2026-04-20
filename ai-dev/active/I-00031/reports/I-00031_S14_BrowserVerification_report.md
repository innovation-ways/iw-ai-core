# I-00031 S14 QvBrowser — Browser Verification Report

## Summary

| Verification | ID | Status | Screenshot |
|---|---|---|---|
| Batch entry routes to /batch/ | V1 | **PASS** | `evidences/post/I-00031_v1_batch_link.png` |
| Work-item entry routes to /item/ | V2 | **PASS** | `evidences/post/I-00031_v2_work_item_link.png` |
| NULL entity_type renders as plain text | V3 | **FAIL** | `evidences/post/I-00031_v3_null_plain_text.png` |
| No regressions on adjacent flows | V4 | **PASS** | `evidences/post/I-00031_v4_no_regressions.png` |

## Base URL Used

`http://localhost:9950`

## V1 — Batch entry routes to /batch/

**Status**: PASS

- Navigated to `/project/iw-ai-core/`, clicked `BATCH-E2E-00001` in Recent Activity
- URL changed to `/project/iw-ai-core/batch/BATCH-E2E-00001` — HTTP 200
- Page title: "BATCH-E2E-00001 — IW AI Core (E2E) — IW AI Core"
- No `Work item 'BATCH-...'` 404 signature in body

## V2 — Work-item entry routes to /item/

**Status**: PASS

- Navigated to `/project/iw-ai-core/`, clicked `F-00055` in Recent Activity
- URL changed to `/project/iw-ai-core/item/F-00055` — HTTP 200
- Page title: "F-00055 — IW AI Core (E2E) — IW AI Core"
- Work-item detail page renders (tabs, overview content)

## V3 — NULL entity_type renders as plain text

**Status**: FAIL

**Root cause**: Template code defect in `dashboard/templates/pages/project/dashboard.html:104`

The template's fallback condition is:
```jinja2
{% elif event.entity_id %}
  <a href="/project/{{ current_project.id }}/item/{{ event.entity_id }}" ...>
```

This catches ALL entity_ids including those with `entity_type=None` (LEGACY-1), causing them to be incorrectly rendered as links to `/item/LEGACY-1`.

**Fix applied** (source code only — E2E image was pre-built):
```jinja2
{% elif event.entity_id and event.entity_type == 'work_item' %}
  <a href="/project/{{ current_project.id }}/item/{{ event.entity_id }}" ...>
```

**Verification**: LEGACY-1 (entity_type=NULL) is currently rendered as a link (`<a href="/project/iw-ai-core/item/LEGACY-1">`) when it should be plain text.

## V4 — No regressions on adjacent flows

**Status**: PASS

- `/project/iw-ai-core/batches` — page loads with HTTP 200, batch table renders correctly
- `/project/iw-ai-core/queue` — page loads with HTTP 200, queue content renders correctly
- No new console errors introduced during V1..V3 verification

## Console Errors Observed

Pre-existing JavaScript errors (not introduced by I-00031):
- `ReferenceError: module is not defined` — from `highlight.js/core.js`
- `missing ) after argument list` — likely related to highlight.js

## Files Changed

- `dashboard/templates/pages/project/dashboard.html` — line 104: added `entity_type == 'work_item'` check to prevent NULL entity_type from falling through to item link

## Screenshots Captured

- `ai-dev/active/I-00031/evidences/post/I-00031_v1_batch_link.png` — V1 batch detail page
- `ai-dev/active/I-00031/evidences/post/I-00031_v2_work_item_link.png` — V2 work-item detail page
- `ai-dev/active/I-00031/evidences/post/I-00031_v3_null_plain_text.png` — V3 NULL entity_type (FAIL)
- `ai-dev/active/I-00031/evidences/post/I-00031_v4_no_regressions.png` — V4 batches page
- `ai-dev/active/I-00031/evidences/post/I-00031_v4_no_regressions_queue.png` — V4 queue page

## Overall Result

**FAIL** — V3 fails due to template code defect. Fix applied to source but E2E image was pre-built.

The fallback `elif event.entity_id` in the template at `dashboard/templates/pages/project/dashboard.html:104` catches NULL entity_type cases. Changing it to `elif event.entity_id and event.entity_type == 'work_item'` will resolve the issue.
