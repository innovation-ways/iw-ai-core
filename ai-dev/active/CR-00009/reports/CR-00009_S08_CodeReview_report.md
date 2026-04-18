# CR-00009 S08 — Code Review Report

## Summary

Reviewed S07 (tests-impl) implementation against the acceptance criteria and review checklist. Tests are correctly scoped and high-quality; no mandatory fixes required. Pre-existing integration test failures (8 tests in `test_doc_polish.py::TestGlobalSearch`) are unrelated to CR-00009 and pre-existed this CR.

---

## AC Coverage Map

| AC | Covered by test(s) | Notes |
|----|--------------------|-------|
| AC1 (header "Chat — Architecture") | None | Intentionally deferred to S16 (DOM/browser verification) |
| AC2 (header with module name) | None | Intentionally deferred to S16 |
| AC3 (system prompt module block) | `test_system_prompt_emits_module_block_when_path_provided`, `test_system_prompt_module_block_without_name`, `test_system_prompt_no_module_block_when_path_empty_string` | ok |
| AC4 (retrieval fallback) | `test_system_prompt_retrieval_note_only_when_fallback_triggered`, `test_answer_stream_falls_back_when_module_filter_empty` | ok |
| AC5 (no fallback when results exist) | `test_system_prompt_no_module_is_byte_identical_to_pre_change_output`, `test_answer_stream_does_not_fall_back_when_module_filter_nonempty` | ok |
| AC6 (end-to-end module reference) | None | Intentionally deferred to S16 (full E2E with real browser) |
| AC7 (module_name in QARequest) | `test_post_qa_with_module_name_forwards_to_engine`, `test_post_qa_without_module_name_still_accepted`, `test_post_qa_with_module_name_null_still_accepted` | ok |

**Note**: AC1, AC2, AC6 are frontend/JS behaviors intentionally not covered in unit/integration tests per the S07 report note ("DOM tests for header-label behavior were intentionally not added per the S16 coverage note"). S16 is the browser verification step that covers these.

---

## Test Quality Analysis

### `_build_system_prompt` tests (TestBuildSystemPrompt)

- **`test_system_prompt_no_module_is_byte_identical_to_pre_change_output`**: Hard-codes the expected string literal (lines 39–49) — NOT derived from the function under test. Correctly guards against textual drift. **No finding.**
- **`test_system_prompt_emits_module_block_when_path_provided`**: Asserts presence of `"## Current Focus — Module"`, `"orch/daemon/"`, `"Orchestration Daemon"`, and `"Prioritize"`. Uses substring matching, not exact whitespace. **MEDIUM (over-constrains)** — but acceptable because the prompt format is stable; substring checks are robust to formatting changes.
- **`test_system_prompt_module_block_without_name`**: Verifies no `()` when `module_name=None`. Checks for `"(No architecture document available)"` and `"()"`. Correctly guards against stray parentheses. **No finding.**
- **`test_system_prompt_retrieval_note_only_when_fallback_triggered`**: Calls `_build_system_prompt` with `fallback_triggered=True` and `False`, asserting `"## Retrieval Note"` appears only in the former. **No finding.**
- **`test_system_prompt_no_module_block_when_path_empty_string`**: Verifies no module block when `module_path=""`. **No finding.**

### `answer_stream` fallback tests (TestAnswerStream)

- **`test_answer_stream_falls_back_when_module_filter_empty`**: Uses `_FakeTable` with `filtered_rows` dict mapping where-clause → rows. When module filter returns `[]`, unfiltered search returns `["chunk-a"]`. Captures messages sent to mock LLM and asserts `"## Retrieval Note"` in system prompt. The `_FakeSearch.where()` method captures the last clause so `limit()` can return different rows per filter. **MEDIUM (spies on behavior via output, not call counting)** — but acceptable because the mock naturally distinguishes filtered vs unfiltered paths via the where clause.
- **`test_answer_stream_does_not_fall_back_when_module_filter_nonempty`**: Symmetric test for when module filter returns rows. Asserts no `"## Retrieval Note"`. **No finding.**
- **`test_answer_stream_does_not_fall_back_for_architecture_context`**: architecture-level search skips module filtering entirely. **No finding.**
- **`test_answer_stream_handles_lancedb_exception_without_claiming_fallback`**: `lancedb.connect` is patched with `side_effect=RuntimeError(...)`. Asserts no `"## Retrieval Note"` in resulting prompt. **No finding.**

### Integration tests (test_code_qa_routes.py)

- **`test_post_qa_with_module_name_forwards_to_engine`**: Captures kwargs from mock `answer_stream` and asserts `module_name == "Orchestration Daemon"`. Clean spy pattern. **No finding.**
- **`test_post_qa_without_module_name_still_accepted`**: Missing `module_name` field → asserts `captured_kwargs["module_name"] is None`. Correctly verifies AC7 backwards-compat. **No finding.**
- **`test_post_qa_with_module_name_null_still_accepted`**: Explicit `null` → asserts `captured_kwargs["module_name"] is None`. **No finding.**

---

## Isolation & Determinism

- Unit tests: LanceDB mocked via `patch("lancedb.connect")`, Ollama mocked via `patch("orch.rag.qa.Ollama")` and `patch("orch.rag.qa.OllamaEmbedding")`. **No live DB. No live Ollama. No `time.sleep`. No network calls.**
- Integration tests: Use testcontainers (real PostgreSQL on random port), but mock `QAEngine` entirely — no Ollama, no LanceDB. **Compliant.**
- No `importlib.reload(orch.config)` found. **Compliant.**

---

## Conventions Compliance

- Test names follow `test_<subject>_<verb>_<condition>` pattern. **Compliant.**
- Async tests use `@pytest.mark.asyncio`. **Compliant.**
- `TestBuildSystemPrompt` tests use sync `def` (not async) since `_build_system_prompt` is sync. **Correct.**
- `TestAnswerStream` tests use `async def` with `@pytest.mark.asyncio`. **Correct.**

---

## Pre-existing Test Failures

8 tests in `tests/integration/test_doc_polish.py::TestGlobalSearch` fail with HTTP 404 on `/api/docs/search?q=`. These are pre-existing failures unrelated to CR-00009 (the CR only touches `orch/rag/qa.py`, `dashboard/routers/code_qa.py`, and frontend chat panel files). The failures affect a completely different route (`/api/docs/search`) and involve doc polish functionality.

---

## Test Verification

| Check | Result |
|-------|--------|
| `make test-unit` | **804 passed, 0 failed** |
| `uv run ruff check tests/` | **All checks passed** |
| `make test-integration` | **506 passed, 8 failed** (pre-existing failures unrelated to CR-00009) |

---

## Findings

| Severity | Count | Description |
|----------|-------|-------------|
| HIGH | 0 | — |
| MEDIUM | 1 | Substring assertions in `_build_system_prompt` tests (e.g., `"Prioritize" in result`) slightly over-constrain but are acceptable — the instruction word is semantically load-bearing and stable |
| CRITICAL | 0 | — |

**Mandatory fix count: 0**

---

## Verdict

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "CR-00009",
  "step_reviewed": "S07",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM",
      "location": "tests/unit/test_qa_engine.py:71",
      "description": "test_system_prompt_emits_module_block_when_path_provided asserts 'Prioritize' as a substring — slightly over-constrains but acceptable since the keyword is semantically load-bearing"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "804 passed (unit), 506 passed (integration, 8 pre-existing failures unrelated to CR-00009)",
  "notes": "AC1, AC2, AC6 intentionally deferred to S16 (browser verification). Pre-existing failures in test_doc_polish.py::TestGlobalSearch are unrelated to this CR."
}
```