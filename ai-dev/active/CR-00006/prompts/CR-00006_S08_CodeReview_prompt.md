# CR-00006 S08 — Tests Review

## Input Files

- `ai-dev/active/CR-00006/CR-00006_CR_Design.md`
- `ai-dev/active/CR-00006/prompts/CR-00006_S07_Tests_prompt.md`
- `tests/CLAUDE.md` — hard rules
- `tests/unit/test_code_qa_streaming.py`
- `tests/unit/test_jobs_aggregator.py`
- `tests/integration/test_jobs_api.py`
- `tests/unit/test_qa_markdown_sanitize.py`

## Output Files

- `ai-dev/work/CR-00006/reports/S08_tests_review.md`

## Context

**Work item**: CR-00006
**Step**: S08
**Agent**: tests-review

Review the four new test modules for coverage, correctness, isolation, and conformance to the project's testing hard rules.

## Review Checklist

### Hard rules (absolute)

- [ ] No test connects to the live DB (port 5433). Grep for `5433`, `IW_CORE_DB_PORT` hardcoded values in the test files.
- [ ] Integration tests use the `testcontainers` fixture pattern from `tests/conftest.py`.
- [ ] No `importlib.reload(orch.config)` — if env vars are manipulated, `monkeypatch.delenv` is used.
- [ ] The integration test does NOT mock the DB session.
- [ ] If the schema is built via `Base.metadata.create_all()`, the `FTS_FUNCTION_SQL + FTS_TRIGGER_SQL` DDL is applied after (consistent with existing fixtures).
- [ ] The psycopg v3 URL replacement (`postgresql+psycopg2://` → `postgresql+psycopg://`) is applied where the testcontainer URL is consumed (may be handled by the shared fixture already — confirm).
- [ ] `DaemonEvent.event_metadata` (Python attribute name) is used, not `metadata`.

### `test_code_qa_streaming.py`

- [ ] The non-buffering assertion compares the time-gap between first and last token frames and requires at least ~3× the per-token sleep delay. This is the core proof that buffering is gone.
- [ ] The fake `QAEngine` yields tokens with `await asyncio.sleep(...)` between them — not a synchronous list.
- [ ] Monkeypatch path points to the correct module location (`orch.rag.QAEngine` or wherever the bridge imports it from).
- [ ] Error-path test asserts a single `event: error` SSE frame with the expected message.
- [ ] Uses `@pytest.mark.asyncio` and `pytest-asyncio` is a confirmed dev dependency.
- [ ] Test collects SSE frames from an async-generator, not from a streaming HTTP response (unit-level, not integration).

### `test_jobs_aggregator.py`

- [ ] Seeds rows for all four source types and asserts a 4-row union.
- [ ] Separate tests for: type filter, status filter, date range, pagination, sort, `get_job` happy/miss paths.
- [ ] Status normalisation test covers at least one BatchStatus → `running`/`completed` mapping AND one DocStatus → `completed` mapping.
- [ ] Uses `session.commit()` on seed, then creates a fresh session before calling the aggregator (catches the "uncommitted" mistake).
- [ ] No global state leaks between tests (fixture rollback/truncation works).

### `test_jobs_api.py`

- [ ] Spins the FastAPI app via `create_app()` (or equivalent).
- [ ] Overrides `get_db` dependency to use the testcontainer session.
- [ ] All 7 test cases cover: list happy, list with type filter, fragment response (no `<html>`), detail happy, detail 404, type-param 422, missing-project 404.
- [ ] HTML content is asserted by looking for specific ids/strings (not brittle full-text matches).
- [ ] No test spins a real Ollama server.

### `test_qa_markdown_sanitize.py`

- [ ] `test_dompurify_loaded_in_base` confirms DOMPurify is in `base.html` AND pinned to a specific semver.
- [ ] `test_qa_panel_uses_dompurify` confirms `marked.parse` + `DOMPurify.sanitize` appear AND the stale `responseSpan.textContent += data.token` path is gone AND `noopener noreferrer` is present.
- [ ] `test_qa_panel_user_bubble_is_text_not_markdown` confirms user bubbles use `textContent` (not `innerHTML`).

### Running

```bash
make test-unit 2>&1 | tail -30
make test-integration 2>&1 | tail -30
```

Both must exit 0. Capture any flakes — assertion timing must be tolerant enough to pass on slower CI machines (the ≥0.3s threshold for the streaming test is sufficient margin for a 5×100ms sleep chain).

### Coverage

- [ ] Streaming bug: tested.
- [ ] Aggregator: union + each filter + sort + pagination + normalisation — tested.
- [ ] API endpoints: list + fragment + detail + error paths — tested.
- [ ] Markdown sanitization: wiring verified (DOM-level XSS verification deferred to S11 browser verification).

### Out of scope

- [ ] No test of the DaemonEvent toast rendering path — that runs in the browser via SSE + `toast.html`. S11 verifies manually.
- [ ] No test of the `code_map_completed` event row being inserted (can be added if seeding + running the completion path is trivial; otherwise acceptable to defer to manual verification).

## Signal completion

If correct and all tests pass:

```bash
iw step-done CR-00006 S08 --summary "Tests review passed: 4 test modules, 18+ test cases covering streaming non-buffering, aggregator union/filter/sort/pagination/normalisation, Jobs API round-trip, and markdown sanitization wiring. All tests pass on unit + integration suites."
```

If issues found:

```bash
iw step-fail CR-00006 S08 --reason "<CRITICAL/HIGH findings>"
```
