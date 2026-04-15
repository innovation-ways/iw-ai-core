# F-00046: Code Understanding: Indexing Engine + Level 1 Map Generation

**Type**: Feature
**Priority**: Critical
**Created**: 2026-04-15
**Status**: Draft

---

## Description

Implements the core RAG indexing pipeline as a **Python-only library** (no HTTP layer) using LlamaIndex + LanceDB + tree-sitter. Runs as an asyncio background job tracked in `CodeIndexJob`. On completion, generates a Level 1 architecture map (narrative + Mermaid diagram) via RAG queries to Ollama and stores it as a `ProjectDoc`. Exposes `CodeIndexJobRunner`, `JOB_REGISTRY`, and related async helpers via `orch/rag/` so that the dashboard HTTP layer (F-00047) can consume them.

**Scope split (Option C)**: F-00046 owns the Python API surface only. All HTTP endpoints, SSE streaming, and dashboard router wiring are F-00047's responsibility. F-00046 and F-00047 must ship together — neither is useful on its own.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

Key facts:
- `orch/rag/` package was created in F-00045 (contains `config.py` and `__init__.py`).
- `CodeIndexJob` ORM model was created in F-00045 and lives in `orch/db/models.py`.
- `ProjectDoc` ORM model already exists in `orch/db/models.py`.
- `DocService` in `orch/doc_service.py` handles `ProjectDoc` CRUD.
- Dashboard routes live in `dashboard/routers/`; they are thin — business logic stays in `orch/`.
- Tests use testcontainers (NEVER port 5433).
- SQLAlchemy 2.0 **sync** ORM (`Mapped[]` declarative style) is used throughout `orch/` and `dashboard/`. There is NO async session factory in this codebase. `dashboard/dependencies.py::get_db()` yields a sync `sqlalchemy.orm.Session`.
- `Project` ORM fields: `id`, `display_name`, `repo_root` (**not** `name` / `repo_path`). Always use `project.repo_root` and `project.display_name`.
- `DocService.create_doc()` / `upsert_doc()` take enum values: `doc_type=DocType.research`, `tier=DocTier.fully_automated`, `editorial_category=EditorialCategory.technical`. Pass `slug=f"{project_id}-architecture-map"` explicitly.
- Because the codebase is sync-only, `CodeIndexJobRunner.run()` runs in an asyncio task but all DB work must be performed via `asyncio.to_thread(...)` wrapping sync `SessionLocal()` blocks.

## Scope

### In Scope

- `orch/rag/indexer.py` — `CodeIndexer` class: walks repo, splits code with LlamaIndex `CodeSplitter`, stores embeddings in LanceDB, tracks per-file SHA256 in a manifest for incremental re-indexing.
- `orch/rag/job.py` — `CodeIndexJobRunner` class: asyncio background job that orchestrates indexing → map generation → DB status updates; global `JOB_REGISTRY`; `start_index_job(job, project, *, mode)` helper that F-00047's route handlers will call.
- `orch/rag/mapgen.py` — `MapGenerator` class: RAG-queries LanceDB index with 8 structured questions, assembles Level 1 markdown + Mermaid diagram, stores as `ProjectDoc`.
- Unit tests for SHA manifest logic, config resolution, and Mermaid generation.
- Integration tests: full index cycle on a small fixture Python repo using testcontainers, invoking `CodeIndexJobRunner` / `start_index_job` directly (no HTTP client).

### Out of Scope

- **HTTP endpoints, SSE streaming, and `dashboard/routers/code*.py` — owned by F-00047.**
- Level 2 / Level 3 map generation (F-00048, F-00049).
- Dashboard UI templates for code understanding — owned by F-00047.
- Authentication/authorization.
- Support for languages other than Python (C++ is best-effort only).
- Alembic migrations — `CodeIndexJob` table already created in F-00045.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `orch/rag/indexer.py`, `orch/rag/job.py`, `orch/rag/mapgen.py` | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | tests-impl | Unit + integration tests for the indexing pipeline (Python API) | — |
| S04 | code-review-impl | Review S03 output | — |
| S05 | code-review-final-impl | Global cross-agent review | — |
| S06 | qv-gate | lint | — |
| S07 | qv-gate | format | — |
| S08 | qv-gate | typecheck | — |
| S09 | qv-gate | unit-tests | — |
| S10 | qv-gate | integration-tests | — |

### Database Changes

- **New tables**: None (CodeIndexJob created in F-00045)
- **Modified tables**: None
- **Migration notes**: No migration required. `CodeIndexJob` table is already created.

### API Changes

- **New endpoints**: None. HTTP/SSE endpoints are F-00047's scope. F-00046 only exposes Python entry points:
  - `orch.rag.job.JOB_REGISTRY` — `dict[str, CodeIndexJobRunner]`
  - `orch.rag.job.CodeIndexJobRunner(job_id, project_id, repo_path, config, index_path, *, reindex: bool = False, mapgen_only: bool = False)`
  - `orch.rag.job.start_index_job(job, project, *, mode: Literal["full", "incremental", "mapgen_only"]) -> CodeIndexJobRunner` — synchronously registers the runner in `JOB_REGISTRY[project.id]` and returns it. The caller (F-00047 route handler) is responsible for scheduling `runner.run()` via FastAPI `BackgroundTasks`.
- **Modified endpoints**: None

### Frontend Changes

- **New components**: None (UI templates deferred to a later feature)
- **Modified components**: None

## Architecture Details

### New Python Dependencies

Add via `uv add`:
```
llama-index-core
llama-index-llms-ollama
llama-index-embeddings-ollama
llama-index-vector-stores-lancedb
lancedb
tree-sitter
tree-sitter-languages
```

### orch/rag/indexer.py — CodeIndexer

```python
class CodeIndexer:
    """
    Indexes a codebase into LanceDB using LlamaIndex CodeSplitter + Ollama embeddings.
    Tracks per-file SHA256 in a manifest.json for incremental re-indexing.
    """
    def __init__(self, project_id: str, config: CodeUnderstandingConfig, index_path: str): ...
    async def index(self, repo_path: str, job_id: str, progress_callback: Callable[[dict], None] | None = None) -> IndexResult: ...
    async def reindex_changed(self, repo_path: str, job_id: str, progress_callback: Callable[[dict], None] | None = None) -> IndexResult: ...
    def _get_manifest_path(self) -> Path: ...
    def _load_manifest(self) -> dict[str, str]: ...   # {file_path: sha256}
    def _save_manifest(self, manifest: dict[str, str]) -> None: ...
    def _compute_sha(self, file_path: Path) -> str: ...
    def _get_changed_files(self, repo_path: str, manifest: dict) -> list[Path]: ...
```

Key details:
- LanceDB store path: `{IW_CORE_INDEX_PATH}/{project_id}/vectors/`
- Manifest path: `{IW_CORE_INDEX_PATH}/{project_id}/manifest.json`
- LanceDB table name: `f"code_{project_id.replace('-', '_')}"`
- Chunking: `LlamaIndex CodeSplitter` with `chunk_lines=40, chunk_lines_overlap=5`
- Python fully supported; C++ best-effort (set `language="cpp"`, fall back to character-based if parsing fails)
- Embed model: from `CodeUnderstandingConfig.resolved_embed_model()` via `OllamaEmbedding`
- Progress events emitted via `asyncio.Queue` during indexing loop

`IndexResult` dataclass:
```python
@dataclass
class IndexResult:
    files_indexed: int
    chunks_created: int
    files_skipped: int  # unchanged files in incremental mode
    errors: list[str]
```

### orch/rag/job.py — CodeIndexJobRunner + JOB_REGISTRY

```python
JOB_REGISTRY: dict[str, CodeIndexJobRunner] = {}

class CodeIndexJobRunner:
    """
    Asyncio background job that:
    1. Updates CodeIndexJob status to 'running'
    2. Calls CodeIndexer.index() or .reindex_changed()
    3. On success: calls MapGenerator.generate_level1()
    4. Updates CodeIndexJob to 'completed' with doc_id, stats
    5. On failure: updates CodeIndexJob to 'failed' with errors
    Emits progress events via asyncio.Queue for SSE consumers.
    """
    def __init__(self, job_id: str, project_id: str, repo_path: str, config: CodeUnderstandingConfig): ...
    async def run(self) -> None: ...

    @property
    def progress_queue(self) -> asyncio.Queue: ...

    def request_cancel(self) -> None:
        """Set a cooperative cancel flag. Non-blocking and safe to call from any thread
        or coroutine. The runner observes the flag at its next checkpoint (between files
        during indexing, between questions during map generation, and after each
        sub-phase transition) and exits cleanly — see the cancel lifecycle below."""
```

Progress event JSON structure emitted to the queue:
```json
{"event": "progress", "files_indexed": 5, "files_total": 42, "chunks_created": 180, "phase": "indexing|mapgen|done|error"}
```

Job lifecycle:
1. Set `JOB_REGISTRY[project_id] = self` on start.
2. Update `CodeIndexJob.status = "running"` in DB.
3. Call `CodeIndexer.index()` or `.reindex_changed()`, emitting progress events.
4. On success, call `MapGenerator.generate_level1()`, emitting `phase="mapgen"`.
5. Update `CodeIndexJob.status = "completed"`, store `doc_id`, `files_indexed`, `chunks_created`.
6. Emit `phase="done"` event.
7. Remove `JOB_REGISTRY[project_id]`.
8. On any exception: update `CodeIndexJob.status = "failed"`, store error message in `errors` JSONB field, emit `phase="error"`, remove from registry.

### Cancellation lifecycle

`CodeIndexJobRunner.request_cancel()` sets an internal `_cancel_requested: bool` flag (or `asyncio.Event`). It does NOT cancel the asyncio task directly — cooperative cancel avoids leaving LanceDB or the DB in an inconsistent half-updated state.

The runner checks the flag at well-defined checkpoints:
1. Between files during the indexing loop (after each file's chunks are embedded and written).
2. Between the 8 map-generation RAG questions in `MapGenerator.generate_level1()`.
3. After each sub-phase transition (`indexing → mapgen → done`).

When the flag is observed as set, the runner:
1. Stops processing further work.
2. Updates `CodeIndexJob.status = "cancelled"` (new terminal status — F-00045 must include `'cancelled'` in the `code_index_job_status` ENUM).
3. Stores a short `errors` entry like `["cancelled by user"]` for audit.
4. Emits a terminal progress event `{"event": "progress", "phase": "cancelled", ...}` — consumers (the SSE stream in F-00047) translate this into `{"event": "done", "status": "cancelled", "job_id": ...}`.
5. Removes itself from `JOB_REGISTRY[project_id]` in the same `finally` block that handles success/failure — there is exactly one cleanup site.

The partial LanceDB state written before cancel is NOT rolled back. The next `mode="full"` run re-embeds from scratch; the next `mode="incremental"` run picks up from the manifest (files already embedded before cancel are skipped, files not yet embedded will be re-processed). Document this explicitly in `orch/rag/job.py`.

### orch/rag/mapgen.py — MapGenerator

```python
class MapGenerator:
    QUESTIONS = [
        ("purpose", "What is the overall purpose and main function of this system?"),
        ("components", "List the main components, services, or modules with a one-sentence description of each."),
        ("entry_points", "What are the main entry points of the application?"),
        ("databases", "What databases or data stores are used and what data do they store?"),
        ("external_services", "What external services, APIs, or integrations does this system use?"),
        ("background_jobs", "What background jobs, workers, or async tasks exist?"),
        ("architecture_style", "What architectural pattern is used (e.g., microservices, monolith, event-driven)?"),
        ("key_patterns", "What are the most important design patterns or technical patterns used?"),
    ]

    async def generate_level1(
        self, project_id: str, config: CodeUnderstandingConfig
    ) -> ProjectDoc: ...
    # generate_level1 opens its own sync `SessionLocal()` inside `asyncio.to_thread(...)`
    # for every DB call — it does NOT receive a session from the caller.

    def _build_mermaid(self, components_answer: str) -> str: ...
    def _assemble_markdown(self, answers: dict[str, str], mermaid: str) -> str: ...
```

`ProjectDoc` fields for the generated document (passed to `DocService.upsert_doc`):
- `doc_id = "architecture-map"` (composite id becomes `{project_id}:architecture-map`)
- `doc_type = DocType.research` (enum, not string)
- `tier = DocTier.fully_automated` (enum)
- `editorial_category = EditorialCategory.technical` (enum)
- `title = f"{project.display_name} — Architecture Map"` (field is `display_name`, not `name`)
- `slug = f"{project_id}-architecture-map"` (pass explicitly — DocService falls back to `_slugify(title)` otherwise)
- `content` = assembled markdown from `_assemble_markdown()`
- `generated_by = "code-understanding:level1"`

Use `DocService.upsert_doc()` (from `orch/doc_service.py`) to persist the `ProjectDoc`. `upsert_doc` returns `(doc, created: bool)`. `DocService` takes a sync `Session`, so call it inside `asyncio.to_thread(...)`.

### orch/rag/job.py — `start_index_job` helper (consumed by F-00047)

```python
def start_index_job(
    job: CodeIndexJob,
    project: Project,
    *,
    mode: Literal["full", "incremental", "mapgen_only"],
) -> CodeIndexJobRunner:
    """
    Synchronously instantiate a CodeIndexJobRunner for the given job row,
    register it in JOB_REGISTRY[project.id], and return it. The caller is
    responsible for scheduling runner.run() via FastAPI BackgroundTasks.

    Raises:
        JobAlreadyRunningError: if JOB_REGISTRY already has an entry for project.id.
    """
```

Behavior:
- `mode="full"` → `CodeIndexJobRunner(..., reindex=False, mapgen_only=False)`
- `mode="incremental"` → `reindex=True, mapgen_only=False`
- `mode="mapgen_only"` → `reindex=False, mapgen_only=True`

**Registration ordering (race prevention)**: `start_index_job` MUST register the runner into `JOB_REGISTRY[project.id] = runner` **synchronously** before returning, not inside `runner.run()`. This guarantees:
1. A concurrent call sees the entry and raises `JobAlreadyRunningError` immediately — F-00047 translates this into HTTP 409.
2. A client subscribing to the progress stream right after a trigger call will find the runner and its queue.

`runner.run()` is scheduled by the caller via FastAPI `BackgroundTasks.add_task(runner.run)`. The `finally` block inside `run()` is responsible for `JOB_REGISTRY.pop(project.id, None)`.

**Concurrency note**: Since the dashboard runs a single event loop (Uvicorn default), registry mutation is serialized by the event loop — no explicit lock is required. Document this assumption in `orch/rag/job.py`.

F-00046 raises `JobAlreadyRunningError` (a new exception in `orch/rag/job.py`) — it does not know or care about HTTP. F-00047 catches it and converts to `HTTPException(status_code=409)`.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00046_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00046_S01_Backend_prompt.md` | Prompt | S01 backend implementation |
| `prompts/F-00046_S02_CodeReview_prompt.md` | Prompt | S02 code review of S01 |
| `prompts/F-00046_S03_Tests_prompt.md` | Prompt | S03 integration tests |
| `prompts/F-00046_S04_CodeReview_prompt.md` | Prompt | S04 code review of S03 |
| `prompts/F-00046_S05_CodeReview_Final_prompt.md` | Prompt | S05 final cross-agent review |

## Acceptance Criteria

### AC1: Full Index Cycle

```
Given a Python repository with at least 3 source files and a persisted CodeIndexJob
When start_index_job(job, project, mode="full") is called and the runner runs to completion
Then LanceDB vectors table is populated with code chunks
 And CodeIndexJob.status = "completed"
 And a ProjectDoc with title "{project.display_name} — Architecture Map" is created
 And CodeIndexJob.doc_id references the created ProjectDoc (composite id "{project_id}:architecture-map")
```

### AC2: Incremental Re-index

```
Given a project that has been fully indexed
 And one source file has been modified since the last index
When start_index_job(job, project, mode="incremental") runs to completion
Then only the changed file is re-embedded
 And unchanged files are skipped (files_skipped > 0 in IndexResult)
 And CodeIndexJob.status = "completed"
```

### AC3: Progress Queue Delivers Events

```
Given a running CodeIndexJobRunner registered in JOB_REGISTRY
When a consumer awaits JOB_REGISTRY[project_id].progress_queue
Then successive progress events are yielded with files_indexed, files_total, chunks_created, phase
 And the terminal event has phase = "done" (success) or phase = "error" (failure)
 And the runner removes itself from JOB_REGISTRY in its finally block
```

### AC4: Ollama Unavailable

```
Given Ollama is not reachable (connection refused)
When an indexing job runs
Then CodeIndexJob.status = "failed"
 And CodeIndexJob.errors contains the error description
 And no partial data is left in LanceDB that would cause inconsistency
 And a final phase="error" event is emitted on progress_queue
```

### AC5: Duplicate Job Prevention

```
Given a CodeIndexJobRunner is already registered in JOB_REGISTRY for a project
When start_index_job(job, project, mode="full") is called again
Then JobAlreadyRunningError is raised
 And JOB_REGISTRY[project.id] still references the original runner
```

### AC6: Regenerate Map Only

```
Given a project has an existing LanceDB index and an existing architecture-map ProjectDoc
When start_index_job(job, project, mode="mapgen_only") runs to completion
Then MapGenerator.generate_level1() runs without re-indexing
 And the existing ProjectDoc is updated (upsert, not duplicated)
 And ProjectDoc.version is incremented when content changes
```

### AC7: Cooperative Cancel

```
Given a CodeIndexJobRunner is registered in JOB_REGISTRY and is mid-indexing
When the consumer (F-00047 DELETE handler) calls runner.request_cancel()
Then the runner observes the flag at its next checkpoint
 And updates CodeIndexJob.status = "cancelled"
 And appends "cancelled by user" to CodeIndexJob.errors
 And emits a terminal progress event with phase="cancelled"
 And removes itself from JOB_REGISTRY in the finally block
 And the partial LanceDB state is left in place (not rolled back)
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Job already running | `project_id` in JOB_REGISTRY | `start_index_job` raises `JobAlreadyRunningError` |
| Empty repository | Repo with no Python files | Complete with `files_indexed=0`, `chunks_created=0` |
| C++ file with parse error | `.cpp` file tree-sitter fails | Fall back to character-based chunking, no error raised |
| Ollama HTTP error | Connection refused | Job status = "failed", error recorded, phase="error" on queue |
| Manifest missing | First run / manifest deleted | Treat all files as changed (full index) |
| ProjectDoc already exists | Second call with mode="mapgen_only" | Upsert: update existing doc, do not create duplicate |
| Runner registration race | Two concurrent `start_index_job` calls | Second call raises `JobAlreadyRunningError` (serialized by event loop) |
| Cancel before first checkpoint | `request_cancel()` called immediately after `start_index_job` | Runner observes flag on first checkpoint, emits `phase="cancelled"`, status = `cancelled`, no LanceDB writes occurred |
| Cancel mid-indexing | `request_cancel()` called between files | Current file's writes complete, then cancel triggers at the next checkpoint; partial LanceDB state left in place |
| Cancel during mapgen | `request_cancel()` called between RAG questions | Mapgen halts, no `ProjectDoc` written for this run, status = `cancelled` |
| Cancel after `phase="done"` | `request_cancel()` called on a nearly-finished runner | Ignored — the terminal phase has already been emitted and the runner is exiting normally |

## Invariants

1. `JOB_REGISTRY` contains at most one entry per `project_id` at any time.
2. A `CodeIndexJob` with `status="running"` always has a corresponding entry in `JOB_REGISTRY`.
3. `request_cancel()` is idempotent — calling it more than once has no additional effect.
4. A runner that observes a cancel flag always reaches a terminal status of `cancelled` (never `completed` or `failed`) and always removes itself from `JOB_REGISTRY`.
5. The manifest SHA256 reflects the actual state of the LanceDB index.
6. The generated `ProjectDoc` `slug` is unique per project (ensured by upsert logic).
7. On job failure, `CodeIndexJob.errors` is never empty.
8. LanceDB table name always follows the pattern `code_{project_id.replace('-', '_')}`.

## Dependencies

- **Depends on**: F-00045 (CodeIndexJob ORM model, orch/rag/ package, CodeUnderstandingConfig)
- **Blocks**: F-00047 (Dashboard Code Tab + Job UI — consumes `start_index_job`/`JOB_REGISTRY`), F-00048, F-00049

## TDD Approach

- **Unit tests** (`tests/unit/`):
  - `_compute_sha()` returns consistent SHA256 for same content, differs for different content
  - `_load_manifest()` / `_save_manifest()` roundtrip (create, load, verify)
  - `_get_changed_files()` returns only files whose SHA differs from manifest
  - `_build_mermaid()` returns a string containing `graph TD`
  - `_assemble_markdown()` returns markdown containing all 8 question keys
  - Config resolution: `resolved_embed_model()` returns correct model string

- **Integration tests** (`tests/integration/`):
  - Full index of a 3-file Python fixture repo → verify LanceDB chunks exist → verify `CodeIndexJob.status = "completed"` → verify `ProjectDoc` created
  - Incremental reindex → only changed file re-embedded (verify via manifest)
  - Failed Ollama (mock HTTP) → `CodeIndexJob.status = "failed"` with error in `errors`, terminal `phase="error"` event on progress_queue
  - `start_index_job` called twice for the same project → second call raises `JobAlreadyRunningError`
  - `mode="mapgen_only"` upserts the architecture-map ProjectDoc (does not duplicate)
  - Cancel mid-indexing: start a fake runner against a ≥3-file fixture, call `request_cancel()` after the first file is processed, assert: terminal `phase="cancelled"` event on queue, `CodeIndexJob.status == "cancelled"`, `errors` contains `"cancelled by user"`, runner removed from `JOB_REGISTRY`
  - Cancel is idempotent: calling `request_cancel()` twice has the same effect as calling it once
  - Cancel after `phase="done"`: calling `request_cancel()` on an exiting runner is a no-op and does not corrupt the terminal status

## Notes

- Do NOT use a live Ollama instance in CI. All integration tests must mock the Ollama HTTP calls.
- `orch/rag/job.py` uses `asyncio` and must be used only from async contexts (FastAPI route handlers or test event loops).
- The `DocService` already handles `ProjectDoc` upsert/creation; prefer it over raw SQL in `MapGenerator`.
- LanceDB is a file-based vector database — index files live on disk at `IW_CORE_INDEX_PATH`. Tests must use `tmp_path` fixture to isolate index files.
- tree-sitter-languages installs pre-compiled grammars for 100+ languages, avoiding the need to compile grammars at runtime.
