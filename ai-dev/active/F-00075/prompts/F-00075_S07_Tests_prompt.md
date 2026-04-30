# F-00075_S07_Tests_prompt

**Work Item**: F-00075 -- MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Same policy as in S01. Full policy: docs/IW_AI_Core_Agent_Constraints.md)

## ⛔ Migrations: agents generate, daemon applies

This work item touches no migrations.

## Input Files

- `ai-dev/active/F-00075/F-00075_Feature_Design.md` — particularly the **Boundary Behavior** and **Invariants** sections; every row and every numbered invariant becomes at least one test.
- `orch/llm_usage.py` (post-S01)
- `dashboard/routers/usage.py` (post-S03)
- `dashboard/templates/fragments/llm_usage_footer.html` (post-S04)
- `tests/CLAUDE.md` — testing conventions, fixture patterns, testcontainer rules.

## Output Files

- `ai-dev/active/F-00075/reports/F-00075_S07_Tests_report.md`
- New file: `tests/unit/test_llm_usage.py`
- New file: `tests/fixtures/minimax_remains.json` (captured live response, response body only — no API key)

## Context

Add comprehensive unit-test coverage for the new MiniMax path in `orch/llm_usage.py` and the router-level pass-through. Capture the real response shape as a fixture so future schema drift fails the suite before users see a wrong number.

## Requirements

### 1. Capture the response fixture

Create `tests/fixtures/minimax_remains.json`. Use the response body verified live on 2026-04-30 21:02 UTC. The full body is in the conversation history of this work item; if it is no longer available, regenerate by running:

```bash
KEY=$(python3 -c "import json; print(json.load(open('/home/sergiog/.local/share/opencode/auth.json'))['minimax']['key'])")
curl -s -H "Authorization: Bearer $KEY" -H "Accept: application/json" \
  https://api.minimax.io/v1/api/openplatform/coding_plan/remains \
  | python3 -m json.tool > tests/fixtures/minimax_remains.json
```

Verify the captured file:

- Contains a row where `model_name == "MiniMax-M*"`.
- Contains `current_interval_total_count`, `current_interval_usage_count`, `remains_time`.
- Contains `base_resp.status_code == 0`.
- Does **not** contain any API key, account ID, or PII.

### 2. Unit tests in `tests/unit/test_llm_usage.py`

Cover every Boundary Behavior row and every Invariant. Use `pytest`, `monkeypatch`, and `unittest.mock.patch` to mock `httpx.get`. Do **not** make real network calls. Do **not** spin up a testcontainer for this file (it's pure unit tests).

#### `_load_minimax_key`

- `test_load_key_from_env_var`: `monkeypatch.setenv("IW_MINIMAX_API_KEY", "sk-cp-test-from-env")` → returns `"sk-cp-test-from-env"`.
- `test_load_key_env_var_wins_over_authjson`: env var set + `auth.json` present with a different value → returns the env value. Use `tmp_path` and monkeypatch `Path.home()` (or refactor `_load_minimax_key` to accept the home path; pick the cleanest approach for the codebase).
- `test_load_key_falls_back_to_authjson`: env var unset, `auth.json` exists with `{"minimax": {"key": "sk-cp-from-file"}}` → returns `"sk-cp-from-file"`.
- `test_load_key_authjson_missing`: env var unset, `auth.json` does not exist → returns `None`.
- `test_load_key_authjson_malformed`: env var unset, `auth.json` contains `"<html>"` → returns `None`, no exception.
- `test_load_key_authjson_no_minimax_section`: env var unset, `auth.json` is `{"openai": {...}}` only → returns `None`.
- `test_load_key_empty_env_treated_as_unset`: `IW_MINIMAX_API_KEY=""` and `auth.json` has a key → returns the auth.json key (empty env var counts as unset).

#### `_format_reset`

- `test_format_reset_two_hours`: `_format_reset(9_812_749)` → `"2h 43m"`.
- `test_format_reset_one_hour_zero_min`: `_format_reset(3_600_000)` → `"1h 0m"`.
- `test_format_reset_minutes_only`: `_format_reset(1_500_000)` → `"25m"`.
- `test_format_reset_zero`: `_format_reset(0)` → `None`.
- `test_format_reset_negative`: `_format_reset(-1)` → `None`.

#### `_minimax_usage_remote` (mocked httpx)

- `test_remote_real_fixture`: load `tests/fixtures/minimax_remains.json`, mock `httpx.get` to return that body → result has `block_pct == 0`, `block_reset` is a non-empty string matching `_format_reset(remains_time)`, `used == 0`, `total == 4500`.
- `test_remote_mid_window`: synthetic body with M* row `total=4500, usage_count=3000` → `block_pct == 33`, `used == 1500`, `total == 4500`.
- `test_remote_fully_consumed`: `total=4500, usage_count=0` → `block_pct == 100`, `used == 4500`.
- `test_remote_missing_m_row`: response with no `MiniMax-M*` row → raises `LookupError`.
- `test_remote_total_zero`: M* row with `total=0` → raises `ValueError`.
- `test_remote_status_code_nonzero`: `base_resp.status_code = 1004, status_msg = "auth error"` → raises `RuntimeError("auth error")`.
- `test_remote_http_error`: mock raises `httpx.HTTPStatusError` → propagates (it's `_minimax_usage()`'s job to catch).
- `test_remote_uses_bearer_header`: capture the kwargs passed to `httpx.get` → `headers["Authorization"] == "Bearer <key>"`, `headers["Accept"] == "application/json"`.
- `test_remote_groupid_appended`: `monkeypatch.setenv("IW_MINIMAX_GROUP_ID", "abc123")` → captured URL contains `?GroupId=abc123`.
- `test_remote_no_groupid_unset`: env unset → captured URL has no query string.
- `test_remote_timeout_bounded`: captured `httpx.get` kwargs include `timeout` ≤ 10.

#### `_minimax_usage` (orchestrator)

- `test_minimax_no_key_returns_zero`: `_load_minimax_key` returns `None` → result is `{"block_pct": 0, "block_reset": None}`. Mock `httpx.get` and assert it was **not** called.
- `test_minimax_remote_success`: key present + httpx returns the real fixture → result equals what `_minimax_usage_remote` returned.
- `test_minimax_handles_status_code_error`: key present, httpx returns `base_resp.status_code = 1004` → result is `{"block_pct": 0, "block_reset": None}`, `logger.exception` was called once. Use `caplog` or a `MagicMock` on the logger.
- `test_minimax_handles_http_error`: key present, `httpx.get` raises `httpx.HTTPStatusError` → result is `{"block_pct": 0, "block_reset": None}`, logged once.
- `test_minimax_handles_connect_timeout`: `httpx.ConnectTimeout` raised → graceful `{0, None}`, logged.
- `test_minimax_handles_malformed_json`: response body is `"<html>"` → graceful `{0, None}`, logged.
- `test_minimax_handles_missing_m_row`: response has no M* row → result is `{"block_pct": 0, "block_reset": None}`. Note: the boundary table says this case should **not** fall back to local; since there is no local path anymore, this just returns the graceful zero state.

#### Cache TTL

- `test_cache_within_ttl_single_call`: warm the cache, call `get_llm_usage()` again 30 seconds later (advance the clock or seed `_cache["ts"]` directly) → `httpx.get` mock has `call_count == 1`.
- `test_cache_after_ttl_two_calls`: call, advance clock to 90 seconds later, call again → `call_count == 2`.
- Important: between tests, reset the module-level `_cache` (e.g. via a fixture that does `orch.llm_usage._cache.clear()`).

#### Router pass-through (smoke test, no network)

- `test_router_passes_minimax_reset_to_template`: use FastAPI `TestClient`, monkeypatch `dashboard.routers.usage.get_llm_usage` to return a stub MiniMax dict containing `block_reset="2h 43m"`, `used=0`, `total=4500`. GET `/api/usage/llm/fragment`. Assert the response body contains `"2h 43m"` and `"0 / 4500 requests"`.
- `test_router_handles_failure_dict`: stub `get_llm_usage` to return `{"claude": {...}, "minimax": {"block_pct": 0, "block_reset": None}}` (no `used`/`total`). GET the fragment. Assert response is HTTP 200, body contains `"5h"` (the template fallback) and does **not** contain `"None"`.

### 3. Determinism

All tests must be deterministic:

- No live HTTP calls.
- No reads from the user's actual `~/.local/share/opencode/auth.json`. Use `monkeypatch.setattr(Path, "home", ...)` or accept a configurable home path.
- No reliance on the system clock for the cache tests; manipulate the cache state directly or use `freezegun`/`time-machine` only if it is already a project test dep — otherwise mutate `_cache["ts"]` directly.

### 4. Fixture cleanliness

- `tests/fixtures/minimax_remains.json` must contain only the response body. Strip any wrapping. Verify with `jq '.base_resp.status_code'` returns `0`.

## Project Conventions

Read `tests/CLAUDE.md` for:
- Where unit tests live (`tests/unit/`).
- How to use the project's test fixtures.
- Naming conventions (`test_*.py`, `test_*` functions).
- Any `conftest.py` patterns relevant.

## TDD Requirement

Add tests for any boundary the implementation steps did not already cover. If a test fails because the implementation is incorrect, that is a finding for the code-review steps, not a license to modify implementation files in this step. Raise it as a blocker if needed.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

`make test-unit` must pass with all the new tests included.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "F-00075",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_llm_usage.py",
    "tests/fixtures/minimax_remains.json"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
