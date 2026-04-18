# CR-00009_S07_Tests_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Step**: S07
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md`
- `ai-dev/active/CR-00009/reports/CR-00009_S01_Backend_report.md`
- `ai-dev/active/CR-00009/reports/CR-00009_S03_Api_report.md`
- `ai-dev/active/CR-00009/reports/CR-00009_S05_Frontend_report.md`
- `orch/rag/qa.py` (the implementation you're testing)
- `dashboard/routers/code_qa.py`
- `tests/conftest.py` and `tests/CLAUDE.md` for fixtures/conventions

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S07_Tests_report.md`

## Context

Write tests that enforce acceptance criteria AC3, AC4, AC5, AC7. AC1, AC2, AC6 are covered by the qv-browser step (S16).

## Requirements

### 1. Unit tests for `_build_system_prompt`

File: `tests/unit/test_qa_engine.py` (create if it does not exist; extend if it does). The `QAEngine.__init__` takes `(project_id, config)` — instantiate with a minimal `CodeUnderstandingConfig` fixture or a simple dataclass-style stub. `_build_system_prompt` is a pure function, so no mocking is needed.

Test cases:

- **test_system_prompt_no_module_is_byte_identical_to_pre_change_output** (AC5):
  - Build the prompt with `module_path=None`, `module_name=None`, `fallback_triggered=False`, a sample `context_doc_content="## Architecture\nBlah"`, and `chunks=["chunk-a", "chunk-b"]`.
  - Assert the output matches an expected string that is exactly the pre-change format. Hard-code the expected string in the test — this guards against textual drift.
- **test_system_prompt_emits_module_block_when_path_provided** (AC3):
  - Call with `module_path="orch/daemon/"`, `module_name="Orchestration Daemon"`.
  - Assert output contains the literal substring `## Current Focus — Module`.
  - Assert output contains both `orch/daemon/` and `Orchestration Daemon`.
  - Assert output contains a "prioritize" instruction to the LLM (case-insensitive).
- **test_system_prompt_module_block_without_name**:
  - Call with `module_path="orch/daemon/"`, `module_name=None`.
  - Assert `## Current Focus — Module` present, `orch/daemon/` present.
  - Assert no stray `()` or `( )` in the rendered path line.
- **test_system_prompt_retrieval_note_only_when_fallback_triggered** (AC4 partial):
  - With `fallback_triggered=True`, assert `## Retrieval Note` substring appears.
  - With `fallback_triggered=False`, assert `## Retrieval Note` does NOT appear.
- **test_system_prompt_no_module_block_when_path_empty_string**:
  - Call with `module_path=""`.
  - Assert no `## Current Focus — Module` substring.

### 2. Unit tests for `answer_stream` retrieval fallback

Same file. Use `pytest.mark.asyncio` (the project already relies on it for async tests — confirm in `pyproject.toml` or `pytest.ini`). Mock LanceDB by monkeypatching `lancedb.connect` to return a stub whose `open_table(...).search(...).where(...).limit(...).to_pandas()` returns a controlled DataFrame.

Hint: the cleanest way is to build a small fake chain class:

```python
class _FakeQuery:
    def __init__(self, rows: list[str]):
        self._rows = rows
    def to_pandas(self):
        import pandas as pd
        return pd.DataFrame({"text": self._rows})

class _FakeSearch:
    def __init__(self, rows_per_where: dict[str, list[str]]):
        self._rows_per_where = rows_per_where
        self._last_where = None
    def where(self, clause):
        self._last_where = clause
        return self
    def limit(self, n):
        return _FakeQuery(self._rows_per_where.get(self._last_where, []))
```

Test cases:

- **test_answer_stream_falls_back_when_module_filter_empty** (AC4):
  - Mock LanceDB so the `file_path LIKE 'orch/daemon/%'` query returns `[]` and the unfiltered query returns `["chunk-a"]`.
  - Mock `OllamaEmbedding.get_query_embedding` to return a fixed vector.
  - Mock `Ollama.astream_chat` to return a trivial async iterator.
  - Call `answer_stream(..., context_level="module", module_path="orch/daemon/", module_name="Daemon")`.
  - Collect streamed output. Assert the mocked `astream_chat` was called with a system prompt containing `## Retrieval Note` (reach the system prompt via a spy on the Ollama mock or by capturing the `messages` arg).
- **test_answer_stream_does_not_fall_back_when_module_filter_nonempty** (AC5):
  - Mock LanceDB so the filtered query returns `["chunk-a"]`.
  - Spy the unfiltered search path and assert it was NOT called.
  - Assert the system prompt does NOT contain `## Retrieval Note`.
- **test_answer_stream_does_not_fall_back_for_architecture_context**:
  - With `context_level="architecture"` and filtered search returning `[]`, no fallback — the original query was already unfiltered.
- **test_answer_stream_handles_lancedb_exception_without_claiming_fallback**:
  - Monkeypatch `lancedb.connect` to raise.
  - Assert `answer_stream` still streams a response (via the mocked Ollama), and the system prompt does NOT contain `## Retrieval Note`.

Use `monkeypatch` over `unittest.mock.patch` for consistency with the rest of the test suite.

### 3. Integration test for `QARequest.module_name` round-trip (AC7)

File: `tests/integration/test_code_qa_routes.py` (exists — extend it). Use the existing FastAPI test-client fixture and DB testcontainer pattern from `tests/conftest.py`. Patch `QAEngine.answer_stream` with a spy.

Test cases:

- **test_post_qa_with_module_name_forwards_to_engine**:
  - POST `/api/projects/{project_id}/code/qa` with body including `"module_name": "Orchestration Daemon"`.
  - Assert the spy was called once with a kwarg `module_name="Orchestration Daemon"`.
- **test_post_qa_without_module_name_still_accepted** (AC7):
  - POST the same endpoint without `module_name` in the body.
  - Assert response is 200 (the spy's streaming body is fine).
  - Assert the spy was called with `module_name=None`.
- **test_post_qa_with_module_name_null_still_accepted**:
  - POST with explicit `"module_name": null`.
  - Assert 200 + `module_name=None` on the spy.

### 4. Do NOT add DOM tests

The header-label behavior is covered by qv-browser (S16). Adding JSDOM tests just to re-cover it would bloat the unit suite. Note this decision in your report.

### 5. Do NOT mock the database in the integration test

Per `CLAUDE.md` hard rules: integration tests use a real PostgreSQL testcontainer. The LanceDB / Ollama layers can (and should) be mocked/spied — that's not the DB.

## Project Conventions

- Read `tests/CLAUDE.md` for fixtures (`FTS_FUNCTION_SQL`, `FTS_TRIGGER_SQL` after `Base.metadata.create_all`), naming (`test_<feature>_<case>`), and `monkeypatch.delenv` preference over `importlib.reload`.
- Tests live under `tests/unit/` (no DB) or `tests/integration/` (with testcontainer).
- Do not import from `orch.config` at test module scope — it reads env at import time.

## TDD Requirement

This step IS the test suite. Your tests should have been the RED phase for S01/S03 — here you ratify them:

1. Write the tests above.
2. Run them against the current tree.
3. If any fail: stop, record the failure in your report, and return with `completion_status: "partial"`. Do NOT modify production code to make tests pass — that's a prior step's concern.
4. If all pass: report green.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all new unit tests must pass.
2. `make test-integration` — all new integration tests must pass.
3. `uv run ruff check tests/`
4. `uv run mypy tests/` (if the project configures mypy for tests — skip if not).

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "CR-00009",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_qa_engine.py",
    "tests/integration/test_code_qa_routes.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
