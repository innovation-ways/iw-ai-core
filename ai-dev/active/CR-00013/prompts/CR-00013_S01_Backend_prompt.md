# CR-00013_S01_Backend_prompt

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Step**: S01
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` — Design document
- `dashboard/routers/worktrees.py` — contains `nav_worktree_badge`, `_git_status`, `_collect_worktrees`
- `dashboard/routers/system.py` — contains `_git_branch_and_stats`, `_project_summaries`
- `dashboard/routers/daemon_control.py` — contains `time.sleep()` calls
- `dashboard/app.py` — FastAPI factory (where middleware is registered)
- `dashboard/dependencies.py` — `get_db` session scope
- `orch/db/session.py` — engine creation (B1)
- `orch/config.py` — env-var loader (new `IW_CORE_DB_POOL_SIZE`, `IW_CORE_DB_MAX_OVERFLOW`)
- `.env.example` — update with new vars
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md` — project conventions

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S01_Backend_report.md` — step report

## Context

You are implementing the first backend slice of **CR-00013**. This slice is about making the dashboard stop hanging on navigation. It has five deliverables, all backend-only (no N+1 query rewrites — those are in S03).

Read the design doc first to understand the full shape of the CR. Then read `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, and project `CLAUDE.md`.

## Requirements

### 1. Request-timing + pool-status middleware (F1, F2) — covers AC7

Add a FastAPI middleware (recommend a pure ASGI or `BaseHTTPMiddleware`) in `dashboard/app.py` (or a new helper under `dashboard/utils/timing.py` imported from `app.py`) that:

- Measures wall-clock duration of each request.
- Counts SQL queries issued during the request. Use a SQLAlchemy event listener on `before_cursor_execute` scoped to a `ContextVar` so counts are per-request and async-safe.
- Logs at WARN when `duration_ms > 500` (threshold configurable via env var `IW_CORE_SLOW_REQUEST_MS`, default 500).
- The WARN log line must be a single structured line containing at minimum: `path`, `method`, `status_code`, `duration_ms`, `db_query_count`, and pool status `{size, checked_out, overflow, checked_in}` read from `orch.db.session.engine.pool.status()` (or the individual `pool.size()`, `pool.checkedout()`, etc. — whichever is stable across SQLAlchemy 2.0).
- Below the threshold, emit DEBUG with the same fields (no INFO spam).
- Do not break the request if the middleware itself fails — wrap in try/except and log at ERROR.

The middleware must be registered in `create_app()` in `dashboard/app.py`.

### 2. Explicit DB pool config + env-driven sizing (B1) — covers AC2

In `orch/config.py`:

- Add two new env vars to the config loader:
  - `IW_CORE_DB_POOL_SIZE` (int, default `20`)
  - `IW_CORE_DB_MAX_OVERFLOW` (int, default `20`)
- Follow the existing "fail fast on missing vars" pattern only for required vars; these two are optional with defaults.
- Expose getter(s) so `orch/db/session.py` can read them.

In `orch/db/session.py`:

- Replace the current `create_engine(get_db_url(), pool_pre_ping=True)` with explicit kwargs:
  ```python
  engine = create_engine(
      get_db_url(),
      pool_pre_ping=True,
      pool_size=<from config>,
      max_overflow=<from config>,
      pool_recycle=1800,
      pool_timeout=10,
  )
  ```
- Do not change the `SessionLocal` sessionmaker signature.
- Keep `pool_pre_ping=True` for now.

In `.env.example`:

- Document both new vars with their defaults and a one-line explanation.

### 3. Worktree-badge TTL cache (A1) — covers AC1

Create a small TTL cache helper (recommended location: `dashboard/utils/ttl_cache.py`) with:

- A class or simple function-decorator that caches a sync callable by a key (or argumentless key for the badge case) with an explicit TTL in seconds.
- Thread-safe under FastAPI's default worker model (GIL-safe is enough; a `threading.Lock` guard is fine).
- Does not hold DB sessions or subprocesses outside its compute function.
- Publishes hit/miss counts (optional; include if straightforward).

In `dashboard/routers/worktrees.py`:

- Modify `nav_worktree_badge` so its body reads the dirty count from the cache with a **30-second TTL** (configurable via env `IW_CORE_BADGE_CACHE_TTL`, default 30).
- The compute function (not the cached wrapper) performs the existing logic: enumerate projects + active batch items, call `_git_status`, sum dirty count. It opens/closes its own DB session via `orch.db.session.SessionLocal` — do not accept the injected `db` from the request, because the cache fill must be independent of the request-scoped session.
- On cache hit, the route must be constant-time (no subprocess, no DB query). On miss, it computes and stores. No need for a background refresher in this step — lazy-populate on miss is acceptable.

### 4. TTL cache for `_git_branch_and_stats` and `/worktrees` page (D1, D2) — covers AC4

In `dashboard/routers/system.py`:

- Wrap `_git_branch_and_stats(repo_root)` in a TTL cache keyed by `repo_root`, with a **15-second TTL** (configurable via `IW_CORE_GIT_STATS_CACHE_TTL`, default 15).

In `dashboard/routers/worktrees.py`:

- The `/worktrees` page (`worktrees_page` handler) calls `_collect_worktrees` which itself calls multiple subprocess helpers. Wrap the **expensive per-worktree reads** in the same TTL cache pattern (keyed by worktree path). Do not cache the top-level handler; the goal is that revisiting `/worktrees` within 15 s reuses prior subprocess results.

### 5. Asyncio-aware sleeps in daemon_control (D3) — covers AC5

In `dashboard/routers/daemon_control.py`:

- Locate the three `time.sleep()` sites at lines ~76, ~96, ~120 (the exact line numbers may shift; find them).
- Convert the three handlers (`daemon_start`, `daemon_stop`, `daemon_restart`) to `async def` and replace `time.sleep(N)` with `await asyncio.sleep(N)`.
- If the handler does any other blocking work (subprocess launch/poll), wrap that in `await asyncio.to_thread(...)` so the event loop is never blocked.
- Keep the same response shape and status codes. These endpoints are called from the Configuration page; their HTML response (if any) must be unchanged.

## Project Conventions

Read `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, and the top-level `CLAUDE.md`:

- Routes are thin — business logic belongs in `orch/` or dashboard helpers, not inline in the router.
- Sync SQLAlchemy 2.0; `Mapped[]` style.
- Tests use testcontainers — never connect to live DB.
- Never hardcode ports/credentials; all config via env.
- Follow existing naming and import organization.

## TDD Requirement

Follow TDD:

1. **RED**: Write failing tests first under `tests/unit/` (and `tests/integration/` where testcontainer is needed). Tests should assert:
   - TTL cache hit/miss/expire behavior.
   - Pool kwargs applied as expected (inspect engine pool attributes).
   - Middleware emits WARN above threshold; DEBUG below.
   - `nav_worktree_badge` on second call within TTL issues zero subprocesses (patch `_git_status` with a counter).
   - `daemon_start` is `async def` and uses `asyncio.sleep`.
2. **GREEN**: Minimal implementation.
3. **REFACTOR**: Tidy without breaking tests.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — all unit tests pass.
2. `make test-integration` — all integration tests pass.
3. `make quality` — lint + format + mypy clean.
4. Do **NOT** report `tests_passed: true` unless ALL tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00013",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/app.py",
    "dashboard/utils/timing.py",
    "dashboard/utils/ttl_cache.py",
    "dashboard/routers/worktrees.py",
    "dashboard/routers/system.py",
    "dashboard/routers/daemon_control.py",
    "orch/config.py",
    "orch/db/session.py",
    ".env.example"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
