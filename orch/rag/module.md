# orch/rag/ — Code Understanding (RAG)

<!-- generated: 2026-05-06 -->

## Purpose

`orch/rag/` is the Code Understanding engine for the IW AI Core dashboard. It powers the **Code** view with indexing, retrieval-augmented generation, streaming Q&A, and multi-level documentation generation (architecture map → per-module docs → per-symbol explanations). All AI inference uses **Ollama** (local LLM) — configured via `CodeUnderstandingConfig` — never the project's default LLM.

## Architecture

```
code files → indexer (chunks + embeddings → LanceDB)
                      │
                      ├─► mapgen      ─► Level 1 architecture doc (architecture-map)
                      ├─► module_gen  ─► Level 2 per-module docs (async LLM, 2-4 min)
                      ├─► symbol_gen  ─► Level 3 per-symbol explanations (tree-sitter)
                      └─► qa          ─► streaming RAG answers (+ evidence + citations)

work_items → doc_indexer ──► docs LanceDB ──► qa (evidence retrieval)
```

## Key Components

| Component | Layer | Responsibility |
|-----------|-------|----------------|
| `CodeIndexer` | indexer | Discover `.py/.cpp/.hpp/.h` files, chunk via LlamaIndex CodeSplitter, embed via Ollama, write to LanceDB with SHA-256 manifest |
| `CodeIndexJobRunner` | job | Asyncio runner that drives `code_index_jobs` table through `queued → running → completed/failed`; orchestrates index → mapgen → index_gen |
| `MapGenerator` | generation | Level 1 architecture doc via 8-section RAG query loop against LanceDB; also generates `diagram-architecture` Mermaid diagram |
| `ModuleGenerator` | generation | Level 2 per-module documentation via 5-question RAG loop; generates `diagram-module-<slug>` Mermaid diagrams; runs as standalone asyncio task |
| `SymbolGenerator` | generation | Level 3 symbol explanation via tree-sitter AST extraction + Ollama; supports Python, C++, JS, TS, Rust, Go |
| `QAEngine` | qa | Context-aware RAG Q&A with streaming via `answer_stream()` (code-only) and `answer_stream_v2()` (work-item-aware with evidence + citations) |
| `Classifier` | qa | Routes queries: `workitem_aware` (needs git history, work-item evidence) vs `code_only` |
| `chat_repo` | memory | DB-access layer for `chat_conversations` + `chat_messages`; token counting via tiktoken with heuristic fallback; soft/hard budget truncation |
| `condense` | memory | CondensePlusContext query rewriting — rewrites follow-up questions into self-contained search queries using last 4 turns |
| `summarize` | memory | Rolling summary via Ollama — preserves named entities, work-item IDs, facts, decisions; extends/refines previous summary |
| `DocIndexer` | doc-indexer | Embeds `work_items.functional_doc_content` into separate docs LanceDB table for evidence retrieval in work-item-aware pipeline |
| `git_log_resolver` | evidence | Maps file paths → work-item IDs by parsing `git log --follow --oneline` for `Merge F-NNNNN:` / `Merge CR-NNNNN:` / `Merge I-NNNNN:` lines |
| `citation_allowlist` | evidence | Strips hallucinated work-item IDs from LLM output after response; `allowed_ids` is the union of all retrieval sources |
| `module_progress` | memory | In-memory progress registry for async ModuleGenerator tasks; dedupes concurrent generation; exposes per-step progress to HTTP spinner endpoint |

## Backing DB Tables

| Table | Purpose |
|-------|---------|
| `code_index_jobs` | Status (queued/running/completed/failed), progress counters (files_indexed, chunks_created, languages_detected), config snapshot |
| `chat_conversations` | Per-session conversation row — `(project_id, session_id)` scoped, tracks `rolling_summary` and `summary_through_message_id` |
| `chat_messages` | Append-only turns — `role`, `content`, `token_count`, `message_metadata` (JSONB) |
| `chat_summarization_jobs` | Background compaction queue — triggered when unsummarized token sum exceeds `HISTORY_HARD_BUDGET_TOKENS = 6000` |
| `doc_index_jobs` | Doc-indexer jobs for work-item content embedding |

## RAG Pipeline Details

### Code Indexing (CodeIndexer)

- **Discovery**: `*.py`, `*.cpp`, `*.hpp`, `*.h` via `repo.rglob()`; skips hidden dirs, `__pycache__`, `.venv`, `node_modules`
- **Chunking**: LlamaIndex `CodeSplitter` (40 lines, 5-line overlap) for known languages; `SentenceSplitter` fallback for unknown
- **Embedding**: Ollama via `OllamaEmbedding`; model resolved from `CodeUnderstandingConfig`
- **Storage**: LanceDB at `{index_path}/{project_id}/vectors/`, table `code_{project_id.replace('-', '_')}`
- **Manifest**: SHA-256 per file tracked in `{index_path}/{project_id}/manifest.json`; enables `reindex_changed()`
- **Seed node**: Empty LanceDB table seeded with `__iwcore_seed__` node to prevent "Table not initialized" errors on fresh DB

### Level 1 — Architecture Map (MapGenerator)

8 RAG queries (top-k=20) against LanceDB, each grounded with `_GROUNDING_TEMPLATE`:
`purpose`, `components`, `entry_points`, `databases`, `external_services`, `background_jobs`, `architecture_style`, `key_patterns`

Output: `project_docs` row with `doc_id = "architecture-map"`, `doc_type = DocType.architecture`

Also generates `diagram-architecture` (Mermaid component diagram with ELK layout + classDef color coding).

### Level 2 — Per-Module Docs (ModuleGenerator)

5 RAG questions per module (top-k=5):
`Primary Responsibility`, `Key Files`, `Dependencies`, `Design Patterns`, `Entry Points`

Slug format: `{project_id}-module-{module_path.strip('/').replace('/', '-')}`

Also generates `diagram-module-{slug}` with Mermaid component diagram.

**Important**: Module generation runs as a standalone `asyncio.Task` outside any HTTP lifecycle. Progress is tracked in-memory via `module_progress.py` — a process restart loses in-flight state.

### Level 3 — Symbol Explanation (SymbolGenerator)

Tree-sitter AST parsing to extract `function_definition`, `class_definition`, `function_item`, `impl_item`, `method_declaration` nodes. Falls back to full file if symbol not found.

### Work-Item-Aware Q&A (answer_stream_v2)

1. `classify_query()` → `workitem_aware` or `code_only`
2. Retrieve evidence from three sources:
   - **LanceDB semantic** (`doc_chunks`): `work_item_id`, `work_item_type`, `work_item_title`, `text`, `score`
   - **Postgres FTS** (`fts_items`): `ts_rank` on `functional_doc_search`
   - **Git log resolver** (`git_log_items`): `git log --follow --oneline` → `Merge F-NNNNN:` patterns
3. Merge + rank with weighted scoring: `alpha=0.45` (FTS) + `beta=0.20` (git) + `gamma=0.35` (semantic)
4. Build `WORKITEM_RELEVANCE_FILTER` block for system prompt (top-3 full docs + top-5 compact)
5. Stream response; apply `citation_allowlist` post-generation to strip hallucinated IDs

### Conversation Memory (F-00077)

**Token-budget truncation strategy**:
- **Soft budget** (`HISTORY_SOFT_BUDGET_TOKENS = 3000`): applied every turn via `_truncate_history()` / `chat_repo.list_messages_for_context()`. Drops oldest messages first; always preserves the last 2 messages even if they alone exceed the budget.
- **Hard budget** (`HISTORY_HARD_BUDGET_TOKENS = 6000`): after assistant message persists, if cumulative token_count of unsummarized messages exceeds this threshold and no in-flight `chat_summarization_jobs` row exists, a new job is enqueued. Daemon poller (`orch/daemon/chat_summarization_poller.py`) runs `summarize_history()` and writes `rolling_summary` + `summary_through_message_id`.

**Hardening lines** (applied unconditionally on every call — Invariant 8):
```
On contradictions in the user's statements, trust the most recent one.
Do not claim to remember anything not present in the provided conversation history.
```

## Configuration

`CodeUnderstandingConfig` — Pydantic model validating `code_understanding` block in project's `config` JSONB:

| Key | Default | Description |
|-----|---------|-------------|
| `provider` | `local` | Only "local" (Ollama) supported in v1 |
| `llm_model` | `null` | Resolved from `index_tier` if null |
| `embed_model` | `null` | Resolved from `index_tier` if null |
| `index_tier` | `balanced` | `fast`/`balanced`/`quality` — controls model defaults |
| `ollama_url` | `http://localhost:11434` | Ollama endpoint |
| `index_path` | `~/.local/share/iw-ai-core/code-index` | LanceDB storage root |

**Tier defaults**:

| Tier | LLM Model | Embed Model |
|------|-----------|-------------|
| `fast` | `gemma4:e4b` | `qwen3-embedding:8b` |
| `balanced` (default) | `gemma4:26b` | `qwen3-embedding:8b` |
| `quality` | `gemma4:31b` | `manutic/nomic-embed-code` |

## Key Invariants

- **Invariant 1**: Messages with `message_metadata.error=True` are excluded from conversation context (never fed to LLM) — prevents partial/interrupted messages from corrupting context
- **Invariant 7**: `get_or_create_conversation` lookup is strictly filtered by `(project_id, session_id, NOT archived)` — no cross-session leakage
- **Invariant 8**: `SYSTEM_PROMPT_HARDENING` applied unconditionally on every `_build_system_prompt()` call
- **Citation allowlist**: Applied AFTER LLM response; `allowed_ids` is the union of all retrieval sources (doc_chunks, fts_items, git_log_items, ranked work_items) to ensure no valid ID is ever stripped

## Dependencies

### Depends On

| Module | What It Uses | Why |
|--------|-------------|-----|
| `orch.db.models` | `CodeIndexJob`, `ProjectDoc`, `ChatConversation`, `ChatMessage`, `WorkItem`, `Project` | All persistence |
| `orch.doc_service` | `DocService` | Creating/updating `ProjectDoc` records for architecture-map, module docs, diagrams |
| `orch.config` | `load_config()` | Fallback index path resolution in `job.py` |
| `llama_index` | `VectorStoreIndex`, `CodeSplitter`, `SentenceSplitter`, `OllamaEmbedding`, `Ollama` | Indexing and LLM calls |
| `lancedb` | Connection, table operations | Vector storage |
| `tiktoken` | Token counting | Chat memory budget management |
| `tree_sitter_languages` | Language parsers | Symbol extraction |
| `httpx` | Async HTTP client | Ollama API calls |

### Depended On By

| Module | What It Uses | Why |
|--------|-------------|-----|
| `dashboard/routers/code.py` | `QAEngine`, `CodeIndexer`, `MapGenerator`, `ModuleGenerator` | Dashboard Code UI |
| `orch/daemon/doc_job_poller.py` | Launches `iw-doc-generator` skill for `doc_generation_jobs` | Async doc regeneration |
| `orch/rag/job.py` | `CodeIndexJobRunner` + `JOB_REGISTRY` | Background indexing job |
| `orch/test_runner.py` | Not directly used | Test/quality runs are separate |

## Extension Points

- **New language support**: Add extension to `SymbolGenerator.LANGUAGE_EXTENSIONS` and `SYMBOL_KINDS` set
- **Custom retrieval rank weights**: Modify `alpha`, `beta`, `gamma` in `QAEngine._merge_and_rank_work_items()`
- **Additional query classification**: Add to `SLASH_OVERRIDE_CHIPS` in `classifier.py`
- **Module diagram styling**: Modify `_MERMAID_CLASSDEF` / `_inject_elk_frontmatter()` in `module_gen.py`

## Test Coverage

| Test Type | Location | Count |
|-----------|----------|-------|
| Unit tests | `tests/unit/test_doc_job_poller.py`, `tests/unit/test_doc_report.py`, `tests/unit/test_doc_job_poller_pid_liveness.py` | ~30 tests |
| Integration tests | `tests/integration/` (DB tests use testcontainers) | — |
| Fixtures | `tests/fixtures/doc_jobs/` | Replay logs for doc-job lifecycle validation |

## Gotchas

1. **Ollama-only inference**: All embedding + LLM calls go to Ollama, not the project's default LLM. If Ollama is offline, indexing silently skips chunks and Q&A yields `"__ERROR__:Local AI unavailable"`
2. **In-memory module progress**: `module_progress.py` state is lost on dashboard restart. In-flight module generation continues but the UI spinner will show stale state until the task completes
3. **Citation allowlist is post-hoc**: `citation_allowlist.filter_citations()` runs after the LLM responds — hallucinated IDs appear in the response briefly before being stripped
4. **Git log resolver cross-project IDs**: `git_log_resolver` returns raw work-item IDs unfiltered by project; callers must scope results to the correct `project_id`
5. **`DaemonEvent.metadata` → `event_metadata`**: SQLAlchemy reserves `metadata` on declarative classes; the DB column is `metadata` but Python uses `event_metadata`
