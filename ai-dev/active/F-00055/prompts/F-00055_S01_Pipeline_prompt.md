# F-00055_S01_Pipeline_prompt

**Work Item**: F-00055 — Work-item-aware code chat: functional behavior Q&A linked to work-item history
**Step**: S01
**Agent**: pipeline-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` — design document (read first)
- `orch/rag/job.py` — code index job runner, `JOB_REGISTRY`, `start_index_job`, progress queue
- `orch/rag/indexer.py` — code chunking, embedding, LanceDB table population for `code_{project_id}`
- `orch/rag/parser.py` — file parsing helpers
- `orch/rag/config.py` — `CodeUnderstandingConfig`, `resolved_embed_model`, `build_code_config_from_project`
- `orch/db/models.py` — `WorkItem` (with `design_doc_content`, `design_doc_search`, `summary`, `type`), `CodeIndexJob`
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S01_Pipeline_report.md`

## Context

Extend the existing code-indexing pipeline so it additionally populates a new LanceDB table `docs_{project_id}` with embeddings of work-item design-doc content. This new table becomes the primary evidence source for the work-item-aware chat pipeline (S03). Must support both full-index (`mode="full"`) and incremental (`mode="incremental"`) runs, mirroring the existing code pass.

## Requirements

### 1. New LanceDB table `docs_{project_id}`

- Use the same hyphen-to-underscore convention as `code_`: e.g. project `iw-ai-core` → table `docs_iw_ai_core`.
- Schema (columns): `work_item_id: str`, `project_id: str`, `work_item_type: str` (feature/incident/change_request), `title: str`, `summary: str | None`, `design_doc_content: str`, `created_at: timestamp`, `completed_at: timestamp | None`, `vector: fixed_size_list<float32>`, `chunk_index: int32`, `text: str`.
- Each work item's design-doc content may be split into multiple chunks — follow the existing `indexer.py` chunking pattern (same chunk-size/overlap as code chunks, or a single-chunk shortcut for docs under the chunk-size threshold; pick whichever matches the existing pattern).
- Use the project's resolved embedding model (`config.resolved_embed_model()` via `OllamaEmbedding`) — same model as the code table.
- Table is created (or recreated, for full mode) by the job runner; incremental mode only re-embeds rows whose source `WorkItem.updated_at > last_indexed_at`.

### 2. Indexer extension (`orch/rag/indexer.py`)

- Add a `index_design_docs(project_id, config, session, mode)` function next to the existing code-indexing entry point.
- Query `WorkItem` for the project where `design_doc_content IS NOT NULL`, ordered by `(created_at ASC, id ASC)`.
- Skip items with `design_doc_content = NULL` (older items pre-skill); include items with `summary IS NOT NULL` but `design_doc_content IS NULL` by emitting a single row with `text = summary` and `chunk_index = 0` so they are retrievable by title-only.
- For each work item, chunk the content and call `OllamaEmbedding.get_text_embedding_batch` (or whichever batch API the existing code-indexer uses — match the pattern precisely).
- Do NOT block on the DB while embedding — follow the existing job's pattern of batching/streaming to the progress queue.

### 3. Job runner extension (`orch/rag/job.py`)

- After the code-indexing pass completes successfully, invoke `index_design_docs(...)` as a follow-on pass within the same `CodeIndexJob`.
- Emit progress queue events for the doc pass matching the existing phase vocabulary: `{"phase": "indexing_docs", "current": N, "total": M, "message": "Embedding design documents"}`.
- On failure of the doc pass, log the error but do NOT fail the overall job (the doc index is best-effort in v1; the code pass is the primary deliverable). Record `CodeIndexJob.errors.append("doc_index: <msg>")` so the dashboard surfaces the partial failure.
- Ensure `mode="mapgen_only"` does NOT touch the docs table (reserved for architecture-map regeneration, not re-embedding).
- The `mode="incremental"` branch should compare `WorkItem.updated_at` against the previous job's `completed_at` and re-embed only updated/new items; use LanceDB `Table.merge_insert(on="work_item_id").when_matched_update_all().when_not_matched_insert_all().execute(chunks)` for the merge. (LanceDB `>=0.30.2` is pinned in `pyproject.toml` and supports `merge_insert`; do NOT implement a delete-then-insert fallback.)

### 4. Logging and progress

- Log the number of work items processed and chunks created at INFO level, consistent with the existing code-indexer logging.
- Update `CodeIndexJob.chunks_created` to include both code chunks and doc chunks (add a separate `doc_chunks_created` int column IF — and only if — the model already supports it without a migration; otherwise put the count in `CodeIndexJob.errors` or a JSON metadata field that already exists; do NOT introduce a new Alembic migration for this step).

### 5. Preserve existing behavior

- The `code_{project_id}` table and its filter-by-`file_path` behavior must be untouched.
- No change to the existing `/api/code/index` endpoint signature or payload — this step extends only the internal pipeline.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for:
- Sync SQLAlchemy 2.0 patterns — `Mapped[]` declarative, `Session` context manager.
- psycopg v3 (`psycopg[binary]`), not psycopg2.
- Testing rules: **NEVER** connect tests to live DB (port 5433); testcontainers only.
- Append-only design: no UPDATE on `step_runs` / `fix_cycles` / `daemon_events`; this pipeline only writes to `CodeIndexJob` (which allows UPDATE for status transitions).

Follow the existing `orch/rag/*.py` code style — matching imports, log formatting, error handling, async where the surrounding code uses async.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: write failing tests in `tests/unit/test_rag_docs_indexer.py` — cover chunking, embedding call, LanceDB row shape, incremental-mode filter, skip-on-null-content, summary-only fallback.
2. **GREEN**: implement minimal indexer extension to pass.
3. **REFACTOR**: deduplicate with the existing code-indexer where possible without changing public behavior.

Do not skip the RED phase.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — must pass with zero failures.
2. `make quality` — ruff + mypy must pass.
3. Smoke-test: run `uv run iw projects list` to confirm the CLI still works; manually invoke the indexer entry point on a seeded in-memory test DB and verify the `docs_{project_id}` table is created and populated.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "pipeline-impl",
  "work_item": "F-00055",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/indexer.py",
    "orch/rag/job.py",
    "tests/unit/test_rag_docs_indexer.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
