# CR-00078_S06_API_report.md

**Step**: S06 — API & Endpoints  
**Work Item**: CR-00078 — Per-batch ignore overlap & force-start  
**Agent**: api-impl  
**Date**: 2026-05-23

---

## What was done

Implemented the three new API endpoints for CR-00078 per the design spec:

### 1. `POST /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}/ignore`

**File**: `dashboard/routers/actions.py`

- Accepts `blocking_item_id`, `file_pattern` (required), and `reason` (optional) as Form fields
- Resolves project, batch, and batch_item with 404 on missing
- Uses `INSERT ... ON CONFLICT DO NOTHING` via `sqlalchemy.dialects.postgresql.insert` for idempotency (same pair in same batch → no-op)
- Sets `ignored_by = "operator"` with inline TODO comment
- Emits `batch_overlap_ignored_by_operator` DaemonEvent
- Returns `HTMLResponse("")` — htmx `outerHTML` swap on `closest .iw-modal-file-row` removes the row

### 2. `POST /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}/ignore-all`

**File**: `dashboard/routers/actions.py`

- No body fields required
- Resolves project, batch, and batch_item with 404 on missing
- Reuses `_get_item_scope_events` helper (same 300s window as `_get_scope_statuses` in batches.py) to query recent `item_held_for_scope` events for the held item
- Builds deduped set of `(blocking_item_id, file_pattern)` pairs from all events' `conflicting_globs`
- Bulk `INSERT ... ON CONFLICT DO NOTHING` for all pairs
- Emits `batch_overlap_ignore_all_by_operator` DaemonEvent with `{candidate_item_id, count, pairs}`
- Returns `HTMLResponse("")` — htmx `innerHTML` swap on `#overlap-modal-root` closes the modal

### 3. GET overlap modal — modified to filter ignored pairs

**File**: `dashboard/routers/batches.py`

- Added `overlap_modal` GET endpoint at `/project/{project_id}/batch/{batch_id}/overlap/{held_item_id}`
- On entry: queries `BatchOverlapIgnore` for `(project_id, batch_id, held_item_id)` to build the `ignored_set`
- Fetches recent `item_held_for_scope` events (same 300s window)
- Groups events into `(blocking_id, glob)` → globs list, then filters out any pair already in `ignored_set`
- If after filtering no sections remain, returns the template with empty `sections` (up to S07 frontend to decide the empty state)
- Renders via `fragments/overlap_modal.html`

### 4. Timeline rendering (logs tab)

**File**: `dashboard/templates/pages/project/batch_detail.html`

The existing `logs` tab iterates `batch_events` and renders each event's `event_type` and `message`. The three new event types (`batch_overlap_ignored_by_operator`, `batch_overlap_ignore_all_by_operator`, `batch_overlap_allowed_by_ignore`) will appear with the default `bg-secondary text-secondary-foreground` badge since they don't match any of the existing colour predicates (`failed`, `completed`, `launched`).

This matches the existing pattern: the template renders whatever `event_type` is stored, and the message comes from `ev.message` which is populated by the `_emit` call in each endpoint. Defensive `.get()` access is used in all emit calls so missing metadata keys fall back safely.

No separate render function was added — the existing Jinja2 iteration over `batch_events` handles the new event types without changes.

---

## Files changed

| File | Change |
|------|--------|
| `dashboard/routers/actions.py` | Added two new POST endpoints + helper `_resolve_overlap_context`, `_get_item_scope_events`; added `BatchOverlapIgnore` to imports; added `pg_insert` at top-level sqlalchemy import |
| `dashboard/routers/batches.py` | Added `BatchOverlapIgnore` to imports; added `_get_item_scope_events` helper; added `overlap_modal` GET endpoint; added CR-00078 section comment |

---

## Preflight results

| Check | Result |
|-------|--------|
| `make format` | ✅ 851 files already formatted |
| `make typecheck` | ✅ Success: no issues found |
| `make lint` | ✅ All checks passed |

**Note on lint**: The `sqlalchemy.dialects.postgresql` import was moved to the top-level `from sqlalchemy import select` block rather than placed in a late-import block inside the CR-00078 section. This avoids a `I001 import block is un-sorted or un-formatted` error from ruff (the late import sits between section headers and the next function, creating an unsortable position). The `# noqa: E402` comment is preserved on the inline form.

---

## Test verification

Ran targeted tests on existing batch action tests:
```
uv run pytest tests/dashboard/test_batches_progress_parity.py -v
→ 16 passed in 28.98s
```

No test file `tests/dashboard/test_actions.py` exists in this worktree. The existing test suite covers the `batches.py` router at module level; endpoint-level behavioural tests are owned by S10.

---

## TDD evidence

`tdd_red_evidence`: `"n/a — endpoint implementation; behavioural tests owned by S10"`

---

## Observations / Notes

1. **Idempotency**: Both `ignore` and `ignore-all` use `ON CONFLICT DO NOTHING` against the composite PK. Repeated POSTs for the same `(project_id, batch_id, held_item_id, blocking_item_id, file_pattern)` are safe no-ops.

2. **Shared helper**: `_get_item_scope_events` is defined in both `batches.py` and `actions.py`. Both mirror the 300s window query from `_get_scope_statuses`. If a future CR refactors scope queries into a shared module, this duplication can be consolidated.

3. **Auth placeholder**: `ignored_by` is hardcoded to `"operator"`. The inline `# TODO(auth): replace placeholder when session subjects land` comment marks the spot for S08 auth.

4. **Missing template**: `fragments/overlap_modal.html` does not yet exist. The GET endpoint returns `templates.TemplateResponse("fragments/overlap_modal.html", ...)`. S07 creates this template; the GET will 500 until then (expected — S07 owns the frontend). S10's tests will stub or mock the template render.