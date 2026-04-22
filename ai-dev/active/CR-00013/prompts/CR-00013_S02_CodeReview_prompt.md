# CR-00013_S02_CodeReview_prompt

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` — Design document
- `ai-dev/active/CR-00013/reports/CR-00013_S01_Backend_report.md` — S01 step report
- All files listed in the S01 report's `files_changed`

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S02_CodeReview_report.md` — review report

## Context

Review the backend changes from S01. This slice implemented observability (timing middleware + pool logging), explicit DB pool sizing, and TTL caching for subprocess-heavy endpoints + asyncio-aware sleeps.

Read the design doc (especially Sections "Current Behavior" and AC1/AC2/AC4/AC5/AC7). Read the S01 report and then review every changed file.

## Review Checklist

### 1. Architecture Compliance

- Middleware is registered once in `create_app()`; not duplicated or registered on sub-routers.
- TTL cache helper lives in `dashboard/utils/` (not in a router) — dashboard helpers pattern.
- `orch/config.py` changes use the existing fail-fast pattern for required vars; the two new vars are **optional** with defaults (not required).
- Pool kwargs applied at engine creation — not at session creation.
- No cross-layer imports (dashboard → orch is OK; orch → dashboard is NOT).

### 2. Code Quality & Correctness

- **Critical**: The cached compute function in `nav_worktree_badge` must open its **own** DB session (via `SessionLocal`), not rely on the request-scoped session from `Depends(get_db)`. A request-scoped session closes when the request returns; a later cache refresh on another request would access a closed session.
- **Critical**: Cache must be thread-safe. Verify a lock guards concurrent fills (no "thundering herd" on cache miss is a nice-to-have but not required; racing fills must not corrupt state).
- **Critical**: `daemon_start`/`daemon_stop`/`daemon_restart` must be `async def` and use `await asyncio.sleep`. Any blocking subprocess inside must go through `await asyncio.to_thread(...)`.
- SQLAlchemy query-counting event listener is scoped per-request (via `ContextVar` or request.state), not global-leaking.
- Middleware wraps body in try/except so a logging bug never 500s a user request.
- WARN log contains at minimum: `path`, `method`, `status_code`, `duration_ms`, `db_query_count`, pool `{size, checked_out, overflow, checked_in}`.
- Pool threshold defaults are sane (`pool_size=20`, `max_overflow=20`, `pool_recycle=1800`, `pool_timeout=10`).
- TTL values default to the CR-specified numbers (badge=30 s, git-stats=15 s).

### 3. Project Conventions

- `dashboard/CLAUDE.md` rules respected (thin routes; business logic in helpers).
- Type hints present on all new functions.
- `from __future__ import annotations` present where other files in the same package use it.
- No hardcoded ports or URLs.
- Env-var names follow `IW_CORE_*` prefix.

### 4. Security

- No secrets logged (the log line should not include connection strings or passwords).
- No user-controlled input reaches `subprocess.run` arguments.
- Query counter must not mutate SQL (read-only event listener).

### 5. Testing

- Unit tests cover: TTL cache hit/miss/expire, pool kwargs applied, middleware log thresholds, badge cache (zero subprocess on hit), `async def` conversion.
- Tests are deterministic (no real sleeps; use monkeypatched time or very small TTLs).
- No tests connect to the live DB (port 5433). Integration tests use testcontainers.

## Test Verification (NON-NEGOTIABLE)

Before submitting:

1. `make test-unit` — clean.
2. `make test-integration` — clean.
3. `make quality` — clean.

## Severity Levels

| Severity | Action |
|----------|--------|
| **CRITICAL** | Must fix before merge |
| **HIGH** | Must fix before merge |
| **MEDIUM (fixable)** | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Optional |
| **LOW** | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00013",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
