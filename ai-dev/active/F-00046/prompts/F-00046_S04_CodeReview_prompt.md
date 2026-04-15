# F-00046_S04_CodeReview_prompt

**Work Item**: F-00046 -- Code Understanding: Indexing Engine + Level 1 Map Generation
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/F-00046/F-00046_Feature_Design.md` -- Design document
- `ai-dev/work/F-00046/reports/F-00046_S03_Tests_report.md` -- S03 implementation report
- `tests/integration/test_code_index_pipeline.py` -- Integration tests
- `tests/conftest.py` -- Existing test fixtures

## Output Files

- `ai-dev/work/F-00046/reports/F-00046_S04_CodeReview_report.md` -- Review report

## Context

You are reviewing the S03 test implementation for F-00046. This step wrote integration tests for the full indexing pipeline **Python API** (F-00046 has no HTTP layer — HTTP/SSE is F-00047's scope). Read the design document for the intended acceptance criteria and boundary behaviors, then review the test file.

If you find any test that uses `fastapi.testclient.TestClient` or hits routes under `dashboard.routers.code*`, flag it CRITICAL — that scope belongs to F-00047 and must not leak into F-00046's test suite.

## Review Checklist

### 1. Test Coverage Completeness

Verify all test suites from the S03 prompt are present (Python API only):
- [ ] `test_full_index_cycle` — full index of a 3-file Python repo via `CodeIndexer.index()`
- [ ] `test_incremental_reindex` — only changed file re-embedded via `reindex_changed()`
- [ ] `test_failed_ollama_marks_job_failed` — Ollama error via runner → job status = "failed"
- [ ] `test_start_index_job_raises_when_already_running` — `JobAlreadyRunningError` on duplicate call
- [ ] `test_runner_emits_progress_then_done` — progress queue delivers events + terminal `done`
- [ ] `test_regenerate_map_upserts_project_doc` — `mode="mapgen_only"` upserts the architecture-map ProjectDoc
- [ ] `test_runner_cleans_up_on_ollama_error` — failed runner leaves no stale `JOB_REGISTRY` entry, emits `phase="error"`

### 2. DB Isolation

- Are testcontainers used (NEVER port 5433)?
- Do tests use the existing `db_session` fixture from `conftest.py`?
- Is there any direct connection to port 5433? If yes: CRITICAL finding.

### 3. Ollama Mocking

- Is Ollama fully mocked in all tests that involve embedding or LLM calls?
- Are `OllamaEmbedding` and `Ollama` LLM both mocked where needed?
- Is the mock applied at the correct import path (where the object is used, not where it is defined)?

### 4. LanceDB Isolation

- Does every test that touches LanceDB use `tmp_path` for the index path?
- Is there any test that writes to a shared/persistent index path? If yes: HIGH finding.

### 5. Fixture Quality

- Are the 3 Python fixture files adequately complex to exercise chunking? (Must have at least 1 class and 2 methods total across files.)
- Does `test_incremental_reindex` actually modify a file's content between the full index and the reindex call?
- Does `test_failed_ollama_marks_job_failed` wait for the async runner to complete before asserting on DB state?

### 6. Assertion Completeness

- `test_full_index_cycle`: checks `files_indexed`, `chunks_created`, LanceDB table exists and has rows, manifest exists with 3 entries?
- `test_incremental_reindex`: checks `files_indexed == 1`, `files_skipped == 2`, manifest SHA updated for changed file?
- `test_failed_ollama_marks_job_failed`: checks `job.status == "failed"` AND `job.errors` is non-empty AND no `ProjectDoc` created?
- `test_start_index_job_raises_when_already_running`: asserts `JobAlreadyRunningError`, original registry entry preserved, new `CodeIndexJob.status` unchanged?
- `test_runner_emits_progress_then_done`: drains `progress_queue` and asserts at least one `phase="progress"`-style event followed by terminal `phase="done"`?
- `test_runner_cleans_up_on_ollama_error`: asserts `JOB_REGISTRY.get(project.id) is None` after failure and terminal `phase="error"` on the queue?

### 7. Async Test Patterns

- Are async tests marked with the correct decorator (`@pytest.mark.asyncio` or `@pytest.mark.anyio`)?
- Does the pattern match what is used in existing integration tests?

### 8. JOB_REGISTRY Cleanup

- Do tests that insert stubs into `JOB_REGISTRY` clean up after themselves (via `yield` fixture or `finally` block)?
- Could a failing test leave `JOB_REGISTRY` in a dirty state that breaks subsequent tests?

### 9. Code Quality

- Are test names descriptive?
- Are test docstrings present explaining what scenario is tested?
- No `time.sleep()` in tests — async tests should await properly?
- No hardcoded port 5433 or localhost Ollama URLs?

## Test Verification (NON-NEGOTIABLE)

Before submitting review:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/ dashboard/
uv run pytest tests/unit/ -v
uv run pytest tests/integration/test_code_index_pipeline.py -v
```

Report results accurately. Integration test failures are HIGH findings.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Connects to live DB (port 5433), breaks test isolation | Must fix before merge |
| **HIGH** | Integration test failure, test missing, assertion incorrect | Must fix before merge |
| **MEDIUM (fixable)** | Incomplete assertions, weak mocking, test order dependency | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better test pattern available | Optional |
| **LOW** | Test naming, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00046",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "notes": ""
}
```
