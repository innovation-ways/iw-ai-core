# CR-00036_S05_API_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Step**: S05
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Allowed: testcontainers via pytest fixtures, read-only `docker ps`/`inspect`/`logs`, `./ai-core.sh` and `make` targets. STOP and raise a blocker if a prohibited command seems necessary. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No `alembic upgrade|downgrade|stamp` against the live DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- `ai-dev/work/CR-00036/reports/CR-00036_S03_Backend_report.md` and `CR-00036_S04_CodeReview_report.md`
- `dashboard/routers/actions.py` — pattern for `restart_merge`, `abandon_merge`, `update_batch_max_parallel` (around lines 928-1630).
- `orch/services/batch_item_approval.py` (or wherever S03 placed `approve_merge`).

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S05_API_report.md`

## Context

You are wiring the dashboard HTTP routes for CR-00036. The service-layer `approve_merge` already exists from S03 — your job is the FastAPI surface.

Read the design doc, especially "Desired Behavior" (3, 5, 6) and AC4, AC6, AC11. Read `dashboard/CLAUDE.md` for the htmx fragment / `_action_response` patterns.

## Requirements

### 1. `POST /actions/item/{item_id}/approve-merge`

In `dashboard/routers/actions.py`, add a route that mirrors the shape of `restart_merge` (currently around line 928).

```python
@router.post("/item/{item_id}/approve-merge", response_class=Response)
def approve_merge_endpoint(
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Operator releases a batch item from awaiting_merge_approval to completed."""
```

Behavior:

1. Resolve the `project_id` from the request session/state via the helper sibling routes use (look at `restart_merge` for the pattern).
2. Locate the `BatchItem` for `(project_id, item_id)`. If none, return 404 via `HTTPException`.
3. Call `orch.services.batch_item_approval.approve_merge(db, project_id, item_id)`.
4. On `ValueError` (wrong status), return a 409 Conflict via `_action_response` (or whatever pattern returns an error toast).
5. On success, return `_action_response("Merge approved — item will merge on the next daemon tick.", toast_type="success")`.

Add the action to the `_VALID_ACTIONS` registry at the top of the file (around line 117, where `restart-merge` is registered).

Authorization: any authenticated dashboard user — match the implicit auth model used by `restart-merge`. No new auth gate.

### 2. `POST /project/{project_id}/api/batch/{batch_id}/auto-merge`

Add an endpoint mirroring `update_batch_max_parallel` (currently around line 1606):

```python
@router.post("/project/{project_id}/api/batch/{batch_id}/auto-merge", response_class=Response)
def update_batch_auto_merge(
    project_id: str,
    batch_id: str,
    auto_merge: str = Form(...),  # accepts "on"/"off" from htmx checkbox
    db: Session = Depends(get_db),
):
```

Behavior:

1. Convert the form value: `"on"`, `"true"`, `"1"` → `True`; `"off"`, `"false"`, `"0"`, missing → `False` (mirror the existing convention; `<input type="checkbox">` only sends the name when checked, so the route MUST handle a missing key — use `auto_merge: str | None = Form(None)` and treat None as False).
2. Load the `Batch` for `(project_id, batch_id)`. 404 if missing.
3. Reject with 409 if `batch.status` is not in `('planning', 'approved', 'paused')`. The error message MUST be operator-readable: "Cannot change auto-merge while batch is {status}".
4. Set `batch.auto_merge = new_value`. Commit.
5. Return `_action_response(f"Auto-merge set to {'on' if new_value else 'off'}.", toast_type="success")`.

### 3. Carry `auto_merge` through the create-batch-from-selection route

Locate the existing route that creates a batch from selected work items (around `dashboard/routers/actions.py:560-580`, where the `Batch(...)` constructor is called with hardcoded `max_parallel=5, auto_publish=False`). Add an `auto_merge` parameter:

- Add an optional Form field `auto_merge: str | None = Form(None)` (same checkbox convention as above).
- When unset, resolve to the project's `auto_merge_default` (from `ProjectConfig`; the route already has access to project context).
- Pass the resolved boolean into the `Batch(...)` constructor.

### 4. Confirm SSE refresh wiring

Both new endpoints should integrate with the existing SSE refresh mechanism:

- `approve-merge` triggers an item-overview refresh (the synthetic MERGE row needs to re-render). Look at how `restart_merge` handles this and copy the pattern.
- `update_batch_auto_merge` triggers a batch-header refresh (look at `update_batch_max_parallel` for the pattern).

Do NOT add a new SSE channel — reuse existing `running-update` / `batch-header-refresh` events.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- Routers thin — delegate to `orch/` services.
- `htmx` POSTs return HTML fragments via `_action_response`, not JSON.
- Composite PKs `(project_id, batch_id)`.

## TDD Requirement

Tests go in `tests/integration/test_dashboard_actions.py` (extend existing) or a new sibling file:

- `approve-merge` happy path (item in awaiting_merge_approval → 200 + status now `completed`).
- `approve-merge` rejection (item in any other status → 409, no DB mutation).
- `approve-merge` on missing item → 404.
- `update_batch_auto_merge` happy path while batch in `planning`.
- `update_batch_auto_merge` rejection while batch in `executing` (409).
- Create-batch-from-selection inherits project's `auto_merge_default` when form field absent.
- Create-batch-from-selection respects explicit form override.

## Pre-flight Quality Gates

Before reporting `complete`:

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

`make test-unit` and `make test-integration` MUST pass.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "api-impl",
  "work_item": "CR-00036",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
