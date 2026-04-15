# F-00046_S01_Backend_prompt

**Work Item**: F-00046 -- Code Understanding: Indexing Engine + Level 1 Map Generation
**Step**: S01
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/F-00046/F-00046_Feature_Design.md` -- Design document (read this first)
- `orch/rag/config.py` -- CodeUnderstandingConfig from F-00045
- `orch/db/models.py` -- CodeIndexJob and ProjectDoc ORM models
- `orch/doc_service.py` -- DocService for ProjectDoc CRUD
- `CLAUDE.md` and `orch/CLAUDE.md` -- Project conventions

## Output Files

- `orch/rag/indexer.py` -- CodeIndexer class
- `orch/rag/job.py` -- CodeIndexJobRunner + JOB_REGISTRY
- `orch/rag/mapgen.py` -- MapGenerator class
- `tests/unit/test_code_indexer.py` -- Unit tests (TDD: write RED first)
- `ai-dev/work/F-00046/reports/F-00046_S01_Backend_report.md` -- Step report

## Context

You are implementing the core RAG indexing pipeline for F-00046. This is the most critical step — it builds the three backend modules that everything else depends on.

Read the design document (`F-00046_Feature_Design.md`) in full before writing any code. Pay particular attention to the Architecture Details section.

## Step 0: Install Dependencies

Before writing any code, install the required Python packages:

```bash
uv add llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama llama-index-vector-stores-lancedb lancedb tree-sitter tree-sitter-languages
```

Verify the install succeeded before continuing.

## TDD Requirement — RED Phase First

Write `tests/unit/test_code_indexer.py` BEFORE writing any implementation. The following unit tests must exist and be RED (failing) before implementation:

1. `test_compute_sha_consistent` — same file content produces same SHA256
2. `test_compute_sha_differs` — different content produces different SHA256
3. `test_manifest_roundtrip` — `_save_manifest()` then `_load_manifest()` returns original dict
4. `test_manifest_missing_returns_empty` — `_load_manifest()` when file absent returns `{}`
5. `test_get_changed_files_all_changed` — empty manifest → all files returned
6. `test_get_changed_files_no_change` — manifest matches current SHAs → empty list returned
7. `test_get_changed_files_partial` — one file changed → only that file returned
8. `test_build_mermaid_contains_graph_td` — output contains `graph TD`
9. `test_assemble_markdown_contains_all_sections` — output contains all 8 question keys as headings
10. `test_index_result_dataclass` — `IndexResult` can be instantiated with all fields

Run `uv run pytest tests/unit/test_code_indexer.py -v` to confirm they are RED before proceeding.

## Requirements

### 1. orch/rag/indexer.py — CodeIndexer

Implement the `CodeIndexer` class exactly as specified in the design document.

**Class signature** (the project is **sync SQLAlchemy** — do NOT import `AsyncSession`):
```python
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from orch.rag.config import CodeUnderstandingConfig

@dataclass
class IndexResult:
    files_indexed: int
    chunks_created: int
    files_skipped: int
    errors: list[str] = field(default_factory=list)

class CodeIndexer:
    def __init__(self, project_id: str, config: CodeUnderstandingConfig, index_path: str) -> None: ...
    async def index(
        self,
        repo_path: str,
        job_id: str,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> IndexResult: ...
    async def reindex_changed(
        self,
        repo_path: str,
        job_id: str,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> IndexResult: ...
    def _get_manifest_path(self) -> Path: ...
    def _load_manifest(self) -> dict[str, str]: ...
    def _save_manifest(self, manifest: dict[str, str]) -> None: ...
    def _compute_sha(self, file_path: Path) -> str: ...
    def _get_changed_files(self, repo_path: str, manifest: dict[str, str]) -> list[Path]: ...
```

CPU-bound file walking and LanceDB I/O should be invoked via `await asyncio.to_thread(...)` from the async methods so the event loop is not blocked. `CodeIndexer` does NOT take a session — it owns no DB state.

**Implementation rules**:

- LanceDB store path: `Path(index_path) / project_id / "vectors"` — create parents if missing.
- Manifest path: `Path(index_path) / project_id / "manifest.json"`.
- LanceDB table name: `f"code_{project_id.replace('-', '_')}"`.
- Use `llama_index.core.node_parser import CodeSplitter` with `chunk_lines=40, chunk_lines_overlap=5`.
- For Python files: set `language="python"` in `CodeSplitter`.
- For C++ files (`.cpp`, `.hpp`, `.h`): set `language="cpp"`. Wrap the splitter call in a `try/except Exception` and fall back to character-based splitting if it fails. Log the fallback but do NOT raise.
- Embed model: instantiate `OllamaEmbedding(model_name=config.resolved_embed_model(), base_url=config.ollama_base_url)`.
- Use `LanceDBVectorStore` from `llama_index.vector_stores.lancedb` with the computed store path and table name.
- The `index()` method processes ALL files in the repo. The `reindex_changed()` method loads the manifest and only processes changed files.
- During indexing, invoke `progress_callback({"event": "progress", "files_indexed": N, "files_total": M, "chunks_created": K, "phase": "indexing"})` after each file. The runner supplies the callback and is responsible for putting events on its asyncio queue.
- After indexing, call `_save_manifest()` with the updated SHA map.
- File discovery: walk `repo_path` recursively, include files matching `*.py`, `*.cpp`, `*.hpp`, `*.h`. Skip hidden directories (`.git`, `__pycache__`, `.venv`, `node_modules`).
- If Ollama is unreachable (connection error), let the exception propagate — `CodeIndexJobRunner` handles it.

### 2. orch/rag/job.py — CodeIndexJobRunner, JOB_REGISTRY, start_index_job, JobAlreadyRunningError

```python
import asyncio
from typing import Literal, TYPE_CHECKING
from orch.db.models import CodeIndexJob, Project
from orch.rag.config import CodeUnderstandingConfig

# Global registry: project_id -> running CodeIndexJobRunner
JOB_REGISTRY: dict[str, "CodeIndexJobRunner"] = {}


class JobAlreadyRunningError(Exception):
    """Raised when start_index_job is called for a project that already has a runner in JOB_REGISTRY."""
    def __init__(self, project_id: str) -> None:
        super().__init__(f"A code index job is already running for project {project_id}")
        self.project_id = project_id


class CodeIndexJobRunner:
    def __init__(
        self,
        job_id: str,
        project_id: str,
        repo_path: str,
        config: CodeUnderstandingConfig,
        index_path: str,
        *,
        reindex: bool = False,
        mapgen_only: bool = False,
    ) -> None: ...

    async def run(self) -> None: ...

    @property
    def progress_queue(self) -> asyncio.Queue: ...

    def request_cancel(self) -> None:
        """Set a cooperative cancel flag. Non-blocking. The runner observes
        the flag at its next checkpoint and exits cleanly with terminal status
        'cancelled'. Idempotent — calling twice has the same effect as once."""
        ...


def start_index_job(
    job: CodeIndexJob,
    project: Project,
    *,
    mode: Literal["full", "incremental", "mapgen_only"],
) -> CodeIndexJobRunner:
    """
    Synchronously create a CodeIndexJobRunner for (job, project), register it in
    JOB_REGISTRY[project.id], and return it. The caller schedules runner.run() via
    FastAPI BackgroundTasks.

    Raises:
        JobAlreadyRunningError: if JOB_REGISTRY[project.id] is already populated.
    """
```

**Implementation rules**:

- **Sync-only ORM**: `orch/db/session.py` provides `SessionLocal` and `get_session()` — there is NO async session factory. All DB work inside `run()` must be wrapped in `await asyncio.to_thread(...)` around a `with SessionLocal() as session:` block. Do NOT introduce an async session factory.
- In `__init__`, create `self._queue: asyncio.Queue = asyncio.Queue()` and `self._cancel_requested: bool = False`.
- `request_cancel()` sets `self._cancel_requested = True`. It is synchronous and non-blocking. Idempotent. Must be safe to call at any time after construction.
- **Registry registration is done by `start_index_job`** — it checks for an existing entry, raises `JobAlreadyRunningError` if present, otherwise sets `JOB_REGISTRY[project.id] = runner` synchronously and returns the runner. `run()` only removes itself from the registry in `finally`. The F-00047 route handler will call `start_index_job` inside the request handler before scheduling `background_tasks.add_task(runner.run)`.
- `start_index_job` maps modes to runner flags: `"full"` → `reindex=False, mapgen_only=False`; `"incremental"` → `reindex=True, mapgen_only=False`; `"mapgen_only"` → `reindex=False, mapgen_only=True`. It does NOT persist the mode on the `CodeIndexJob` row (the F-00045 schema has no `job_type` column and F-00046 must not invent one).
- **Scope boundary**: F-00046 must NOT create any file under `dashboard/routers/`. The HTTP/SSE layer is F-00047's scope. If you need to verify the integration, call `start_index_job` directly in a pytest — do not spin up a FastAPI app here.
- `run()` must:
  1. (Registry already populated by `start_index_job`.)
  2. In `asyncio.to_thread`: open `SessionLocal()`, load `CodeIndexJob` by `self.job_id`, set `status = "running"`, commit.
  3. If `self.mapgen_only` is True, skip steps 3–5 and jump straight to map generation.
  4. Otherwise create a `CodeIndexer` instance.
  5. Define `progress_callback` that calls `self._queue.put_nowait(event)` (or `asyncio.run_coroutine_threadsafe` if the callback is invoked from the worker thread — choose one consistent approach and document it).
  6. `await` `indexer.index()` or `indexer.reindex_changed()` based on `self.reindex` flag.
  7. On success: emit `phase="mapgen"` event, then `await MapGenerator(config).generate_level1(project_id, config)`.
  8. In `asyncio.to_thread`: update `CodeIndexJob.status = "completed"`, set `files_indexed`, `chunks_created`, `doc_id` (the composite `ProjectDoc.id`) from the generated doc, commit.
  9. Put `{"event": "progress", "phase": "done", ...}` on queue.
  10. On any `Exception`: in `asyncio.to_thread`, update `CodeIndexJob.status = "failed"` and append `str(e)` to `errors` JSONB; put `{"event": "progress", "phase": "error", "message": str(e)}` on queue.
  11. In a `finally` block: `JOB_REGISTRY.pop(self.project_id, None)`.

- **Cooperative cancellation**: between steps 6 and 7, between 8-question RAG loops inside `MapGenerator.generate_level1()`, and after each sub-phase transition, check `self._cancel_requested`. When set:
  a. Stop processing (break out of indexing / mapgen loops).
  b. In `asyncio.to_thread`: update `CodeIndexJob.status = "cancelled"`, append `"cancelled by user"` to `errors` JSONB.
  c. Put `{"event": "progress", "phase": "cancelled", ...}` on the queue.
  d. Fall through to the same `finally` cleanup — there must be exactly one registry cleanup site. Do NOT add a second `JOB_REGISTRY.pop(...)` in the cancel branch.
  e. Partial LanceDB state is intentionally left in place (not rolled back). Document this in a one-line comment in `run()`.
  f. If `phase="done"` has already been emitted before the cancel flag is observed, the cancel is a no-op — the runner is already exiting normally.
  g. `MapGenerator.generate_level1()` must accept and honour a cancel-check callback (e.g. `cancel_check: Callable[[], bool]`) passed from the runner, so the map phase can be interrupted between RAG questions without leaking the cancellation concept outside the runner's module.

- Progress event structure for indexing phase:
  ```python
  {"event": "progress", "files_indexed": N, "files_total": M, "chunks_created": K, "phase": "indexing"}
  ```
- Progress event structure for map generation phase:
  ```python
  {"event": "progress", "files_indexed": N, "files_total": M, "chunks_created": K, "phase": "mapgen"}
  ```

**Important**: If `orch/db/session.py` only provides a sync session, wrap DB calls in `asyncio.to_thread()`. Do NOT introduce an async session factory if one doesn't exist — check first.

### 3. orch/rag/mapgen.py — MapGenerator

```python
from orch.rag.config import CodeUnderstandingConfig
from orch.db.models import ProjectDoc

class MapGenerator:
    QUESTIONS: list[tuple[str, str]] = [...]  # 8 tuples from design doc

    async def generate_level1(
        self,
        project_id: str,
        config: CodeUnderstandingConfig,
    ) -> ProjectDoc: ...

    def _build_mermaid(self, components_answer: str) -> str: ...
    def _assemble_markdown(self, answers: dict[str, str], mermaid: str) -> str: ...
```

`generate_level1()` opens its own sync `SessionLocal()` (wrapped in `asyncio.to_thread`) for each DB call. It does NOT take a session parameter.

**Implementation rules**:

- In `generate_level1()`:
  1. Load the LanceDB index for `project_id` using the same path/table name convention as `CodeIndexer`.
  2. Create an `OllamaEmbedding` and `Ollama` LLM from config.
  3. Build a `VectorStoreIndex` from the LanceDB store.
  4. Create a `QueryEngine` from the index.
  5. For each of the 8 `QUESTIONS`, call `query_engine.query(question)` and collect the `str(response)` answer.
  6. Call `_build_mermaid(answers["components"])` to generate a Mermaid diagram.
  7. Call `_assemble_markdown(answers, mermaid)` to produce the full document content.
  8. Open `SessionLocal()` inside `asyncio.to_thread(...)`. Inside the thread: load the `Project` row (for `display_name`), build the `DocService(session)`, call `upsert_doc(project_id, doc_id="architecture-map", title=f"{project.display_name} — Architecture Map", slug=f"{project_id}-architecture-map", doc_type=DocType.research, tier=DocTier.fully_automated, editorial_category=EditorialCategory.technical, content=markdown, generated_by="code-understanding:level1")`. `upsert_doc` returns `(doc, created)`. Commit the session before returning.
  9. Return the `ProjectDoc` returned by `upsert_doc`.

**Important**: `DocType`, `DocTier`, `EditorialCategory` are Python `enum.Enum` subclasses defined in `orch/db/models.py`. Pass enum members, never string literals — `DocService.create_doc()` takes typed enum parameters and mypy will fail on strings.

- `_build_mermaid()` must call the Ollama LLM directly (not via RAG) to generate a `graph TD` Mermaid diagram from the components answer. The prompt should be:
  ```
  Given these components: {components_answer}
  Generate a Mermaid graph TD diagram showing the relationships between components.
  Output ONLY the Mermaid code block, no explanation.
  ```
  Extract the code between ```mermaid and ``` fences. If extraction fails, return a minimal valid diagram: `graph TD\n  A[System]`.

- `_assemble_markdown()` must produce markdown with sections for each of the 8 questions, followed by the Mermaid diagram. Example structure:
  ```markdown
  # Architecture Map

  ## Purpose
  {answers["purpose"]}

  ## Components
  {answers["components"]}

  ## Entry Points
  {answers["entry_points"]}

  ## Databases & Data Stores
  {answers["databases"]}

  ## External Services
  {answers["external_services"]}

  ## Background Jobs
  {answers["background_jobs"]}

  ## Architecture Style
  {answers["architecture_style"]}

  ## Key Patterns
  {answers["key_patterns"]}

  ## Architecture Diagram

  ```mermaid
  {mermaid}
  ```
  ```

- `ProjectDoc` fields passed to `DocService.upsert_doc`:
  - `doc_id = "architecture-map"` — composite ID becomes `{project_id}:architecture-map`
  - `doc_type = DocType.research` (enum)
  - `tier = DocTier.fully_automated` (enum)
  - `editorial_category = EditorialCategory.technical` (enum)
  - `title = f"{project.display_name} — Architecture Map"` (field is `display_name`, not `name`)
  - `slug = f"{project_id}-architecture-map"` (pass explicitly)
  - `generated_by = "code-understanding:level1"`

### 4. Unit Tests — GREEN Phase

After writing the RED tests and implementing the three modules, make all unit tests pass:

```bash
uv run pytest tests/unit/test_code_indexer.py -v
```

All 10 tests must pass. Fix any failures before reporting.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for all conventions. Key points:
- SQLAlchemy 2.0 `Mapped[]` declarative style — match existing models.
- Check `orch/db/session.py` — if it only has sync session, do NOT add async session factory.
- Type annotations required on all public methods.
- No hardcoded paths, URLs, or credentials — read from config only.
- `ruff` is the linter/formatter — run `uv run ruff check .` and `uv run ruff format .` before reporting.
- `mypy` for type checking — run `uv run mypy orch/` before reporting.

## Test Verification (NON-NEGOTIABLE)

Before reporting completion, run ALL of:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/
uv run pytest tests/unit/ -v
```

All must pass with zero errors. Do NOT report `tests_passed: true` unless they do.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00046",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/indexer.py",
    "orch/rag/job.py",
    "orch/rag/mapgen.py",
    "tests/unit/test_code_indexer.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
