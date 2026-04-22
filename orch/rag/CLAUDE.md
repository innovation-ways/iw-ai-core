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
