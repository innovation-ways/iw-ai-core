# F-00060: Hybrid Code Q&A retrieval — semantic + FTS + git-log

**Type**: Feature
**Priority**: High
**Created**: 2026-04-23
**Status**: Draft

---

## Description

The Code view's `answer_stream_v2` in `orch/rag/qa.py` today classifies questions as `workitem_aware` vs `code_only`, fires phase events, and then calls three stub functions that return empty data — the LLM ultimately sees only code chunks, never design-doc context. This feature replaces the stubs with a real **hybrid retriever** that combines three signals: semantic similarity over a new LanceDB `docs_{project_id}` table (indexed from the `functional_doc_content` column F-00059 adds), PostgreSQL FTS over `functional_doc_search`, and the existing `git_log_resolver` that maps code files to work-item IDs. Candidates are merged and ranked; the top 3 get their full functional doc injected into the LLM's system prompt, candidates 4–8 get title + summary + best-matched chunk, and the LLM is explicitly instructed to cite only items whose reasoning addresses the question. The emitted citations pass through the already-present-but-unused `citation_allowlist.filter_citations` so IDs the LLM never mentions are dropped, and citation snippets prefer `functional_doc_content[:300]` over `summary`. A sibling background job — `doc_index_jobs` + `DocIndexJobRunner` + a daemon poller — keeps the vector index fresh and exposes itself in the unified Jobs view alongside `code_index_jobs`, with a "Re-index Docs" button on the Code view.

## Project Context

Read `CLAUDE.md`, `orch/CLAUDE.md`, `orch/rag/CLAUDE.md`, `dashboard/CLAUDE.md`, and `tests/CLAUDE.md` for the RAG pipeline shape, daemon polling conventions, LanceDB layout, htmx patterns, and testcontainer rules.

## Scope

### In Scope

- New `doc_index_jobs` table modelled 1:1 on `code_index_jobs` (same status enum, same counters, same indexes).
- New `DocIndexer` class (`orch/rag/doc_indexer.py`) that embeds `work_items.functional_doc_content` into a LanceDB table `docs_{project_id}` via Ollama + LlamaIndex `SentenceSplitter`, with an `updated_at` watermark so re-indexing only re-embeds changed rows.
- New `DocIndexJobRunner` (asyncio, pattern-matched to `CodeIndexJobRunner`) + `JOB_REGISTRY` guard against concurrent runs per project.
- New daemon poller `orch/daemon/doc_index_poller.py` with 10-min stall detection, orphan recovery on daemon boot, and `MAX_CONCURRENT_JOBS_PER_PROJECT=1` for this job type.
- Implementation of `_retrieve_evidence_bundle`, `_fetch_full_work_items`, and `_build_workitem_system_prompt` in `orch/rag/qa.py`; extension of `_merge_and_rank_work_items` to blend semantic scores with the existing FTS + git-log scores.
- Semantic retrieval: cosine top-K=20 over `docs_{project_id}`, grouped by `work_item_id`.
- FTS retrieval: `functional_doc_search @@ plainto_tsquery('english', question)` with `ts_rank`, top-K=20.
- Git-log retrieval: reuse `git_log_resolver` over the file paths of the code chunks already retrieved by the code-RAG path.
- Merge + rank: dedupe by `work_item_id`, sum normalised scores (α=0.45 FTS, γ=0.35 semantic, β=0.20 git-log; weights sum to 1.0), cap at N=8.
- Prompt layout: `_build_workitem_system_prompt` emits a *Work Item Context* section appended to the existing system prompt; top-3 candidates include full `functional_doc_content` truncated to ~3000 tokens; candidates 4–8 include only title + summary + best-matched chunk. Explicit relevance-filter instruction.
- Citation allowlist: pipe the LLM's streamed output through `citation_allowlist.filter_citations(text, bundle.allowed_ids)` before emitting citation events to the UI; only IDs the LLM mentioned survive.
- Citation snippet: use `item.functional_doc_content[:300]` when non-NULL, falling back to `item.summary` otherwise.
- Jobs aggregator: add `JobType.doc_indexing` and `_fetch_doc_indexing()` so the unified Jobs view surfaces doc-index jobs alongside code-index jobs.
- API endpoint: `POST /project/{project_id}/api/code/reindex-docs` enqueues a `DocIndexJob`.
- Frontend: "Re-index Docs" button added to the existing action dropdown on the Code view; progress fragment reused from `code_job_status.html` (extended to render both job types).
- Tests: integration for the job lifecycle + crash-recovery + indexer watermark idempotency + retriever top-N + allowlist + jobs-aggregator; unit for prompt layout, citation snippet fallback, merge-rank math, FTS query shape.

### Out of Scope

- Any change to `code_index_jobs`, the code indexer, or the `code_only` Q&A branch.
- Embedding of `design_doc_content` (technical docs) into LanceDB — functional docs are the only semantic surface; technical docs remain FTS-only via the existing `design_doc_search`.
- Streaming progress to the browser for doc-index jobs beyond the existing Jobs-view polling.
- Cross-project retrieval. Each project's doc index is isolated.
- Auto-triggering `DocIndexJob` on `iw approve` or post-merge hooks — that is a follow-up; V1 is manual re-index button + any operator invocation.
- Changing the classifier or its slash-override set (`why`, `history`, `findusages`).
- A new metrics/eval dashboard — the eval fixture lives as a test, not a UI.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | `doc_index_jobs` table + ORM `DocIndexJob` + Alembic migration (up/down) mirroring `code_index_jobs` exactly; add indexes `idx_doc_index_jobs_project_id` and `idx_doc_index_jobs_status` | — |
| S02 | backend-impl | `orch/rag/doc_indexer.py` (`DocIndexer` class: LanceDB table `docs_{project_id}`, SentenceSplitter, OllamaEmbedding from `CodeUnderstandingConfig`, upsert by `(work_item_id, chunk_index)` keyed on `updated_at` watermark); `orch/rag/doc_job.py` (`DocIndexJobRunner` async, `JOB_REGISTRY` guard, progress counters into `doc_index_jobs`); extend `orch/jobs/aggregator.py` with `JobType.doc_indexing` and `_fetch_doc_indexing()` | — (after S01) |
| S03 | backend-impl | `orch/rag/qa.py`: implement `_retrieve_evidence_bundle` (semantic+FTS+git-log), `_fetch_full_work_items` (load full rows with `functional_doc_content` included), extend `_merge_and_rank_work_items` to rebalance the blend to α=0.45 FTS / γ=0.35 semantic / β=0.20 git-log (sums to 1.0), add `_build_workitem_system_prompt` that appends the Work Item Context section to the existing system prompt, update citation emission at `qa.py:383–391` to use `functional_doc_content[:300]` when non-NULL, wire `citation_allowlist.filter_citations` into the streamed-output pipeline so only LLM-mentioned IDs emit citation events | — (after S02) |
| S04 | pipeline-impl | `orch/daemon/doc_index_poller.py` (mirrors `DocJobPoller` — stall timeout 600 s, `MAX_CONCURRENT_JOBS_PER_PROJECT=1`, orphan recovery on daemon boot that marks running → error with `error_message='orphaned by daemon restart'`); register the poller in `orch/daemon/main.py` alongside the existing pollers | S05 (after S03) |
| S05 | api-impl | `POST /project/{project_id}/api/code/reindex-docs` in `dashboard/routers/code_ui.py` that inserts a `doc_index_jobs` row and returns the htmx fragment for the Jobs row; respects existing authorization guard; returns 409 if a doc-index job for the project is already `running` | S04 (after S03) |
| S06 | frontend-impl | Add "Re-index Docs" entry to the Code-view action dropdown in `dashboard/templates/project_code.html` (around lines 38–73); the dropdown item points `hx-post` at the new endpoint; reuse `fragments/code_job_status.html` for progress (parameterise by `job_type` if needed) | — (after S05) |
| S07 | tests-impl | Integration: doc-index job queued→running→completed; killing the runner mid-write leaves partial LanceDB data and re-queue resumes from `updated_at` watermark; orphan-recovery on daemon boot; indexer idempotency; retriever returns expected top-N for seeded docs; allowlist strips IDs the LLM did not mention; citation snippet fallback (null functional doc → summary); jobs-aggregator returns doc-index rows; POST endpoint creates a job and the poller picks it up. Unit: prompt layout (top-3 full vs 4–8 chunk; relevance-filter instruction present); merge-rank math with α/β/γ; FTS query shape; citation-allowlist wiring | — (after S04–S06) |
| S08 | code-review-final-impl | Global cross-layer review: DB/ORM symmetry vs `code_index_jobs`, retrieval↔indexing contract, prompt-budget discipline (token count check), LanceDB URI isolation (`code_*` untouched), daemon orphan recovery, jobs-aggregator symmetry, AC1..AC6 coverage, no regressions to `code_only` | — |
| S09 | qv-gate | `make lint` | — |
| S10 | qv-gate | `uv run ruff format --check .` | — |
| S11 | qv-gate | `make typecheck` | — |
| S12 | qv-gate | `make test-unit` | — |
| S13 | qv-gate | `make test-integration` (timeout 900) | — |
| S14 | qv-browser | End-to-end: click "Re-index Docs" → job appears and completes in the Jobs view; ask a workitem-aware question in Code view → answer narrative references functional-doc reasoning; citations filtered by allowlist; `code_only` path regression check (ask a "show me the signature" question and confirm it behaves unchanged) | — |

### Database Changes

- **New tables**: `doc_index_jobs`.
- **Modified tables**: None.
- **Migration notes**: Alembic revision is a structural clone of the last migration that added `code_index_jobs`. Downgradeable. No FTS trigger. No new PG enums (status is TEXT, same as `code_index_jobs`).

`doc_index_jobs` columns (exactly mirrors `code_index_jobs`):

- `id` TEXT PRIMARY KEY (UUID as TEXT)
- `project_id` TEXT FK → `projects.id`, NOT NULL, `ON DELETE CASCADE`
- `status` TEXT NOT NULL DEFAULT `queued` — values `queued | running | completed | failed | cancelled`
- `provider` TEXT NOT NULL DEFAULT `local`
- `llm_model`, `embed_model`, `index_tier` TEXT NULL
- `items_discovered`, `items_indexed`, `chunks_created` INT NOT NULL DEFAULT 0
- `errors` JSONB NOT NULL DEFAULT `[]`
- `triggered_at` TIMESTAMPTZ NOT NULL DEFAULT `NOW()`
- `started_at`, `completed_at` TIMESTAMPTZ NULL
- `error_message` TEXT NULL
- Indexes: `idx_doc_index_jobs_project_id`, `idx_doc_index_jobs_status`

Column names adopt `items_*` instead of `files_*` to match the doc domain; otherwise the shape is identical.

### API Changes

- **New endpoints**:
  - `POST /project/{project_id}/api/code/reindex-docs` — enqueues a `DocIndexJob`. Returns 200 with an htmx fragment containing the newly-queued job row. Returns 409 with a fragment surfacing "already running" if one exists.
- **Modified endpoints**: None — the Q&A endpoint signature is unchanged; only the `workitem_aware` branch internals change.

### Frontend Changes

- **New templates**: None strictly new — the progress fragment `fragments/code_job_status.html` is extended (parameterised) to render doc-index jobs as well.
- **Modified templates**:
  - `dashboard/templates/project_code.html` — new dropdown item "Re-index Docs".
  - `dashboard/templates/fragments/code_job_status.html` — render `job_type` row label.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00060/F-00060_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00060/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00060/prompts/F-00060_S01_Database_prompt.md` | Prompt | S01 |
| `ai-dev/active/F-00060/prompts/F-00060_S02_Backend_prompt.md` | Prompt | S02 (indexing) |
| `ai-dev/active/F-00060/prompts/F-00060_S03_Backend_prompt.md` | Prompt | S03 (retrieval) |
| `ai-dev/active/F-00060/prompts/F-00060_S04_Pipeline_prompt.md` | Prompt | S04 |
| `ai-dev/active/F-00060/prompts/F-00060_S05_API_prompt.md` | Prompt | S05 |
| `ai-dev/active/F-00060/prompts/F-00060_S06_Frontend_prompt.md` | Prompt | S06 |
| `ai-dev/active/F-00060/prompts/F-00060_S07_Tests_prompt.md` | Prompt | S07 |
| `ai-dev/active/F-00060/prompts/F-00060_S08_CodeReview_Final_prompt.md` | Prompt | S08 |
| `ai-dev/active/F-00060/prompts/F-00060_S14_BrowserVerification_prompt.md` | Prompt | S14 |

**Source files created / modified**:

- `orch/db/models.py` (modified — `DocIndexJob` class)
- `orch/db/migrations/versions/{hash}_add_doc_index_jobs.py` (new)
- `orch/rag/doc_indexer.py` (new)
- `orch/rag/doc_job.py` (new — `DocIndexJobRunner` + `JOB_REGISTRY` guard for doc jobs)
- `orch/rag/qa.py` (modified — three stubs implemented, prompt builder, citation snippet, allowlist wire-in)
- `orch/rag/evidence.py` (no change expected — `DocChunk` and `allowed_ids` already present)
- `orch/daemon/doc_index_poller.py` (new)
- `orch/daemon/main.py` (modified — register poller)
- `orch/jobs/aggregator.py` (modified — new `JobType.doc_indexing` + `_fetch_doc_indexing()`)
- `dashboard/routers/code_ui.py` (modified — new endpoint)
- `dashboard/templates/project_code.html` (modified — new dropdown item)
- `dashboard/templates/fragments/code_job_status.html` (modified — `job_type` rendering)
- `tests/integration/test_doc_index_job_lifecycle.py` (new)
- `tests/integration/test_doc_indexer.py` (new)
- `tests/integration/test_qa_v2_hybrid_retrieval.py` (new)
- `tests/integration/test_jobs_aggregator_doc_index.py` (new)
- `tests/integration/test_reindex_docs_endpoint.py` (new)
- `tests/unit/test_qa_v2_prompt_layout.py` (new)
- `tests/unit/test_qa_v2_citation_snippet.py` (new)
- `tests/unit/test_qa_v2_merge_rank.py` (new)
- `tests/unit/test_qa_v2_allowlist_wiring.py` (new)

Reports are created during execution in `ai-dev/active/F-00060/reports/`.

## Acceptance Criteria

### AC1: Full project re-index completes and surfaces in Jobs view

```
Given   iw-ai-core has ~60 work items with populated functional_doc_content (via F-00059 backfill)
When    an operator clicks "Re-index Docs" on the Code view
Then    a doc_index_jobs row transitions queued → running → completed within 10 minutes on local Ollama
And     the row appears in the unified /jobs view with job_type='doc_indexing' and the correct project_id
And     items_indexed >= 60 and chunks_created > 0 on completion
```

### AC2: Originating-item question cites and incorporates the design

```
Given   CR-00011 created the "New project" button (as reflected in git-log Merge CR-00011: commits)
And     CR-00011.functional_doc_content is populated with the reasoning
When    a user asks "when was the New project button created? What does it do?" in the Code view
Then    the streamed answer cites CR-00011 and narrates its functional-doc reasoning in prose
And     no unrelated work-item ID appears in the citation list
And     the citation snippet for CR-00011 is drawn from its functional_doc_content, not its summary
```

### AC3: Relevance filter drops off-topic items

```
Given   a button was introduced by F-A, recoloured blue by CR-B, and reshaped from circle to square by CR-C
And     git-log reports all three items for the file containing the button
When    a user asks "why is button X blue?" in the Code view
Then    the streamed answer cites CR-B only
And     the emitted citation events do NOT include F-A or CR-C
And     CR-C's shape-change reasoning is not paraphrased in the answer
```

### AC4: Backfill gap does not crash the retriever

```
Given   a candidate work item I-00099 with functional_doc_content = NULL (not yet backfilled)
When    the hybrid retriever assembles the bundle and sends context to the LLM
Then    I-00099 is included with title + summary + git-log signal only (no functional doc section)
And     no exception is raised anywhere in the pipeline
And     the citation snippet for I-00099 falls back to item.summary
```

### AC5: Citation allowlist gates emission

```
Given   the retriever produces a bundle with allowed_ids = {F-00042, CR-00011, I-00033}
And     the LLM's streamed response mentions only CR-00011 by name
When    the SSE citation events are emitted
Then    only one citation event is emitted and its work_item_id is CR-00011
And     F-00042 and I-00033 are NOT emitted as citations
And     any additional IDs hallucinated by the LLM that are not in allowed_ids are dropped
```

### AC6: DocIndexJob is crash-recoverable

```
Given   a DocIndexJob is status='running' and has written chunks_created=120 so far
When    the daemon process is killed (SIGKILL) and restarted
Then    the poller's orphan-recovery marks the job status='failed' with error_message='orphaned by daemon restart'
And     re-queuing a new job for the same project resumes from the updated_at watermark
And     already-embedded work_items (those whose updated_at is older than the watermark) are NOT re-embedded
```

## Boundary Behavior

Every row becomes a mandatory test case.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Retriever invoked on a project with zero work items | `work_items` table empty for project | Bundle is empty; retriever returns without error; answer falls back to code-only context with a single "no work-item context available" note |
| Semantic index not yet built | `docs_{project_id}` table missing in LanceDB | Retriever treats semantic contribution as empty; FTS + git-log still return candidates; answer proceeds |
| LanceDB query fails (corrupt segment) | Simulated I/O error | Retriever logs + treats semantic contribution as empty; FTS + git-log carry the answer; no exception propagates to the SSE stream |
| Code chunks have no files in common with any work item | git-log resolver returns `{}` | Bundle has empty `git_log_items`; FTS + semantic fill the top-N |
| Same work item appears in all three sources | Deduping by work_item_id | Single row in merged list; scores summed |
| LLM hallucinates a fabricated ID like `F-99999` | Not in `bundle.allowed_ids` | `citation_allowlist.filter_citations` strips it from the text AND does not emit a citation event |
| LLM answers without citing any work item | Empty intersection with allowed_ids | Zero citation events emitted; answer streams normally |
| Concurrent re-index request | A `doc_index_jobs` row for the project is already `running` | POST endpoint returns 409; no second row inserted |
| Re-index after a partial failure | Previous job ended in `failed` | New job starts from scratch (not from watermark) — operator explicitly asked for a full reindex |
| Reindex when every item is unchanged | All `updated_at` older than last index's watermark | `items_indexed=0`, `chunks_created=0`, job completes in seconds |
| Embed model change between runs | `embed_model` differs from the stored value | Current job drops the old table and re-embeds everything (same policy as `code_index_jobs`) |
| Daemon kill mid-embedding | Runner holding an open LanceDB writer | On restart, orphan-recovery sets status=`failed`, error_message includes 'orphaned' |
| Question length > context window | Very long question + 3 full docs | System prompt truncates docs before context history; never drops the question itself |
| `functional_doc_content` contains HTML tags or control chars | Unusual payload | Indexer sanitises text before embedding (strip NULs); prompt injection protection is out of scope (the content is operator-authored) |

## Invariants

1. The `code_only` branch of `answer_stream` is never entered from the new retriever path and is byte-for-byte unchanged by this feature.
2. `code_index_jobs` rows are never inserted, updated, or queried by any new code in this feature — the two job types are strictly independent tables.
3. For every citation event emitted on the SSE stream, the `work_item_id` is a member of `bundle.allowed_ids` (enforced by `citation_allowlist.filter_citations`).
4. The `docs_{project_id}` LanceDB table never holds rows for work items belonging to any other project.
5. `DocIndexJob.status` transitions are monotonic: `queued → running → {completed, failed, cancelled}`; no regressions.
6. On daemon boot, every `running` `doc_index_jobs` row older than the boot time is transitioned to `failed` with an "orphaned" `error_message` before any new polling begins.
7. The system prompt contains at most 3 full functional-doc bodies + 5 chunk snippets; this is asserted in a unit test.

## Dependencies

- **Depends on**: F-00059 (the `functional_doc_content` column + `functional_doc_search` TSVECTOR must exist and ideally be populated for meaningful retrieval).
- **Blocks**: None.

## TDD Approach

**Unit tests**:
- Prompt-layout assembly: given a bundle with 8 candidates, assert top-3 include full doc, 4–8 include only chunk, and the relevance-filter instruction string is present.
- Citation-snippet fallback: functional doc populated → snippet sliced from functional; NULL → falls back to summary.
- Merge-rank math: mocked semantic + FTS + git-log inputs, assert final ordering with α=0.45 FTS / γ=0.35 semantic / β=0.20 git-log (sum=1.0).
- Allowlist wire-in: mocked LLM stream emits text with known IDs, assert final emitted citations match the intersection with allowed_ids.
- FTS query shape: inspect the SQLAlchemy SQL generated for the `functional_doc_search @@ plainto_tsquery(...)` path.

**Integration tests** (Postgres testcontainer + LanceDB temp dir):
- DocIndexJob lifecycle: enqueue → poller runs → status=completed → counters populated.
- Crash-recovery: simulate runner death by raising inside the asyncio task; assert orphan-recovery marks `failed` on next poll.
- Indexer idempotency: run twice with no `updated_at` changes → second run `items_indexed=0`.
- Indexer watermark: bump `updated_at` on one item → second run re-embeds exactly one item.
- Hybrid retriever end-to-end: seed 10 items with known content, ask a question known to match item X, assert X is rank-1.
- Jobs aggregator: after inserting a `doc_index_jobs` row, `JobsAggregator.list_jobs()` contains it with the right `JobType`.
- POST endpoint: returns 200 + htmx fragment; second request while first is running returns 409.

**Browser tests** (S14 qv-browser):
- Click re-index button → job appears in Jobs view and completes.
- Ask workitem-aware question → answer cites only LLM-mentioned items; snippet text matches functional doc.
- Ask `code_only` question → answer behaviour unchanged (regression guard).

**Edge cases**: every Boundary Behavior row gets at least one test.

## Notes

- **Prompt budget**: 3 × ~3K tokens (top-3 full docs) + 5 × ~500 tokens (chunk snippets) = ~10K tokens for the Work Item Context section, plus the existing system prompt (~2K), plus conversation history (≤5 turns, ~2K) = ~14K total. Local Ollama context is typically 8K; we set `num_ctx=16384` via the config path already used by the code-only branch. If the model still truncates, `_build_workitem_system_prompt` drops from the tail of candidates 8 → 4 before touching the full top-3.
- **Tokeniser**: approximate via `len(text) // 4` for the budget check (matches the existing code-index chunker heuristic). Exact tokenisation is not worth the dependency.
- **LanceDB schema**: columns `work_item_id` (TEXT), `work_item_type` (TEXT), `work_item_title` (TEXT), `chunk_index` (INT), `text` (TEXT), `embedding` (FloatArray). Primary retrieval key is `(work_item_id, chunk_index)` for upsert; scoring returns cosine distance which we invert to a similarity score in `[0, 1]` for the merge-rank blend.
- **Normalisation for merge-rank**: divide each source's scores by its own max (within the result set) before applying α/β/γ so mixing FTS `ts_rank` (unbounded) with cosine similarity is sane.
- **Git-log scope**: the resolver is run over the file paths already fetched by the code-RAG step — it is NOT a second `git log` traversal of the whole repo. This reuses the existing work and bounds I/O.
- **Manual trigger only (V1)**: `DocIndexJob` is not auto-enqueued on `iw approve` or post-merge. Operators run the button or a CLI (follow-up). The retriever must tolerate a stale index; semantic becomes empty for un-indexed items and FTS + git-log carry the answer.
- **No changes to classifier**: `classify_query` routing is unchanged. Slash chips `/why`, `/history`, `/findusages` still force `workitem_aware`.
- **Browser evidence pre-state**: deferred — the dashboard is not running against this worktree. Post-state captured by S14 into `evidences/post/`.
