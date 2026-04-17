# CR-00006 S07 — Tests Implementation

## Input Files

- `tests/CLAUDE.md` — hard rules for testing (NEVER mock DB in integration tests; NEVER connect to live DB; use testcontainers; run `FTS_FUNCTION_SQL + FTS_TRIGGER_SQL` after `create_all()`)
- `tests/conftest.py` — fixture patterns (testcontainer setup, session cleanup)
- `ai-dev/active/CR-00006/CR-00006_CR_Design.md` — source of truth for acceptance criteria
- `dashboard/routers/code_qa.py` — the non-buffering bridge (target of streaming test)
- `orch/jobs/aggregator.py` — target of aggregator tests
- `dashboard/routers/jobs_ui.py` — target of API integration tests
- `dashboard/templates/fragments/code_qa_panel.html` — extract the `qaRenderMarkdown` helper for testability if possible

## Output Files

- **New**: `tests/unit/test_code_qa_streaming.py`
- **New**: `tests/unit/test_jobs_aggregator.py`
- **New**: `tests/integration/test_jobs_api.py`
- **New**: `tests/unit/test_qa_markdown_sanitize.py` (Python-side check against the `DOMPurify` config string; OR a node-based test — see notes below)

## Context

**Work item**: CR-00006
**Step**: S07
**Agent**: tests-impl

You are writing the test coverage for the backend + API changes and a smoke-test for the markdown sanitization.

## Test 1: Streaming bridge does not buffer

File: `tests/unit/test_code_qa_streaming.py`

Goal: prove that `_sse_generator` yields SSE frames as tokens are produced, not after all tokens are produced.

Approach:

```python
import asyncio
import time
import types
from unittest.mock import patch

import pytest
from dashboard.routers.code_qa import _sse_generator  # adjust import based on final name
from orch.rag.config import CodeUnderstandingConfig


class FakeAnswerStream:
    """Async generator yielding 5 tokens with a 100ms delay between each."""

    def __init__(self, delay_s: float = 0.1, tokens: list[str] = None):
        self.delay_s = delay_s
        self.tokens = tokens or ["a ", "b ", "c ", "d ", "e"]

    async def __call__(self, **kwargs):
        for tok in self.tokens:
            await asyncio.sleep(self.delay_s)
            yield tok


@pytest.mark.asyncio
async def test_sse_generator_streams_tokens_live(monkeypatch):
    """First token must arrive well before the last — proves no end-to-end buffering."""

    fake_stream = FakeAnswerStream(delay_s=0.1)

    class FakeEngine:
        def __init__(self, project_id, config):
            pass

        async def answer_stream(self, **kw):
            async for t in fake_stream(**kw):
                yield t

    monkeypatch.setattr("orch.rag.qa.QAEngine", FakeEngine)

    cfg = CodeUnderstandingConfig()  # default values are fine for this test
    timestamps = []

    async for frame in _sse_generator(
        project_id="P1",
        question="q",
        context_level="architecture",
        context_doc_id=None,
        module_path=None,
        conversation_history=[],
        db_session=None,  # the fake engine ignores it
        config=cfg,
    ):
        timestamps.append((time.monotonic(), frame))

    # Expect 5 token frames + 1 done frame
    assert len(timestamps) == 6
    token_times = [t for t, frame in timestamps if '"token"' in frame]
    assert len(token_times) == 5

    # Last token must arrive at least 0.3s after the first — proves streaming.
    assert token_times[-1] - token_times[0] >= 0.3
```

Notes:
- The test uses `monkeypatch.setattr` to replace the `QAEngine` class inside `orch.rag.qa`. Adjust the attribute path if the bridge imports it differently.
- If the bridge takes `db_session` and passes it to `QAEngine.answer_stream`, and the FakeEngine ignores it, `None` is fine.
- Mark with `pytest.mark.asyncio` (requires `pytest-asyncio` — confirm it's already in dev deps; if not, flag as a blocker).

Add a second test that asserts error handling:

```python
@pytest.mark.asyncio
async def test_sse_generator_handles_connection_error(monkeypatch):
    class FailingEngine:
        def __init__(self, *a, **kw): pass
        async def answer_stream(self, **kw):
            raise ConnectionRefusedError("no ollama")
            yield  # make it a generator

    monkeypatch.setattr("orch.rag.qa.QAEngine", FailingEngine)

    frames = []
    async for f in _sse_generator(
        project_id="P1",
        question="q",
        context_level="architecture",
        context_doc_id=None,
        module_path=None,
        conversation_history=[],
        db_session=None,
        config=CodeUnderstandingConfig(),
    ):
        frames.append(f)

    assert any('"event": "error"' in f for f in frames)
    assert any("Local AI unavailable" in f for f in frames)
```

## Test 2: JobsAggregator unions and filters four sources

File: `tests/unit/test_jobs_aggregator.py`

Use the project's existing testcontainer fixture pattern (see `tests/conftest.py`). Critical rules:
- Run `Base.metadata.create_all()` on the testcontainer engine.
- Run `FTS_FUNCTION_SQL + FTS_TRIGGER_SQL` after `create_all()` (WorkItem FTS trigger is orthogonal to this test but required for the schema to be consistent — follow the existing conftest pattern).
- Use psycopg v3 URL (`postgresql+psycopg://` — replace `postgresql+psycopg2://` if the testcontainer returns the legacy URL).

Test cases:

1. **Empty state**: aggregator returns `JobListResult(rows=[], total=0, page=1, page_size=25)` for a project with no jobs.
2. **Four-source union**: seed one row in each of `code_index_jobs`, `doc_generation_jobs`, `batches`, `project_docs` (with `doc_type=DocType.research`). Assert `len(rows) == 4` and each `job_type` appears exactly once.
3. **Type filter**: `types=[JobType.code_mapping]` narrows to 1 row.
4. **Status filter**: seed a failed + a completed code_index job, assert `statuses=["completed"]` narrows to 1 row.
5. **Date range**: seed jobs with varying `started_at`; assert `date_from` / `date_to` filter as expected.
6. **Pagination**: seed 30 jobs; assert `page=1, page_size=10` returns 10 rows and `total=30`; `page=4` returns `[]`.
7. **Sort**: `sort_by="started_at", sort_dir="asc"` vs `"desc"` produces inverse orderings.
8. **`get_job`**: returns the exact seeded row for each of the four types; returns `None` for a bad id.
9. **Status normalisation**: seed a `BatchStatus.executing` batch, assert its normalised status string is `"running"`; seed a `DocStatus.published` research doc, assert `"completed"`.

## Test 3: Jobs API round-trip

File: `tests/integration/test_jobs_api.py`

Use FastAPI's `TestClient` with the testcontainer DB. Spin the app via `create_app()`; override `get_db` dependency to point at the testcontainer session.

Test cases:

1. `GET /project/{p}/jobs` returns HTTP 200 and HTML containing each seeded job's id.
2. `GET /project/{p}/jobs?type=code_mapping` returns HTML that contains code_mapping rows and does NOT contain batch rows.
3. `GET /project/{p}/jobs/fragment/table` returns HTML that does NOT contain `<html>` or `<body>` (it's a fragment).
4. `GET /project/{p}/jobs/code_mapping/{job_id}` returns HTTP 200 and HTML containing job-specific fields (e.g., `llm_model` value).
5. `GET /project/{p}/jobs/code_mapping/bogus-id` returns HTTP 404.
6. `GET /project/{p}/jobs/invalid_type/{job_id}` returns HTTP 422.
7. `GET /project/bogus-project/jobs` returns HTTP 404.

## Test 4: Markdown sanitization smoke test

Because the sanitization runs in the browser (DOMPurify + marked.js), a pure-Python test is limited. Two acceptable approaches:

**Option A (preferred if simple)**: extract the minimum surface you can verify in Python — grep the template to confirm DOMPurify is wired correctly:

File: `tests/unit/test_qa_markdown_sanitize.py`

```python
import re
from pathlib import Path

TEMPLATE_PATH = Path("dashboard/templates/fragments/code_qa_panel.html")
BASE_PATH = Path("dashboard/templates/base.html")


def test_dompurify_loaded_in_base():
    content = BASE_PATH.read_text()
    assert "dompurify" in content.lower()
    # Must be a pinned version — no @latest, no floating major
    assert re.search(r"dompurify@\d+\.\d+\.\d+", content), "DOMPurify must be pinned to a specific version"


def test_qa_panel_uses_dompurify():
    content = TEMPLATE_PATH.read_text()
    assert "DOMPurify.sanitize" in content
    assert "marked.parse" in content
    # Must set innerHTML only via the render helper, never via direct string concat with untrusted content
    assert "responseSpan.textContent +=" not in content, "Stale textContent append path must be gone"
    # Links must enforce rel on target=_blank
    assert "noopener noreferrer" in content


def test_qa_panel_user_bubble_is_text_not_markdown():
    content = TEMPLATE_PATH.read_text()
    # The user bubble function must use textContent (no markdown rendering of user input)
    # Find the function body
    match = re.search(r"function qaAppendUserBubble.*?^  \}", content, re.DOTALL | re.MULTILINE)
    assert match is not None
    body = match.group(0)
    assert "innerHTML" not in body
    assert "textContent" in body
```

**Option B (defer to manual browser verification in S11)**: skip the Python test and rely on `playwright-cli` in QV for the DOM-level check. Option A is strictly better (cheap + catches regressions) — implement it.

## Running the tests

```bash
make test-unit          # unit tests, no containers
make test-integration   # with PostgreSQL testcontainer
```

Both should pass on a clean checkout.

## Do NOT

- Do NOT use live DB (port 5433) — testcontainers only.
- Do NOT mock the DB in the integration test — the design explicitly bans this for `FOR UPDATE` correctness.
- Do NOT import `orch.config` inside tests and call `importlib.reload` — use `monkeypatch.delenv` instead (per `CLAUDE.md` critical rules).

## Signal completion

```bash
iw step-done CR-00006 S07 --summary "Added test_code_qa_streaming.py (2 tests proving non-buffering and error path), test_jobs_aggregator.py (9 tests covering union/filter/sort/pagination/normalisation), test_jobs_api.py (7 integration tests via testcontainer), test_qa_markdown_sanitize.py (template-grep tests for DOMPurify wiring)"
```

If a test can't run (e.g., `pytest-asyncio` missing):

```bash
iw step-fail CR-00006 S07 --reason "<what failed and what would unblock>"
```
