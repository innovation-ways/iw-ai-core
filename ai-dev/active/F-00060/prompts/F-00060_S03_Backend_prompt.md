# F-00060_S03_Backend_prompt

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S03 — RAG retrieval layer
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Same rules as S01.

---

## Input Files

- `ai-dev/active/F-00060/F-00060_Feature_Design.md` — see *Scope*, *AC2–AC5*, *Boundary Behavior*, *Invariants*, *Notes / Prompt budget*
- `ai-dev/active/F-00060/reports/F-00060_S02_Backend_report.md` — confirms DocIndexer + LanceDB table shape
- `orch/rag/qa.py` — current stubs at lines 315, 324, 327, 330 and citation emission at 383–391
- `orch/rag/evidence.py` — `EvidenceBundle`, `DocChunk`, `allowed_ids` property
- `orch/rag/citation_allowlist.py` — `filter_citations(text, allowed_ids)` and `extract_citations(text)`
- `orch/rag/git_log_resolver.py` — existing resolver (merge-pattern regex over `git log --follow --oneline`)
- `orch/rag/classifier.py` — unchanged; do not modify
- `orch/db/models.py` — `WorkItem` with new `functional_doc_*` columns (F-00059) and existing `design_doc_search`

## Output Files

- `ai-dev/active/F-00060/reports/F-00060_S03_Backend_report.md` (new)
- `orch/rag/qa.py` (modified — stubs implemented; prompt builder; citation snippet; allowlist wire-in)

## Context

This step makes the work-item-aware branch of `answer_stream_v2` actually
work. It consumes the LanceDB table + `DocIndexer` from S02, the
`functional_doc_*` columns from F-00059, and the existing `git_log_resolver`
and `citation_allowlist`.

## Requirements

### 1. Implement `_retrieve_evidence_bundle`

Replace the stub at `qa.py:315`. Populate all four collections on the
`EvidenceBundle` return value:

- `doc_chunks`: semantic top-K=20 over `docs_{project_id}`. Query with
  `OllamaEmbedding.get_query_embedding(question)`; LanceDB
  `.search(vector).limit(20).to_pandas()`. Build one `DocChunk` per row with
  score inverted to `1 - cosine_distance` so higher = better.
- `fts_items`: `functional_doc_search @@ plainto_tsquery('english', question)`
  ordered by `ts_rank(...)` DESC, limit 20. Pattern mirrors
  `dashboard/routers/search.py:59–71`.
- `git_log_items`: call
  `git_log_resolver.resolve_work_items_for_files([chunk.file_path for chunk in code_chunks])`.
  Flatten to a unique list of WorkItem rows (use a single SELECT by
  composite-key).
- `code_chunks`: already populated by the caller; pass through.

### 2. Implement `_fetch_full_work_items`

Replace the stub at `qa.py:324`. Given a list of partial WorkItem rows
(maybe already in session), ensure each row has `functional_doc_content`,
`summary`, `title`, `type`, and `id` loaded. If any are detached, re-attach
or re-query by composite primary key `(project_id, id)` in a single
`WHERE (project_id, id) IN (...)` query.

### 3. Extend `_merge_and_rank_work_items`

The existing function blends FTS and git-log. Rebalance to include a third
contribution from `bundle.doc_chunks` grouped by `work_item_id`, and adjust
the weights so they sum to 1.0 (convex blend):

- For each `work_item_id`, take the max chunk score as the item's semantic
  score.
- Normalise each source's scores by dividing by that source's max so the
  blend with unbounded `ts_rank` is sane.
- Final score: `0.45 * fts_norm + 0.35 * semantic_norm + 0.20 * git_log_norm`
  (α=0.45, γ=0.35, β=0.20; α+γ+β=1.0).
- Update the existing α/β constants in place — do not leave α=0.5 / β=0.3
  behind as dead code.
- Cap the returned list at N=8 items.

### 4. Implement `_build_workitem_system_prompt`

Replace the stub at `qa.py:330`. Produce a string to append to the existing
system prompt. Structure:

```
## Work Item Context

The following work items may be related to the user's question. Decide
which ones actually address it. Cite only the items whose reasoning answers
the question. If an item touched related code but does not address the
question (for example, it changed shape while the user asked about
colour), omit it from your citations.

### Candidate 1: <ID> — <title> (<type>)
<full functional_doc_content, truncated to ~3000 tokens / ~12000 chars>

### Candidate 2: <ID> — <title> (<type>)
...

### Candidate 3: <ID> — <title> (<type>)
...

### Additional candidates (summary only)

- <ID> — <title>: <summary or functional_doc_content[:200]>
  Matched excerpt: "<best-matched chunk text, first 300 chars>"
- <ID> — <title>: ...
- ...
```

Rules:

- Top 3 of the merged list get the full functional doc. Truncate at 12 000
  chars; append `…` if truncated.
- Candidates 4–8 get the compact form above.
- If an item has `functional_doc_content == NULL`, it is **demoted to the
  compact form** regardless of its merge-rank position (even if it would
  otherwise be in the top-3). The full-doc block is omitted for that item,
  and its compact-form summary falls back to `item.summary` (AC4). The
  item is NOT dropped from the context entirely — title + summary + its
  git-log / FTS signal still reach the LLM.
- Token budget enforcement: before returning, estimate total chars; if
  over 56 000 (~14 K tokens), drop candidates from position 8 backward one
  at a time until under budget, then (only if still over) drop the full-doc
  top-3 to compact form as a last resort.
- Always include the relevance-filter instruction verbatim as the top of
  the block.

Integrate the returned string into the existing `_build_system_prompt` by
appending before the "Relevant Code Excerpts" section (or wherever the code
context sits today — place it immediately above).

### 5. Update citation snippet

At `qa.py:383–391`, change the snippet source:

```python
snippet = (item.functional_doc_content or "")[:300].strip() or (item.summary or "")
```

### 6. Wire `citation_allowlist.filter_citations`

The LLM's streamed output must be passed through `filter_citations` before
citation events are emitted:

1. Accumulate the streamed answer text in a buffer.
2. When streaming completes (or on chunks if feasible), call
   `extract_citations(accumulated_text)` → set of IDs the LLM actually
   named.
3. For each candidate item in `full_items[:5]`, emit a citation event only
   if `item.id` is in both `bundle.allowed_ids` (true by construction) AND
   the extracted set from the LLM output.
4. IDs in the extracted set that are NOT in `bundle.allowed_ids` are
   hallucinations — log and drop (same as `filter_citations` does inside
   the text).

This enforces Invariant 3.

### 7. Do not touch the code_only branch

`answer_stream()` must remain byte-for-byte unchanged from this step's
diff. Any incidental refactor must be reverted.

## Project Conventions

Read `orch/rag/CLAUDE.md`. Dataclasses over ad-hoc dicts. Do not silently
swallow exceptions — `bundle.retrieval_cutoff` should still be set even on
partial-failure paths.

## TDD Requirement

1. **RED**:
   - `tests/unit/test_qa_v2_prompt_layout.py` — 8 candidates in, top-3 full
     doc + 4–8 compact; 3-candidate case; NULL functional doc fallback;
     over-budget truncation.
   - `tests/unit/test_qa_v2_citation_snippet.py` — NULL → summary;
     non-NULL → first 300 chars; empty → empty.
   - `tests/unit/test_qa_v2_merge_rank.py` — α/β/γ math with parameterised
     inputs; normalisation boundary cases (all-zero score, single-item
     source).
   - `tests/unit/test_qa_v2_allowlist_wiring.py` — LLM output containing
     `F-00042` but bundle allowed_ids = {CR-00011} → only CR-00011 emitted;
     LLM containing `F-99999` (hallucination) → no event.
   - `tests/integration/test_qa_v2_hybrid_retrieval.py` — seed a testcontainer
     with 3 items + their LanceDB chunks, mock git-log, ask a question that
     semantically matches item 2 only → item 2 is rank-1.
2. **GREEN**: implement.
3. **REFACTOR**: verify no `answer_stream` regressions by running the
   existing code-only test suite unchanged.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass.
2. `make test-integration` — pass.
3. `make lint` + `make typecheck` — pass.

## Subagent Result Contract

Standard JSON with `step: "S03"`, `agent: "backend-impl"`, `work_item: "F-00060"`.
