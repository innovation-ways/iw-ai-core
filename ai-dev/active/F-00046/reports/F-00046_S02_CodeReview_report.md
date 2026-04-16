# F-00046 S02 Code Review Report

**Step**: S02 — Code Review of S01 (backend-impl)
**Agent**: code-review-impl
**Work Item**: F-00046 — Code Understanding: Indexing Engine + Level 1 Map Generation

## Summary

The S01 implementation is well-structured and passes all quality checks, but contains one **CRITICAL** bug in `MapGenerator`: the LanceDB store path is hardcoded to `~/.iw-ai-core/indexes/{project_id}/vectors` instead of using the configurable `index_path` that `CodeIndexer` and `CodeIndexJobRunner` receive via `CodeUnderstandingConfig` or `orch.config.load_config()`. This means if a user changes `IW_CORE_INDEX_PATH` in their environment, `CodeIndexer` will use the correct path but `MapGenerator` will use the wrong one, causing map generation to fail or read stale data.

## Quality Check Results

| Check | Result |
|-------|--------|
| `uv run ruff check orch/rag/ tests/unit/test_code_indexer.py` | All checks passed |
| `uv run ruff format --check .` | 171 files already formatted |
| `uv run mypy orch/` | 0 errors |
| `uv run pytest tests/unit/test_code_indexer.py -v` | 10 passed in 1.15s |

## Architecture Compliance

### ✅ Correct

- `CodeIndexer.__init__` signature matches design (project_id, config, index_path)
- `CodeIndexer.index()` and `reindex_changed()` accept `progress_callback: Callable[[dict], None] | None`
- `CodeIndexJobRunner.__init__` accepts `mapgen_only: bool = False`
- `JOB_REGISTRY` is a module-level `dict[str, CodeIndexJobRunner]` in `orch/rag/job.py`
- `start_index_job(job, project, *, mode)` raises `JobAlreadyRunningError` when `JOB_REGISTRY[project.id]` is already populated
- `JobAlreadyRunningError` is defined in `orch/rag/job.py` and exported
- `CodeIndexJobRunner.__init__` accepts `reindex: bool = False`
- `CodeIndexJobRunner.run()` registers in `JOB_REGISTRY` synchronously before returning (via `start_index_job`)
- `CodeIndexJobRunner.run()` removes itself from `JOB_REGISTRY` in `finally` block
- `CodeIndexJobRunner` catches ALL exceptions (line 114: `except Exception as e`)
- `str(e)` stored in `errors` JSONB field (line 122)
- `phase="error"` event emitted on exception (line 115-121)
- Progress events emitted during indexing loop (lines 134-144)
- `phase="mapgen"` event emitted before mapgen (line 98-106)
- `phase="done"` event emitted on success (line 110)
- `CodeSplitter` used with `chunk_lines=40, chunk_lines_overlap=5`
- `language="python"` for `.py` files
- `language="cpp"` for `.cpp`/`.hpp`/`.h` files
- `try/except` fallback to character-based splitting when tree-sitter fails on C++ (lines 256-262)
- Hidden directories (`.git`, `__pycache__`, `.venv`, `node_modules`) excluded from file discovery
- File extensions: `.py`, `.cpp`, `.hpp`, `.h`
- `LanceDBVectorStore` table name follows pattern `f"code_{project_id.replace('-', '_')}"`
- `MapGenerator` uses all 8 `QUESTIONS` from the design document
- `MapGenerator._assemble_markdown()` produces 8 sections plus Mermaid diagram
- `ProjectDoc` created with `doc_type=DocType.research`, `tier=DocTier.fully_automated`, `editorial_category=EditorialCategory.technical`
- `generated_by = "code-understanding:level1"` set on ProjectDoc
- No new files under `dashboard/routers/` — scope boundary respected
- All DB operations in `MapGenerator` wrapped in `asyncio.to_thread()`
- All DB operations in `CodeIndexJobRunner` wrapped in `asyncio.to_thread()`
- Type annotations on all public methods
- `_build_mermaid()` has fallback to minimal valid diagram if parsing fails (line 118)
- Imports organized correctly (stdlib, third-party, local)
- No hardcoded credentials or API keys

### ❌ CRITICAL Bug

**File**: `orch/rag/mapgen.py:52`

```python
store_path = f"~/.iw-ai-core/indexes/{project_id}/vectors"
```

The `store_path` is **hardcoded** as `~/.iw-ai-core/indexes/{project_id}/vectors` instead of being constructed from a configurable `index_path`.

In contrast:
- `CodeIndexer` receives `index_path: str` in its constructor and correctly uses `Path(self.index_path) / self.project_id / "vectors"` (lines 124, 174)
- `CodeIndexJobRunner` calls `load_config().index_path` to get the correct path (job.py:208)

If a user sets `IW_CORE_INDEX_PATH=/custom/path`, `CodeIndexer` will write to `/custom/path/{project_id}/vectors/` but `MapGenerator` will look in `~/.iw-ai-core/indexes/{project_id}/vectors/`, causing map generation to fail or read the wrong index.

**Fix**: `MapGenerator.generate_level1()` must receive `index_path: str` as a parameter (or read it from `load_config()`) and construct `store_path = f"{index_path}/{project_id}/vectors"`. The caller (`_run_mapgen`) must pass `self.index_path` when instantiating or calling `MapGenerator`.

Similarly on line 43 in `mapgen.py`, the manifest path is not used by MapGenerator (MapGenerator only reads LanceDB vectors, not the manifest), but the store_path bug affects the vector store reads.

### Design Note

The `_run_mapgen` method in `job.py:126-149` calls `MapGenerator().generate_level1(self.project_id, self.config)` without passing `index_path`. The fix requires:
1. `MapGenerator.generate_level1` to accept an `index_path` parameter
2. `CodeIndexJobRunner._run_mapgen` to pass `self.index_path` to `MapGenerator`

## Testing Assessment

- **10 unit tests present** in `tests/unit/test_code_indexer.py` ✅
- Test names clearly describe what they verify ✅
- Tests are true unit tests (no DB, no network, no file system beyond `tmp_path`) ✅
- `test_manifest_roundtrip` uses `tmp_path` for isolation ✅
- `test_build_mermaid_contains_graph_td` mocks the Ollama LLM call ✅
- Tests cover: SHA consistency, SHA differs, manifest roundtrip, manifest missing, get_changed_files (all/none/partial), mermaid contains graph TD, assemble_markdown sections, IndexResult dataclass ✅

**Missing test coverage** (non-blocking for S02, can be addressed in S03):
- `start_index_job` raises `JobAlreadyRunningError` when project already in registry
- Cooperative cancellation end-to-end

## Findings

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00046",
  "step_reviewed": "S01",
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "architecture",
      "file": "orch/rag/mapgen.py",
      "line": 52,
      "description": "store_path is hardcoded to '~/.iw-ai-core/indexes/{project_id}/vectors' instead of using the configurable index_path. This will cause MapGenerator to read from the wrong LanceDB store if IW_CORE_INDEX_PATH differs from the default.",
      "suggestion": "Add index_path: str parameter to MapGenerator.generate_level1(). Construct store_path = f\"{index_path}/{project_id}/vectors\". Update CodeIndexJobRunner._run_mapgen() to pass self.index_path to MapGenerator().generate_level1(). Alternatively read from load_config().index_path inside generate_level1()."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "10 passed, 0 failed",
  "notes": "The hardcoded path in MapGenerator is the only blocker. All other architecture, quality, and testing aspects are correct. The fix is straightforward: accept index_path as a parameter or read from orch.config."
}
```