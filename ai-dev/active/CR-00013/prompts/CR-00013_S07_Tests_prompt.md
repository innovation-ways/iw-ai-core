# CR-00013_S07_Tests_prompt

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Step**: S07
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` — Design (AC1–AC8)
- `ai-dev/active/CR-00013/reports/CR-00013_S01_Backend_report.md` — files changed in S01
- `ai-dev/active/CR-00013/reports/CR-00013_S03_Backend_report.md` — files changed in S03
- `ai-dev/active/CR-00013/reports/CR-00013_S05_Frontend_report.md` — files changed in S05
- `tests/conftest.py` — existing fixtures (testcontainer, FTS init, query-count helper if present)
- `tests/CLAUDE.md` — test conventions

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S07_Tests_report.md` — step report
- New test files under `tests/unit/` and `tests/integration/`

## Context

S01, S03, and S05 implemented the behavior changes but may have written only enough tests to prove local correctness. S07's job is to add the **regression coverage** that locks the improvements in — and to ensure tests would fail on pre-change code.

Read the design doc's AC section carefully. Every AC must have at least one test that asserts its observable behavior.

## Requirements

### 1. Unit tests for S01 deliverables

Under `tests/unit/`:

- `test_ttl_cache.py` — hit/miss/expire behavior with monkeypatched time; concurrent fill safety (no corruption under `threading.Thread` races).
- `test_timing_middleware.py` — emits WARN with required fields when duration > threshold; emits DEBUG below threshold; does not swallow upstream exceptions; includes pool status dict.
- `test_db_pool_config.py` — `create_engine` called with `pool_size=20, max_overflow=20, pool_recycle=1800, pool_timeout=10` by default; overridable via env (`IW_CORE_DB_POOL_SIZE`, `IW_CORE_DB_MAX_OVERFLOW`). Use `monkeypatch.setenv` — never `importlib.reload`.
- `test_daemon_control_async.py` — `daemon_start`, `daemon_stop`, `daemon_restart` are coroutine functions (`inspect.iscoroutinefunction(...) is True`) and call `asyncio.sleep` (patch + assert called).

### 2. Integration tests for S01 deliverables

Under `tests/integration/`:

- `test_nav_worktree_badge_cache.py` — seed projects + batch items. Patch `_git_status` with a call counter. Hit `/system/nav/worktree-badge` twice within TTL → `_git_status` call count unchanged after second hit. Advance mocked time past TTL → call count increases.
- `test_git_branch_and_stats_cache.py` — patch the underlying `subprocess.check_output` (or the module-level helper invoked by `_git_branch_and_stats`) with a call counter. Invoke `_git_branch_and_stats(repo_root)` twice within the 15 s TTL → subprocess call count does not increase on the second call. Advance mocked time past TTL → call count increases. This is the explicit AC4 test for the `system.py` cache.

### 3. Integration tests for S03 deliverables (N+1 regression)

Under `tests/integration/`:

- `test_projects_stats_bounded_queries.py` — seed N projects (N=0, 1, 10). Hit `/`. Assert query count ≤ K (a small constant, e.g., K=5 to allow the app's baseline queries).
- `test_project_dashboard_bounded_queries.py` — seed a project with M active batches. Hit `/project/{pid}`. Query count bounded.
- `test_batch_detail_bounded_queries.py` — seed a batch with M items. Hit batch detail. Query count bounded.
- `test_item_detail_bounded_queries.py` — seed an item with M steps. Hit each item detail tab (design, tests, quality, etc.). Query count bounded.
- `test_running_tasks_bounded_queries.py` — seed with failed steps. Hit `/system/running`. Query count bounded.

Use a **query-counter fixture** based on a SQLAlchemy `after_cursor_execute` event listener on the test engine. Reset between tests. If the fixture already exists in `tests/conftest.py`, use it; otherwise add it there.

**IMPORTANT**: These tests must **fail** on pre-S03 code. Verify by stashing S03 changes locally, running the tests, seeing them fail, then unstashing. Document this in the report.

### 4. Unit/integration tests for S05 deliverables

Under `tests/unit/`:

- `test_base_html_renders.py` — render `base.html` via the app's Jinja environment and assert:
  - No `cdn.tailwindcss.com` substring.
  - `<link rel="stylesheet" href="/static/styles.css">` present.
  - No `fonts.googleapis.com` / `fonts.gstatic.com` references.
  - Mermaid / hljs / DOMPurify / streaming-markdown **not** present by default.
- `test_static_assets.py` — `dashboard/static/styles.css` exists and is non-empty; Inter `.woff2` files exist under `dashboard/static/fonts/inter/`.

Under `tests/integration/`:

- `test_pages_lazy_libs.py` — for a page known to use Mermaid (pick one from S05 report), hit the route and assert the response body contains the Mermaid script tag. For a page that does **not** use Mermaid, assert it's absent. Same for hljs.

### 5. Browser-level assertion (optional but recommended)

If feasible in the integration test harness, add a smoke test hitting `/` and asserting `200 OK` + no 5xx in the logs. (The S15 browser verification will do the full end-to-end.)

## Semantic Correctness (I003 lesson — MANDATORY)

I003's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Your tests must verify SPECIFIC VALUES and BOUNDED COUNTS, not presence-only:

- BAD: `assert query_count > 0` (truthy — passes even if the N+1 is untouched).
- GOOD: `assert query_count <= K` where K is a concrete small constant for the rewritten route.

- BAD: `assert "tailwindcss" not in html` (passes on an empty body).
- GOOD: `assert "cdn.tailwindcss.com" not in html and '<link rel="stylesheet" href="/static/styles.css">' in html`.

- BAD: `assert spawn.call_count >= 1` (passes whether or not the cache short-circuits).
- GOOD: `assert spawn.call_count == 1` after two calls within TTL, and `assert spawn.call_count == 2` after advancing past TTL.

- BAD: `assert any(r.levelname == "WARNING" for r in caplog.records)` (passes even if the record is from an unrelated source).
- GOOD: assert a WARNING record exists whose message includes `path`, `duration_ms > 500`, and `db_query_count` keys/values.

Apply this discipline to every assertion — the red→green stash check is the backstop, but each assertion should be tight enough that a regression reintroducing the behavior would flip it red on its own.

## Project Conventions

Read `tests/CLAUDE.md`:

- Never connect to live DB (port 5433) — testcontainers only.
- Never call `importlib.reload(orch.config)` — use `monkeypatch.delenv`.
- Never mock the DB in integration tests.
- Always run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- Replace psycopg2 URLs in testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.

## TDD Discipline

This step adds tests for behavior already implemented in S01/S03/S05, but the tests MUST be valid regression guards. For each test, verify it would fail on pre-change code:

1. `git stash` the relevant impl changes.
2. Run the new test — must fail.
3. `git stash pop` — must pass.

Document the red→green verification in the step report.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all new and existing tests pass.
2. `make test-integration` — all new and existing tests pass.
3. `make quality` — clean.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "CR-00013",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_ttl_cache.py",
    "tests/unit/test_timing_middleware.py",
    "tests/unit/test_db_pool_config.py",
    "tests/unit/test_daemon_control_async.py",
    "tests/unit/test_base_html_renders.py",
    "tests/unit/test_static_assets.py",
    "tests/integration/test_nav_worktree_badge_cache.py",
    "tests/integration/test_git_branch_and_stats_cache.py",
    "tests/integration/test_projects_stats_bounded_queries.py",
    "tests/integration/test_project_dashboard_bounded_queries.py",
    "tests/integration/test_batch_detail_bounded_queries.py",
    "tests/integration/test_item_detail_bounded_queries.py",
    "tests/integration/test_running_tasks_bounded_queries.py",
    "tests/integration/test_pages_lazy_libs.py",
    "tests/conftest.py (query-counter fixture if added)"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "red→green verification documented in report"
}
```
