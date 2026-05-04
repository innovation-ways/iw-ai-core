# orch/rag/ — Code Understanding (RAG)

Indexing, retrieval, and generation support for the dashboard **Code** view. Powers module browsing, symbol explanation, and streaming Q&A with work-item-aware citations.

## Pipeline

```
code files → indexer (chunks + embeddings → LanceDB)
                      │
                      ├─► mapgen      ─► Level 1 architecture doc
                      ├─► module_gen  ─► Level 2 per-module docs (async LLM)
                      ├─► symbol_gen  ─► Level 3 per-symbol explanations (tree-sitter)
                      └─► qa          ─► streaming RAG answers (+ evidence + citations)
```

## Files

| File | Purpose |
|------|---------|
| `config.py` | `CodeUnderstandingConfig` Pydantic model — validates the `code_understanding` block in a project's `config` JSONB; provider/tier enums + per-tier model defaults |
| `indexer.py` | `CodeIndexer` — discover files, chunk via LlamaIndex CodeSplitter, embed via Ollama, write to LanceDB |
| `job.py` | `CodeIndexJobRunner` + `JOB_REGISTRY` — asyncio runner that drives the `code_index_jobs` row through queued → running → completed/failed |
| `parser.py` | Parse module list from a Level 1 architecture doc (regex over H2/H3 structure) |
| `mapgen.py` | `MapGenerator` — RAG-backed Level 1 architecture doc generation |
| `module_gen.py` | `ModuleGenerator` — Level 2 per-module documentation (long-running LLM task) |
| `module_progress.py` | In-memory progress registry for module_gen (runs outside any HTTP lifecycle) |
| `symbol_gen.py` | `SymbolGenerator` — Level 3 symbol explanation via tree-sitter + Ollama |
| `qa.py` | `QAEngine` — context-aware RAG Q&A with streaming + conversation history |
| `classifier.py` | Routes queries: work-item-aware (needs git history) vs. code-only |
| `evidence.py` | `EvidenceBundle` — citation metadata (file_path, line_range, symbol_name, work_item_id) |
| `git_log_resolver.py` | Maps files/symbols to work-item IDs by parsing `git log --follow --oneline` for `Merge F-NNNNN:` / `Merge CR-NNNNN:` / `Merge I-NNNNN:` lines |
| `citation_allowlist.py` | Strips hallucinated work-item IDs from LLM output before surfacing to UI |

## Backing DB table

`code_index_jobs` — status (queued/running/completed/failed), progress counters, config snapshot.

## Consumers

- **UI**: `dashboard/routers/code.py`, `code_ui.py`, `code_qa.py` (all three delegate heavy work here)
- **Caching**: Level 2 module docs are cached in `project_docs` (doc_type=module) via `orch/doc_service.py`; regeneration flows through `doc_generation_jobs`

## Gotchas

- Embedding + LLM calls go to **Ollama**, not the project's default LLM — configured in `CodeUnderstandingConfig`
- Module generation runs as a standalone asyncio task (2-4 min for local LLM) — progress is tracked in memory (`module_progress.py`), not the DB. A process restart loses in-flight module generation state
- `citation_allowlist` is applied AFTER the LLM responds; any work-item ID the model invents but that git_log_resolver cannot prove is dropped

## Conversation memory (F-00077)

Persistent chat memory backed by PostgreSQL. Powers multi-turn code Q&A with token-budget truncation, query rewriting (CondensePlusContext), and rolling-summary compaction.

### DB Tables

| Table | Purpose |
|-------|---------|
| `chat_conversations` | Per-session row — `(project_id, session_id)` scoped, tracks `rolling_summary` and `summary_through_message_id` for compaction state |
| `chat_messages` | Append-only turns — `role` (user/assistant/system), `content`, `token_count`, `message_metadata` (JSONB) |
| `chat_summarization_jobs` | Background compaction queue — `status` (queued/running/completed/failed), triggered by `HISTORY_HARD_BUDGET_TOKENS` overflow |

### Condense → Retrieve → Answer flow

```
User turn N+1
    │
    ▼
chat_repo.list_messages_for_context()  ← token-budget truncation (soft budget = 3000)
    │                                    always preserves last 2 messages
    ▼
condense_query(history, question, llm)  ← CondensePlusContext pattern
    │  len(history) < 2  →  returns question unchanged (no LLM call)
    │  len(history) >= 2 →  calls llm.complete() with CONDENSE_PROMPT
    │                     last 4 turns max for the condense prompt
    ▼
OllamaEmbedding.get_query_embedding(condensed_query)  ← retrieval uses condensed
    │
    ▼
LanceDB top-k retrieval (filtered by module_path if context_level=module)
    │
    ▼
Build system prompt  ← context doc + chunks + WORKITEM_BLOCK + hardening lines
    │
    ▼
Prepend rolling_summary as synthetic system note (if set on conversation)
    │
    ▼
Stream response via Ollama LLM (original question in user turn)
```

### Token-budget truncation strategy

- **Soft budget** (`HISTORY_SOFT_BUDGET_TOKENS = 3000`): applied every turn via `_truncate_history()` / `list_messages_for_context()`. Drops oldest messages first; always preserves the last 2 messages even if they alone exceed the budget.
- **Hard budget** (`HISTORY_HARD_BUDGET_TOKENS = 6000`): after the assistant message persists, if cumulative `token_count` of unsummarized messages exceeds this threshold and no in-flight `chat_summarization_jobs` row exists, a new job is enqueued. The daemon poller (`orch/daemon/chat_summarization_poller.py`, S04) runs `summarize_history()` and writes `rolling_summary` + `summary_through_message_id`.

### Hardening lines

Every system prompt produced by `_build_system_prompt()` appends:

```
On contradictions in the user's statements, trust the most recent one.
Do not claim to remember anything not present in the provided conversation history.
```

These are defined as `SYSTEM_PROMPT_HARDENING` in `qa.py` and are applied unconditionally (no flag) on every call — see Invariant 8.

### Key files

| File | Purpose |
|------|---------|
| `chat_repo.py` | DB-access layer: `get_or_create_conversation`, `append_message`, `list_messages_for_context`, `list_conversations_for_session`, `get_conversation`, `archive_conversation`, `count_tokens` (tiktoken with heuristic fallback) |
| `condense.py` | `condense_query()` — CondensePlusContext pattern; graceful degradation on LLM failure (`daemon_event` type `condense_failed`) |
| `summarize.py` | `summarize_history()` — rolling summary; preserves named entities, work-item IDs, facts, decisions; extends/refines previous summary; re-raises on LLM failure |
| `qa.py` | `QAEngine.answer_stream()` — DB-backed history loading, condense before retrieval, summary prepend, hardening lines; `answer_stream_v2()` uses same treatment for work-item-aware path |
