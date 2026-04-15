# OSS RAG Frameworks and Vector Databases for Codebase Understanding

**Research ID**: R-00046  
**Date**: 2026-04-15  
**Mode**: deep  
**Depth**: deep  
**Editorial Category**: technical

---

## Primary Question

What proven, OSS (permissive-license) RAG frameworks and vector databases are available for a Python-native codebase RAG use case — and should we build a custom RAG pipeline or adopt an existing framework?

## Context

Building a codebase understanding feature in IW AI Core (Python/FastAPI). Needs to: index codebases (Python + C++) using AST-aware chunking, store embeddings, retrieve top-k chunks at query time, inject into an LLM prompt. LLM and embedding backends are Ollama (local) or cloud providers — configurable per project. Single Linux server, RTX 5090 32GB VRAM.

**Hard constraints**: OSS with permissive license (MIT, Apache 2.0) only. No GPL, LGPL, PolyForm, or proprietary. Prefer importable Python library over separate service.

---

## Executive Summary

For a Python/FastAPI codebase RAG system on a single Linux server with Ollama as the LLM/embedding backend, the winning stack is: **LlamaIndex (MIT) as the RAG orchestration layer + LanceDB (Apache 2.0) as the embedded vector database + tree-sitter for AST-aware chunking**. LlamaIndex ships a built-in `CodeSplitter` backed by tree-sitter, has first-class Ollama integration for both embedding and generation, and supports LanceDB as a vector store — all three are proven to interoperate without duct tape. A fully custom pipeline (direct Ollama HTTP + LanceDB + raw tree-sitter) is viable but eliminates no meaningful complexity while adding implementation burden. All full-stack RAG platforms evaluated (AnythingLLM, PrivateGPT, RAGFlow) are disqualified — they are applications, not libraries, and impose a container-service topology that conflicts with the embedded-library requirement. pgvector on the existing PostgreSQL instance is a valid zero-new-infrastructure alternative to LanceDB, but adds embedding workload to the operational database that also drives daemon polling.

---

## 1. RAG Frameworks Evaluated [HIGH]

### LlamaIndex ✅ RECOMMENDED

**License**: MIT — PERMITTED ([LICENSE](https://github.com/run-llama/llama_index/blob/main/LICENSE))  
**GitHub stars**: ~48,600 | **Production use**: Salesforce Agentforce + numerous enterprises

[Purpose-built data framework for RAG](https://sider.ai/blog/ai-tools/llamaindex-review-2025-is-it-the-best-rag-framework-for-production-ai). Covers ingestion, parsing, chunking, indexing, retrieval, query engines, agents, evaluation, and observability.

**Ollama support**: Dedicated first-party packages: [`llama-index-llms-ollama`](https://pypi.org/project/llama-index-llms-ollama/) and [`llama-index-embeddings-ollama`](https://pypi.org/project/llama-index-embeddings-ollama/). Covers both LLM generation (`OllamaLLM`) and embedding (`OllamaEmbedding`) via Ollama's local API. [Tested with nomic-embed-text and Llama family models](https://developers.llamaindex.ai/python/framework/getting_started/starter_example_local/).

**Code RAG features**: Ships a [`CodeSplitter`](https://developers.llamaindex.ai/python/framework-api-reference/node_parsers/code/) node parser that wraps tree-sitter internally and splits code at AST boundaries (functions, classes, methods). Configurable via `chunk_lines`, `chunk_lines_overlap`, and `max_chars`. Falls back to character-based splitting when AST parsing fails. This eliminates the most complex custom work.

**Vector DB flexibility**: Supports LanceDB, Qdrant, ChromaDB, Weaviate, Milvus, pgvector, Pinecone, and others via a `VectorStore` abstraction — dependency injection, not hard-coded coupling.

**Complexity overhead**: ~8 lines for a basic RAG pipeline. High-level API. Framework manages chunking, embedding, and retrieval implicitly — less verbose than Haystack, less auditable. [Framework latency: ~6 ms](https://myengineeringpath.dev/tools/llamaindex-vs-haystack/).

**Verdict**: **RECOMMENDED.** Best fit for this use case. Built for RAG, native Ollama support, built-in code chunker using tree-sitter, thin abstraction layer, MIT license.

---

### Haystack 2.x ✅ STRONG ALTERNATIVE

**License**: Apache 2.0 — PERMITTED ([LICENSE](https://github.com/deepset-ai/haystack/blob/main/LICENSE))  
**GitHub stars**: ~24,800 | **Production use**: Apple, Netflix, Airbus, LEGO, Comcast, Databricks, NVIDIA, Intel

Explicit DAG-based pipeline construction — every component is wired explicitly. [Enterprise-grade, designed for compliance-sensitive environments (HIPAA, SOC2)](https://www.morphik.ai/blog/guide-to-oss-rag-frameworks-for-developers).

**Ollama support**: Full support via [`ollama-haystack`](https://haystack.deepset.ai/integrations/ollama) package — `OllamaGenerator`, `OllamaChatGenerator`, `OllamaTextEmbedder`, `OllamaDocumentEmbedder`.

**Code RAG features**: **None built-in.** No AST-aware code chunker. Custom preprocessor components must be hand-rolled using the `@component` decorator — tree-sitter integration is manual. More transparent but more work.

**Vector DB flexibility**: [Supports Chroma, FAISS, LanceDB, Milvus, Qdrant, Weaviate, pgvector, Elasticsearch, MongoDB Atlas, and more](https://haystack.deepset.ai/integrations).

**Complexity overhead**: ~45 lines for basic RAG. Fully auditable — [pipelines can be serialized to YAML and version-controlled](https://myengineeringpath.dev/tools/llamaindex-vs-haystack/). Framework latency: ~5.9 ms. Token usage: ~1.57k (lowest of the three frameworks).

**Verdict**: **STRONG ALTERNATIVE for teams needing explicit pipeline control and auditability.** The lack of a built-in code chunker is a meaningful gap for this specific use case. Best choice if pipeline debuggability and compliance requirements outweigh implementation speed.

---

### LangChain ⚠ NOT RECOMMENDED

**License**: MIT — PERMITTED ([source](https://www.educate.io/blog/is-langchain-open-source))  
**GitHub stars**: ~95,000+

[Highest framework overhead (~10 ms, ~2.40k tokens)](https://mayur-ds.medium.com/langchain-vs-haystack-vs-llamaindex-rag-showdown-2025-28c222d34b0a). No native code-specific chunker. [Active community backlash against abstraction complexity in 2025](https://github.com/orgs/community/discussions/182015). No meaningful advantage over LlamaIndex for this scenario.

**Verdict**: **NOT RECOMMENDED.** Highest complexity, no code RAG advantage.

---

### DSPy ⚠ NOT APPLICABLE

**License**: MIT — PERMITTED  

Declarative framework for *optimizing* LLM programs — not a RAG pipeline framework. Lacks ingestion, chunking, and retrieval primitives. [Ollama can be connected via LiteLLM adapter](https://medium.com/@bravekjh/plug-dspy-into-ollama-or-openai-for-rag-inference-8a7de41c8ca3) but that is not its purpose.

**Verdict**: **NOT APPLICABLE.** Best used for advanced prompt optimization *alongside* another framework, not as a replacement.

---

### IBM InstructLab ✗ DISQUALIFIED (wrong category)

**License**: CC-BY-4.0 (content/taxonomy) + Apache 2.0 (software) — [source](https://instructlab.ai/)

InstructLab is a **model fine-tuning framework**, not a RAG framework. It helps LLMs learn new knowledge via synthetic data generation and community-contributed skill recipes. Evaluating it against LlamaIndex or Haystack is a category error.

**Verdict**: **DISQUALIFIED.** Does not solve retrieval, chunking, or vector indexing problems.

---

## 2. Vector Databases Evaluated [HIGH]

### LanceDB ✅ RECOMMENDED

**License**: Apache 2.0 — PERMITTED ([GitHub](https://github.com/lancedb/lancedb))  
**GitHub stars**: ~10,000 | **Embedded**: YES (fully in-process)

Embedded, serverless vector database built on the Lance columnar format (a Parquet successor). [Runs in-process — no server, no Docker, pure `pip install lancedb`](https://docs.lancedb.com/faq/faq-oss).

**Code RAG fit**: Excellent. LanceDB has published a [first-party tutorial on building RAG on codebases](https://www.lancedb.com/blog/building-rag-on-codebases-part-1) using tree-sitter + LanceDB as the reference architecture. The [CodeQA project (MIT)](https://github.com/sankalp1999/code_qa) uses this exact stack. Lance format delivers faster scans than Parquet with zero-copy versioning for incremental updates.

**Performance**: Handles larger-than-memory datasets via disk-based indexing. At ~15,000–36,000 chunks for a 180K LOC codebase (typical density), LanceDB's embedded mode handles this trivially. RTX 5090 and nomic-embed-code throughput will be the rate-limiting factor, not LanceDB write speed.

**Production maturity**: Suitable for millions of vectors on a single node. Younger ecosystem than Qdrant but growing fast.

**Verdict**: **RECOMMENDED.** Uniquely fits the "importable library, no service" constraint. Proven in code RAG. Apache 2.0.

---

### ChromaDB ✅ VIABLE

**License**: Apache 2.0 — PERMITTED ([GitHub](https://github.com/chroma-core/chroma))  
**GitHub stars**: ~27,400 | **Embedded**: YES (chromadb.Client() with persistence)

2025 Rust-core rewrite delivers 4x faster writes and queries. Extremely simple four-operation API — the easiest to learn. Can run fully embedded or as a separate server. [~27,400 GitHub stars, v1.5.7 (April 2026)](https://github.com/chroma-core/chroma).

**Code RAG fit**: Good for prototyping. No code-specific features. Scales for most code corpora under 10M vectors.

**Verdict**: **VIABLE ALTERNATIVE.** Simpler API than LanceDB, no code-specific optimization. Good for teams prioritizing API simplicity.

---

### Qdrant ✅ BEST FOR SCALE (but requires service)

**License**: Apache 2.0 — PERMITTED ([GitHub](https://github.com/qdrant/qdrant))  
**GitHub stars**: ~27,000 | **Embedded**: NO (Docker required for stable production use)

High-performance vector search engine written in Rust. [Used by TripAdvisor (1B+ reviews), OpenTable (60k+ restaurants), HubSpot Breeze AI](https://qdrant.tech/blog/2025-recap/). Sub-5ms queries on hundreds of millions of vectors. GPU-accelerated HNSW indexing added in 2025. [Well-documented Ollama integration](https://qdrant.tech/documentation/embeddings/ollama/).

**Verdict**: **BEST FOR SCALE but not the starting point.** Requires a separate Docker container, conflicting with the embedded-library preference. Natural upgrade path from LanceDB if the project outgrows single-server embedded operation.

---

### pgvector (PostgreSQL extension) 🔄 COMPELLING ALTERNATIVE

**License**: PostgreSQL License (permissive, similar to MIT) — PERMITTED ([GitHub](https://github.com/pgvector/pgvector))  
**Embedded**: NO but **uses existing PostgreSQL on port 5433 — no new infrastructure**

Adds vector similarity search to PostgreSQL using IVFFlat and HNSW indexes. [Python integration via SQLAlchemy + `pgvector` package](https://medium.com/@levi_stringer/rag-with-pg-vector-with-sql-alchemy-d08d96bfa293). Fits with the existing ORM patterns in IW AI Core.

**Performance**: [pgvector 0.8.0 delivers up to 5.7x improvement for specific patterns](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/). Adequate for ~100K–500K code chunks. [Scale limitations become significant at 2M+ vectors — benchmark vs production gap is real](https://thenewstack.io/why-pgvector-benchmarks-lie/).

**Code RAG fit**: Good for keeping all data in one database. Strong operational simplicity — everything in PostgreSQL.

**Key trade-off**: pgvector adds embedding workload (index builds, similarity queries) to the same DB instance that drives daemon polling, step tracking, and worktree state. Risk of latency spikes during indexing affecting operational queries.

**Verdict**: **COMPELLING if database sprawl is a hard constraint.** Zero new infrastructure (IW AI Core already runs PostgreSQL on port 5433). Adequate performance for the expected codebase sizes. Recommended to run on a separate PostgreSQL instance or schema to isolate embedding workload from operational state.

---

### Milvus Lite ✅ VALID

**License**: Apache 2.0 — PERMITTED ([GitHub](https://github.com/milvus-io/milvus))  
**GitHub stars**: ~35,000 | **Embedded**: YES (Milvus Lite via pip)

[Milvus Lite runs embedded in-process](https://github.com/milvus-io/milvus-lite) with the same API as full Milvus — enabling seamless scale-up to Docker/K8s when needed. Powers AI at NVIDIA, Meta, and Salesforce.

**Verdict**: **VALID ALTERNATIVE to LanceDB.** Clean graduation path from embedded to full cluster. LanceDB has a stronger code RAG story (dedicated tutorials, reference implementations), but Milvus Lite is a solid choice if future cluster-scale is a likely requirement.

---

### Weaviate ⚠ NOT RECOMMENDED (initially)

**License**: BSD-3-Clause — PERMITTED ([GitHub](https://github.com/weaviate/weaviate))  
**Embedded**: NO (Docker required)

Feature-rich: built-in hybrid search, reranking, multi-tenancy. Server-only topology, highest resource requirements. No code-specific features.

**Verdict**: **NOT RECOMMENDED for initial deployment.** Overkill for single-server code RAG. Good upgrade target if multi-tenant code search across many projects at scale is needed.

---

## 3. Full-Stack RAG Platforms Evaluated [HIGH]

All evaluated platforms are **applications, not libraries**. None can be imported into a FastAPI process. All require a separate service/container. None meet the "embedded-library preferred" constraint and none add code-RAG-specific value that LlamaIndex + LanceDB does not already provide.

| Platform | License | Verdict |
|---|---|---|
| **AnythingLLM** ([MIT](https://github.com/Mintplex-Labs/anything-llm)) | MIT | DISQUALIFIED — application, not library |
| **PrivateGPT** ([Apache 2.0](https://docs.privategpt.dev/)) | Apache 2.0 | DISQUALIFIED — application, not library |
| **RAGFlow** ([Apache 2.0](https://github.com/infiniflow/ragflow)) | Apache 2.0 | DISQUALIFIED — PDF/document focus, service-only |
| **Verba (Weaviate)** | BSD-3 | DISQUALIFIED — Weaviate-coupled, service-only |
| **Open-WebUI RAG** | MIT | NOT APPLICABLE — UI layer only |

None of these platforms meet the "service adds clear, substantial benefits" bar for this use case. They are designed for end-user document Q&A, not for programmatic API integration inside an existing Python service.

---

## 4. Build vs. Adopt Analysis [HIGH]

### Fully Custom Pipeline (direct Ollama + LanceDB + tree-sitter)

**Pros**: Maximum control, zero framework lock-in, minimal dependency surface, fully auditable, fits IW AI Core's explicit architecture philosophy.

**Cons**: Must implement retrieval logic, embedding batching, document management, and query interfaces from scratch. LlamaIndex's `CodeSplitter` + `VectorStoreIndex` + Ollama integration is exactly this pipeline — already written and tested.

**Estimated build effort**: 3–5 days for a correct, production-quality custom pipeline (AST-aware chunking, incremental indexing, Ollama embedding batching, query-time retrieval, result formatting).

### LlamaIndex (adopted framework)

**Pros**: `CodeSplitter` eliminates the hardest custom work (tree-sitter query grammar, language fallbacks). `VectorStoreIndex` + LanceDB integration is proven and maintained. Ollama integration tracks API changes. ~8 lines for basic pipeline vs ~200 lines custom. MIT license — can vendor or fork freely.

**Cons**: Adds ~48k lines of transitive dependency code. Implicit abstractions are less auditable than Haystack. LlamaIndex evolves quickly — pin versions in `pyproject.toml`.

### Verdict: Adopt LlamaIndex with thin custom wrapping

LlamaIndex occupies a sweet spot for this use case: it eliminates the hardest boilerplate (`CodeSplitter`, vector store management, embedding batching) while remaining thin enough that custom tree-sitter logic can be layered alongside it or replace its `CodeSplitter` for C++ parsing tuning. The MIT license means it can be vendored or modified freely. The custom pipeline path has no meaningful advantage over LlamaIndex + LanceDB when evaluated against actual implementation work required.

**The one scenario favoring a fully custom pipeline**: if LlamaIndex's abstractions create unacceptable debugging friction in a production incident. Valid long-term concern — not a reason to incur upfront build cost before the feature is proven.

---

## 5. Recommendation Matrix

### RAG Frameworks

| Dimension | LlamaIndex | Haystack | LangChain | Custom |
|---|---|---|---|---|
| License | MIT ✓ | Apache 2.0 ✓ | MIT ✓ | N/A |
| Ollama LLM support | YES (first-party) | YES (first-party) | YES | YES |
| Ollama embedding support | YES | YES | YES | YES |
| Built-in code chunker | **YES (tree-sitter)** | NO | NO | Manual |
| Vector DB flexibility | HIGH (10+) | HIGH (10+) | HIGHEST | Unlimited |
| FastAPI integration | Library import | Library import | Library import | Library import |
| LanceDB support | YES | YES | YES | YES (direct) |
| pgvector support | YES | YES | YES | YES |
| Framework latency | ~6 ms | ~5.9 ms | ~10 ms | ~0 |
| Learning curve | LOW | MEDIUM-HIGH | HIGH | HIGH (build) |
| Pipeline auditability | MEDIUM | **HIGH** | LOW | HIGH |
| GitHub stars | 48,600 | 24,800 | ~95,000+ | N/A |
| **Recommended team size** | **1–3** | 5+ | Any | Any |

### Vector Databases

| Dimension | LanceDB | ChromaDB | Qdrant | pgvector | Milvus Lite |
|---|---|---|---|---|---|
| License | Apache 2.0 ✓ | Apache 2.0 ✓ | Apache 2.0 ✓ | PG License ✓ | Apache 2.0 ✓ |
| Embedded (no server) | **YES** | **YES** | NO | NO (uses PG) | **YES** |
| Python API quality | GOOD | EXCELLENT | EXCELLENT | Via SQLAlchemy | GOOD |
| Code RAG fit | **EXCELLENT** | GOOD | GOOD | GOOD | GOOD |
| Disk-efficient large corpora | **EXCELLENT** (Lance) | GOOD | N/A (server) | GOOD | GOOD |
| Ollama compatible | YES | YES | YES | YES | YES |
| Filtered search | GOOD | BASIC | **EXCELLENT** | GOOD | GOOD |
| Production maturity | MEDIUM-HIGH | MEDIUM-HIGH | **VERY HIGH** | **VERY HIGH** | MEDIUM |
| No new service required | **BEST** | GOOD | POOR | GOOD (existing DB) | GOOD |

---

## 6. Final Recommendation

### Primary Stack: LlamaIndex + LanceDB + nomic-embed-code (via Ollama)

**RAG framework**: LlamaIndex (MIT)
```python
# Installation
uv add llama-index llama-index-llms-ollama llama-index-embeddings-ollama llama-index-vector-stores-lancedb

# Embedding backend (local)
from llama_index.embeddings.ollama import OllamaEmbedding
embed_model = OllamaEmbedding(model_name="manutic/nomic-embed-code", base_url="http://localhost:11434")

# LLM backend (local)
from llama_index.llms.ollama import Ollama
llm = Ollama(model="gemma4:26b", base_url="http://localhost:11434")

# Code chunking
from llama_index.core.node_parser import CodeSplitter
splitter = CodeSplitter(language="python", chunk_lines=40, chunk_lines_overlap=5)

# Vector store
from llama_index.vector_stores.lancedb import LanceDBVectorStore
store = LanceDBVectorStore(uri="~/.iw-ai-core/indexes/{project_id}/")
```

**Chunking notes**:
- Use `CodeSplitter` with `language="python"` for Python files
- Verify C++ grammar coverage in LlamaIndex's bundled tree-sitter version — write direct tree-sitter queries using [`tree-sitter-cpp`](https://github.com/tree-sitter/tree-sitter-cpp) if `CodeSplitter` produces poor results on template-heavy C++
- Store chunk metadata (file path, language, function name, class name) as filterable document metadata fields

**Vector database**: LanceDB (Apache 2.0)
- Fully embedded — no additional server or container
- Separate LanceDB tables per registered project
- Store on local SSD at `~/.iw-ai-core/indexes/{project_id}/`
- Index manifest (`manifest.json`) tracks per-file SHA for incremental re-indexing

**Integration pattern**: Implement as `orch/rag/` module — importable by both the daemon and the FastAPI dashboard. Extend `orch/config.py` with RAG-specific config.

**Provider config schema** (per-project):
```yaml
code_understanding:
  provider: local | claude-code | opencode
  ollama_url: http://localhost:11434
  llm_model: gemma4:26b           # balanced default
  embed_model: manutic/nomic-embed-code
  index_path: ~/.iw-ai-core/indexes/{project_id}/
  max_chunk_tokens: 512
  top_k_retrieval: 8
```

**Fallback**: If LlamaIndex abstractions prove too opaque in production incidents, the fallback is a fully custom pipeline: direct tree-sitter queries + direct Ollama HTTP calls for embeddings + LanceDB Python API directly. 3–5 day reimplementation with full control. LanceDB remains the vector store in both paths.

**Do not adopt**:
- Qdrant, Weaviate, full Milvus (require separate services — violates embedded-library preference)
- pgvector on the existing port-5433 operational DB (adds embedding workload to daemon-critical database)
- AnythingLLM, PrivateGPT, RAGFlow (applications, not libraries)

---

## 7. Limitations

1. **nomic-embed-code Ollama status**: The `manutic/nomic-embed-code` model on Ollama is a community upload. Verify it matches the official Nomic AI release and produces correct embedding dimensions before production use. Alternative: call nomic-embed-code via `sentence-transformers` directly. `qwen3-embedding:8b` (official Ollama library) is the safe fallback.

2. **LlamaIndex C++ chunking quality**: `CodeSplitter`'s C++ grammar quality has not been independently benchmarked. Tree-sitter's C++ grammar is mature (used in editors), but LlamaIndex's bundled grammar version should be verified on template-heavy C++ code before relying on it.

3. **LanceDB HNSW index build times**: Not benchmarked for a cold full re-index of a ~180K LOC codebase. Expected: 15,000–36,000 chunks at typical code density — well within LanceDB's embedded capabilities. RTX 5090 + nomic-embed-code embedding throughput will be the bottleneck, not LanceDB.

4. **LlamaIndex version stability**: History of breaking API changes between minor versions. Pin dependency version in `pyproject.toml` and lock with `uv lock`.

5. **pgvector as alternative**: If database sprawl is a hard constraint, pgvector on a separate PostgreSQL schema (not port 5433 operational DB) is a valid alternative to LanceDB. Not prototyped in this research.

---

## 8. Sources

| # | Title | Credibility | URL | License |
|---|---|---|---|---|
| 1 | LlamaIndex Ollama LLM Integration Docs | HIGH (official) | [developers.llamaindex.ai](https://developers.llamaindex.ai/python/framework/integrations/llm/ollama/) | MIT |
| 2 | llama-index-llms-ollama PyPI | HIGH (official) | [pypi.org](https://pypi.org/project/llama-index-llms-ollama/) | MIT |
| 3 | llama-index-embeddings-ollama PyPI | HIGH (official) | [pypi.org](https://pypi.org/project/llama-index-embeddings-ollama/) | MIT |
| 4 | LlamaIndex CodeSplitter API Reference | HIGH (official) | [developers.llamaindex.ai](https://developers.llamaindex.ai/python/framework-api-reference/node_parsers/code/) | MIT |
| 5 | Haystack Ollama Integration | HIGH (official) | [haystack.deepset.ai](https://haystack.deepset.ai/integrations/ollama) | Apache 2.0 |
| 6 | Haystack Integrations (all) | HIGH (official) | [haystack.deepset.ai](https://haystack.deepset.ai/integrations) | Apache 2.0 |
| 7 | LlamaIndex vs Haystack Comparison | MEDIUM | [myengineeringpath.dev](https://myengineeringpath.dev/tools/llamaindex-vs-haystack/) | N/A |
| 8 | Morphik OSS RAG Guide 2025 | MEDIUM | [morphik.ai](https://www.morphik.ai/blog/guide-to-oss-rag-frameworks-for-developers) | N/A |
| 9 | LangChain Complexity Discussion | MEDIUM (community) | [github.com](https://github.com/orgs/community/discussions/182015) | N/A |
| 10 | LanceDB GitHub | HIGH (official) | [github.com/lancedb/lancedb](https://github.com/lancedb/lancedb) | Apache 2.0 |
| 11 | LanceDB FAQ OSS | HIGH (official) | [docs.lancedb.com](https://docs.lancedb.com/faq/faq-oss) | Apache 2.0 |
| 12 | Building RAG on Codebases (LanceDB Part 1) | HIGH (official) | [lancedb.com/blog](https://www.lancedb.com/blog/building-rag-on-codebases-part-1) | N/A |
| 13 | CodeQA (tree-sitter + LanceDB reference impl) | MEDIUM (community) | [github.com/sankalp1999/code_qa](https://github.com/sankalp1999/code_qa) | MIT |
| 14 | ChromaDB GitHub | HIGH (official) | [github.com/chroma-core/chroma](https://github.com/chroma-core/chroma) | Apache 2.0 |
| 15 | Qdrant GitHub | HIGH (official) | [github.com/qdrant/qdrant](https://github.com/qdrant/qdrant) | Apache 2.0 |
| 16 | Qdrant 2025 Recap | HIGH (official) | [qdrant.tech/blog](https://qdrant.tech/blog/2025-recap/) | Apache 2.0 |
| 17 | Qdrant + Ollama Integration Docs | HIGH (official) | [qdrant.tech/documentation](https://qdrant.tech/documentation/embeddings/ollama/) | Apache 2.0 |
| 18 | Vector Database Comparison 2026 | MEDIUM | [4xxi.com](https://4xxi.com/articles/vector-database-comparison/) | N/A |
| 19 | Milvus Lite GitHub | HIGH (official) | [github.com/milvus-io/milvus-lite](https://github.com/milvus-io/milvus-lite) | Apache 2.0 |
| 20 | pgvector GitHub | HIGH (official) | [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector) | PG License |
| 21 | pgvector 0.8.0 Performance — AWS | HIGH (official) | [aws.amazon.com](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/) | N/A |
| 22 | Why pgvector Benchmarks Lie | MEDIUM | [thenewstack.io](https://thenewstack.io/why-pgvector-benchmarks-lie/) | N/A |
| 23 | AnythingLLM GitHub | HIGH (official) | [github.com/Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm) | MIT |
| 24 | PrivateGPT LLM Backends Docs | HIGH (official) | [docs.privategpt.dev](https://docs.privategpt.dev/manual/advanced-setup/llm-backends) | Apache 2.0 |
| 25 | RAGFlow LICENSE | HIGH (official) | [github.com/infiniflow/ragflow](https://github.com/infiniflow/ragflow/blob/main/LICENSE) | Apache 2.0 |
| 26 | InstructLab official site | HIGH (official) | [instructlab.ai](https://instructlab.ai/) | CC-BY-4.0 / Apache 2.0 |
| 27 | nomic-embed-code on Ollama | MEDIUM (community) | [ollama.com/manutic/nomic-embed-code](https://ollama.com/manutic/nomic-embed-code) | N/A |
| 28 | LlamaIndex review 2025 — sider.ai | MEDIUM | [sider.ai](https://sider.ai/blog/ai-tools/llamaindex-review-2025-is-it-the-best-rag-framework-for-production-ai) | N/A |
