# CR-00013: Dashboard navigation performance — eliminate multi-second hangs between pages

**Type**: Change Request
**Priority**: High
**Reason**: Performance regression — navigating page-to-page in the dashboard hangs for several seconds under normal use. Root causes verified in code: sidebar-badge subprocess storm, undersized DB pool, multiple N+1 queries on entry-point pages, blocking subprocess calls in sync routes, and client-side asset bloat. No request-timing observability exists to measure improvements.
**Created**: 2026-04-21
**Status**: Draft

---

## Description

Remove the causes of multi-second hangs when navigating between dashboard pages. The biggest single cause is the sidebar worktree-badge endpoint running sequential `git status` subprocesses on every page load while holding a DB session; it combines with a default-sized SQLAlchemy pool to starve other requests. This CR caches subprocess-heavy endpoints behind a TTL, sizes the DB pool explicitly, eliminates N+1 queries on hot routes, and trims client-side bloat in `base.html`. Observability is added first so improvements are measurable.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key pointers:

- `dashboard/CLAUDE.md` — FastAPI + Jinja2 + htmx + Tailwind CDN stack. Routes are thin; business logic belongs in `orch/`. **This CR relaxes the "No build step — Tailwind loaded from CDN" rule** (see E1 below).
- `orch/CLAUDE.md` — Sync SQLAlchemy 2.0, psycopg v3, composite PKs `(project_id, id)`.
- `tests/CLAUDE.md` — Integration tests use testcontainers; never connect to live DB.

## Current Behavior

### Sidebar worktree badge (hottest path)
- `dashboard/templates/base.html:218-221` — sidebar renders `<span hx-get="/system/nav/worktree-badge" hx-trigger="load, every 60s">` on every page.
- `dashboard/routers/worktrees.py:335-365` — `nav_worktree_badge` is a **sync** route that:
  1. Queries all enabled `Project` rows and calls `_git_status(project.repo_root)` per project (subprocess).
  2. Queries all active `BatchItem` rows and calls `_git_status(worktree_path)` per item (subprocess).
- With 5 projects × ~10 active worktrees = up to 15 sequential `git status` calls per page navigation, each with a 5 s subprocess timeout. The handler holds its DB session for the full duration.

### DB connection pool
- `orch/db/session.py:34` — `create_engine(get_db_url(), pool_pre_ping=True)` uses SQLAlchemy defaults: `pool_size=5`, `max_overflow=10`, total 15 connections.
- Under concurrent load (SSE pollers + sidebar badge holding sessions + normal navigation), the pool saturates and new requests block on connection checkout.

### N+1 query hotspots
- `dashboard/routers/projects.py:71-120` `_project_stats` — 4 count queries × N projects on the project selector (`/`).
- `dashboard/routers/project_dashboard.py:102-121` `_active_batches` — 2 count queries per active batch.
- `dashboard/routers/batches.py:114-181` `_batch_item_rows` — per-item `WorkItem` + `WorkflowStep` queries inside a loop.
- `dashboard/routers/items.py:322-330` `_get_steps` — per-step `StepRun` query; called by 4+ item-detail routes.
- `dashboard/routers/running.py:132-137` `_query_failed_steps` — per-step `StepRun` query.

### Blocking subprocess in sync routes
- `dashboard/routers/system.py:141-173` `_git_branch_and_stats` — 3 sequential `subprocess.check_output` calls (5 s timeout each), invoked per project by `_project_summaries` (`system.py:179-209`).
- `dashboard/routers/worktrees.py:46-124` — subprocess calls in `/worktrees` page loader.
- `dashboard/routers/daemon_control.py:76, 96, 120` — `time.sleep()` on sync route handlers.

### Client-side asset loading
- `dashboard/templates/base.html:30` — Tailwind CDN runtime JIT (`cdn.tailwindcss.com`); compiles utility classes in the browser on every page load.
- `dashboard/templates/base.html:12-14` — render-blocking `fonts.googleapis.com` link.
- `dashboard/templates/base.html:77-142` — Mermaid (~2 MB), Highlight.js core + 11 language scripts, DOMPurify, streaming-markdown loaded on **every** page regardless of whether the page uses them.

### Observability
- No request-timing middleware. No pool-status logging. Performance regressions are invisible until a human notices the lag.

## Desired Behavior

- `/system/nav/worktree-badge` responds in <50 ms regardless of worktree count (served from in-memory TTL cache; background refresh or lazy-populate on cache miss).
- `orch/db/session.py` engine is configured with explicit `pool_size`, `max_overflow`, `pool_recycle`, and `pool_timeout`; values come from env (`IW_CORE_DB_POOL_SIZE`, `IW_CORE_DB_MAX_OVERFLOW`) with sensible defaults (20/20).
- Project selector, project dashboard, batch detail, item detail, and running-tasks pages issue bounded query counts independent of row counts (no N+1).
- `system.py` git-stat reads and `worktrees.py` page loader are cached with TTL; `daemon_control.py` `time.sleep` calls no longer block the event loop.
- `base.html` uses a prebuilt Tailwind CSS file (no runtime JIT); Mermaid / Highlight.js / DOMPurify / streaming-markdown are moved to per-page `{% block head %}` includes; Inter font is self-hosted.
- A request-timing middleware logs `{path, duration_ms, db_query_count}` at WARN above 500 ms; pool status is logged on slow requests.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `dashboard/routers/worktrees.py:nav_worktree_badge` | Sync subprocess loop per request | TTL-cached dirty count, O(1) response |
| `orch/db/session.py` engine | Default pool (5+10) | Explicit sized pool (env-driven) |
| `orch/config.py` | No pool-related env vars | `IW_CORE_DB_POOL_SIZE`, `IW_CORE_DB_MAX_OVERFLOW` |
| `dashboard/routers/projects.py:_project_stats` | 4×N count queries | 1 aggregation query |
| `dashboard/routers/project_dashboard.py:_active_batches` | 2×N count queries | 1 aggregation query |
| `dashboard/routers/batches.py:_batch_item_rows` | Per-item queries | Bulk load |
| `dashboard/routers/items.py:_get_steps` | Per-step query | Bulk load |
| `dashboard/routers/running.py:_query_failed_steps` | Per-step query | Bulk load |
| `dashboard/routers/system.py:_git_branch_and_stats` | 3 subprocesses per call | TTL-cached |
| `dashboard/routers/daemon_control.py` sleep calls | `time.sleep` in sync handlers | `asyncio.sleep` / `asyncio.to_thread` |
| `dashboard/app.py` | No timing middleware | Request-timing + pool-status middleware |
| `dashboard/templates/base.html` | Tailwind CDN JIT + eager libs | Prebuilt CSS + lazy libs |
| `Makefile` | No CSS build target | `make css` + hook into dev/quality as needed |
| `dashboard/CLAUDE.md` | Says "No build step" | Documents Tailwind build step |
| `.env.example` | No pool vars | Documents new vars |

### Breaking Changes

- **None external.** Dashboard UI and HTTP contracts unchanged.
- **Internal convention shift:** `dashboard/CLAUDE.md` "No build step" rule is relaxed. Dashboard CSS now requires `make css` (or equivalent) before first run; instructions updated in-repo.
- New env vars `IW_CORE_DB_POOL_SIZE` and `IW_CORE_DB_MAX_OVERFLOW` are additive with sensible defaults — existing `.env` files continue to work.

### Data Migration

- **None.** No schema or data changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | F1 timing middleware + F2 pool logging; B1 pool config + env; A1 badge TTL cache; D1/D2 git-stat TTL cache; D3 async sleep | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | backend-impl | C1–C5 N+1 query rewrites across 5 routers | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | frontend-impl | E1 prebuilt Tailwind + Makefile + CLAUDE.md update; E2 lazy-load Mermaid/hljs/DOMPurify/SMD; E3 self-host Inter | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | tests-impl | Tests for cache, pool, middleware, N+1 regression (query-count assertions), base.html render, prebuilt-CSS presence | — |
| S08 | code-review-impl | Review S07 | — |
| S09 | code-review-final-impl | Global cross-layer review | — |
| S10–S14 | qv-gate | lint, format, typecheck, unit-tests, integration-tests | — |
| S15 | qv-browser | Browser verification of visual parity and nav-hang elimination | — |

Agent slugs used: `backend-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No Alembic migration. No `iw migration-lock` acquired.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: `/system/nav/worktree-badge` — response body unchanged, latency reduced to <50 ms via cache
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: `dashboard/templates/base.html` — CSS source swap, lazy-load script hoisting; per-page templates that use Mermaid/hljs add `{% block head %}` includes
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00013/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00013_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00013_S01_Backend_prompt.md` | Prompt | Observability, pool, badge cache, subprocess hygiene |
| `prompts/CR-00013_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00013_S03_Backend_prompt.md` | Prompt | N+1 query fixes |
| `prompts/CR-00013_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00013_S05_Frontend_prompt.md` | Prompt | Prebuilt Tailwind + lazy libs + self-hosted font |
| `prompts/CR-00013_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00013_S07_Tests_prompt.md` | Prompt | Tests for all changes |
| `prompts/CR-00013_S08_CodeReview_prompt.md` | Prompt | Review S07 |
| `prompts/CR-00013_S09_CodeReview_Final_prompt.md` | Prompt | Global cross-layer review |
| `prompts/CR-00013_S15_BrowserVerification_prompt.md` | Prompt | Browser verification |
| `evidences/pre/*.png` | Evidence | Pre-change screenshots (captured at CR creation) |
| `evidences/post/*.png` | Evidence | Post-change screenshots (captured by S15) |

QV gates S10–S14 are driven by `command` + `gate` in the manifest and do not use prompt files.

Reports are created during execution in `ai-dev/work/CR-00013/reports/`.

## Acceptance Criteria

### AC1: Sidebar worktree badge is constant-time

```
Given the dashboard is running with 5+ projects and 10+ active worktrees
When a page loads and htmx fires GET /system/nav/worktree-badge
Then the response completes in under 50 ms
And the handler makes zero subprocess calls on cache hits
And the cache refreshes in the background (or on miss) at most every 30 s
```

### AC2: DB pool is sized explicitly and configurable

```
Given orch/db/session.py has been modified
When the engine is created
Then pool_size, max_overflow, pool_recycle, and pool_timeout are set explicitly
And pool_size and max_overflow default to 20 each
And they can be overridden via IW_CORE_DB_POOL_SIZE and IW_CORE_DB_MAX_OVERFLOW env vars
And the .env.example file documents both variables
```

### AC3: N+1 hotspots issue bounded query counts

```
Given a project selector page with N projects or a batch detail with N items
When the page is rendered
Then the number of SQL queries does not scale with N (is bounded by a small constant)
And this is enforced by a regression test using a query counter
```

Target routes:
- `GET /` (project selector) — `_project_stats`
- `GET /project/{pid}` — `_active_batches`
- `GET /project/{pid}/batch/{bid}` — `_batch_item_rows`
- `GET /project/{pid}/item/{iid}` (any tab) — `_get_steps`
- `GET /system/running` — `_query_failed_steps`

### AC4: Subprocess calls on hot paths are cached

```
Given the system status page and /worktrees page
When they are rendered twice in quick succession (within TTL)
Then git subprocess calls are issued on the first render only
And the second render reads from the in-memory cache
```

### AC5: Daemon control sleeps do not block the event loop

```
Given a request to /daemon/start, /daemon/stop, or /daemon/restart
When the handler waits for the daemon state to settle
Then it uses asyncio-aware sleeping (asyncio.sleep or asyncio.to_thread)
And other concurrent HTTP requests are not blocked during the wait
```

### AC6: Tailwind is prebuilt; client-side bloat is reduced

```
Given dashboard/templates/base.html
When any page is served
Then the runtime Tailwind CDN script is no longer present
And a prebuilt dashboard/static/styles.css is linked instead
And Mermaid, Highlight.js + language scripts, DOMPurify, streaming-markdown are loaded only on pages that declare them via {% block head %}
And the Inter font is served from /static (no fonts.googleapis.com link)
And make css produces the prebuilt CSS
And dashboard/CLAUDE.md documents the build step
```

### AC7: Request-timing observability is present

```
Given the FastAPI app is running
When a request completes in more than 500 ms
Then a log line at WARN level is emitted with path, duration_ms, and db_query_count
And the pool's current status (size, checked_out, overflow) is included
```

### AC8: No visual or functional regression

```
Given any dashboard page visited prior to this CR
When it is visited after the CR is applied
Then the visible layout, controls, and behavior are unchanged
And the diff of pre/ and post/ screenshots is visually equivalent (cosmetic-only differences allowed where a design token changed)
```

## Rollback Plan

- **Database**: Not applicable (no schema changes).
- **Code**: Single revert of the squash-merge commit restores prior behavior. Each step commits atomically and can be cherry-picked/reverted independently if needed.
- **Data**: No data loss on rollback.

Operational rollback notes:
- Env-var defaults (B1) are backward compatible — setting `IW_CORE_DB_POOL_SIZE` unset falls back to the new default (20), which is strictly larger than the old implicit 5. Reverting code without reverting env is safe.
- The TTL cache (A1/D1/D2) is in-process memory; restart clears it. No cleanup needed.
- The prebuilt CSS file (E1) is checked in (or produced at `make` time). If reverted, `base.html` returns to CDN and no file is needed.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Unit tests**:
  - Pool config: engine built with expected kwargs from env vars (default and override).
  - TTL cache helper: hit/miss behavior, expiry, concurrent access guard.
  - Request-timing middleware: emits WARN log above threshold; includes pool status.
  - N+1 regression: each hotspot route asserted to issue ≤K queries for varying N (use SQLAlchemy event or a query counter fixture).
  - Daemon control: `time.sleep` no longer called in sync handlers (or handler is `async def`).

- **Integration tests** (testcontainer-backed):
  - `_get_steps`, `_active_batches`, `_batch_item_rows`, `_project_stats`, `_query_failed_steps` — populate N rows and assert query count ≤K.
  - `/system/nav/worktree-badge` end-to-end: first call populates cache, second call served from cache (zero subprocess spawns).

- **Updated tests**:
  - Any test asserting on the exact number of queries on the modified routes must be adjusted to the new lower bound.
  - Any test importing `SessionLocal` directly must still work after pool-kwarg changes.

- **Browser tests (S15)**:
  - Visual parity on project selector, project dashboard, system status, item detail.
  - Sidebar badge renders and refreshes.
  - Pages that use Mermaid (e.g., item design-doc view) still render diagrams.
  - Pages that use Highlight.js (e.g., code view) still colorize code blocks.
  - No console errors on any visited page.

## Notes

- **Order matters.** S01 (observability + pool + caching) must land before S03 (N+1 fixes) so regression tests can measure from a stable baseline. S05 (frontend) is independent and could run in parallel with S03 in principle, but the workflow keeps it sequential for simpler review.
- **Risk: stale cache.** A1/D1/D2 use TTLs; short TTLs (30 s for dirty-count, 10–15 s for git stats) keep visible lag within user tolerance while eliminating the subprocess storm.
- **Risk: CSS drift.** E1 moves Tailwind to a build step. The CLAUDE.md update and Makefile target must be clear enough that future contributors regenerate CSS after template edits. Consider adding a lint check that the CSS is up-to-date (out of scope for this CR; note only).
- **Risk: pool oversizing.** PostgreSQL has its own `max_connections`. Defaulting to 20+20 = 40 per dashboard instance is conservative for a single-instance deploy but documented in `.env.example`.
- **Observability first.** F1/F2 in S01 provide the baseline. S15 should capture a post-change median and p95 from the logs as evidence.
