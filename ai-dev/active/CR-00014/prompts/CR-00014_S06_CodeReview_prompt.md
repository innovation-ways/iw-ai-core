# CR-00014_S06_CodeReview_prompt

**Work Item**: CR-00014 — Orchestration DB instance-identity fingerprint
**Step Being Reviewed**: S05 (api-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/CR-00014/CR-00014_CR_Design.md`
- `ai-dev/active/CR-00014/reports/CR-00014_S05_API_report.md`
- All files listed in the S05 report's `files_changed`
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00014/reports/CR-00014_S06_CodeReview_report.md`

## Review Checklist

### 1. Lifespan gate correctness

- Identity verification is in the FastAPI lifespan (or equivalent startup hook), BEFORE `yield`.
- On mismatch/missing-with-env-set, the handler **raises** — not `sys.exit`, not silent return. Uvicorn must see the failure and refuse to bind.
- Bootstrap and match paths proceed to `yield` normally.
- The short-lived session opened at startup is **closed** (context manager or explicit `session.close()`), even on raise.
- No migration of deprecated `@app.on_event("startup")` hooks dropped existing startup behavior silently.

### 2. `/healthz/identity` endpoint

- Router registered in `create_app()`; path is exactly `/healthz/identity`.
- Response shape matches the design: `{expected, actual, mode, match}`. Keys always present; values nullable.
- Status codes match: 200 for match / bootstrap; 503 for mismatch / missing-with-env-set.
- Uses `response.status_code = ...` pattern (not raising HTTPException — the JSON body is the point of the endpoint).
- Uses `Depends(get_db)` — session is request-scoped and properly closed by the dependency.
- `check_identity` is the *pure* one; never `verify_instance_identity` here (the endpoint must not raise on mismatch — it must return a structured body with 503).

### 3. Auth bypass

- If the dashboard has any global auth middleware, `/healthz/identity` is exempted using the same pattern as any pre-existing healthz route.
- Documented in `dashboard/CLAUDE.md` if this is the first `/healthz/*` route.

### 4. No regression on dashboard startup

- Existing templates and routers still mount.
- SSE endpoints (if any) still work.
- The dashboard still serves the homepage at `/`.

### 5. Code quality

- No duplicated UUID parsing / env-var reading in `dashboard/` — it all goes through `orch.db.identity`.
- No `print()` — logging via `logging.getLogger(__name__)`.
- No hardcoded ports/URLs/credentials.

### 6. Smoke evidence

- S05 report contains the curl output of `/healthz/identity` in bootstrap mode OR a clear note that the smoke was deferred — if deferred, reviewer must run it.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Fix in place.

## Subagent Result Contract

Same pattern as S02.

## Lifecycle commands

```bash
uv run iw step-start CR-00014 --step S06
# review + fix ...
uv run iw step-done CR-00014 --step S06 --report ai-dev/active/CR-00014/reports/CR-00014_S06_CodeReview_report.md
```
