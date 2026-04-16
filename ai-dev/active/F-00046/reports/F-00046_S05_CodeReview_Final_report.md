# F-00046 S05 Code Review Final Report

**Step**: S05 — Final Cross-Agent Review
**Agent**: code-review-final-impl
**Work Item**: F-00046 — Code Understanding: Indexing Engine + Level 1 Map Generation
**Steps Reviewed**: S01 (backend-impl), S03 (tests-impl)

---

## Summary

**Verdict: FAIL**

The implementation has 5 CRITICAL issues that must be fixed before merge, plus 1 HIGH issue. Two integration tests pass; five fail due to DB isolation bugs and the absolute-path manifest issue.

---

## Test Results

| Suite | Passed | Failed | Total |
|-------|--------|--------|-------|
| Unit (`tests/unit/`) | 712 | 0 | 712 |
| Integration (`test_code_index_pipeline.py`) | 2 | 5 | 7 |

**Integration test failures:**
- `test_incremental_reindex` — manifest keys are absolute paths
- `test_failed_ollama_marks_job_failed` — runner hits live DB
- `test_runner_emits_progress_then_done` — runner hits live DB
- `test_regenerate_map_upserts_project_doc` — `SessionLocal` captured at function definition time
- `test_runner_cleans_up_on_ollama_error` — runner hits live DB

---

## Quality Checks

| Check | Result |
|-------|--------|
| `uv run ruff check orch/rag/ tests/integration/test_code_index_pipeline.py` | ✅ All checks passed |
| `uv run mypy orch/rag/` | ✅ 0 errors |
| Unit tests | ✅ 712 passed |

---

## CRITICAL Findings

### CRITICAL #1: Manifest keys are absolute paths

**Severity:** CRITICAL  
**Category:** completeness / integration  
**File:** `orch/rag/indexer.py`  
**Lines:** 70, 79, 88, 97, 145, 171, 211, 217

**Description:** `_get_changed_files()` and `index()` use `rel = str(file_path)` which produces **absolute paths** like `/tmp/pytest-.../repo/main.py`. The manifest should store relative paths for cross-environment portability.

**Impact:** `test_incremental_reindex` fails because `manifest["main.py"]` lookup fails — the key is the full absolute path.

**Fix:**
```python
# In index(), reindex_changed(), and _get_changed_files():
rel = str(file_path.relative_to(repo_path))  # instead of str(file_path)
```

---

### CRITICAL #2: MapGenerator store_path hardcoded (S02 regression)

**Severity:** CRITICAL  
**Category:** architecture  
**File:** `orch/rag/mapgen.py`  
**Line:** 52

**Description:** `MapGenerator.generate_level1()` hardcodes:
```python
store_path = f"~/.iw-ai-core/indexes/{project_id}/vectors"
```
This was flagged as CRITICAL in S02 but **was not fixed**.

**Impact:** If `IW_CORE_INDEX_PATH` is set to a non-default value, `CodeIndexer` writes to the correct path but `MapGenerator` reads from the wrong path, causing map generation to fail or read stale data.

**Fix:** `generate_level1()` must receive `index_path: str` as a parameter (or read from `load_config()`) and construct:
```python
store_path = f"{index_path}/{project_id}/vectors"
```
The caller (`_run_mapgen` in `job.py:132`) must pass `self.index_path`.

---

### CRITICAL #3: Integration tests hit live DB (SessionLocal bound at import time)

**Severity:** CRITICAL  
**Category:** testing / integration  
**File:** `orch/rag/job.py`  
**Lines:** 53, 122, 160–182

**Description:** `CodeIndexJobRunner.run()` calls `self._db_set_status()` via `asyncio.to_thread()`. Inside `_db_set_status`, `SessionLocal()` is called, which is bound to the **live platform DB** (`localhost:5433/iw_orch`) at module import time in `orch/db/session.py`.

**Impact:** 4 integration tests fail with:
```
psycopg.errors.UndefinedTable: relation "code_index_jobs" does not exist
host=localhost port=5433 database=iw_orch
```

**Fix:** Tests must patch `SessionLocal` at `orch.db.session.SessionLocal` **before** the runner's thread is spawned. The patch must ensure the thread uses the test engine's session. Alternatively, refactor `CodeIndexJobRunner` to accept a configurable session factory (dependency injection).

---

### CRITICAL #4: MapGenerator SessionLocal captured at function definition time

**Severity:** CRITICAL  
**Category:** testing  
**File:** `orch/rag/mapgen.py`  
**Lines:** 79–100

**Description:** `do_upsert()` is a nested function that imports `SessionLocal` at **function definition time**:
```python
def do_upsert() -> ProjectDoc:
    with SessionLocal() as session:  # captured at definition time
        ...
```
When `asyncio.to_thread(do_upsert)` is called, the `SessionLocal` reference in `do_upsert.__globals__` is the **original**, not the patched mock.

**Impact:** `test_regenerate_map_upserts_project_doc` fails because the patch at `orch.db.session.SessionLocal` doesn't affect the captured reference inside `do_upsert`.

**Fix:** Either (a) pass `SessionLocal` as a parameter to `generate_level1()`, or (b) patch at the correct import path `orch.rag.mapgen.SessionLocal` (but this requires patching before import), or (c) restructure `do_upsert` to not capture `SessionLocal`.

---

### CRITICAL #5: Missing API exports from `orch/rag/__init__.py`

**Severity:** CRITICAL  
**Category:** completeness / architecture  
**File:** `orch/rag/__init__.py`

**Description:** The package `__init__.py` only contains a docstring. The public API is not exported:
```python
"""orch.rag — Code Understanding: indexing, retrieval, and generation support."""
```

The design specifies F-00047 imports should use `from orch.rag import start_index_job, JOB_REGISTRY, CodeIndexJobRunner, JobAlreadyRunningError`. Currently these are only importable from `orch.rag.job`.

**Impact:** F-00047 must import from `orch.rag.job` directly. This is a minor API ergonomics issue but violates the stated design contract.

**Fix:** Add to `orch/rag/__init__.py`:
```python
from orch.rag.job import (
    JOB_REGISTRY,
    CodeIndexJobRunner,
    JobAlreadyRunningError,
    start_index_job,
)

__all__ = ["JOB_REGISTRY", "CodeIndexJobRunner", "JobAlreadyRunningError", "start_index_job"]
```

---

## HIGH Findings

### HIGH #1: `test_full_index_cycle` incomplete LanceDB verification

**Severity:** HIGH  
**Category:** testing  
**File:** `tests/integration/test_code_index_pipeline.py`  
**Lines:** 96–128

**Description:** The test asserts `chunks_created > 0` but never opens the LanceDB table to verify rows actually exist. The mock `LanceDBVectorStore.add` short-circuits the real storage path, so the test doesn't verify actual data persistence.

**Fix:** After the index call, open the LanceDB table and assert that rows exist with the expected chunk content.

---

## Design Document Compliance

### ✅ Implemented correctly:
- `CodeIndexer` with all methods (`index`, `reindex_changed`, `_get_manifest_path`, `_load_manifest`, `_save_manifest`, `_compute_sha`, `_get_changed_files`)
- `CodeIndexJobRunner` with `run()`, `progress_queue`, `request_cancel()`, cooperative cancellation
- `MapGenerator` with all 8 `QUESTIONS`, `_build_mermaid`, `_assemble_markdown`
- `IndexResult` dataclass
- `start_index_job(job, project, *, mode)` with correct signature and mode mapping
- `JOB_REGISTRY` at module level in `job.py`
- `JobAlreadyRunningError` defined and raised correctly
- Runner registers synchronously before returning (line 220)
- Runner removes itself from registry in `finally` block (line 124)
- All 3 mode values handled (`"full"`, `"incremental"`, `"mapgen_only"`)
- Project field uses `repo_root` and `display_name` (not `name`/`repo_path`)
- All DB operations wrapped in `asyncio.to_thread()`
- No HTTP/FastAPI/router code in F-00046 scope ✅
- Dependencies added to `pyproject.toml` ✅

### ❌ Not implemented / broken:
- MapGenerator `store_path` uses hardcoded path (should use configurable `index_path`)
- Manifest keys are absolute paths (should be relative)
- `orch/rag/__init__.py` doesn't export public API

---

## Mandatory Fix Count

| Severity | Count |
|----------|-------|
| CRITICAL | 5 |
| HIGH | 1 |
| **Total** | **6** |

---

## JSON Findings

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "F-00046",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "completeness",
      "file": "orch/rag/indexer.py",
      "line": 70,
      "description": "Manifest keys are absolute paths (str(file_path)) instead of relative (file_path.relative_to(repo_path)). Causes test_incremental_reindex to fail.",
      "suggestion": "Use rel = str(file_path.relative_to(repo_path)) in index(), reindex_changed(), and _get_changed_files().",
      "cross_cutting": false
    },
    {
      "severity": "CRITICAL",
      "category": "architecture",
      "file": "orch/rag/mapgen.py",
      "line": 52,
      "description": "MapGenerator.generate_level1() hardcodes store_path to '~/.iw-ai-core/indexes/{project_id}/vectors' instead of using configurable index_path. This was flagged CRITICAL in S02 but NOT fixed. Will cause mapgen to read wrong LanceDB store if IW_CORE_INDEX_PATH differs from default.",
      "suggestion": "Add index_path: str parameter to generate_level1(). Construct store_path = f'{index_path}/{project_id}/vectors'. Update job.py:_run_mapgen to pass self.index_path.",
      "cross_cutting": true
    },
    {
      "severity": "CRITICAL",
      "category": "testing",
      "file": "orch/rag/job.py",
      "line": 160,
      "description": "CodeIndexJobRunner._db_set_status uses SessionLocal() bound to live DB at import time. Runner calls _db_set_status via asyncio.to_thread() in a separate thread, which connects to localhost:5433/iw_orch instead of testcontainer. 4 integration tests fail with 'relation code_index_jobs does not exist'.",
      "suggestion": "Tests must patch SessionLocal at orch.db.session.SessionLocal before runner thread is spawned, or refactor runner to accept a configurable session factory.",
      "cross_cutting": true
    },
    {
      "severity": "CRITICAL",
      "category": "testing",
      "file": "orch/rag/mapgen.py",
      "line": 79,
      "description": "do_upsert() nested function captures SessionLocal import at function definition time. Patching orch.db.session.SessionLocal does not affect the captured reference inside do_upsert.__globals__. test_regenerate_map_upserts_project_doc fails with 'Project not found'.",
      "suggestion": "Pass SessionLocal as a parameter to generate_level1(), or restructure do_upsert to not capture SessionLocal at definition time.",
      "cross_cutting": false
    },
    {
      "severity": "CRITICAL",
      "category": "completeness",
      "file": "orch/rag/__init__.py",
      "line": 1,
      "description": "orch/rag/__init__.py only has a docstring and does not export the public API (start_index_job, JOB_REGISTRY, CodeIndexJobRunner, JobAlreadyRunningError). F-00047 must import from orch.rag.job directly, violating the design contract.",
      "suggestion": "Add exports to __init__.py: from orch.rag.job import (JOB_REGISTRY, CodeIndexJobRunner, JobAlreadyRunningError, start_index_job).",
      "cross_cutting": true
    },
    {
      "severity": "HIGH",
      "category": "testing",
      "file": "tests/integration/test_code_index_pipeline.py",
      "line": 96,
      "description": "test_full_index_cycle asserts chunks_created > 0 but never verifies LanceDB table actually has rows. The mock LanceDBVectorStore.add short-circuits real storage.",
      "suggestion": "Open LanceDB table after index call and assert rows exist with expected content.",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 6,
  "tests_passed": false,
  "test_summary": "712 unit passed, 2 integration passed, 5 failed",
  "missing_requirements": [
    "MapGenerator must use configurable index_path, not hardcoded path",
    "Manifest keys must be relative paths, not absolute",
    "Integration tests must properly isolate SessionLocal for runner threads",
    "MapGenerator SessionLocal capture must be fixed for test mocking",
    "orch/rag/__init__.py must export public API"
  ],
  "notes": "S02 CRITICAL bug (hardcoded MapGenerator path) was NOT fixed — regression from S02. S04 identified the SessionLocal test isolation issue but no fix was applied. The implementation is architecturally sound (correct method signatures, proper asyncio patterns, correct mode mapping, cooperative cancellation, finally-block cleanup) but has critical test infrastructure and path-handling bugs."
}
```

---

## Recommendation

Return to `backend-impl` and `tests-impl` for fix cycle. The 6 mandatory fixes are:

**Backend (S01 fix cycle):**
1. Fix manifest keys to use relative paths (`file_path.relative_to(repo_path)`)
2. Fix MapGenerator to accept and use `index_path` parameter (S02 regression)

**Tests (S03 fix cycle):**
3. Fix SessionLocal patching for runner thread DB calls
4. Fix MapGenerator SessionLocal capture issue  
5. Add LanceDB table verification in `test_full_index_cycle`
6. Export public API from `orch/rag/__init__.py`