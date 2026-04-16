# F-00046 S04 Code Review Report

## Step Reviewed
**S03 (tests-impl)** — Integration tests for F-00046 Code Indexing Pipeline

## Test Results
```
Unit tests:      712 passed, 1 warning
Integration:     3 passed, 4 failed
```

---

## Findings

### CRITICAL #1: Tests bypass testcontainer and connect to live DB (port 5433)

**Severity:** CRITICAL  
**Category:** testing  
**Affected tests:** `test_failed_ollama_marks_job_failed`, `test_runner_emits_progress_then_done`, `test_runner_cleans_up_on_ollama_error`

**Root cause:** `CodeIndexJobRunner.run()` calls `_db_set_status()` via `asyncio.to_thread()`. Inside `_db_set_status`, `SessionLocal()` is imported and instantiated at runtime, connecting to the live platform DB (`localhost:5433/iw_orch`) instead of the testcontainer.

```
psycopg.errors.UndefinedTable: relation "code_index_jobs" does not exist
host=localhost port=5433 database=iw_orch
```

Tests that call `CodeIndexJobRunner.run()` or `start_index_job()` + `runner.run()` directly cannot use the testcontainer's transactional session because the runner spawns its own thread with its own `SessionLocal()` connection.

**Fix required:** Tests must patch `SessionLocal` (at `orch.db.session.SessionLocal`) so the runner's thread uses the test engine's session. See `tests/integration/conftest.py::db_session_factory` which already provides a sessionmaker bound to the test engine.

---

### CRITICAL #2: `test_regenerate_map_upserts_project_doc` fails with `ValueError: Project not found`

**Severity:** CRITICAL  
**Category:** testing  
**File:** `tests/integration/test_code_index_pipeline.py:418`

**Root cause:** The test patches `orch.db.session.SessionLocal` globally, but `MapGenerator.generate_level1()` calls `asyncio.to_thread(do_upsert)`. Inside `do_upsert()`, `SessionLocal` is imported as a local import inside the function. The patch at `orch.db.session.SessionLocal` is applied before the thread is spawned, but the local import inside `do_upsert()` creates a new reference that the patch doesn't intercept.

```
ValueError: Project test-proj-mapgen-upsert not found
```

The `mock_session.get.return_value = project` is set up, but when `session.get(Project, project_id)` is called inside `do_upsert()`, it uses the REAL `SessionLocal` because the patch path doesn't cover the local import inside the nested function.

**Fix required:** The patch target must cover the actual import path used at runtime inside the thread. Consider patching `orch.rag.mapgen.SessionLocal` directly, or restructuring the test to use a context manager that patches at the correct import location.

---

### HIGH #1: `test_incremental_reindex` — manifest keys are absolute paths

**Severity:** HIGH  
**Category:** testing  
**File:** `tests/integration/test_code_index_pipeline.py:179`

```python
assert "main.py" in manifest  # FAILS
# Actual keys: '/tmp/pytest-of-sergiog/.../repo/main.py'
```

**Root cause:** In `orch/rag/indexer.py`:
- Line 145: `rel = str(file_path)` stores **absolute path** as manifest key
- Line 171: `_get_changed_files()` also uses `rel = str(file_path)` (absolute)

But the test expects relative filenames like `"main.py"`.

**Fix required:** Use relative paths in manifest: `rel = str(file_path.relative_to(repo_path))`

---

### HIGH #2: Incomplete LanceDB table verification in `test_full_index_cycle`

**Severity:** HIGH  
**Category:** testing  
**File:** `tests/integration/test_code_index_pipeline.py:96-128`

**Issue:** The test asserts `chunks_created > 0` but never verifies the LanceDB table actually exists and contains the expected rows. The docstring acknowledges a workaround for a bug in S01 (LanceDB.add expects BaseNode not strings), but the test doesn't verify the workaround actually produced valid data.

**Fix required:** After the index call, open the LanceDB table and assert that rows exist with the expected embeddings/chunks.

---

### MEDIUM #1: `test_regenerate_map_upserts_project_doc` — mock session bypasses real DB

**Severity:** MEDIUM_FIXABLE  
**Category:** testing  
**File:** `tests/integration/test_code_index_pipeline.py:341-446`

The test creates `existing_doc` and `existing_version` via `db_session` (testcontainer), then patches `SessionLocal` with a MagicMock. But `MapGenerator` uses the mock, so:
- `upsert_doc` merges into the mock session (in-memory only)
- Nothing is ever committed to the real test DB
- The assertions check `updated_doc.version > 1` but this is the mock object, not the real DB state

**Fix required:** Either (a) verify the mock was called with correct arguments rather than asserting on mock object state, or (b) use `db_session_factory` to create a session that writes to the test DB.

---

### MEDIUM #2: `test_full_index_cycle` — no Ollama embedding mock

**Severity:** MEDIUM_FIXABLE  
**Category:** testing  
**File:** `tests/integration/test_code_index_pipeline.py:96-129`

The test mocks `LanceDBVectorStore.add` but does not mock `OllamaEmbedding`. If `CodeIndexer._embed_and_store()` actually calls `embedding.aget_text_embedding()`, the test would hit a real Ollama instance.

Note: Since the test passes, embedding may not be called due to the LanceDB mock short-circuiting the flow. However, this is fragile — if the implementation changes, the test could fail unexpectedly.

**Fix required:** Add `OllamaEmbedding` mock at `orch.rag.indexer.OllamaEmbedding` or where it's actually instantiated.

---

### MEDIUM #3: `test_incremental_reindex` — no SHA verification for changed file

**Severity:** MEDIUM_FIXABLE  
**Category:** testing  
**File:** `tests/integration/test_code_index_pipeline.py:136-180`

The test asserts `files_indexed == 1` and `files_skipped == 2` but doesn't verify the SHA in the manifest for `main.py` actually changed. The manifest SHA should reflect the NEW content's SHA after reindexing.

**Fix required:** After reindex, compute the SHA of the modified `main.py` and assert `manifest["main.py"]` equals the new SHA.

---

### LOW #1: `test_runner_emits_progress_then_done` — runner registered in JOB_REGISTRY but no cleanup

**Severity:** LOW  
**Category:** testing  
**File:** `tests/integration/test_code_index_pipeline.py:277-333`

`start_index_job()` is called at line 312 which registers the runner in `JOB_REGISTRY`. The runner is awaited via `runner_task`, so cleanup happens. However, if an assertion fails mid-test, `JOB_REGISTRY` could be left dirty. Consider wrapping in `try/finally` or using a fixture.

---

## Summary

| Severity | Count | Must Fix Before Merge |
|----------|-------|----------------------|
| CRITICAL | 2 | YES |
| HIGH | 2 | YES |
| MEDIUM_FIXABLE | 3 | YES (in fix cycle) |
| MEDIUM_SUGGESTION | 0 | - |
| LOW | 1 | No |

**Mandatory fix count: 4** (2 CRITICAL + 2 HIGH)

**Verdict: FAIL** — Integration tests have critical DB isolation issues and HIGH assertion gaps.

---

## Recommendation

Return to `tests-impl` agent (S03) with the 4 mandatory fixes:
1. CRITICAL #1: Patch `SessionLocal` for runner thread so tests use testcontainer DB
2. CRITICAL #2: Fix `SessionLocal` patch path for `MapGenerator.generate_level1()` 
3. HIGH #1: Use relative paths in manifest keys
4. HIGH #2: Verify LanceDB table has rows after `test_full_index_cycle`
