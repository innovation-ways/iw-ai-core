# CR-00014_S05_API_prompt

**Work Item**: CR-00014 — Orchestration DB instance-identity fingerprint
**Step**: S05
**Agent**: api-impl

---

## Input Files

- `ai-dev/active/CR-00014/CR-00014_CR_Design.md` — Design document (Desired Behavior points 4 + 6, AC1–AC3)
- `ai-dev/active/CR-00014/reports/CR-00014_S03_Backend_report.md` — identity module is available as `orch.db.identity`
- `dashboard/app.py` — FastAPI factory `create_app()` — registration point for lifespan / routes / middleware
- `dashboard/dependencies.py` — `get_db` session pattern
- `dashboard/CLAUDE.md` — dashboard-specific conventions (htmx, auth patterns if any)

## Output Files

- `ai-dev/active/CR-00014/reports/CR-00014_S05_API_report.md`
- `dashboard/app.py` — startup gate via FastAPI lifespan
- `dashboard/routers/healthz.py` (new, if no existing `healthz` router) — `/healthz/identity` endpoint
- Related: register the new router in `create_app()`

## Context

You're adding the dashboard-side of identity verification. The dashboard must: (a) refuse to accept traffic if identity is mismatched at startup, and (b) expose `/healthz/identity` so external probes can detect mismatch even after a hot-swap (theoretical — dashboards don't live-reload DB connections, but the endpoint is still cheap insurance).

Read the design doc's AC2 and AC3 to understand the exact HTTP contract.

## Requirements

### 1. FastAPI lifespan gate

Replace or augment the current `create_app()` factory with a lifespan handler (FastAPI 0.93+ pattern: `@asynccontextmanager` yielded from a `lifespan=` argument to `FastAPI(...)`).

On startup (before `yield`):

- Open a short-lived `SessionLocal()` session.
- Call `orch.db.identity.verify_instance_identity(session)`.
- On `IdentityStatus.mode == "match"`: log INFO `Dashboard: DB identity verified (<short-uuid>)`; proceed.
- On `"bootstrap"`: log the bootstrap notice at INFO (once per process); proceed.
- On `"mismatch"` or `"missing"` with env set: log the boxed ERROR block at ERROR level, then **raise** `RuntimeError` so FastAPI startup fails and uvicorn reports unhealthy. Do NOT `sys.exit` from within a library boundary — raise and let uvicorn propagate.

If the current `create_app()` does not have a lifespan, introduce one. Don't break any existing startup hooks — migrate any existing `@app.on_event("startup")` callbacks into the lifespan handler (they're deprecated anyway in modern FastAPI).

### 2. `/healthz/identity` endpoint

Add a new router `dashboard/routers/healthz.py` (or extend an existing healthz router if one already exists — search `dashboard/routers/` first):

```python
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from orch.db.identity import check_identity, IdentityStatus
from dashboard.dependencies import get_db

router = APIRouter(prefix="/healthz", tags=["health"])


@router.get("/identity")
def identity_check(response: Response, session: Session = Depends(get_db)) -> dict:
    status_info: IdentityStatus = check_identity(session)  # never raises

    payload = {
        "expected": str(status_info.expected) if status_info.expected else None,
        "actual": str(status_info.actual) if status_info.actual else None,
        "mode": status_info.mode,
        "match": status_info.mode == "match",
    }

    if status_info.mode in ("mismatch", "missing"):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload
```

- Register the router in `create_app()`.
- Endpoint MUST bypass any auth middleware. If the dashboard uses auth (check `dashboard/` for any `Depends` auth pattern), apply the bypass the same way other `/healthz*` routes do (look for an existing healthz endpoint for precedent). If there's no existing bypass pattern, add a comment noting this route is intentionally unauthenticated and why.
- Response shape must match the design doc's AC2/AC3 exactly.

### 3. Status code semantics

- `mode == "match"` → 200
- `mode == "bootstrap"` → 200 (health probes should not go red just because the user hasn't set the env var)
- `mode == "mismatch"` → 503
- `mode == "missing"` with env set → 503
- `mode == "missing"` with env unset (shouldn't normally happen — bootstrap assumes the row exists) → treat as 503 to flag it

Verify those map cleanly in `check_identity`. If the module from S03 doesn't distinguish "missing with env set" from "missing with env unset", clarify with the S03 agent or mirror the same decision tree in the endpoint.

### 4. No new dependencies

Use existing FastAPI / SQLAlchemy. Do NOT add a new package.

### 5. Dashboard CLAUDE.md

If adding a `/healthz/*` convention for the first time, document it briefly in `dashboard/CLAUDE.md` under a "Health endpoints" subsection so future routers follow the same pattern.

## Project Conventions

Read `dashboard/CLAUDE.md` for:

- htmx vs. JSON conventions (this is a JSON probe endpoint, not an htmx view).
- Router registration order.
- Any templating / logging conventions.

## TDD Requirement

Smoke coverage here; the formal unit/integration tests for this live in S07. At minimum, run the endpoint locally:

```bash
# With daemon+dashboard already running in bootstrap mode:
curl -s http://localhost:9900/healthz/identity | jq
# Expected: {"expected": null, "actual": "<uuid>", "mode": "bootstrap", "match": null|false}
# Status: 200
```

Confirm startup refuses on a mismatched env (temporarily export `IW_CORE_EXPECTED_INSTANCE_ID=00000000-0000-0000-0000-000000000000` and start the dashboard — it should fail startup with the boxed ERROR). Unset before finishing.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass.
2. `make lint` — pass.
3. Live smoke: dashboard starts in bootstrap mode; `/healthz/identity` returns 200 + JSON; dashboard refuses to start with a bogus expected UUID set.

## Subagent Result Contract

Standard S*_API JSON. `files_changed` must list every file touched including `dashboard/app.py`.

## Lifecycle commands

```bash
uv run iw step-start CR-00014 --step S05
# implement ...
uv run iw step-done CR-00014 --step S05 --report ai-dev/active/CR-00014/reports/CR-00014_S05_API_report.md
```
