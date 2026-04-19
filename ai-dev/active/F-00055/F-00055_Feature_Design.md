# F-00055: Work-Item-Aware Code Chat — Functional Behavior Q&A Linked to Work-Item History

**Type**: Feature
**Priority**: High
**Created**: 2026-04-19
**Status**: Draft

---

## Description

Extends the existing Code chat (`orch/rag/qa.py` + `dashboard/routers/code_qa.py` + `dashboard/static/chat/*`) so that non-technical *and* technical users can ask functional "why does X do Y" questions and receive a plain-language answer backed by a chronological narrative of the work items (Features, Incidents, Change Requests) that shaped that behavior. Retrieval blends the existing LanceDB code index with a new design-doc LanceDB index, Postgres full-text search on `work_items.design_doc_search`, and a git-log-derived file→work-item resolver. The answer is rendered with inline item-ID citation chips (`F-NNNNN`, `CR-NNNNN`, `I-NNNNN`) and a Linear-style work-item feed below the prose, while phase-event SSE messages keep the user informed during retrieval ("Looking up related items…", "Reading design documents…").

## Project Context

Read the project's `CLAUDE.md`, `orch/CLAUDE.md`, and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Prior research for this feature: [R-00057](../../docs/research/R-00057-nl-code-qa-work-item-history.md) (landscape), [R-00058](../../docs/research/R-00058-nl-to-ui-element-resolution.md) (technique), [R-00059](../../docs/research/R-00059-work-item-narrative-presentation.md) (presentation).

## Scope

### In Scope

- **Design-doc embedding index** — extend the existing `orch/rag/job.py` + `orch/rag/indexer.py` pipeline to populate a new LanceDB table `docs_{project_id}` with embeddings of `WorkItem.design_doc_content`, keyed by `(project_id, work_item_id)` and carrying type/title/summary/dates as metadata.
- **Phase-aware `QAEngine`** — `answer_stream` becomes a state machine emitting named phases (`retrieving`, `finding_items`, `reading_docs`, `composing`) via a new SSE event channel.
- **Hybrid work-item retrieval** — combines (a) LanceDB semantic search over design-doc embeddings, (b) Postgres FTS over `work_items.design_doc_search`, (c) git-log file→work-item resolver against squash-merge first lines containing `{F,I,CR}-NNNNN` patterns.
- **Query classifier** — lightweight LLM classifier routes queries to the work-item-aware pipeline when the query phrasing signals "why/how/behavior" intent; explicit slash commands (`/why`, `/history`, `/findusages`) override the classifier.
- **Citation allowlist** — LLM output is post-filtered so only work-item IDs present in the retrieved evidence bundle may render as citation chips; unknown IDs are stripped and logged.
- **SSE protocol extension** — new `phase` event alongside existing `token`, `citation`, `done`, `error`; `citation` event payload gains `work_item_type` and `work_item_id` fields for the new chip variant.
- **Frontend work-item chip** — new citation chip variant showing ID + type glyph (F / CR / I) with hover-popover and click-through to the work-item detail page (`/project/{id}/item/{work_item_id}`).
- **Linear-style work-item feed** — new chat fragment rendered below the answer prose showing 3–5 items sorted chronologically: `date · ID · title · 1-2 sentence impact summary`, drawer-expandable to full design-doc summary.
- **Phase-status strip** — UI element above the streaming answer that shows the current phase label; collapses into the sources panel once composition finishes.
- **Tone-switch chip** — per-answer affordance ("Show implementation details" / "Show functional summary") that re-renders the same evidence bundle at the other register.
- **`/findusages` consolidation** — the existing slash command routes into the new pipeline (symbol-anchored retrieval + work-item linkage), replacing the current stub behavior.
- **Slash-command aliases** — register `/why` (canonical) and `/history` (alias) in `dashboard/static/chat/composer.js`; both force the work-item-aware pipeline regardless of classifier output.
- **Evaluation set** — at least 10 curated (question, expected-shape, must-cite work items) tuples sourced from the current iw-ai-core baseline, executed as integration tests.

### Out of Scope

- **UI-element resolution** (NL → DOM/accessible-name → template/source) — deferred to F-TBD v1.5 per [R-00058](../../docs/research/R-00058-nl-to-ui-element-resolution.md).
- **Playwright runtime accessibility-snapshot indexing** — deferred to v1.5.
- **Static Jinja2 template parse + `data-tmpl-src` preprocessor** — deferred to v1.5.
- **Browser element-picker UX** — deferred to v1.5.
- **Cross-project chat** — each project keeps its own chat scoped by `project_id`; no cross-project synthesis.
- **LLM-rewriting of work-item titles at ingest time** — v1 uses curated titles as-is (the project controls Feature/CR/Incident titles via `iw-new-*` skills).
- **Streaming of phase sub-progress** — v1 emits one phase event per phase transition, not incremental progress within a phase.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | pipeline-impl | Extend `orch/rag/job.py` + `orch/rag/indexer.py` to populate LanceDB `docs_{project_id}` with design-doc embeddings during index + reindex jobs | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | backend-impl | Extend `QAEngine.answer_stream` to phase-aware state machine; add hybrid retrieval (code LanceDB + docs LanceDB + Postgres FTS); add git-log file→work-item resolver; add LLM query classifier; enforce citation allowlist | — (after S02) |
| S04 | code-review-impl | Review S03 | — |
| S05 | api-impl | Extend `/api/projects/{id}/code/qa` SSE generator with `phase` event type; extend `_CitationTracker` + citation event payload with `work_item_type`/`work_item_id`; consolidate `/findusages` routing | — (after S04) |
| S06 | code-review-impl | Review S05 | — |
| S07 | frontend-impl | `stream.js` `onPhase` callback; `render.js` work-item chip variant routing through existing `[data-cite]`; new `chat/parts/work_item_chip.html`, `chat/parts/work_item_feed.html`, `chat/parts/phase_strip.html`; `composer.js` slash aliases + tone-switch chip; citation-chip popover links to item detail page | — (after S06) |
| S08 | code-review-impl | Review S07 | — |
| S09 | tests-impl | Unit tests (phase emission, citation allowlist, classifier, retriever merge); integration tests (full SSE flow, slash override, classifier auto-detect, findusages); eval set of ≥10 (question, expected-shape, must-cite) tuples against current iw-ai-core baseline | — (after S08) |
| S10 | code-review-impl | Review S09 | — |
| S11 | code-review-final-impl | Global cross-agent review: pipeline ↔ backend ↔ api ↔ frontend ↔ tests integration, AC coverage, no regressions to existing Code-chat code-only behavior | — (after S10) |
| S12 | code-review-fix-final-impl | Fix CRITICAL and HIGH findings from S11 | — (after S11) |
| S13 | qv-gate | `uv run ruff check .` | — |
| S14 | qv-gate | `uv run ruff format --check .` | — |
| S15 | qv-gate | `uv run mypy orch/ dashboard/` | — |
| S16 | qv-gate | `make test-unit` | — |
| S17 | qv-gate | `make test-integration` | — |
| S18 | qv-browser | Browser verification in isolated worktree stack | — |

### Database Changes

- **New tables**: None (v1 uses existing infrastructure).
- **Modified tables**: None.
- **New LanceDB table**: `docs_{project_id}` (created by indexer; not a Postgres migration — managed by `lancedb.connect`/`create_table` pattern already used for `code_{project_id}`).
- **Migration notes**: No Alembic migration required. The existing `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` already maintain `work_items.design_doc_search`.

### API Changes

- **New endpoints**:
  - `POST /api/projects/{project_id}/code/qa/rerender` — SSE stream; body `{render_id, tone: "technical"|"functional"}`; backs the tone-switch chip (AC5) by re-composing against a cached evidence bundle without re-running retrieval. Returns 410 Gone if `render_id` is expired/evicted; frontend falls back to a full re-submit.
- **Modified endpoints**:
  - `POST /api/projects/{project_id}/code/qa` — SSE stream gains `phase` event type; `composing` phase `detail` gains a `render_id` (UUID hex) used by the rerender endpoint; `citation` event payload gains `work_item_type` + `work_item_id` fields (existing `n`, `label`, `url`, `snippet` unchanged).
- **Breaking changes**: None (new `phase` event is additive; existing clients ignoring unknown events continue to function).

### Frontend Changes

- **New components**:
  - `dashboard/templates/chat/parts/work_item_chip.html` — ID + type-glyph citation chip.
  - `dashboard/templates/chat/parts/work_item_feed.html` — Linear-style chronological feed rendered below the answer prose.
  - `dashboard/templates/chat/parts/phase_strip.html` — phase-label status strip shown during retrieval, collapsed on first token.
- **Modified components**:
  - `dashboard/static/chat/stream.js` — add `onPhase` callback; consume new `phase` SSE event.
  - `dashboard/static/chat/render.js` — route work-item citations through distinct chip class; popover links to `/project/{id}/item/{work_item_id}`.
  - `dashboard/static/chat/composer.js` — register `/why` and `/history` slash aliases; add per-answer tone-switch chip; update `/findusages` slot.
  - `dashboard/static/chat/citations.js` — extend map entries with `type` + `id` fields.

## File Manifest

All files for this work item live under `ai-dev/active/F-00055/`.

| File | Type | Purpose |
|------|------|---------|
| `F-00055_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00055_S01_Pipeline_prompt.md` | Prompt | S01 — design-doc embedding indexer |
| `prompts/F-00055_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `prompts/F-00055_S03_Backend_prompt.md` | Prompt | S03 — phase-aware QAEngine + hybrid retrieval |
| `prompts/F-00055_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/F-00055_S05_API_prompt.md` | Prompt | S05 — SSE phase event + work-item citation payload |
| `prompts/F-00055_S06_CodeReview_prompt.md` | Prompt | S06 — review S05 |
| `prompts/F-00055_S07_Frontend_prompt.md` | Prompt | S07 — stream/render/composer + new templates |
| `prompts/F-00055_S08_CodeReview_prompt.md` | Prompt | S08 — review S07 |
| `prompts/F-00055_S09_Tests_prompt.md` | Prompt | S09 — unit + integration + eval set |
| `prompts/F-00055_S10_CodeReview_prompt.md` | Prompt | S10 — review S09 |
| `prompts/F-00055_S11_CodeReview_Final_prompt.md` | Prompt | S11 — global cross-agent review |
| `prompts/F-00055_S12_CodeReview_Fix_Final_prompt.md` | Prompt | S12 — fix CRITICAL/HIGH findings |
| `prompts/F-00055_S18_BrowserVerification_prompt.md` | Prompt | S18 — browser verification |

### Files to Create or Modify in Implementation

**Create**:
- `dashboard/templates/chat/parts/work_item_chip.html`
- `dashboard/templates/chat/parts/work_item_feed.html`
- `dashboard/templates/chat/parts/phase_strip.html`
- `tests/unit/test_qa_engine_phase_events.py`
- `tests/unit/test_qa_engine_hybrid_retrieval.py`
- `tests/unit/test_qa_engine_classifier.py`
- `tests/unit/test_qa_engine_citation_allowlist.py`
- `tests/unit/test_qa_git_log_resolver.py`
- `tests/integration/test_code_qa_workitem_flow.py`
- `tests/integration/test_code_qa_eval_set.py`
- `tests/fixtures/eval_set_f00055.json`
- `scripts/regen_eval_set_f00055.py` — regenerates the eval-set fixture from the current platform DB; run manually when merged work items churn
- `tests/unit/test_qa_engine_render_cache.py`
- `tests/unit/test_code_qa_router_rerender.py`

**Modify**:
- `orch/rag/qa.py` — phase-aware state machine, hybrid retrieval, classifier, citation allowlist
- `orch/rag/indexer.py` — design-doc embedding pass
- `orch/rag/job.py` — trigger design-doc pass in index + reindex modes
- `orch/rag/parser.py` — if needed, helpers for git-log parsing
- `dashboard/routers/code_qa.py` — extend `_CitationTracker`, `_sse_generator`, request schema
- `dashboard/static/chat/stream.js` — `phase` event handler
- `dashboard/static/chat/render.js` — work-item chip variant + popover routing
- `dashboard/static/chat/composer.js` — slash aliases + tone-switch chip
- `dashboard/static/chat/citations.js` — type/id fields

## Acceptance Criteria

### AC1: Functional-behavior query returns answer plus linked work-item feed

```
Given a project with merged work items whose design docs describe a specific behavior
When the user asks "why does the daemon retry 3 times?" in the Code chat
Then the assistant emits phase events in the sequence (retrieving, finding_items, reading_docs, composing)
And streams a functional-register answer containing inline work-item citation chips (F-NNNNN, CR-NNNNN, I-NNNNN) that each correspond to an ID from the retrieved evidence bundle
And renders a Linear-style feed of 3–5 work items sorted ascending by creation date below the answer
And each feed entry shows "YYYY-MM-DD · ID · title · 1-2 sentence summary"
```

### AC2: Explicit slash trigger overrides auto-detection

```
Given the user adds the /why chip (or alias /history) to their query
When they submit the query
Then the work-item-aware pipeline runs unconditionally, skipping the LLM query classifier
And the SSE stream emits phase events and work-item citation events
```

### AC3: Auto-detection routes behavior questions without a slash chip

```
Given no slash chip is present on the query
When the query contains behavior/why-intent signals (e.g., "why", "how does", "feature", "behavior")
Then the classifier routes to the work-item-aware pipeline

Given the query is a pure code reference ("show me the function signature of parse_id")
Then the classifier routes to the default code-only pipeline (no phase events, no work-item feed)
```

### AC4: Hallucinated citations impossible by construction

```
Given the LLM emits a citation marker referencing an ID not present in the retrieved evidence bundle
When the answer is rendered
Then the marker is stripped from the output before the client renders the chip
And the retrieval-miss event is logged with the unknown ID and the surrounding answer context
```

### AC5: Tone adapts to query register with post-answer rewrite

```
Given the user asks in functional register ("why does the export only support CSV?")
When the answer is composed
Then the L1 prose reads as plain-language functional explanation

Given the user then clicks the "Show implementation details" chip below the answer
When the re-render fires
Then the client POSTs to /api/projects/{pid}/code/qa/rerender with the render_id emitted in the composing-phase detail
And the server re-composes against its in-memory render cache (LRU, TTL 10m, cap 64) without re-running retrieval
And the same evidence bundle is re-synthesized at technical register
And the chip label flips to "Show functional summary"

Given the render_id has expired or been evicted from the cache
When the user clicks the tone-switch chip
Then the rerender endpoint returns HTTP 410 Gone
And the client falls back to re-submitting the original question with a tone:<register> context chip
```

### AC6: Phase-event feedback during retrieval

```
Given retrieval takes more than 500ms
When the user is waiting for the first token
Then at least one phase label is visible in the chat UI before any answer token appears
And the phase strip collapses into the sources panel once the composing phase ends
```

### AC7: /findusages consolidation

```
Given the user adds the /findusages chip with a symbol name
When they submit
Then the work-item-aware pipeline runs with the symbol as the retrieval anchor
And the response includes both symbol usage locations (code context) and the work items that introduced or modified those usages
```

### AC8: Evaluation set passes against current iw-ai-core baseline

```
Given a curated eval set of at least 10 tuples of (question, expected_answer_shape, must_cite_work_items)
When the integration test runs the eval set against the current iw-ai-core project data
Then for each tuple the phase sequence fires in order
And at least one must_cite work-item ID appears in the emitted citation events
And the answer contains all expected key terms from expected_answer_shape
```

### AC9: No regression to default code-only chat

```
Given a purely code-structural question ("where is the CodeIndexJob model defined?")
When the classifier routes it to the default pipeline
Then no phase events are emitted
And no work-item citation chips appear
And the answer streams as today (token events only), preserving every existing behavior of R-00051 and earlier releases
```

### AC10: Citation chip links to work-item detail page

```
Given a streaming answer contains a work-item citation chip for F-00042
When the user clicks the chip
Then the popover opens showing the work item's title, 1-2 sentence summary, and a link
And the link target is /project/{project_id}/item/F-00042
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Empty `docs_{project_id}` LanceDB table | No design-doc embeddings yet indexed | Hybrid retrieval falls back to Postgres FTS + code LanceDB; answer streams with "(limited work-item context)" annotation; no phase-events short-circuit |
| Work item with `design_doc_content = NULL` | Older item pre-iw-new-* skills | Item is retrievable by title via FTS but has no body to synthesize from; feed row still renders with summary if present, otherwise shows "(no design document)" |
| LLM emits work-item ID not in retrieved bundle | Hallucinated citation | Citation is stripped at render time; retrieval-miss logged; answer continues without the chip |
| Git log contains no work-item-ID match for file | File pre-dates squash-merge convention | File→item resolver returns empty; retrieval still produces results via LanceDB/FTS; answer streams without git-log-derived items |
| Query classifier returns low-confidence signal | Ambiguous query | Default to code-only pipeline; user can re-send with `/why` to force work-item-aware |
| `/why` chip present but no work items match | No retrieval results at all | Emit `phase: finding_items` with count=0; compose answer noting no matching items found; do NOT synthesize fictional items |
| Tone-switch chip clicked before composing finishes | Race condition | Disable the chip until `done` event arrives; show a skeleton state on the chip during the disabled window |
| SSE connection drops mid-phase | Client abort or server error | Client shows partial phase strip; server emits `error` event; client renders error state in assistant bubble; no partial citation chips persist |
| LanceDB `docs_{project_id}` table missing | Project has never been indexed | Router already returns 404 for missing `code_{project_id}`; reuse same guard for `docs_` or graceful-degrade to FTS-only with a warning banner |
| Work-item feed overflows 5 items | 12 items touching the behavior | Show top-5 by retrieval-relevance score; expose "Show N more items" link that opens the full list in the sources panel |
| `project_id` has hyphens | e.g., `iw-ai-core` | Table name becomes `docs_iw_ai_core` (same hyphen-to-underscore rule as existing `code_` table) |

## Invariants

Conditions that must hold true after implementation. Each maps to a test.

1. Every citation chip rendered in the answer references a work-item ID present in the evidence bundle returned by the retrieval step (enforced structurally, not by prompt).
2. Phase events are emitted in the fixed order `retrieving → finding_items → reading_docs → composing`; no phase may fire more than once per answer; no phase may be skipped when the work-item-aware pipeline runs.
3. The default code-only pipeline (no slash chip, non-behavior query) emits no `phase` events and no work-item `citation` events, preserving bit-for-bit the existing SSE payload shape.
4. Work-item citation events carry both `work_item_type` (`feature|incident|change_request`) and `work_item_id` (`F-NNNNN`/`I-NNNNN`/`CR-NNNNN` format) fields; the router rejects payloads violating either format.
5. The LanceDB table `docs_{project_id}` is created or recreated by every full index job; design-doc changes picked up by `iw doc-update` are reindexed in the subsequent reindex job.
6. `/why`, `/history`, and `/findusages` slash chips all route to the same pipeline; `/findusages` additionally sets a symbol-anchor flag in the request.
7. Conversation history passed by `composer.js` remains truncated to `QAEngine.MAX_HISTORY_TURNS` turns regardless of which pipeline runs.
8. When `design_doc_content IS NULL` for a retrieved item, the feed row renders with a "(no design document)" placeholder and does not crash the renderer.
9. Per-project isolation: retrieval for project A never returns work items from project B (verified by composite-PK `(project_id, id)` scoping at every retrieval layer).
10. The existing `code_{project_id}` LanceDB table and its filter-by-path behavior for `context_level == "module"` remain unchanged.

## Dependencies

- **Depends on**: None. References prior research (R-00057, R-00058, R-00059) but depends only on infrastructure already merged to `main`.
- **Blocks**: UI-element resolution Feature (future v1.5), browser element-picker Feature (future v1.5).

## TDD Approach

- **Unit tests** (`tests/unit/`):
  - `test_qa_engine_phase_events.py` — `QAEngine.answer_stream` emits the correct phase sequence in the correct order; default pipeline emits no phases.
  - `test_qa_engine_hybrid_retrieval.py` — merge logic for LanceDB (code) + LanceDB (docs) + Postgres FTS retrieves correct ranking; tie-breakers; empty-result fallbacks.
  - `test_qa_engine_classifier.py` — classifier routes behavior queries to work-item pipeline and code queries to default; handles low-confidence cases.
  - `test_qa_engine_citation_allowlist.py` — LLM-emitted IDs not in the evidence bundle are stripped; logged as retrieval misses; in-bundle IDs pass through.
  - `test_qa_git_log_resolver.py` — parses squash-merge commit first lines (e.g., `Merge CR-00010: …`) into `{F,I,CR}-NNNNN` IDs; handles files pre-convention (returns empty).
- **Integration tests** (`tests/integration/`):
  - `test_code_qa_workitem_flow.py` — full SSE flow: POST → phase events → token events → citation events → done; asserts event sequence and payload shapes.
  - `test_code_qa_eval_set.py` — runs `tests/fixtures/eval_set_f00055.json` against a PostgreSQL testcontainer seeded with current iw-ai-core work items; asserts for each tuple: phase sequence fired, must-cite IDs appeared in citations, expected key terms present in output.
- **Edge cases**:
  - Empty `docs_{project_id}` — fallback path works.
  - Hallucinated citation — stripped at render time.
  - `/findusages` on a non-existent symbol — returns empty feed, does not crash.
  - Project with zero work items — feed is empty, phase events still emit.
  - LLM timeout mid-composition — error event emitted, partial content preserved.

## Notes

### Research basis

- [R-00057](../../docs/research/R-00057-nl-code-qa-work-item-history.md) established whitespace: no competitor combines non-technical framing + behavior-level query + work-item-narrative history.
- [R-00058](../../docs/research/R-00058-nl-to-ui-element-resolution.md) established that accessibility-tree-first hybrid retrieval dominates vision; v1 *does not* build UI-element resolution and defers that path to v1.5.
- [R-00059](../../docs/research/R-00059-work-item-narrative-presentation.md) established the answer shape: functional-first + Linear-style feed + inline citations + 3-layer progressive disclosure; NO percentages, NO generic disclaimers, NO chain-of-thought reasoning displays.

### Risks

- **Classifier accuracy** — LLM-based query classification may misroute queries. Mitigation: slash commands (`/why`, `/history`) always override the classifier; integration tests include at least 5 borderline phrasings.
- **Latency** — hybrid retrieval + agentic design-doc read + LLM composition may push total time past 15s. Mitigation: phase-event UI keeps the user informed; retrieval runs in parallel where possible; tests assert phase 1 fires within 2s.
- **Citation chip overload** — answers with 10+ inline citations become visually noisy. Mitigation: cap inline chips at 5; remainder accessible via sources panel and the feed below.
- **LanceDB `docs_` table build cost** — full design-doc embedding on every reindex may be expensive. Mitigation: incremental mode (reindex changed docs only) should be the default; full rebuild reserved for `regen-map`.

### Deferred v1.5 items (intentionally out of scope)

- UI-element resolution (NL description → template/source element) — R-00058 primary recommendation.
- Static Jinja2 template parse + `data-tmpl-src` preprocessor.
- Playwright runtime accessibility-snapshot indexing.
- Browser element-picker UX.

### Browser evidence

- Pre-implementation screenshot **deferred** — dev environment not confirmed running at design time. S18 (qv-browser) captures the post-implementation state in the isolated worktree stack.
