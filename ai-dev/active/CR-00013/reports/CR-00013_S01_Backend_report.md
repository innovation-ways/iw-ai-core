# CR-00013 S01 Backend Report

**Step**: S01
**Agent**: backend-impl
**Work Item**: CR-00013 -- Dashboard navigation performance
**Completion Status**: complete

---

## What Was Done

Implemented the first backend slice of CR-00013 covering 5 deliverables:

### F1/F2: Request-timing + pool-status middleware
- Created `dashboard/utils/timing.py` with `TimingMiddleware` (BaseHTTPMiddleware)
- SQL query counter via `ContextVar` + `before_cursor_execute` event listener
- WARN log when duration > threshold (configurable via `IW_CORE_SLOW_REQUEST_MS`, default 500ms)
- DEBUG log below threshold
- Pool status in log: size, checked_out, overflow, checked_in
- Registered in `dashboard/app.py` `create_app()`

### B1: Explicit DB pool config + env-driven sizing
- Added `IW_CORE_DB_POOL_SIZE` (default 20) and `IW_CORE_DB_MAX_OVERFLOW` (default 20) to `orch/config.py`
- Added `get_db_pool_size()` and `get_db_max_overflow()` getter functions
- Updated `orch/db/session.py` to use explicit pool kwargs: `pool_size`, `max_overflow`, `pool_recycle=1800`, `pool_timeout=10`
- Updated `.env.example` with new vars

### A1: Worktree-badge TTL cache
- Created `dashboard/utils/ttl_cache.py` with thread-safe `TTLCache` class (GIL-safe via `threading.Lock`)
- Added `_compute_dirty_count()` in `worktrees.py` with its own DB session
- Module-level `_badge_cache` with 30s TTL (configurable via `IW_CORE_BADGE_CACHE_TTL`)
- `nav_worktree_badge` now checks cache first, computes on miss

### D1/D2: TTL cache for git stats and worktrees page
- Wrapped `_git_status`, `_commits_ahead`, `_current_branch` in `worktrees.py` with 15s TTL cache keyed by path (via `IW_CORE_GIT_STATS_CACHE_TTL`)
- Wrapped `_git_branch_and_stats` in `system.py` with 15s TTL cache keyed by repo_root

### D3: Asyncio-aware sleeps in daemon_control
- Converted `daemon_start`, `daemon_stop`, `daemon_restart` from `def` to `async def`
- Replaced `time.sleep(N)` with `await asyncio.sleep(N)`
- Wrapped subprocess calls in `await asyncio.to_thread(...)` to avoid blocking event loop

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/utils/timing.py` | NEW - Request-timing middleware |
| `dashboard/utils/ttl_cache.py` | NEW - TTL cache helper |
| `dashboard/app.py` | Added timing middleware registration |
| `dashboard/routers/worktrees.py` | TTL caching for badge + per-worktree git calls |
| `dashboard/routers/system.py` | TTL caching for `_git_branch_and_stats` |
| `dashboard/routers/daemon_control.py` | Async def with asyncio.sleep |
| `orch/config.py` | Added pool config vars + getters |
| `orch/db/session.py` | Explicit pool kwargs |
| `.env.example` | Documented new env vars |
| `tests/unit/test_ttl_cache.py` | NEW - TTL cache tests |
| `tests/unit/test_timing_middleware.py` | NEW - Middleware tests |
| `tests/unit/test_pool_config.py` | NEW - Pool config tests |
| `tests/unit/test_worktrees_caching.py` | NEW - Caching tests |
| `tests/unit/test_daemon_control_async.py` | NEW - Async daemon control tests |

---

## Test Results

| Suite | Result |
|-------|--------|
| `make test-unit` | 1264 passed, 19 warnings (pre-existing warnings) |
| `make test-integration` | 924 passed, 7 skipped, 34 warnings (pre-existing warnings) |
| `uv run mypy orch/ dashboard/` | Success: no issues found |
| `uv run ruff check` on changed files | All checks passed |

**Note**: `make quality` reports 48 lint errors, but these are all pre-existing (the baseline before this CR also showed 48 errors). My changes introduced zero new lint errors.

---

## Blockers

None.

---

## Notes

- The TTL cache implementation uses `threading.Lock` for GIL-safe concurrent access under FastAPI's default worker model.
- Pool status logging uses `contextlib.suppress(Exception)` for robustness - pool attributes may not be accessible in all SQLAlchemy configurations.
- The `nav_worktree_badge` now uses an independent DB session from `SessionLocal` rather than the request-scoped injected `db` session, ensuring cache fills don't hold the request's session.
- The timing middleware's `before_cursor_execute` listener is registered/removed per-request to avoid global side effects.
