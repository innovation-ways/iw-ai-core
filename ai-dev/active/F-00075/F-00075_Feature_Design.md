# F-00075: MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)

**Type**: Feature
**Priority**: Medium
**Created**: 2026-04-30
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

This feature does not touch the database. No migration is involved.

---

## Description

The dashboard footer's MiniMax usage bar currently reports a wrong percentage (observed: 19% on 2026-04-30 while platform.minimax.io showed 0%). The number is a local estimate computed from `~/.local/share/opencode/opencode.db` against an epoch-aligned 5h grid that does not match MiniMax's actual billing window, and it counts tokens while the Coding Plan tier counts requests. This feature replaces that estimate with a direct call to MiniMax's authoritative quota endpoint (`GET https://api.minimax.io/v1/api/openplatform/coding_plan/remains`), reads only the `MiniMax-M*` row (the dashboard's "Text Generation" bar), surfaces a 5h reset countdown next to the bar (mirroring the Claude pattern), and removes the local-SQLite path entirely so it can never produce a misleading number again.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key references for this feature:

- `orch/llm_usage.py` — current implementation (Claude logic stays untouched).
- `dashboard/routers/usage.py:1-41` — the `/api/usage/llm/fragment` route that consumes `get_llm_usage()`.
- `dashboard/templates/fragments/llm_usage_footer.html` — the htmx fragment template.
- Project uses `httpx >=0.27` (already a dependency at `pyproject.toml:55`).

## Scope

### In Scope

- Add `_load_minimax_key()` helper in `orch/llm_usage.py`: env var `IW_MINIMAX_API_KEY` first, fall back to `~/.local/share/opencode/auth.json` → `["minimax"]["key"]`, return `None` if neither.
- Add `_minimax_usage_remote(key)` in `orch/llm_usage.py`: calls `GET https://api.minimax.io/v1/api/openplatform/coding_plan/remains` with `Authorization: Bearer {key}`, parses the `MiniMax-M*` row, returns `{"block_pct", "block_reset", "used", "total"}`. Honors optional `IW_MINIMAX_GROUP_ID` env var (appended as `?GroupId=`).
- Rewrite `_minimax_usage()` to call the remote helper and return `{"block_pct": 0, "block_reset": None}` on any failure (missing key, network error, HTTP non-2xx, `base_resp.status_code != 0`, missing `MiniMax-M*` row, parse error). All failures logged via `logger.exception`.
- **Delete the SQLite-reading code path entirely**: remove the `sqlite3` import, the `_OPENCODE_DB` constant, the `_FIVE_H_MS` constant, the `_MINIMAX_5H_LIMIT` constant and `IW_MINIMAX_5H_LIMIT` env var.
- Update `dashboard/routers/usage.py` to pass `minimax_reset`, `minimax_5h_used`, `minimax_5h_total` into the template context (mirroring `claude_reset`).
- Update `dashboard/templates/fragments/llm_usage_footer.html` to render the reset countdown next to the MiniMax bar (use `{{ minimax_reset or '5h' }}` like the Claude row uses `{{ claude_reset or '5h' }}`) AND add a `title` attribute exposing used/total request counts as a tooltip. The tooltip is rendered via a Jinja `is not none` guard so the failure path (where `used`/`total` are missing) does not produce `"None / None requests"`.
- Add unit tests in `tests/unit/test_llm_usage.py` plus a captured response fixture at `tests/fixtures/minimax_remains.json`.
- Document `IW_MINIMAX_API_KEY` and `IW_MINIMAX_GROUP_ID` (optional) in `.env.example` if present, or in the `orch/llm_usage.py` module docstring.

### Out of Scope

- A new JSON usage endpoint. The htmx fragment endpoint remains the only consumer.
- Surfacing the `coding-plan-vlm` or `coding-plan-search` rows. They are MCP-tool quotas, not the "Text Generation" bar.
- Any change to Claude usage logic, including `_claude_usage()`, `IW_CLAUDE_*` env vars, ccusage integration, or the JSONL token scanner.
- Replacing the in-process 60s cache. Same cache layer is reused.
- Database changes, migrations, or new ORM models.
- Persisting historical MiniMax usage to disk or DB.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Rewrite `orch/llm_usage.py` MiniMax path: add `_load_minimax_key()` and `_minimax_usage_remote()`, rewrite `_minimax_usage()`, delete SQLite code, update module docstring. | — |
| S02 | code-review-impl | Review S01 (backend). | — |
| S03 | api-impl | Update `dashboard/routers/usage.py` to forward `minimax_reset`, `minimax_5h_used`, `minimax_5h_total` to the template. | — |
| S04 | frontend-impl | Update `dashboard/templates/fragments/llm_usage_footer.html` to show reset countdown and optional tooltip. | — |
| S05 | code-review-impl | Review S03 (API). | — |
| S06 | code-review-impl | Review S04 (frontend). | — |
| S07 | tests-impl | Add `tests/unit/test_llm_usage.py` and capture `tests/fixtures/minimax_remains.json`. | — |
| S08 | code-review-final-impl | Cross-layer global review. | — |
| S09..S13 | qv-gate | lint, format, typecheck, unit-tests, integration-tests. | — |
| S14 | qv-browser | Verify dashboard footer end-to-end in isolated worktree stack. | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — feature is configuration-driven and stateless.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: `GET /api/usage/llm/fragment` — same path and content type, but the rendered HTML now includes a MiniMax reset countdown and the percentage is sourced from the live MiniMax API.

### Frontend Changes

- **New components**: None
- **Modified components**: `dashboard/templates/fragments/llm_usage_footer.html` — adds the `{{ minimax_reset or '5h' }}` label next to the MiniMax bar and a `title` attribute on the row showing used/total request counts. The `title` attribute is emitted only when both `minimax_5h_used` and `minimax_5h_total` are not `None` (success branch); on the failure branch the tooltip is omitted entirely.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00075/F-00075_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00075/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/F-00075/prompts/F-00075_S01_Backend_prompt.md` | Prompt | S01 — orch/llm_usage.py rewrite |
| `ai-dev/active/F-00075/prompts/F-00075_S02_CodeReview_Backend_prompt.md` | Prompt | S02 — review S01 |
| `ai-dev/active/F-00075/prompts/F-00075_S03_API_prompt.md` | Prompt | S03 — dashboard/routers/usage.py |
| `ai-dev/active/F-00075/prompts/F-00075_S04_Frontend_prompt.md` | Prompt | S04 — footer template |
| `ai-dev/active/F-00075/prompts/F-00075_S05_CodeReview_API_prompt.md` | Prompt | S05 — review S03 |
| `ai-dev/active/F-00075/prompts/F-00075_S06_CodeReview_Frontend_prompt.md` | Prompt | S06 — review S04 |
| `ai-dev/active/F-00075/prompts/F-00075_S07_Tests_prompt.md` | Prompt | S07 — tests + fixture |
| `ai-dev/active/F-00075/prompts/F-00075_S08_CodeReview_Final_prompt.md` | Prompt | S08 — cross-layer review |
| `ai-dev/active/F-00075/prompts/F-00075_S14_BrowserVerification_prompt.md` | Prompt | S14 — browser QV |
| `orch/llm_usage.py` | Source | Backend rewrite (S01) |
| `dashboard/routers/usage.py` | Source | Pass through new template vars (S03) |
| `dashboard/templates/fragments/llm_usage_footer.html` | Source | Reset countdown + tooltip (S04) |
| `tests/unit/test_llm_usage.py` | Test | New unit tests (S07) |
| `tests/fixtures/minimax_remains.json` | Test fixture | Captured live response (S07) |

Pre-evidence already captured at `ai-dev/active/F-00075/evidences/pre/`:
- `F-00075-before-footer.png` — dashboard with wrong 19% MiniMax bar.
- `F-00075-before-fragment.html` — raw `/api/usage/llm/fragment` HTML showing 19% and no reset countdown.

Reports are created during execution in `ai-dev/active/F-00075/reports/`.

## Acceptance Criteria

### AC1: MiniMax % matches platform.minimax.io within the 60s cache window

```
Given IW_MINIMAX_API_KEY is set OR ~/.local/share/opencode/auth.json contains a minimax.key
And the MiniMax /coding_plan/remains endpoint returns a successful response with a row where model_name == "MiniMax-M*"
When the dashboard requests GET /api/usage/llm/fragment
Then the rendered MiniMax bar percentage equals round((current_interval_total_count - current_interval_usage_count) / current_interval_total_count * 100), capped at 100
And on a second request within 60 seconds, no new outbound HTTP call is made (same value served from the in-process cache)
```

### AC2: Reset countdown rendered next to the MiniMax bar

```
Given the MiniMax remote call succeeded
When the dashboard renders /api/usage/llm/fragment
Then the MiniMax row shows a reset countdown formatted as "Xh Ym" when remains_time >= 1 hour
And formatted as "Ym" when remains_time < 1 hour
And the source value is row["remains_time"] (milliseconds) from the MiniMax-M* row
```

### AC3: Graceful failure shows 0% with no exception

```
Given any of: missing API key, network error, HTTP non-2xx, base_resp.status_code != 0, missing MiniMax-M* row, total == 0, JSON parse error
When the dashboard requests GET /api/usage/llm/fragment
Then the MiniMax bar shows 0% and the reset slot shows "5h" (template fallback)
And no exception bubbles to the FastAPI request handler (HTTP 200 OK)
And the failure is logged exactly once per cache window:
  - missing API key → logger.warning("MiniMax API key not configured; usage bar will show 0%")
  - any runtime failure (network error, HTTP non-2xx, status_code != 0, missing M* row, total == 0, JSON parse error) → logger.exception("MiniMax usage fetch failed")
```

### AC4: Cache TTL respected

```
Given the cache is warm (last refresh < 60 seconds ago)
When two get_llm_usage() calls occur within the cache window
Then exactly one outbound HTTP request to api.minimax.io is made
And both calls return the same MiniMax block_pct value
```

### AC5: No regression for Claude

```
Given Claude usage logic is untouched
When the dashboard renders /api/usage/llm/fragment
Then both Claude bars render exactly as before (block_pct, week_pct, block_reset)
And no new fields are required in the Claude template branch
```

### AC6: SQLite path is fully removed

```
Given the implementation is complete
When grepping orch/llm_usage.py for SQLite-related symbols
Then "_OPENCODE_DB", "import sqlite3", "_FIVE_H_MS", "_MINIMAX_5H_LIMIT", and "IW_MINIMAX_5H_LIMIT" return zero matches in that file
```

### AC7: Optional GroupId escape hatch

```
Given the operator sets IW_MINIMAX_GROUP_ID=<value> in the environment
When _minimax_usage_remote(key) builds the request URL
Then the URL includes "?GroupId=<value>" as a query parameter
And when IW_MINIMAX_GROUP_ID is unset, the URL has no query string
```

## Boundary Behavior

Define edge cases. **Every row becomes a mandatory test case.**

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| 0/4500 used (real fixture) | Captured response with `current_interval_total_count=4500`, `current_interval_usage_count=4500`, `remains_time≈9812749` | `block_pct=0`, `block_reset` ≈ `"2h 43m"` (matches `remains_time`) |
| Mid-window usage | Synthetic row with `total=4500`, `usage_count=3000` (so used=1500) | `block_pct=33` |
| Fully consumed | `total=4500`, `usage_count=0` | `block_pct=100` |
| `MiniMax-M*` row absent | Response with rows for other models only | `{"block_pct": 0, "block_reset": None}`, no exception |
| `total == 0` | M* row present but `current_interval_total_count=0` | `{"block_pct": 0, "block_reset": None}` |
| `base_resp.status_code != 0` | e.g. `{"status_code": 1004, "status_msg": "auth error"}` | `{"block_pct": 0, "block_reset": None}`, `logger.exception` called |
| HTTP 5xx | Mock `httpx.get` to raise `httpx.HTTPStatusError` | `{"block_pct": 0, "block_reset": None}`, `logger.exception` called |
| Network timeout | Mock `httpx.get` to raise `httpx.ConnectTimeout` | `{"block_pct": 0, "block_reset": None}`, `logger.exception` called |
| Malformed JSON | Mock response body = `"<html>"` | `{"block_pct": 0, "block_reset": None}`, `logger.exception` called |
| No env var, no auth.json | `IW_MINIMAX_API_KEY` unset, `~/.local/share/opencode/auth.json` missing | `_load_minimax_key()` returns `None`, `_minimax_usage()` returns `{"block_pct": 0, "block_reset": None}`, no HTTP call, `logger.warning` called once |
| Env var wins over auth.json | Both set with different values | `_load_minimax_key()` returns the env-var value |
| auth.json fallback | env var unset, auth.json present with `minimax.key` | `_load_minimax_key()` returns the auth.json value |
| auth.json malformed | env var unset, auth.json contains invalid JSON | `_load_minimax_key()` returns `None`, no exception |
| `remains_time` < 1 hour | row with `remains_time = 1_500_000` (25 minutes) | `block_reset == "25m"` (no leading "0h") |
| `remains_time` exactly 1 hour | row with `remains_time = 3_600_000` | `block_reset == "1h 0m"` |
| Cache TTL respected | Two calls 30 s apart | `httpx.get` invoked exactly once |
| Cache expiry | Two calls 90 s apart | `httpx.get` invoked twice |
| GroupId env var set | `IW_MINIMAX_GROUP_ID=abc` | URL = `https://api.minimax.io/v1/api/openplatform/coding_plan/remains?GroupId=abc` |

## Invariants

Conditions that **must hold true** after implementation. Each maps to a test.

1. `_minimax_usage()` never raises. Every documented failure mode returns `{"block_pct": int, "block_reset": str | None}` and logs the failure exactly once per cache window.
2. The MiniMax bar percentage in the rendered fragment always equals what `_minimax_usage_remote()` would return for that response, modulo the 60s cache.
3. `orch/llm_usage.py` contains no `sqlite3`, no `_OPENCODE_DB`, no `_FIVE_H_MS`, no `_MINIMAX_5H_LIMIT`, no `IW_MINIMAX_5H_LIMIT` after the change.
4. Claude logic (`_claude_usage()`, `_run_ccusage()`, `_block_start()`, `_sum_jsonl_tokens()`, `IW_CLAUDE_*` env vars) is byte-for-byte unchanged.
5. The 60s in-process cache (`_CACHE_TTL`, `_cache`, `_cache_lock`) is reused, not duplicated or replaced.
6. `_load_minimax_key()` reads `IW_MINIMAX_API_KEY` first; only when it is unset (or empty string) does it consult `~/.local/share/opencode/auth.json`.
7. The HTTP request always uses `Authorization: Bearer {key}` and `Accept: application/json`. No other auth header variants.
8. The HTTP timeout for the MiniMax call is bounded (≤10 seconds) so a hung remote cannot block the dashboard.
9. The fixture `tests/fixtures/minimax_remains.json` contains no API keys and no PII; it is the verbatim response body only.
10. The footer fragment continues to render in <50ms from a warm cache (no regression in dashboard latency).

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Unit tests** (`tests/unit/test_llm_usage.py`):
  - Real-fixture parse: load `tests/fixtures/minimax_remains.json`, assert `block_pct=0`, `block_reset` matches the `remains_time` field via the `_format_reset()` formatter.
  - Synthetic mid-window: stub the response with `total=4500`, `usage_count=3000` → `block_pct=33`.
  - Fully consumed: `total=4500`, `usage_count=0` → `block_pct=100`.
  - Missing M* row → `{"block_pct": 0, "block_reset": None}`.
  - `total == 0` → `{"block_pct": 0, "block_reset": None}`.
  - `base_resp.status_code != 0` → graceful 0% + `logger.exception` called once.
  - `httpx.HTTPStatusError` / `httpx.ConnectTimeout` / `httpx.RequestError` → graceful 0% + `logger.exception` called once each.
  - Malformed JSON → graceful 0% + `logger.exception` called once.
  - `_load_minimax_key()`: env var wins; auth.json fallback works; both missing returns `None`; malformed auth.json returns `None`.
  - Cache TTL: `monkeypatch.setattr` to mock httpx, call `get_llm_usage()` twice within the TTL window, assert `mock.call_count == 1`.
  - Cache expiry: advance the cache timestamp past the TTL, call again, assert `mock.call_count == 2`.
  - GroupId: with `IW_MINIMAX_GROUP_ID` set, the captured request URL contains `?GroupId=<value>`; without, it has no query.
  - Reset formatter: `_format_reset(9_812_749)` → `"2h 43m"`; `_format_reset(1_500_000)` → `"25m"`; `_format_reset(3_600_000)` → `"1h 0m"`; `_format_reset(0)` → `None` or sentinel matching the existing Claude format.
- **Integration tests** (use the existing `tests/integration/` patterns, no new test container):
  - Optional smoke test that asserts `dashboard/routers/usage.py` passes the new keys to the template; this can be covered as a unit test using FastAPI's `TestClient` against a stub `_minimax_usage()` if the integration tier already has a usage-router test, otherwise skip the integration tier for this feature.
- **Edge cases**: Listed exhaustively in the Boundary Behavior table — every row is a test.

## Notes

### Why we removed the local SQLite fallback

The user explicitly directed (2026-04-30) that the local SQLite estimate must be removed entirely: "I don't want the local counter for minimax, it's wrong so I don't want to keep it." Keeping it as a "fallback" would risk reintroducing the same misleading number on transient network failures. Failure mode is now an honest 0% + log entry.

### Risks and mitigations

- **The `/coding_plan/remains` endpoint is undocumented by MiniMax.** Mitigation: schema-drift is detected by the fixture-based unit tests (a shape change breaks the test before users see a wrong number). On any failure the bar shows 0% and the error is logged. We accept the tradeoff: an undocumented endpoint that might break vs. a documented local computation that is currently wrong.
- **Cookie-only auth regression (MiniMax-M2#88).** The endpoint historically returned 1004 errors when called without a browser session cookie. As of 2026-04-30 the user's `sk-cp-` Bearer token works correctly (HTTP 200 verified). If a future regression reintroduces the cookie requirement, the existing failure path covers it (logged, 0% shown).
- **Per-account `GroupId` requirement.** Some MiniMax accounts may need `?GroupId=<id>`. The user's account works without it. The optional `IW_MINIMAX_GROUP_ID` env var is included as a documented escape hatch and is not exposed in the dashboard UI.
- **API key plaintext in opencode auth.json.** This is pre-existing; not introduced by this feature. The fallback only reads the file, never writes it. The env-var path (`IW_MINIMAX_API_KEY`) is the recommended source for production.
- **Coding Plan counts requests, not tokens.** The new path correctly reflects this. The deprecated `IW_MINIMAX_5H_LIMIT` was a token threshold, no longer applicable, and is removed.

### Reference fixture

The empirical response captured on 2026-04-30 21:02 UTC for `MiniMax-M*` was:

```
current_interval_total_count: 4500
current_interval_usage_count: 4500   (this is REMAINING, not used)
remains_time: 9812749 ms (~2h 43m)
start_time: 1777579200000  (2026-04-30 20:00 UTC)
end_time:   1777593600000  (2026-04-30 23:00 UTC = 01:00 UTC tomorrow corrected — see fixture for exact value)
current_weekly_total_count: 0   (no weekly cap on Coding Plan M*)
```

Naming gotcha encoded once: `current_interval_usage_count` is the **remaining** quota in this window, not used. `used = total - usage_count`. The Swift opencode-bar reference implementation confirms this.
