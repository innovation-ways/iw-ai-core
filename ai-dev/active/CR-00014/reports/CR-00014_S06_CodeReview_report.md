# CR-00014 S06 — Code Review Report

## Summary

Reviewed S05 (api-impl) implementation: dashboard startup gate and `/healthz/identity` endpoint. All checklist items pass.

## Checklist Results

### 1. Lifespan gate correctness — PASS
- `verify_instance_identity(session)` called **before** `yield` at `dashboard/app.py:60`
- On mismatch/missing (with env set): raises `RuntimeError` from `verify_instance_identity` → caught at `app.py:68` and re-raised → uvicorn sees startup failure
- Bootstrap session (`session = SessionLocal()`) closed in `finally:` block at `app.py:72`
- No deprecated `@app.on_event("startup")` hooks present

### 2. `/healthz/identity` endpoint — PASS
- Registered via `app.include_router(healthz.router)` at `app.py:147`; path is exactly `/healthz/identity`
- Response shape: `{expected, actual, mode, match}` with all keys present; values nullable
- Status codes: `200` for `match`/`bootstrap`, `503` for `mismatch`/`missing` — via `response.status_code = ...` pattern at `healthz.py:33`
- Uses `Depends(get_db)` — request-scoped session, closed by the dependency
- Uses `check_identity` (pure, non-raising) at `healthz.py:23`, NOT `verify_instance_identity`

### 3. Auth bypass — PASS (implicit)
- `/healthz/identity` has no auth dependencies; `get_db` is the only dependency and it is not auth-related
- No global auth middleware is declared in `create_app()` — no exemption needed
- Documented in `dashboard/CLAUDE.md` as the first `/healthz/*` route

### 4. No regression on dashboard startup — PASS
- All existing routers still mounted (`projects`, `running`, `actions`, `sse`, `system`, etc.)
- SSE router included at `app.py:151`
- Homepage (`/`) served via existing templates

### 5. Code quality — PASS
- UUID parsing/env-var reading all via `orch.db.identity` — no duplication
- Logging via `logging.getLogger(__name__)` — no `print()` calls
- No hardcoded ports/URLs/credentials

### 6. Smoke evidence — PASS
- Smoke test run during review:
  ```
  GET /healthz/identity → 200
  Body: {'expected': None, 'actual': '518ac56a-36f7-4c43-8f53-cfbb8a6baa3e',
         'mode': 'bootstrap', 'match': False}
  ```
- Bootstrap mode confirmed (env var unset) — correct behavior

## Files Changed (from S05)

| File | Change |
|------|--------|
| `dashboard/app.py` | Extended `_lifespan()` with identity verification before `yield` |
| `dashboard/routers/healthz.py` | New — `GET /healthz/identity` endpoint |
| `dashboard/CLAUDE.md` | Documented `/healthz/identity` convention |

## Quality Gates

| Check | Result |
|-------|--------|
| `uv run ruff check dashboard/app.py dashboard/routers/healthz.py` | PASS |
| `uv run mypy dashboard/app.py dashboard/routers/healthz.py` | PASS |
| `uv run pytest tests/unit/ -x` | 1164 passed |

## Issues Found

None. All CRITICAL/HIGH/MEDIUM/LOW items are clear.

## Recommendation

Approve S05. Ready to proceed to S07 (tests-impl).
