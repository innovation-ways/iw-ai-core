# F-00046 S01 Backend Report

**Step**: S01 — Backend Implementation
**Agent**: backend-impl
**Work Item**: F-00046 — Code Understanding: Indexing Engine + Level 1 Map Generation

## Summary

Implemented the three core backend modules for the RAG indexing pipeline:
- `orch/rag/indexer.py` — `CodeIndexer` class
- `orch/rag/job.py` — `CodeIndexJobRunner` + `JOB_REGISTRY` + `start_index_job()`
- `orch/rag/mapgen.py` — `MapGenerator` class

Also wrote RED-phase unit tests that now pass (GREEN phase complete).

## Files Changed

| File | Change |
|------|--------|
| `orch/rag/indexer.py` | New — `CodeIndexer` with SHA manifest, LanceDB indexing, CodeSplitter |
| `orch/rag/job.py` | New — `CodeIndexJobRunner`, `JOB_REGISTRY`, `start_index_job()`, `JobAlreadyRunningError` |
| `orch/rag/mapgen.py` | New — `MapGenerator` with 8 RAG questions, Mermaid generation |
| `tests/unit/test_code_indexer.py` | New — 10 unit tests (RED→GREEN) |

## Dependencies Added

```
llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama
llama-index-vector-stores-lancedb lancedb tree-sitter tree-sitter-languages pandas
```

## Test Results

```
uv run pytest tests/unit/test_code_indexer.py -v
10 passed in 1.15s
```

All 712 unit tests pass (0 failures).

## Quality Checks

| Check | Result |
|-------|--------|
| `uv run ruff check orch/rag/ tests/unit/test_code_indexer.py` | All checks passed |
| `uv run ruff format --check .` | 171 files already formatted |
| `uv run mypy orch/rag/` | 0 errors |

## Key Implementation Notes

- **Sync-only ORM**: All DB operations wrapped in `asyncio.to_thread()` around sync `SessionLocal()` blocks — no async session factory added.
- **`LanceDBVectorStore`**: Uses `uri=` path constructor; table name `code_{project_id.replace('-', '_')}`.
- **`CodeSplitter`**: `language=` required (not optional); falls back to `SentenceSplitter` on error for non-Python files.
- **Progress callback**: `progress_callback` is a plain sync function invoked via `asyncio.to_thread()` — the `CodeIndexer` methods are async but the callback itself is not.
- **`start_index_job`**: Reads config from `project.config["code_understanding"]` dict, not from global config; registers runner synchronously before returning.
- **Cooperative cancellation**: `request_cancel()` sets `_cancel_requested = True`; runner checks flag at well-defined checkpoints.
- **`_split_file` return type**: Uses `type: ignore[return-value]` on `splitter.split_text()` calls because `SentenceSplitter.split_text()` returns `list[str]` at runtime despite type annotation claiming `list[BaseNode]`.

## Notes

- Ollama is not running locally so `_build_mermaid()` in tests is mocked. Live execution requires Ollama at `localhost:11434`.
- `CodeIndexer` does not take a DB session — it is session-free and only manages LanceDB and the manifest.
- `MapGenerator.generate_level1()` accepts an optional `cancel_check: Callable[[], bool]` callback for cooperative cancellation between RAG questions.
- The `JOB_REGISTRY` is intentionally not locked — the FastAPI event loop serializes access.
