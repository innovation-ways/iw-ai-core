# I-00038_S03_Tests_prompt

**Work Item**: I-00038 -- Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00038/I-00038_Issue_Design.md` — read **Test to Reproduce**, **Acceptance Criteria**, **Regression Prevention**.
- `ai-dev/active/I-00038/reports/I-00038_S01_Frontend_report.md` — list of files changed by S01.
- `dashboard/static/sse-shared-worker.js` and `dashboard/static/sse-client.js` (from S01).
- `tests/dashboard/browser/conftest.py` — existing Playwright harness with `dashboard_server` and `playwright_session` fixtures.
- `tests/dashboard/` — for the template-rendering test style.
- `tests/CLAUDE.md` — test conventions and critical rules.

## Output Files

- `tests/dashboard/browser/test_sse_shared_worker.py` — the reproduction test (multi-tab connection count).
- `tests/dashboard/test_sse_client_wiring.py` — template-rendering test (assert `sse-client.js` is included in `base.html`; assert no stray `EventSource('/api/stream/events')` in migrated pages).
- `ai-dev/active/I-00038/reports/I-00038_S03_Tests_report.md` — step report.

## Context

This step writes the regression tests that:

1. **Prove the bug existed** — would FAIL against the pre-fix code.
2. **Prove the fix works** — PASS against the current (post-S01) code.
3. **Prevent recurrence** — run in `make test-integration` / `make check`.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "sse-client.js" in html` (shape only — just asserts a string appears somewhere)
- BAD: `assert sse_connections > 0` (shape only — asserts "some connection exists", passes trivially)
- GOOD: `assert sse_connections_from_browser <= 2` (semantic — the specific bound that defines "fixed")
- GOOD: `assert len(event_source_in_templates) == 0` (semantic — specific count that captures "zero stray EventSource")

For this bug specifically: the assertion that defines "fixed" is **connection count does not scale with tab count**. A passing test that merely opens a tab and confirms an event arrives will pass on both pre- and post-fix code and does **not** catch the regression. You MUST write a test that distinguishes them.

## Requirements

### 1. Regression test: `tests/dashboard/browser/test_sse_shared_worker.py`

Use the existing fixtures in `tests/dashboard/browser/conftest.py`. Add a new module-scoped fixture if needed (e.g. `dashboard_server_sse` — or reuse `dashboard_server`).

The test must:

1. Open **N = 6** Playwright browser contexts (tabs), each navigating to a different dashboard page that calls `iwSSE.on(...)`:
   - `/project/iw-ai-core/`
   - `/project/iw-ai-core/batches`
   - `/project/iw-ai-core/item/<some existing item>` (discover one via the seed DB or skip if none exist)
   - `/project/iw-ai-core/tests`
   - `/project/iw-ai-core/quality`
   - `/system/running`
   (If fewer than 6 URLs are reachable in the test env, open the same page in multiple contexts — the point is to hit multiple SharedWorker clients simultaneously.)
2. Wait for each page to signal its SSE client is ready (either via a small `window.__iwSSEReady` flag set by the client on connect, or a polling loop on `iwSSE.ready` — S01 must expose a readiness signal; if not, fail the test with a blocker in the report).
3. Query the server-side established connection count via `ss -tn`:

   ```python
   import subprocess
   out = subprocess.check_output(
       ["ss", "-tn", "state", "established", f"( sport = :{port} )"],
       text=True,
   )
   count = max(0, len(out.strip().splitlines()) - 1)
   ```

4. Assert the precise bound: **`assert count <= 2`** (one SharedWorker connection + a narrow margin for the test's own HTTP probes or pending keep-alives). Document the reasoning inline so future maintainers don't raise the bound to paper over a regression.
5. As a control, assert that **at least one** `running-update` event is received in one of the contexts after triggering a daemon event (or mocking one — see step 6). This proves the fanout still works.

If no real daemon event can be triggered in the test harness, insert a `DaemonEvent` row directly with `event_type='test-ping'` using a short-lived session — actually no, the server filter is `_WATCHED_EVENTS`; pick one type that IS watched (e.g. `step_launched`) and insert a `DaemonEvent` row. The SSE generator polls every 5 s, so allow ≥ 6 s for the fanout.

6. On teardown, close all contexts; re-check connection count; assert it drops (upstream is closed when the last port disconnects).

```python
@pytest.mark.browser
def test_multi_tab_does_not_exhaust_connection_budget(dashboard_server):
    """N tabs MUST NOT produce N /api/stream/events connections.

    Pre-fix: 6 tabs → 6 SSE connections (one per tab).
    Post-fix: 6 tabs → 1 SSE connection (shared across all via SharedWorker).
    """
    port = _extract_port(dashboard_server)
    sessions = []
    try:
        for url_suffix in PAGES:
            session = f"i00038-{uuid4().hex[:8]}"
            subprocess.run(
                ["playwright-cli", f"-s={session}", "open", dashboard_server + url_suffix],
                check=True, capture_output=True, timeout=30,
            )
            _wait_for_sse_ready(session)
            sessions.append(session)

        count = _count_sse_connections(port)
        assert count <= 2, (
            f"Expected ≤ 2 SSE connections (1 SharedWorker + margin); got {count}. "
            "The dashboard has regressed to per-tab EventSource."
        )
    finally:
        for s in sessions:
            subprocess.run(["playwright-cli", f"-s={s}", "close"], capture_output=True)
```

`_count_sse_connections` should be in a helper module (or test-local) and use `ss -tn state established '( sport = :<port> )'` — falling back gracefully with `pytest.skip` if `ss` is unavailable.

### 2. Template-rendering test: `tests/dashboard/test_sse_client_wiring.py`

A fast, non-browser test using `TestClient` (follow the pattern in `tests/dashboard/test_chat_templates.py`):

1. **Assert base.html wires in the client**:

   ```python
   response = client.get("/")
   assert response.status_code == 200
   assert "/static/sse-client.js" in response.text
   ```

2. **Assert no migrated page emits direct EventSource to the global stream** — parse each of the 7 migrated page HTMLs and assert:

   ```python
   assert "new EventSource('/api/stream/events')" not in response.text
   ```

   Run this for each of the 7 pages listed in the design doc's **Affected Components**. Parametrize with `pytest.mark.parametrize`.

3. **Assert each migrated page registers at least one `iwSSE.on(...)` handler**:

   ```python
   assert "iwSSE.on(" in response.text
   ```

4. **Assert out-of-scope pages are NOT broken** — load `oss.html`, `code` page, a docs page; confirm they still return 200.

### 3. Handle test environment gaps gracefully

- If `ss` is not on `$PATH` in CI, `pytest.skip("ss(8) required for socket counting")`.
- If the Playwright harness can't reach the dashboard (port collision), skip with a clear message.
- The test MUST NOT leave a dashboard process or playwright-cli session behind (the `try/finally` pattern above is mandatory).

### 4. Critical DB rules (from tests/CLAUDE.md)

- **NEVER** connect tests to the live DB on port 5433 — use testcontainers.
- **NEVER** call `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- **NEVER** mock the database in integration tests.
- **MUST** replace `postgresql+psycopg2://` with `postgresql+psycopg://` in testcontainer URLs.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- **CRITICAL**: `DaemonEvent.metadata` is named `event_metadata` in Python.

The browser-level test uses the existing `dashboard_server` fixture which starts Uvicorn against the host DB — audit the fixture and align with tests/CLAUDE.md. If the fixture currently hits the live DB, flag it as a HIGH blocker in your report rather than papering over it.

## TDD Requirement

1. **Write the test first** (against the pre-fix state conceptually — i.e. reason through what the old code would do).
2. Confirm the test would **FAIL** against the old code (7 tabs → 7 connections).
3. Run the test against the S01 code — it MUST pass (≤ 2 connections).

Do not skip the "would FAIL against old code" reasoning — document it in the test module docstring.

## Test Verification

Run before reporting complete:

```bash
make lint
make test-unit
make test-integration   # runs the browser-level test
```

All three must pass with zero failures. Report honestly.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00038",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/browser/test_sse_shared_worker.py",
    "tests/dashboard/test_sse_client_wiring.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (unit+integration)",
  "blockers": [],
  "notes": "Reproduction test asserts connection count ≤ 2 over 6 concurrent tabs"
}
```
