# F-00060_S02_Backend_prompt

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S02 — RAG indexing layer
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Same rules as S01. Testcontainers allowed. LanceDB is a local file-backed
index (no Docker container), so no container concerns here.

---

## Input Files

- `ai-dev/active/F-00060/F-00060_Feature_Design.md` — see *Scope*, *AC1*, *AC6*, *Boundary Behavior*, *Notes / LanceDB schema*
- `ai-dev/active/F-00060/reports/F-00060_S01_Database_report.md` — confirms `doc_index_jobs` exists
- `orch/rag/indexer.py` — existing `CodeIndexer` pattern (LanceDB table naming, embedding, chunking)
- `orch/rag/job.py` — existing `CodeIndexJobRunner` + `JOB_REGISTRY` pattern to mirror
- `orch/rag/config.py` — `CodeUnderstandingConfig` (provider, tier defaults, index path, Ollama URL)
- `orch/jobs/aggregator.py` — existing `JobType` enum + `list_jobs` method

## Output Files

- `ai-dev/active/F-00060/reports/F-00060_S02_Backend_report.md` (new)
- `orch/rag/doc_indexer.py` (new — `DocIndexer` class)
- `orch/rag/doc_job.py` (new — `DocIndexJobRunner`, `JOB_REGISTRY_DOC`, `JobAlreadyRunningError` reuse or sibling)
- `orch/jobs/aggregator.py` (modified — `JobType.doc_indexing`, `_fetch_doc_indexing()`)

## Context

This step builds the indexing half of F-00060: pull `functional_doc_content`
from `work_items` (populated by F-00059), chunk + embed + store in a new
LanceDB table, track progress in the `doc_index_jobs` row, and expose the
job to the unified Jobs view.

S03 implements the retrieval half. They are tightly coupled by the LanceDB
schema defined here.

## Requirements

### 1. `DocIndexer` — `orch/rag/doc_indexer.py`

Class with the following shape, mirroring `CodeIndexer`:

```python
class DocIndexer:
    def __init__(
        self,
        project_id: str,
        config: CodeUnderstandingConfig,
        index_path: Path,
        db_session_factory: Callable[[], Session],
    ) -> None: ...

    def index_all(self, progress_queue: asyncio.Queue | None) -> DocIndexResult: ...

    def reindex_changed(
        self,
        watermark: datetime | None,
        progress_queue: asyncio.Queue | None,
    ) -> DocIndexResult: ...
```

Behaviour:

- LanceDB URI: `{index_path}/{project_id}/vectors/` — same root as the code
  index. Table name: `docs_{project_id.replace('-', '_')}`.
- Schema: `work_item_id TEXT`, `work_item_type TEXT`, `work_item_title TEXT`,
  `chunk_index INT`, `text TEXT`, `embedding` vector of dim matching the
  embed model.
- Chunking: `from llama_index.core.node_parser import SentenceSplitter` with
  `chunk_size=512` and `chunk_overlap=64`.
- Embedding: `OllamaEmbedding(model_name=config.resolved_embed_model(), base_url=config.ollama_url)` — same call shape as the code indexer.
- Upsert key: `(work_item_id, chunk_index)`. Re-indexing a changed item
  DELETES all existing rows for that `work_item_id`, then inserts the new
  chunks.
- Watermark: `reindex_changed(watermark)` queries
  `SELECT id, type, title, functional_doc_content, updated_at FROM work_items WHERE project_id = ? AND updated_at > ?`
  (or `IS NOT NULL` when watermark is None). Items with NULL
  `functional_doc_content` are **skipped, not deleted** — the retriever
  gracefully handles their absence.
- Progress: each indexed item emits `{"items_indexed": N, "chunks_created": M}`
  into `progress_queue` so the runner can persist counters.
- Embed-model-change policy: if the stored `embed_model` for the table does
  not match the current `config.resolved_embed_model()`, DROP the table and
  re-embed everything (same policy as `CodeIndexer`).
- Sanitise text: strip NUL characters and normalise whitespace before
  embedding.

Return a `DocIndexResult` dataclass with `items_discovered`, `items_indexed`,
`chunks_created`, `errors: list[dict]`.

### 2. `DocIndexJobRunner` — `orch/rag/doc_job.py`

Mirror `CodeIndexJobRunner` almost line-for-line:

- Constructor: `job_id`, `project_id`, `config`, `index_path`,
  `db_session_factory`.
- `async def run(self)`:
  1. Set status → `running`, `started_at = NOW()`.
  2. Load the previous successful job's `completed_at` as watermark (or
     None if first run).
  3. Call `DocIndexer(...).reindex_changed(watermark, self.progress_queue)`.
  4. Drain progress queue → persist counters to DB (same batch-size pattern
     as the code runner).
  5. On success: status → `completed`, `completed_at = NOW()`.
  6. On exception: status → `failed`, `error_message = str(exc)[:2000]`,
     append the exception to `errors` JSONB.

Job registry: `JOB_REGISTRY_DOC: dict[str, DocIndexJobRunner]` sibling of
the code registry. Raise `JobAlreadyRunningError` (reuse existing exception
class) on second `register()` for the same project_id.

### 3. Jobs aggregator extension

In `orch/jobs/aggregator.py`:

- Add `JobType.doc_indexing = "doc_indexing"` to the `StrEnum`.
- Add `_fetch_doc_indexing(self, session, project_ids) -> list[JobRow]` that
  queries `doc_index_jobs` and returns `JobRow` objects with
  `title = f"Doc index — {job.embed_model or job.index_tier or 'default'}"`,
  `status = job.status`, `started_at`, `finished_at = completed_at`, and
  the raw fields in `raw`.
- In `list_jobs`, include the new type alongside the existing ones.

## Project Conventions

Read `orch/rag/CLAUDE.md`. LlamaIndex `SentenceSplitter` for prose. Ollama
embeddings. LanceDB write via `lancedb.connect(uri).create_table(...)` or
`overwrite_table(...)` — match whatever the code indexer uses. Typed
dataclasses. psycopg v3.

## TDD Requirement

1. **RED**:
   - `tests/integration/test_doc_indexer.py`:
     - Index 3 items with distinct content → 3 work_item_ids in the table,
       chunks match expectation.
     - Update one item's `functional_doc_content` + bump `updated_at` →
       second run removes old chunks for that id and inserts new ones.
     - Skip items with NULL `functional_doc_content` — they are not in the
       table.
     - Embed-model change → table dropped + full re-index.
   - `tests/integration/test_doc_index_job_runner.py`:
     - Runner enqueue + execute → status transitions; counters written.
     - Second `register()` for same project raises `JobAlreadyRunningError`.
   - `tests/integration/test_jobs_aggregator_doc_index.py`:
     - Insert a `doc_index_jobs` row → `list_jobs()` returns it with
       `JobType.doc_indexing`.
2. **GREEN**: implement.
3. **REFACTOR**: verify the `docs_*` table is truly disjoint from `code_*`.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass.
2. `make test-unit` — pass (no regressions).
3. `make lint` and `make typecheck` — pass.

## Subagent Result Contract

Standard JSON with `step: "S02"`, `agent: "backend-impl"`, `work_item: "F-00060"`.
