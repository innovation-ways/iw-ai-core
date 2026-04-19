# F-00055_S03_Backend_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S03
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` — design document (read in full; focus on AC1, AC2, AC3, AC4, AC6, AC9, Invariants 1–7, 9, 10)
- `ai-dev/active/F-00055/reports/F-00055_S01_Pipeline_report.md`, `F-00055_S02_CodeReview_report.md`
- `orch/rag/qa.py` — `QAEngine.answer_stream`, `_build_system_prompt`, `_truncate_history` (integration target)
- `orch/rag/config.py` — `CodeUnderstandingConfig`, `resolved_llm_model`, `resolved_embed_model`
- `orch/db/models.py` — `WorkItem` (with composite PK `(project_id, id)`, `design_doc_content`, `design_doc_search`, `summary`, `type`, `created_at`, `completed_at`), `ProjectDoc`
- `docs/research/R-00059-work-item-narrative-presentation.md` — for answer-shape rules (citation allowlist, tone, phase cadence)
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S03_Backend_report.md`

## Context

Transform `QAEngine.answer_stream` from a single-phase retrieval+compose call into a phase-aware state machine that runs the new **work-item-aware pipeline** when triggered, while preserving the **default code-only pipeline** untouched for non-behavior queries. The new pipeline combines three retrieval sources, resolves files to work items via git log, and enforces a citation allowlist so the LLM cannot hallucinate item IDs.

## Requirements

### 1. Phase-event channel

`answer_stream` currently yields `str` tokens. Change its yield type to `dict` carrying one of two shapes:

```python
{"kind": "phase", "name": "retrieving|finding_items|reading_docs|composing", "detail": {...}}
{"kind": "token", "text": "..."}
{"kind": "citation", "n": 1, "work_item_type": "feature|incident|change_request",
 "work_item_id": "F-00042", "label": "F-00042 — <title>", "url": "/project/{pid}/item/F-00042",
 "snippet": "<1-2 sentence summary from design doc>"}
```

The router (S05) translates each dict into the appropriate SSE event type. Keep the signature backwards compatible by keeping `str` yields possible during a deprecation window — OR introduce a new method `answer_stream_v2` and have the router call it. Prefer the second: new method, old one calls into it and flattens dicts to strings for any legacy caller. Confirm with current callers (only `dashboard/routers/code_qa.py` — will be updated in S05).

### 2. Query classifier

Add `_classify_query(question, context_chips) -> Literal["workitem_aware", "code_only"]`:

- If `context_chips` contains `why`, `history`, or `findusages` → return `"workitem_aware"` (slash override; AC2).
- Else call a small LLM prompt against `Ollama(model=config.resolved_llm_model())` asking the model to classify as one of the two strings. Cap timeout at 2s; on timeout default to `"code_only"` (AC3 low-confidence behavior).
- Classifier prompt is deterministic, temperature 0, one-shot; include 3–5 exemplars in the system prompt.

### 3. Hybrid retrieval (for `workitem_aware`)

Implement `_retrieve_evidence_bundle(project_id, question, session, config, symbol_hint=None) -> EvidenceBundle`:

```python
@dataclass
class EvidenceBundle:
    question: str
    code_chunks: list[CodeChunk]              # from existing code_{project_id} LanceDB
    doc_chunks: list[DocChunk]                # from new docs_{project_id} LanceDB
    fts_items: list[WorkItem]                 # from Postgres FTS on design_doc_search
    git_log_items: list[WorkItem]             # from git log parsing
    work_items: list[WorkItem]                # merged + deduped, sorted by created_at ASC
    retrieval_cutoff: datetime                # "as of" timestamp
```

- Run the three retrieval sources in parallel via `asyncio.gather` or `ThreadPoolExecutor`.
- **Code LanceDB**: reuse the existing top-k=8 embedding search; no filter unless `context_level == "module"`.
- **Docs LanceDB**: new top-k=8 embedding search against `docs_{project_id}`; extract `work_item_id` from each hit.
- **Postgres FTS**: `SELECT * FROM work_items WHERE project_id = :pid AND design_doc_search @@ plainto_tsquery('english', :q) ORDER BY ts_rank(design_doc_search, plainto_tsquery('english', :q)) DESC LIMIT 10`.
- **Git-log resolver**: for each distinct file in `code_chunks`, run `git log --follow --oneline -- <file>` via `subprocess.run` with `cwd=project.repo_root` (resolved from the `Project` row via the existing `project_id`; `Project.repo_root` is guaranteed non-null — see `orch/db/models.py:237`), a 10-second timeout per file, and a 30s total cap across files. Do NOT rely on the daemon's CWD (the daemon runs out of a worktree that may not share ancestry with the project's main repo). Use `shell=False` and pass argv as a list to avoid injection. Parse first-line `Merge {F,I,CR}-NNNNN:` patterns into work-item IDs. Deduplicate by ID. (Put the parser in `orch/rag/git_log_resolver.py` — new module; accepts a `repo_root: Path` argument.)
- **Merge + rank**: all three sources contribute candidate work-item IDs; score each ID by `α * doc_score + β * fts_score + γ * git_log_recency` (α=0.5, β=0.3, γ=0.2 as starting weights; expose as module constants for tuning). Take top-5 by combined score.
- Fetch the full `WorkItem` rows for the selected IDs from Postgres, preserving `summary`, `design_doc_content`, `created_at`, `type`, `title`.

### 4. Citation allowlist

Implement `_filter_citations(answer_text, allowed_ids) -> tuple[str, list[str]]`:

- Scan the LLM output for patterns matching `\b(F|I|CR)-\d{5}\b`.
- Any match whose ID is NOT in `allowed_ids` (the set from the evidence bundle) is stripped (regex-replace with empty string) AND logged to a structured logger at WARNING level with the offending ID and ±40 chars of context. Return the filtered text and the list of stripped IDs.
- Called inline on each streamed token: buffer tokens until sentence boundary (`.`, `!`, `?`, `\n`), apply filter, emit. This means tokens are not *individually* yielded verbatim — they are yielded per-sentence. (Accept this tradeoff — per R-00059, citations are sentence-scoped anyway.)

### 5. System prompt for work-item-aware composition

Build a new system prompt for the work-item-aware pipeline (keep `_build_system_prompt` for the default pipeline). Include:

- The evidence bundle rendered as structured markdown:
  - `## Code Context` — top chunks grouped by file.
  - `## Related Work Items` — each item with ID, type, title, date, summary, design-doc excerpt.
  - `## Retrieval Provenance` — retrieval cutoff timestamp and counts per source.
- Instruction: compose a plain-language functional answer; insert inline citations using the literal form `[F-NNNNN]`, `[CR-NNNNN]`, or `[I-NNNNN]` (matching allowlist IDs); NEVER invent IDs; NEVER use percentage confidence; NEVER emit generic disclaimers.
- Register instruction: derived from the query phrasing — if the query is functional-register (contains "why", "what does", "how is X used"), compose in plain-language functional register; if technical ("show the signature", "what's the implementation of"), compose in technical register.
- Hard cap: 4 paragraphs max before sources.

### 6. Emit phases and citations in correct order

Phase sequence (Invariant 2):

1. `phase("retrieving")` — emitted BEFORE any retrieval starts.
2. `phase("finding_items", {count: N})` — after hybrid retrieval completes; N is the number of distinct work-item candidates before top-5 trim.
3. `phase("reading_docs", {count: M})` — after fetching full `WorkItem` rows; M is the final top-5 count.
4. `phase("composing")` — just before the first LLM token arrives.
5. One `citation` event per retrieved work item (not one per LLM occurrence) — emitted IMMEDIATELY after `reading_docs` with `n` as the 1-based index in the sorted feed order (ascending by `created_at`). This ensures the feed renders in stable order regardless of LLM output.
6. Token events stream as filtered sentences arrive.
7. `done` (router emits; engine simply ends the generator).

### 7. Preserve default code-only pipeline

- When `_classify_query` returns `"code_only"`: emit NO `phase` events, NO work-item `citation` events; stream tokens exactly as today (AC9, Invariant 3).
- Keep `_build_system_prompt`, the `context_level == "module"` filter, the `/diagram` directive block, and all other existing behavior untouched.

### 8. Data classes and module layout

- New file `orch/rag/evidence.py` with `EvidenceBundle`, `CodeChunk`, `DocChunk` dataclasses.
- New file `orch/rag/git_log_resolver.py` with `resolve_work_items_for_files(files: Sequence[str], *, repo_root: Path) -> dict[str, list[str]]`.
- New file `orch/rag/classifier.py` with `classify_query(question, config) -> Literal["workitem_aware", "code_only"]` and the allowlist filter (or put the filter in `orch/rag/citation_allowlist.py` — pick a split that's grep-friendly).

### 9. Evidence-bundle render cache (AC5 "without refetching")

AC5 requires the tone-switch chip to re-render at the opposite register without re-running retrieval. Implement this as a **server-side, request-scoped cache** on the `QAEngine` instance:

- Attribute: `self._render_cache: OrderedDict[str, tuple[datetime, EvidenceBundle, str]]` — ordered-dict for LRU eviction; value is `(created_at, bundle, original_question)`.
- Capacity: `RENDER_CACHE_MAX = 64` entries; TTL: `RENDER_CACHE_TTL = timedelta(minutes=10)`. Enforce both on every `_cache_get` / `_cache_put` call; evict the oldest when over capacity; drop expired entries on read.
- Key: `render_id = uuid.uuid4().hex` — generated once per retrieval before the `composing` phase fires.
- Emit the `render_id` as part of the `composing` phase detail: `{"kind": "phase", "name": "composing", "detail": {"render_id": "<hex>", "count": M}}` so the frontend can stash it on the bubble.
- New engine method: `async def rerender(render_id: str, tone: Literal["technical", "functional"]) -> AsyncIterator[dict]`:
  - Look up bundle by `render_id`; on miss or expiry, raise `RenderCacheMiss` (router maps to 410 Gone; frontend falls back to full re-submit).
  - On hit, re-run **only** the composition step (`_compose_with_bundle(bundle, register=tone)`); yield `phase:composing` (no retrieving/finding_items/reading_docs), then filtered token events, then a final `done` sentinel.
  - Re-emit the same `citation` events (sorted-by-date order) so the feed stays consistent between the two renders.
- The router wires a new endpoint in S05 (`POST /api/projects/{pid}/code/qa/rerender`) that accepts `{render_id, tone}` and streams the rerender output using the same SSE protocol. The main `/code/qa` endpoint is NOT overloaded with this mode — keep the split clean.
- Thread-safety: wrap `_render_cache` access in a `threading.Lock` since the engine runs inside `_run_qa_in_thread` across worker threads.
- Tests: `tests/unit/test_qa_engine_render_cache.py` — hit, miss (expired), miss (evicted), capacity enforcement, LRU ordering.

## Project Conventions

Read `orch/CLAUDE.md`:
- Sync SQLAlchemy 2.0; psycopg v3.
- Do NOT call `importlib.reload(orch.config)` in tests — use `monkeypatch.delenv()` instead.
- `DaemonEvent.metadata` is `event_metadata` in Python (not relevant here, but indicative of the care needed).
- Tests use PostgreSQL testcontainers only — never port 5433.

## TDD Requirement

Follow Red-Green-Refactor. Required tests:

1. `tests/unit/test_qa_engine_phase_events.py` — phase sequence correctness; no phases in code-only path.
2. `tests/unit/test_qa_engine_classifier.py` — slash override, LLM classifier behavior (mocked), timeout fallback.
3. `tests/unit/test_qa_engine_citation_allowlist.py` — in-allowlist passes, out-of-allowlist stripped + logged.
4. `tests/unit/test_qa_git_log_resolver.py` — parses `Merge F-NNNNN:`, `Merge CR-NNNNN:`, `Merge I-NNNNN:`; ignores non-matching commits; handles files pre-convention.
5. `tests/unit/test_qa_engine_hybrid_retrieval.py` — merge-and-rank logic; parallel execution; top-5 cap.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — must pass.
2. `uv run ruff check .` and `uv run mypy orch/ dashboard/` — must pass.
3. Smoke test: manually invoke `QAEngine.answer_stream_v2` against a seeded test DB and verify the emitted dict sequence.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00055",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/qa.py",
    "orch/rag/evidence.py",
    "orch/rag/git_log_resolver.py",
    "orch/rag/classifier.py",
    "tests/unit/test_qa_engine_phase_events.py",
    "tests/unit/test_qa_engine_classifier.py",
    "tests/unit/test_qa_engine_citation_allowlist.py",
    "tests/unit/test_qa_git_log_resolver.py",
    "tests/unit/test_qa_engine_hybrid_retrieval.py",
    "tests/unit/test_qa_engine_render_cache.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
