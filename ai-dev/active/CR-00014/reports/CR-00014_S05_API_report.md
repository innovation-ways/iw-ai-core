# CR-00014 S05 — API Implementation Report

## Summary

Implemented the dashboard startup gate and `/healthz/identity` endpoint for CR-00014 (Orchestration DB instance-identity fingerprint).

## Files Changed

| File | Change |
|------|--------|
| `dashboard/app.py` | Extended `_lifespan()` with identity verification gate; added `healthz` router import and registration |
| `dashboard/routers/healthz.py` | New — `GET /healthz/identity` endpoint using `check_identity()` from `orch.db.identity` |
| `dashboard/CLAUDE.md` | Added "Health endpoints" subsection documenting `/healthz/identity` convention |

## What Was Done

### 1. FastAPI Lifespan Gate (`dashboard/app.py`)

The existing `_lifespan()` was extended to call `verify_instance_identity(session)` **before** the `yield`:

- **match**: logs `INFO Dashboard: DB identity verified (<short-uuid>)`
- **bootstrap** (env unset): logs the bootstrap notice at INFO
- **mismatch** / **missing** (with env set): logs the error at ERROR level, then **raises** `RuntimeError` so FastAPI startup fails and uvicorn reports unhealthy

The original `mark_orphaned_runs()` call is preserved inside the lifespan before the identity check.

### 2. `/healthz/identity` Endpoint (`dashboard/routers/healthz.py`)

New router at `prefix="/healthz"` with one endpoint:

```
GET /healthz/identity
```

Response body:
```json
{
  "expected": "<uuid>" | null,
  "actual": "<uuid>" | null,
  "mode": "match" | "mismatch" | "bootstrap" | "missing",
  "match": true | false | null
}
```

Status codes:
- `mode == "match"` → 200
- `mode == "bootstrap"` → 200
- `mode == "mismatch"` → 503
- `mode == "missing"` → 503

The route is intentionally unauthenticated so external probes can reach it (documented in CLAUDE.md).

### 3. Dashboard CLAUDE.md

Added "Health endpoints" section documenting the `/healthz/identity` convention for future routers.

## Test Results

| Check | Result |
|-------|--------|
| `make test-unit` | PASS — 1164 passed |
| `uv run ruff check dashboard/app.py dashboard/routers/healthz.py` | PASS — All checks passed |
| `uv run mypy dashboard/app.py dashboard/routers/healthz.py` | PASS — no issues found |

## Notes

- The lifespan gate raises `RuntimeError` (from `verify_instance_identity`) on mismatch/missing rather than calling `sys.exit`, letting uvicorn propagate the failure.
- Bootstrap mode (env unset) proceeds normally with a logged notice — it does not block startup.
- Status code semantics follow the design doc's AC2/AC3 exactly.
- No new dependencies added.