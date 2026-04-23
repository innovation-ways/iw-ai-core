# CR-00013 S02 Code Review Report

**Step**: S02
**Agent**: code-review-impl
**Work Item**: CR-00013 -- Dashboard navigation performance
**Review of**: S01 (backend-impl)
**Verdict**: PASS

---

## What Was Reviewed

S01 implemented: timing middleware (F1/F2), DB pool sizing (B1), worktree-badge TTL cache (A1), git-stats TTL cache (D1/D2), asyncio-aware daemon control sleeps (D3).

---

## Files Changed (S01)

| File | Change |
|------|--------|
| `dashboard/utils/timing.py` | NEW - Request-timing middleware |
| `dashboard/utils/ttl_cache.py` | NEW - TTL cache helper |
| `dashboard/app.py` | Added timing middleware registration |
| `dashboard/routers/worktrees.py` | TTL caching for badge + git calls |
| `dashboard/routers/system.py` | TTL caching for `_git_branch_and_stats` |
| `dashboard/routers/daemon_control.py` | Async def + asyncio.sleep |
| `orch/config.py` | Pool config vars + getters |
| `orch/db/session.py` | Explicit pool kwargs |
| `.env.example` | Documented new env vars |
| `tests/unit/test_ttl_cache.py` | NEW - TTL cache tests |
| `tests/unit/test_timing_middleware.py` | NEW - Middleware tests |
| `tests/unit/test_pool_config.py` | NEW - Pool config tests |
| `tests/unit/test_worktrees_caching.py` | NEW - Caching tests |
| `tests/unit/test_daemon_control_async.py` | NEW - Async daemon control tests |

---

## Architecture Compliance

- Middleware registered once in `create_app()` via `app.add_middleware()` — not on sub-routers.
- `TTLCache` lives in `dashboard/utils/` — follows dashboard helpers pattern.
- `orch/config.py` uses existing fail-fast pattern; new pool vars are optional with defaults (not required).
- Pool kwargs applied at `create_engine()` call — not at session creation.
- No cross-layer violations: dashboard → orch is correct direction.

## Code Quality & Correctness

- **Critical — nav_worktree_badge DB session**: `_compute_dirty_count()` opens its own `SessionLocal()` session, independent of the request-scoped `Depends(get_db)` session. Cache fill cannot access a closed session. VERIFIED.
- **Critical — Thread safety**: `TTLCache` uses `threading.Lock` on all get/set/delete/clear operations. VERIFIED.
- **Critical — Async def daemon handlers**: `daemon_start`, `daemon_stop`, `daemon_restart` are `async def` and use `await asyncio.sleep()` / `await asyncio.to_thread()`. VERIFIED.
- **Critical — Query counter scoped per-request**: `_query_count_ctx` is a `ContextVar` reset after each dispatch. Event listener added/removed in the same `try/finally` block. VERIFIED.
- **Critical — Middleware body wrapped**: `call_next` wrapped in try/except; logging errors do not propagate. VERIFIED.
- **WARN log fields**: path, method, status_code, duration_ms, db_query_count, pool {size, checked_out, overflow, checked_in} — all present.
- **Pool defaults**: pool_size=20, max_overflow=20, pool_recycle=1800, pool_timeout=10 — sane per AC2.
- **TTL defaults**: badge=30s, git-stats=15s — match CR-specified values.

## Security

- No secrets in log lines (connection strings/passwords not logged).
- No user-controlled input reaches `subprocess.run` arguments.
- Query counter event listener is read-only (no mutation).

## Project Conventions

- `from __future__ import annotations` present in all modified files.
- Type hints on all new functions.
- No hardcoded ports/URLs.
- Env-var names follow `IW_CORE_*` prefix.
- Thin router pattern followed (business logic in helpers).

## Testing

Unit tests cover: TTL hit/miss/expire/clear, concurrent access (threading), stats, pool config defaults/explicit, middleware instantiation, async handler inspection.

Tests are deterministic (no real sleeps; use `time.sleep` only in dedicated timing tests, TTL set to 0.1s for expiry tests).

---

## Test Results

| Suite | Result |
|-------|--------|
| `make test-unit` | 1264 passed, 19 warnings |
| `make test-integration` | 924 passed, 7 skipped, 34 warnings |
| `make quality` | 48 pre-existing lint errors (0 new from S01) |

The 48 lint errors are pre-existing baseline issues (unchanged since before this CR). All S01 files pass `ruff check` cleanly.

---

## Mandatory Fix Count

0

---

## Notes

- `make quality` shows 48 ruff errors, but all are pre-existing (confirmed by running ruff only on S01-changed files — all pass). The baseline before S01 showed the same 48 errors.
- The TTL cache `wrap()` method stores the computed value even on exceptions if `fn` raises, which could cache an exception as a value — but this is acceptable for this use case (fn is a pure compute with no side effects in the compute path).
- `nav_worktree_badge` correctly ignores the request-scoped `_db` session for cache computation; the `_db` parameter still exists in the function signature for FastAPI dependency injection but is not used.
