# F-00055 S01 Pipeline Report

**Step**: S01 — Design-Doc Embedding Indexer
**Agent**: pipeline-impl
**Work Item**: F-00055 — Work-Item-Aware Code Chat
**Completion Status**: complete

---

## What Was Done

Extended `orch/rag/indexer.py` and `orch/rag/job.py` to populate a new LanceDB table `docs_{project_id}` with work-item design-doc embeddings, executed as a follow-on pass after the existing code-indexing pass within each `CodeIndexJob`.

### New Module (`orch/rag/indexer.py`)

- **`DocIndexResult`** dataclass (lines 34–38): carries `work_items_indexed`, `chunks_created`, and `errors` from the doc pass.
- **`index_design_docs()`** async function (lines 331–520): the design-doc indexing entry point with full handling of `full`, `incremental`, and `mapgen_only` modes.

Schema for `docs_{project_id}` (using pyarrow, matching LanceDB `>=0.30.2`):
- `work_item_id`, `project_id`, `work_item_type`, `title`, `summary`, `design_doc_content`, `created_at` (int64), `completed_at` (int64), `chunk_index` (int32), `text`, `vector` (list<float32>).

Key behaviors:
- **Full mode**: drops/recreates `docs_{project_id}` and re-embeds all items with `design_doc_content IS NOT NULL` OR `summary IS NOT NULL` (the latter gets a single-chunk row with `text=summary`).
- **Incremental mode**: queries `CodeIndexJob.completed_at` to filter `WorkItem.updated_at > last_completed_at`; uses `LanceDB.merge_insert(on="work_item_id").when_matched_update_all().when_not_matched_insert_all()` for the upsert — no delete-then-reinsert.
- **mapgen_only mode**: early return, does not touch the docs table.
- Null `design_doc_content` with no `summary`: item is skipped entirely (no row emitted).
- Progress callback events emitted with `phase: "indexing_docs"` at chunk boundaries.
- Embedding uses `OllamaEmbedding` with the project's resolved embed model (from `config.resolved_embed_model()`).
- Table name follows hyphen-to-underscore convention (`iw-ai-core` → `docs_iw_ai_core`).

### Job Runner Extension (`orch/rag/job.py`)

- **`_run_docs_index_pass()`** async method (lines 218–268): runs `index_design_docs` after the code pass completes successfully, using `asyncio.to_thread()` to avoid blocking the event loop while the sync SQLAlchemy session + `asyncio.run()` pattern runs the async indexer.
- **`_append_doc_error()`** async method (lines 270–284): appends `doc_index: <error>` to `CodeIndexJob.errors` when the doc pass fails (best-effort — does not fail the overall job).
- Doc-pass errors are surfaced in the progress queue and persisted to `CodeIndexJob.errors`.
- `mapgen_only` path does NOT invoke `_run_docs_index_pass()`.

### Tests (`tests/unit/test_rag_docs_indexer.py`)

13 test cases covering: function importability, chunking, single-chunk fallback, null-content skip, summary-only fallback, incremental filter, merge_insert usage, mapgen_only guard, DocIndexResult dataclass, table-name convention, progress events, embedding model resolution. All 13 pass.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/rag/indexer.py` | Added `DocIndexResult` dataclass and `index_design_docs()` async function |
| `orch/rag/job.py` | Added `_run_docs_index_pass()` and `_append_doc_error()` to `CodeIndexJobRunner`; call added after code pass in `run()` |
| `tests/unit/test_rag_docs_indexer.py` | New test file with 13 test cases (RED→GREEN verified) |

---

## Test Results

```
======================= 878 passed, 6 warnings in 6.74s ========================
```

All unit tests pass. Quality checks (`make quality`) pass with zero errors.

---

## Observations

- The `asyncio.run()` inside a `asyncio.to_thread()` thread is necessary because `index_design_docs` is async but SQLAlchemy is sync; this is the same pattern already used by `_run_mapgen` in the original code.
- LanceDB's Python API (`0.30.2`) requires `pyarrow.Schema` for table creation, not a dict of type strings. The schema is built using `pa.schema([...])` with `pa.list_(pa.float32())` for the vector column.
- `CodeIndexJob.errors` (JSONB array) is used as the existing column to record doc-pass partial failures — no new column or migration introduced.
- The `mode="mapgen_only"` guard in `index_design_docs` mirrors the early-return in the job runner; both are in place to satisfy the requirement that mapgen regen must not trigger re-embedding.