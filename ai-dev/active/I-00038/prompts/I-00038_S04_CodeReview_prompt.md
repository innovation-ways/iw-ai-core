# I-00038_S04_CodeReview_prompt

**Work Item**: I-00038 -- Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00038/I-00038_Issue_Design.md` — acceptance criteria and **Test to Reproduce** section.
- `ai-dev/active/I-00038/reports/I-00038_S03_Tests_report.md`
- `tests/dashboard/browser/test_sse_shared_worker.py`
- `tests/dashboard/test_sse_client_wiring.py`
- `tests/CLAUDE.md` — critical test rules.
- `tests/dashboard/browser/conftest.py` — fixture conventions.

## Output Files

- `ai-dev/active/I-00038/reports/I-00038_S04_CodeReview_report.md`

## Context

Review the tests produced in S03. The most important check is whether the reproduction test actually distinguishes pre- and post-fix behavior — not just "SSE works".

## Review Checklist

### 1. Semantic correctness (CRITICAL)

- **Does `test_multi_tab_does_not_exhaust_connection_budget` assert a specific numeric bound on connection count?** (`<= 2` or similar, not just "> 0").
- **Would the test FAIL on pre-fix code?** Walk through the pre-fix scenario: 6 tabs × 1 EventSource each = 6 connections. A passing assertion on pre-fix code is a BUG in the test.
- **Does the test actually open 6 distinct tabs?** Opening the same Playwright context multiple times does not increment the browser's per-origin connection count — each tab must be a separate context.
- **Do template tests assert SPECIFIC VALUES, not shape?**
  - `"new EventSource('/api/stream/events')" not in response.text` ✓ (specific string, specific absence)
  - `"iwSSE.on(" in response.text` ✓
  - `"sse-client.js" in response.text` ✓
  - Not: `"EventSource" not in response.text` ✗ (would break if any other EventSource remains elsewhere on the page)

### 2. Coverage vs acceptance criteria

Map each AC to tests:

| AC | Test that covers it | Adequate? |
|----|---------------------|-----------|
| AC1 (multi-tab responsiveness) | `test_multi_tab_does_not_exhaust_connection_budget` | ✓ if it opens ≥ 6 tabs and asserts bound |
| AC2 (connection count = 1) | same | ✓ if the bound is ≤ 2 (1 plus margin is fine; ≤ 6 is too loose) |
| AC3 (fallback preserves behavior) | New test or skip with `pytest.skip` rationale | If absent, flag as MEDIUM (fixable) |
| AC4 (all event types delivered) | Either in the browser test (trigger event, observe fanout in ≥ 2 tabs) or in unit tests | Must be present somehow |
| AC5 (regression test exists and runs in `make test-integration`) | test file placement + marker | Verify with `pytest --collect-only` |
| AC6 (no direct EventSource to /api/stream/events in templates) | `test_sse_client_wiring.py` parametrized | ✓ |
| AC7 (out-of-scope EventSource preserved) | Negative assertion: oss/code pages still contain their own `new EventSource` for job streams | Should be present |

### 3. Test isolation and determinism

- **No `sleep`-only synchronization**: any `time.sleep(...)` must be justified (SSE polls every 5 s; accept ≤ 10 s waits when waiting for a real event fanout).
- **Teardown cleans up**: every playwright-cli session is closed in `finally`; the dashboard subprocess is terminated.
- **No DB pollution**: if the test inserts a `DaemonEvent`, it uses a testcontainer OR a monkey-patched session — NEVER the live DB on port 5433 (see tests/CLAUDE.md).
- **No network assumptions**: if `ss` is unavailable, the test skips cleanly (`pytest.skip`) rather than crashing.
- **Parallel-safe**: tests don't hardcode a single port that would collide if the module runs in parallel.

### 4. Fixture reuse

- Does the test reuse `dashboard_server` from `conftest.py`, or spin up its own server? Prefer reuse to avoid duplication.
- If a new fixture is needed, is it under `conftest.py` (shared) or inline (private)? Match convention.

### 5. Code quality

- Test names start with `test_` and describe WHAT they verify.
- Helper functions (`_count_sse_connections`, `_wait_for_sse_ready`) have docstrings and are named with a leading underscore to mark them private.
- No commented-out code.

### 6. tests/CLAUDE.md compliance

- No `importlib.reload(orch.config)` calls.
- If a testcontainer is used, URL replacement `postgresql+psycopg2://` → `postgresql+psycopg://` is applied.
- If `Base.metadata.create_all()` is called, `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` are run afterwards.
- `DaemonEvent` is accessed via `event_metadata` (not `metadata`).
- No live DB (port 5433) in tests.

## Test Verification

Run the tests yourself:

```bash
make test-unit
make test-integration
```

Report results in `tests_passed` / `test_summary`.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Test does not distinguish pre- and post-fix behavior; test connects to live DB | Must fix |
| HIGH | Missing AC coverage; flaky synchronization; bound is too loose (e.g. `<= 6` instead of `<= 2`) | Must fix |
| MEDIUM (fixable) | Missing fallback test; missing fanout test; weak assertions | Should fix |
| MEDIUM (suggestion) | Better helper factoring; more descriptive docstring | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00038",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
