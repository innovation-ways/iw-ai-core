# F-00081 S04 — API Implementation Report

**Work Item**: F-00081 — Per-Item / Per-Step Agent + Model Override
**Step**: S04 (API Implementation)
**Agent**: api-impl

---

## What Was Done

Implemented four HTTP endpoints for runtime override controls:

1. **`GET /project/{project_id}/api/runtime-options`** — Returns enabled `agent_runtime_options` rows ordered by `sort_order, id`, with `Cache-Control: max-age=60`. Used by the frontend to populate dropdowns.

2. **`PATCH /project/{project_id}/api/item/{item_id}/runtime-override`** — Sets or clears the item-level override. Validates item exists, has at least one editable step (`pending | failed`), and `option_id` references an enabled row. Emits one `runtime_override_changed` DaemonEvent.

3. **`PATCH /project/{project_id}/api/item/{item_id}/step/{step_id}/runtime-override`** — Sets or clears the step-level override. Validates step status is `pending` or `failed`. Returns 409 Conflict for non-editable steps (AC4). Emits one `runtime_override_changed` DaemonEvent.

4. **`PATCH /project/{project_id}/api/item/{item_id}/runtime-override/bulk`** — Applies override to all editable steps in one transaction. Silently skips non-editable steps. Emits exactly one DaemonEvent when any steps are updated; zero events when zero steps are updated (boundary case AC6).

All PATCH endpoints accept `application/x-www-form-urlencoded` with `option_id` as an integer or empty string (to clear).

### Notable design decisions

- **`StepStatus.paused` does not exist** — `paused` is a `WorkItemStatus`, not a `StepStatus`. The actual editable step statuses are `pending` and `failed`. The design doc AC4 says `pending | failed | paused` but the StepStatus enum has no `paused` value; S01 did not add it. The implementation uses the actual enum values (`pending | failed`). This is a discrepancy between the design doc and the S01 schema.

- **Actor placeholder** — Uses `"dashboard"` as the actor string since no real auth model exists (matching the pattern used by other endpoints in `actions.py`).

- **htmx response shape** — All PATCH endpoints return `204 No Content`. The frontend (S05) re-fetches via htmx to refresh badges after a change. The GET endpoint returns JSON (the one JSON exception per the design doc's catalogue endpoint).

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/runtime_overrides.py` | New router with 4 endpoints |
| `dashboard/app.py` | Registered `runtime_overrides.router`; ruff auto-fixed an import sort issue |
| `tests/dashboard/test_runtime_overrides_api.py` | 23 tests covering all endpoints and rejection cases |

---

## Test Results

```
tests/dashboard/test_runtime_overrides_api.py: 23 passed
tests/integration/test_agent_runtime_options.py: 14 passed (S01)
tests/unit/test_agent_runtime_resolver.py: 8 passed (S02)
tests/unit/test_agent_runtime_audit.py: 5 passed (S02)
```

**Full dashboard suite**: 566 passed, 14 skipped, 1 xfailed (all pre-existing).

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ 2 files reformatted (runtime_overrides.py + test file), 654 files already formatted |
| `make typecheck` | ✅ No issues in 238 source files |
| `make lint` | ✅ All checks passed (ruff auto-fixed app.py import sort) |
| `make test-frontend` | ✅ 566 passed, 14 skipped, 1 xfailed |
| `make test-integration` | Timed out at 300s (full suite); targeted run of `test_agent_runtime_options.py` passed (14/14) |

---

## Notes

- The GET endpoint had a bug where `project_id` was named `_project_id`, causing FastAPI to treat it as a required query parameter instead of a path parameter. Fixed by using `project_id` directly.

- The `emit_runtime_override_changed` helper from `orch/agent_runtime/audit.py` (S02) was used for all DaemonEvent emission, satisfying AC6 (single event per API call, even for bulk).

- The bulk endpoint skips non-editable steps silently (no error) and emits no event when zero steps are affected — matching the boundary case in the design doc.

---

**Next step**: S05 (Frontend) — compressed strip macro, new CLI/Model columns + dropdowns.
