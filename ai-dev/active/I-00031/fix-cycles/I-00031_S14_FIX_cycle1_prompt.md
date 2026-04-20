# I-00031 S14 Browser Verification Fix Cycle 1/2

The end-to-end browser verification for step S14 of work item I-00031 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

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


## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/I-00031/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
