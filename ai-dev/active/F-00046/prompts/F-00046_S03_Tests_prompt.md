# F-00046_S03_Tests_prompt

**Work Item**: F-00046 -- Code Understanding: Indexing Engine + Level 1 Map Generation
**Step**: S03
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/F-00046/F-00046_Feature_Design.md` -- Design document
- `ai-dev/work/F-00046/reports/F-00046_S01_Backend_report.md` -- S01 report
- `orch/rag/indexer.py`, `orch/rag/job.py`, `orch/rag/mapgen.py` -- Backend modules under test
- `tests/conftest.py` -- Existing test fixtures
- `tests/CLAUDE.md` -- Test conventions (read this carefully)
- `CLAUDE.md` -- Project conventions

## Output Files

- `tests/integration/test_code_index_pipeline.py` -- Integration tests
- `ai-dev/work/F-00046/reports/F-00046_S03_Tests_report.md` -- Step report

## Context

You are writing integration tests for the F-00046 indexing pipeline **Python API**. F-00046 is library code only — there is no FastAPI router or HTTP layer in this feature (HTTP/SSE is F-00047's scope). Drive the tests by calling `CodeIndexer`, `CodeIndexJobRunner`, and `start_index_job` directly. Do NOT use a `TestClient` to hit HTTP routes.

Read `tests/CLAUDE.md` and `tests/conftest.py` in full before writing any test code — the project has specific testcontainer patterns and fixtures that you MUST follow.

**Critical rules**:
- NEVER connect to port 5433 (live DB). ALL DB operations use testcontainers.
- NEVER require a live Ollama instance. Mock all Ollama HTTP calls.
- Use `tmp_path` pytest fixture for all LanceDB index files.
- Match the exact fixture and session patterns in the existing integration tests.
- Do NOT import `dashboard.app` or `fastapi.testclient` in this test file — this test suite exercises the Python API only.

## Test Cases to Implement

### Test Suite 1: Full Index Cycle (`test_full_index_cycle`)

**Setup**:
- Create a temporary directory with 3 Python source files using `tmp_path`:
  ```
  repo/
    main.py       — contains a simple class with 2 methods
    utils.py      — contains 3 helper functions
    models.py     — contains 2 dataclasses
  ```
- Mock `OllamaEmbedding` to return a fixed 384-dimension embedding vector for any input. Note: mocking at `orch.rag.indexer.OllamaEmbedding` only works if `indexer.py` imports and constructs it directly. If LlamaIndex resolves the embed model via `llama_index.core.Settings`, patch `Settings.embed_model` in the test instead. Verify which path the S01 implementation took before choosing the patch target.
- Mock `Ollama` LLM to return a fixed string response for any query (same caveat as above — check `orch.rag.mapgen`).
- Use the existing testcontainer-backed **sync** session fixture from `tests/conftest.py`. The project has no async session; use `Session`, not `AsyncSession`.
- Create a `Project` row in the DB — required fields are `id`, `display_name`, `repo_root` (**not** `name` / `repo_path`). Set `repo_root` to the temp repo dir.
- Create a `CodeIndexJob` row with `status="queued"` (schema provided by F-00045).

**Action**: Call `await CodeIndexer(project_id, config, str(tmp_path / "index")).index(repo_path, job.id)` (note the signature takes `job_id: str`, not a job object or session).

**Assertions**:
- `result.files_indexed == 3`
- `result.chunks_created > 0`
- `result.errors == []`
- LanceDB table `code_{project_id_underscored}` exists and has rows.
- Manifest file exists at `{tmp_path}/index/{project_id}/manifest.json`.
- Manifest contains 3 entries (one per file).

### Test Suite 2: Incremental Reindex (`test_incremental_reindex`)

**Setup**: Same as Suite 1, but after a full index, modify `main.py` content.

**Action**: Call `await indexer.reindex_changed(repo_path, job.id)`.

**Assertions**:
- `result.files_indexed == 1` (only `main.py` changed)
- `result.files_skipped == 2` (`utils.py` and `models.py` unchanged)
- LanceDB table still has rows.
- Manifest SHA for `main.py` is updated; others unchanged.

### Test Suite 3: Failed Ollama (`test_failed_ollama_marks_job_failed`)

**Setup**:
- Create the same 3-file Python repo.
- Mock `OllamaEmbedding` to raise `httpx.ConnectError("Connection refused")` on any call.
- Create a `CodeIndexJob` with `status="queued"`.

**Action**: Run `CodeIndexJobRunner(job_id, project_id, repo_path, config, str(tmp_path / "index"), reindex=False).run()` inside `asyncio.run()` or use `pytest-anyio`/`pytest-asyncio`.

**Assertions**:
- After the runner completes, reload `CodeIndexJob` from DB.
- `job.status == "failed"`
- `job.errors` is not empty (contains the error message).
- No `ProjectDoc` was created.

### Test Suite 4: Duplicate Job Prevention (`test_start_index_job_raises_when_already_running`) — AC5

**Setup**:
- Create a `Project` in the DB via the testcontainer session.
- Create a `CodeIndexJob` row with `status="queued"`.
- Manually insert a stub `CodeIndexJobRunner` (or any sentinel) into `JOB_REGISTRY[project.id]` to simulate an in-flight job.

**Action**: Call `start_index_job(new_job, project, mode="full")`.

**Assertions**:
- `JobAlreadyRunningError` is raised.
- `JOB_REGISTRY[project.id]` still references the original stub (not overwritten).
- The `new_job` row's `status` is unchanged (not flipped to `running`).

**Cleanup**: `JOB_REGISTRY.pop(project.id, None)` in a `finally`.

### Test Suite 5: Progress Queue Delivers Events (`test_runner_emits_progress_then_done`) — AC3

**Setup**:
- Create `Project` + `CodeIndexJob` in the testcontainer session.
- Mock `CodeIndexer.index` (or the effective method) to emit 2 progress events via the runner's `progress_queue` and then return a valid `IndexResult`.
- Mock `MapGenerator.generate_level1` to return a stub `ProjectDoc` without hitting LanceDB/Ollama.

**Action**: Instantiate `CodeIndexJobRunner(...)`, register it via `start_index_job`, then `await runner.run()`. In parallel, drain `runner.progress_queue` into a list until a terminal event is received.

**Assertions**:
- Drained events include at least 2 `phase="indexing"` (or `"mapgen"`) progress events.
- The final event has `phase="done"`.
- After `run()` completes, `JOB_REGISTRY.get(project.id) is None` (finally block ran).
- `CodeIndexJob.status` in DB is `"completed"`.

### Test Suite 6: Regenerate-Map Upsert (`test_regenerate_map_upserts_project_doc`) — AC6

**Setup**:
- Use the existing testcontainer-backed sync session fixture.
- Create a `Project` with `id`, `display_name`, `repo_root = str(tmp_path / "repo")`.
- Pre-seed an existing `ProjectDoc` via `DocService.create_doc(project_id, doc_id="architecture-map", title="Old Title", slug=f"{project_id}-architecture-map", doc_type=DocType.research, tier=DocTier.fully_automated, editorial_category=EditorialCategory.technical, content="stale content", generated_by="code-understanding:level1")`. Capture the composite id (`"{project_id}:architecture-map"`).
- Mock `MapGenerator._build_mermaid` to return a fixed `"graph TD\n  A[App]"` string so no LLM is needed.
- Patch the LanceDB/LlamaIndex query path used inside `generate_level1`: the simplest approach is to monkeypatch `MapGenerator.generate_level1` itself is NOT allowed (that's what we're testing); instead, patch the `query_engine.query` call path so each `QUESTIONS` call returns a deterministic `MagicMock(response="stub answer")`. If the `VectorStoreIndex.from_vector_store` path blocks on LanceDB, patch it to return a stub index whose `.as_query_engine()` yields the mocked engine.

**Action**: `await MapGenerator(config).generate_level1(project_id, config)`.

**Assertions**:
- Query `ProjectDoc` count for this `project_id` with `doc_id="architecture-map"` — count is exactly **1** (not 2).
- The row's `title` equals `f"{project.display_name} — Architecture Map"` (updated, not "Old Title").
- The row's `content` contains `"graph TD"` (updated).
- The row's `version` has been incremented (upsert via `DocService.update_doc` bumps version when content hash changes).
- A new `ProjectDocVersion` row exists for the new version.

**Cleanup**: `tmp_path` handles disk; the session fixture rolls back.

### Test Suite 7: Runner Removes Itself On Failure (`test_runner_cleans_up_on_ollama_error`) — AC4 cross-check

**Setup**:
- Testcontainer-backed sync session.
- Create a `Project` with a valid `repo_root` pointing at a 3-file Python repo on `tmp_path`.
- Patch `orch.rag.indexer.OllamaEmbedding` (or the effective resolution site — match whatever S01 shipped) to raise `httpx.ConnectError("Connection refused")` on first use.
- Create a `CodeIndexJob` with `status="queued"` and register a runner via `start_index_job(job, project, mode="full")`.

**Action**: `await runner.run()` (the runner will fail internally).

**Assertions**:
- After `run()` returns, reload `CodeIndexJob` from DB: `job.status == "failed"`.
- `job.errors` contains `"Connection refused"` (or at minimum is non-empty).
- `job.doc_id` is `None` (no ProjectDoc was created).
- `JOB_REGISTRY.get(project.id) is None` (runner cleaned up in `finally`).
- A terminal `phase="error"` event was emitted on `runner.progress_queue` (drain in a task).
- Query the DB directly: no `ProjectDoc` row with `doc_id="architecture-map"` was created for this project.

**Cleanup**: `JOB_REGISTRY.pop(project.id, None)` defensively in a `finally` even though `run()` should have cleared it.

## Implementation Guidelines

### Mocking Ollama

Use `unittest.mock.patch` or `pytest-mock`'s `mocker.patch` to mock Ollama:

```python
from unittest.mock import patch, MagicMock

# Mock OllamaEmbedding to return fixed vectors
with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed:
    mock_embed.return_value.get_text_embedding.return_value = [0.1] * 384
    mock_embed.return_value.get_text_embedding_batch.return_value = [[0.1] * 384] * n
    ...
```

### Async Tests

If the project uses `pytest-asyncio`, mark async tests with `@pytest.mark.asyncio`.
If it uses `anyio`, use `@pytest.mark.anyio`.
Check `tests/conftest.py` and existing integration tests to determine which is used, then match it.

### Testcontainer Session

Use the same session fixture as existing integration tests. Do NOT create a new testcontainer session — reuse the existing `db_session` or `async_session` fixture from `conftest.py`.

### LanceDB in Tests

LanceDB is file-based. Always pass `str(tmp_path / "index")` as the `index_path` to `CodeIndexer` and `CodeIndexJobRunner`. This ensures test isolation and automatic cleanup.

### Fixture Python Files

Create them directly with `Path.write_text()`:

```python
(tmp_path / "repo" / "main.py").write_text(
    "class App:\n    def run(self):\n        pass\n    def stop(self):\n        pass\n"
)
```

## Test Verification (NON-NEGOTIABLE)

After writing all tests:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/ dashboard/
uv run pytest tests/unit/ -v
uv run pytest tests/integration/test_code_index_pipeline.py -v
```

All must pass. Do NOT report `tests_passed: true` unless all pass with zero failures.

If an integration test requires infrastructure that makes it impractical in CI (e.g., LanceDB has unexpected behavior with mocked embeddings), document the issue in `blockers` and provide a partial implementation that covers as many test cases as possible.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "F-00046",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_code_index_pipeline.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
