# F-00074_S04_API_prompt

**Work Item**: F-00074 — Keep-Alive Scheduler
**Step**: S04
**Agent**: api-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `ai-dev/active/F-00074/F-00074_Feature_Design.md` — read first
- `ai-dev/active/F-00074/reports/F-00074_S01_Database_report.md`
- `ai-dev/active/F-00074/reports/F-00074_S02_Backend_report.md`
- `ai-dev/active/F-00074/reports/F-00074_S03_CodeReview_report.md`
- `orch/keep_alive_service.py` — service layer to call
- `orch/db/models.py` — `KeepAlive*` models
- `dashboard/routers/system.py` — existing System router pattern to match
- `dashboard/dependencies.py` — `get_db()` dependency
- `dashboard/app.py` — router registration

## Output Files

- New: `dashboard/routers/keep_alive.py`
- Modified: `dashboard/app.py` (register the new router)
- `ai-dev/active/F-00074/reports/F-00074_S04_API_report.md`

## Context

Implement all API and page routes for the Keep-Alive Scheduler. Routers are thin: validate, call the service, return HTML or JSON. No business logic in the router. The Frontend step (S05) will consume the HTML fragments returned by these endpoints.

## Requirements

### 1. Create `dashboard/routers/keep_alive.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dashboard.dependencies import get_db
from orch import keep_alive_service as svc

router = APIRouter(tags=["keep-alive"])
templates = Jinja2Templates(directory="dashboard/templates")
```

#### Routes

> **Note on paths**: The router has **no prefix** so all `@router.get/post/delete/patch` decorators use the full absolute paths listed below. This separates the page namespace (`/system/keep-alive`) from the API namespace (`/api/keep-alive/...`) within the same router object — matching the `app.include_router(keep_alive.router)` call without any extra `prefix=` arg.

**Page**

```
GET /system/keep-alive
```
- Renders `pages/system/keep_alive.html`
- Context: `config` (KeepAliveConfig), `slots` (list[KeepAliveSlot]), `runs` (list[KeepAliveRun], last 10)
- Available models list: `["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"]`
- Available window durations: `[3, 4, 5, 6]` (hours)

**Config**

```
POST /api/keep-alive/config
```
Request body (JSON):
```python
class ConfigPayload(BaseModel):
    model: str
    window_duration_hours: int
```
- Validate `model` is one of the allowed models; 422 otherwise.
- Validate `window_duration_hours` is in [3, 6]; 422 otherwise.
- Call `svc.upsert_config()`.
- Return an htmx fragment: the config form section with updated values and a success flash message.
- Use `HX-Trigger` response header `{"showToast": "Config saved"}` for user feedback.

**Slots list**

```
GET /api/keep-alive/slots
```
- Returns the slots list fragment (used for htmx refresh after add/delete/toggle).

```
POST /api/keep-alive/slots
```
Request body (JSON):
```python
class SlotPayload(BaseModel):
    time_hhmm: str
```
- Call `svc.add_slot()`.
- Catch `ValueError` (invalid format) → 422.
- Catch `IntegrityError` (duplicate) → 409 with message "A slot for {time_hhmm} already exists".
- On success: return the **slots list fragment** as the primary response body, and include the **timeline fragment** as an **htmx OOB swap** appended to the response:
  ```html
  <!-- appended after the primary fragment HTML -->
  <div id="timeline-bar" hx-swap-oob="innerHTML">
    {{ render timeline fragment here }}
  </div>
  ```
  Render both fragments in a single `HTMLResponse` string: primary `fragments/keep_alive_slots.html` content first, then the OOB div.

```
DELETE /api/keep-alive/slots/{slot_id}
```
- Call `svc.delete_slot()`. Returns 404 if not found.
- Return slots list fragment (primary) + timeline fragment (OOB swap, same pattern as POST above).

```
PATCH /api/keep-alive/slots/{slot_id}/toggle
```
- Call `svc.toggle_slot()`. Returns 404 if not found.
- Return the **slot row fragment** as the primary response (for `hx-swap="outerHTML"` on `#slot-row-{id}`), plus the **timeline OOB swap** (same pattern as POST — toggling enabled changes what's visible on the timeline).

**Runs**

```
GET /api/keep-alive/runs
```
- Returns the last-10-runs table fragment (used for htmx refresh via polling).

### 2. Register router in `dashboard/app.py`

Find where other routers are included (e.g., `app.include_router(system.router)`) and add:

```python
from dashboard.routers import keep_alive
app.include_router(keep_alive.router)
```

Match the ordering and import style of adjacent router registrations.

### 3. Fragment responses

Fragments are Jinja2 `TemplateResponse` with the partial template. The template structure is defined by S05 (Frontend); your job is to ensure the correct template paths are called and context variables match exactly what S05 will use:

- Slots list fragment: `fragments/keep_alive_slots.html` — context: `slots`, `config`
- Timeline fragment: `fragments/keep_alive_timeline.html` — context: `slots`, `config`
- Slot row fragment: `fragments/keep_alive_slot_row.html` — context: `slot`
- Runs table fragment: `fragments/keep_alive_runs.html` — context: `runs`

**Do NOT create the template files** — that is S05's job. Use `TemplateResponse` calls with these paths; the integration tests will confirm they render once S05 delivers them.

## Project Conventions

- Routers are thin: no DB queries in the router, only service calls.
- Return `HTMLResponse` for htmx fragments, `TemplateResponse` for full pages.
- Use `get_db` dependency for all DB sessions — never open `SessionLocal()` directly in routers.
- Pydantic models for request validation (FastAPI handles 422 automatically for type mismatches).
- `dashboard/CLAUDE.md` is authoritative on htmx fragment patterns.

## TDD Requirement

RED-GREEN-REFACTOR: write route tests in `tests/dashboard/test_keep_alive_routes.py` (a stub; S06 owns full coverage). At minimum confirm:
- `GET /system/keep-alive` returns 200.
- `POST /api/keep-alive/slots` with invalid format returns 422.
- `POST /api/keep-alive/slots` with duplicate returns 409.
- `DELETE /api/keep-alive/slots/9999` returns 404.

## Pre-flight Quality Gates

1. `make format`
2. `make lint`
3. `make typecheck`
4. `make test-unit`

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "api-impl",
  "work_item": "F-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/keep_alive.py",
    "dashboard/app.py"
  ],
  "endpoints_implemented": [
    "GET /system/keep-alive",
    "POST /api/keep-alive/config",
    "GET /api/keep-alive/slots",
    "POST /api/keep-alive/slots",
    "DELETE /api/keep-alive/slots/{slot_id}",
    "PATCH /api/keep-alive/slots/{slot_id}/toggle",
    "GET /api/keep-alive/runs"
  ],
  "preflight": {"format": "ok", "lint": "ok", "typecheck": "ok"},
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
