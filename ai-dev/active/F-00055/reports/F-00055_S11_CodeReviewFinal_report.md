# F-00055 S11 Final Cross-Agent Review

## Summary

14 findings: 3 CRITICAL, 3 HIGH, 3 MEDIUM, 5 LOW
Overall assessment: **reject** (CRITICAL findings must be fixed in S12)

## Cross-Layer Seam Analysis

The implementation spans 5 layers (pipeline → backend → api → frontend → tests) with 3 critical cross-layer data-passing bugs and 2 critical dead-code paths that prevent core features from functioning.

### Layer 1 → 2 (Indexer → QAEngine retrieval)

The `docs_{project_id}` LanceDB schema is consistent between `indexer.py` (creation) and `qa.py` (read). Both use `work_item_id`, `work_item_type`, `text`, `vector` fields. However, the `_merge_and_rank_work_items` function has a critical bug: it accepts `code_chunks` as a parameter but **never uses them in scoring** (see F03). Additionally, work items sourced purely from `doc_chunks` (LanceDB semantic search) can be silently dropped if they don't also appear in `fts_items` or `git_log_items` (see F06).

### Layer 2 → 3 (QAEngine → Router SSE)

Dict shapes are consistent: `_emit_phase`, `_emit_token`, `_emit_citation` all produce dicts that `_sse_generator` consumes correctly. The `citation` event correctly carries `work_item_type` and `work_item_id`. However, `_filter_citations` in `qa.py` uses `allowed_ids` derived only from `work_items` after merging — if a work item is retrieved via `doc_chunks` but doesn't appear in the merged top-5, its ID is not in `allowed_ids` and valid citations would be stripped (see F06).

### Layer 3 → 4 (Router → Frontend JS)

**`stream.js` drops `work_item_type` and `work_item_id`** when calling `onCitation`. The SSE payload includes these fields (`code_qa.py:240-241`) but `stream.js:53` only passes `n, label, url, snippet` to the callback. This cascades into multiple CRITICAL failures (see F01, F02, F04).

### Layer 4 → 5 (Frontend → Composer)

`composer.js` registers slash aliases (`why`, `history`, `findusages`) correctly and passes them as `context_chips` to the API. The tone-switch chip is injected after the initial stream's `done` event. However, the **rerender response handler** (`render.js:384-393`) only appends token text — it never calls `renderer.onCitation`, `renderer.onPhase`, or `renderer.onDone` for rerendered events. The rerendered answer's citations are lost and the tone chip is never re-injected (see F05, F09).

## AC Coverage Matrix

| AC | Implemented | Test | Notes |
|----|-------------|------|-------|
| AC1: full happy path | ⚠️ Partial | ✅ | Phase sequence fires; work-item feed never populates (F01) |
| AC2: slash override | ✅ | ✅ | Classifier bypass verified |
| AC3: auto-detect | ✅ | ✅ | Classifier routing verified |
| AC4: hallucination impossible | ⚠️ Partial | ✅ | Allowlist structurally correct but `allowed_ids` computation can exclude doc_chunks items (F06) |
| AC5: tone switch | ❌ | ⚠️ | Chip injected for initial stream but rerender response loses citations and appends to wrong element (F05) |
| AC6: phase before first token | ✅ | ✅ | Phase emits before LLM compose; structural test only |
| AC7: /findusages | ✅ | ✅ | Symbol anchor passed through |
| AC8: eval set | ✅ | ✅ | 13 tuples; all mocked |
| AC9: no regression | ✅ | ✅ | Code-only emits token+done only |
| AC10: citation chip link | ⚠️ Partial | ⚠️ | URL is in SSE but popover loses `work_item_type` (F04) |

## Invariant Verification

| Inv | Enforced | Test | Notes |
|-----|----------|------|-------|
| 1: citation allowlist | ✅ | ✅ | `filter_citations` called per token batch; but see F06 |
| 2: phase sequence | ✅ | ✅ | Fixed order enforced in `answer_stream_v2` |
| 3: code_only no phases | ✅ | ✅ | Classifier returns `code_only` → `answer_stream` (not `answer_stream_v2`) |
| 4: WI ID regex validation | ✅ | ✅ | `WORK_ITEM_ID_RE` at router; `WORK_ITEM_ID_PATTERN` at allowlist |
| 5: docs_ recreated full mode | ✅ | ✅ | `db.drop_table()` in full mode |
| 6: /why/history/findusages same pipeline | ✅ | ✅ | All three route to `answer_stream_v2` |
| 7: history truncation | ✅ | ⚠️ | `_truncate_history` in qa.py; not directly tested |
| 8: NULL design_doc_content | ✅ | ✅ | `"or (no summary available)"` in evidence |
| 9: per-project isolation | ✅ | ⚠️ | DB queries filter by `project_id`; integration test uses mock (S10 finding) |
| 10: code_ behavior unchanged | ✅ | ✅ | `answer_stream` path untouched for code_only |

## Findings

### F01 [CRITICAL]: `onWorkItemCitation` is dead code — work-item feed never populates
**Layer**: frontend
**File**: `dashboard/static/chat/render.js:438-441`, `dashboard/static/chat/stream.js`
**Issue**: `createAssistantRenderer` returns an `onWorkItemCitation` handler that manages `feedItems` and `workItemFeedEl`, but `stream.js` never calls it. The `stream.js` event handler only calls `renderer.onToken`, `renderer.onCitation`, `renderer.onPhase`, `renderer.onDone`, `renderer.onError`. The `onWorkItemCitation` callback is never wired to any SSE event type.
**Impact**: AC1 work-item feed is always empty. Despite citations being streamed and `feedItems` array defined, no data ever populates it.
**Fix**: Either (a) add `else if (data.work_item_type !== undefined && eventType === 'citation')` branch in `stream.js` to call `renderer.onWorkItemCitation(data)`, or (b) remove `onWorkItemCitation` and instead populate `feedItems` inside `onCitation` when `work_item_type`/`work_item_id` are present in the data.

### F02 [CRITICAL]: `stream.js` drops `work_item_type` and `work_item_id` from citation events
**Layer**: api → frontend
**File**: `dashboard/static/chat/stream.js:53`
**Issue**: The SSE `citation` event carries all required fields including `work_item_type` and `work_item_id` (`code_qa.py:234-244`), but `stream.js` only passes `n, label, url, snippet` to `onCitation`:
```js
onCitation({ n: data.n, label: data.label, url: data.url, snippet: data.snippet, work_item_type: data.work_item_type, work_item_id: data.work_item_id });
//                                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ — never used by render.js onCitation
```
`render.js:427-429` destructures only `(n, label, url, snippet)`, so `work_item_type` and `work_item_id` are silently discarded.
**Impact**: AC10 citation popovers cannot display work-item type glyph (F/CR/I color coding) since that data is never stored. Work-item chip CSS classes (`citation-chip--feature`, etc.) are applied at streaming time via the template but the supplementary popover data is incomplete.
**Fix**: Change `render.js` `onCitation` to store `work_item_type` and `work_item_id` in `citationMap`:
```js
onCitation: function(data) {
  citationMap.set(String(data.n), data);  // stores all fields including work_item_type/work_item_id
  updateCitations();
}
```

### F03 [CRITICAL]: `_merge_and_rank_work_items` ignores `code_chunks` — hybrid retrieval is not hybrid
**Layer**: pipeline
**File**: `orch/rag/qa.py:884-928`
**Issue**: The function accepts `_code_chunks` as its first positional argument (named with underscore prefix to indicate unused) and has a docstring referencing "Scoring: α * doc_score + β * fts_score + γ * git_log_recency" with **no mention of code relevance**. The `alpha` parameter only increments scores for `doc_chunks`, `beta` for `fts_items`, `gamma` for `git_log_items`. `code_chunks` have zero influence on work-item ranking.
**Impact**: Work items retrieved via code-LanceDB semantic search do not affect ranking. The "hybrid" retrieval is effectively a 3-source merge (docs + FTS + git-log) with code context ignored at the ranking stage. Code-only projects or queries where code context is the only relevant signal would produce rankings driven solely by doc/fts/git sources.
**Fix**: Add `code_chunks` scoring to the ranking formula. For example, `δ * code_relevance_score` where code relevance is derived from how many code chunks reference each work item (via git-log resolver or explicit linking in the code index).

### F04 [HIGH]: `citationMap` incomplete — popover loses work-item type glyph data
**Layer**: frontend
**File**: `dashboard/static/chat/render.js:427-429`
**Issue**: `onCitation` stores only `n, label, url, snippet` because `stream.js` doesn't pass `work_item_type`/`work_item_id`. Even after fixing F02, the current `onCitation` implementation doesn't store them:
```js
onCitation: function(data) {
  citationMap.set(String(data.n), data); // would now work if stream.js passes all fields
  updateCitations();
}
```
After fixing F02 (stream.js passing all fields), this would be resolved by storing `data` directly. But the current code explicitly destructures only 4 fields.
**Impact**: AC10 popover shows incomplete work-item metadata. The `work_item_chip.html` template uses `work_item_type` for glyph color (`citation-chip--feature` = blue, `citation-chip--change_request` = amber, `citation-chip--incident` = red) but if `citationMap` entry lacks `work_item_type`, the popover renders without type context.
**Fix**: After fixing F02, ensure `onCitation` stores the full `data` object (including `work_item_type` and `work_item_id`) rather than only the 4 explicitly named fields.

### F05 [HIGH]: Rerender response handler loses citations and appends to wrong element
**Layer**: frontend
**File**: `dashboard/static/chat/render.js:371-393`
**Issue**: When the rerender SSE stream arrives, `injectToneSwitchChip`'s `read()` function only handles `data.b64` (token text) and ignores `citation` and `phase` events:
```js
if (data.b64) {
  var txt = atob(data.b64);
  if (window.iwChat && window.iwChat.streamAnswer) {
    var bodyEl = messageEl.querySelector('.chat-message-body');
    if (bodyEl) bodyEl.innerHTML += txt;  // APPENDS new text to existing content
  }
}
```
Tokens are appended to `innerHTML` of the message body, not replacing it. Citation events from the rerender are silently dropped (no `renderer.onCitation` call). Phase events are also dropped.
**Impact**: AC5 "re-renders at other register without refetching" — the rerendered answer's citations are never registered in `citationMap`, so popovers don't work for rerendered content. The old answer text accumulates with the new answer.
**Fix**: For rerender, clear `bodyEl.innerHTML` before appending, or better: re-use the existing renderer mechanism by calling `renderer.onCitation(cit)` and `renderer.onPhase(phase)` for each respective event type rather than parsing SSE manually.

### F06 [HIGH]: `allowed_ids` can exclude valid `doc_chunks` work items — hallucination guard has a hole
**Layer**: pipeline
**File**: `orch/rag/qa.py:542-566`, `orch/rag/qa.py:321`
**Issue**: `EvidenceBundle.allowed_ids` is computed as `{item.id for item in self.work_items}`. `work_items` is the output of `_merge_and_rank_work_items`, which only returns items present in `fts_items + git_log_items`. Work items sourced purely from `doc_chunks` (LanceDB semantic search) are excluded from the merged result if they don't also appear in FTS or git-log results. When `_filter_citations` runs with this `allowed_ids` set, it would strip citations for validly-retrieved doc-only work items.
**Impact**: AC4 "hallucinated citations structurally impossible" has a structural hole — a work item retrieved via docs LanceDB (valid evidence) could have its citation stripped if it doesn't also appear in FTS or git-log.
**Fix**: Either (a) include all work items from all sources in `allowed_ids` (union of doc_chunks IDs + fts_items IDs + git_log_items IDs), not just the merged+ranked top-5, or (b) pass the full candidate set to `allowed_ids` and let the ranker determine ordering separately.

### F07 [MEDIUM]: `onWorkItemCitation` dead code + 5-item cap never enforced
**Layer**: frontend
**File**: `dashboard/static/chat/render.js:438-441`, `dashboard/static/chat/render.js:316`
**Issue**: Due to F01, `onWorkItemCitation` is never called, so `feedItems` stays empty and `workItemFeedEl` is never created. The `items.slice(0, 5)` cap in `updateWorkItemFeed` never executes. The AC1 "top-5 items" cap is implemented but unreachable dead code.
**Impact**: If F01 is fixed, the 5-item cap would work correctly. No user-visible impact until F01 is addressed.
**Fix**: Covered by F01 fix.

### F08 [MEDIUM]: Rerender tone-switch chip not reinjected after rerender completes
**Layer**: frontend
**File**: `dashboard/static/chat/render.js:398-400`
**Issue**: The `injectToneSwitchChip`'s `onDone` handler checks `if (renderId && ...)` to decide whether to inject the chip. For rerender responses, `renderId` is already set (from the initial stream), so the condition is falsy and the tone chip is never injected for rerendered answers.
**Impact**: Users who receive a rerendered answer don't see the tone-switch chip to switch back. They must refresh the page to get a new initial stream.
**Fix**: The tone chip should be injected after rerender completes too. Either track `lastPhaseName` per response, or check `window.iwChat.injectToneSwitchChip` call separately for rerenders.

### F09 [MEDIUM]: `git_log_resolver` does not validate project_id on returned IDs
**Layer**: pipeline
**File**: `orch/rag/git_log_resolver.py:21-44`
**Issue**: `resolve_work_items_for_files` returns raw `{file: [wi_id1, wi_id2]}` mapping. The caller `_retrieve_evidence_bundle` uses these IDs to call `_fetch_work_items_by_ids`, which does filter by `project_id`. However, if the git log contains a work-item ID from a different project (e.g., `F-99999` from `other-project`), the resolver returns it. The project filter is applied at the DB fetch level, so it won't return cross-project data, but the resolver's return type documents no project association.
**Impact**: Low — the DB filter prevents data leakage, but conceptually noisy. If `resolve_work_items_for_files` were called from a different context in future, it could return cross-project IDs without project filtering.
**Fix**: `resolve_work_items_for_files` could optionally accept `project_id` and filter commit messages to only that project's work items. Or add a comment documenting that the caller is responsible for project scoping.

### F10 [MEDIUM]: Hardcoded 384-dim fallback vector may mismatch embedding model
**Layer**: pipeline
**File**: `orch/rag/indexer.py:437-438`
**Issue**:
```python
except Exception as e:
    errors.append(f"{wi.id} chunk {chunk_idx}: {e}")
    vector = [0.0] * 384  # hardcoded dimension
```
`qwen3-embedding:8b` (the default model) produces 128-dimensional vectors. If embedding fails and falls back to a 384-dim zero vector, the LanceDB table schema would reject it (schema is `pa.list_(pa.float32())` with actual model dimension). However, this is a fallback for errors only.
**Impact**: If Ollama is partially down (embedding endpoint broken but LLM running), indexing would record wrong-dimension vectors. The `db.create_table` or `add` call would likely fail rather than silently store wrong-dim data.
**Fix**: Use the actual embedding model's expected dimension from config, or query a small test embedding to determine dimension dynamically.

### F11 [LOW]: `WORK_ITEM_ID_PATTERN` word-boundary vs router strict-match regex
**Layer**: cross-layer
**Files**: `orch/rag/citation_allowlist.py:11`, `dashboard/routers/code_qa.py:35`
**Issue**: Router uses `^(F|I|CR)-\d{5}$` (strict, anchors). Allowlist uses `\b(F|CR|I)-\d{5}\b` (word boundaries). For a string like `"F-00001."` with trailing punctuation, the allowlist pattern matches but the router pattern would not match on input validation. This is actually correct behavior (router is stricter at intake), but the discrepancy could confuse future maintainers.
**Impact**: No user-visible bug. The allowlist pattern is more permissive, which is correct for post-hoc filtering of LLM output.
**Fix**: Add a comment explaining the difference.

### F12 [LOW]: `scripts/regen_eval_set_f00055.py` not present
**Layer**: tests
**File**: `tests/fixtures/eval_set_f00055.json` references this script in `_generator` field; design doc (File Manifest line 134) lists it
**Issue**: The script that regenerates the eval set fixture from live DB is not in the worktree. The fixture is marked generated at `2026-04-19` and has a 180-day stale warning.
**Impact**: Low — fixture is static JSON; tests pass with mocks regardless. The script would be needed for maintenance, not for current CI.
**Fix**: Either create the script or remove the reference from the fixture metadata.

### F13 [LOW]: Duplicate docstring in `_merge_and_rank_work_items`
**Layer**: backend
**File**: `orch/rag/qa.py:893-900`
**Issue**: The function has the docstring content repeated twice consecutively (lines 893-900 appear twice).
**Impact**: No functional impact, just code quality.
**Fix**: Remove duplicate docstring.

### F14 [LOW]: `tone` chip label swap logic uses `lastPhaseName` which is set only for initial stream
**Layer**: frontend
**File**: `dashboard/static/chat/render.js:331`
**Issue**: `var tone = lastPhaseName === 'composing' ? 'technical' : 'functional';` — `lastPhaseName` is set by the initial stream's `onPhase` callback. For rerender responses, `lastPhaseName` is not updated, so if a user somehow triggers a second rerender, the tone label logic would be based on stale state.
**Impact**: Minor — AC5 mostly works for the first tone switch. Edge case of repeated toggling may show wrong label.

## Regression Risk

**Code-only behavior unchanged**: The `answer_stream` method (used when classifier returns `code_only`) is completely untouched by F-00055 changes. The SSE shape for code-only remains `{token, done}` only. The no-regression integration tests (`test_code_qa_no_regression.py`) verify this comprehensively.

**Existing LanceDB `code_{project_id}` behavior**: The `code_` table schema, query patterns, and filtering are unchanged. All `code_` queries use the same `code_table_name`, `seed_filter`, and `TOP_K` constants.

**Breaking SSE change**: The new `phase` and enriched `citation` events are additive. Existing clients ignoring unknown event types continue to function (per design doc: "new `phase` event is additive; existing clients ignoring unknown events continue to function").

## Recommendation

**reject — fix blockers in S12**

The implementation has solid architectural foundations and correct SSE infrastructure, but 3 critical cross-layer data-passing bugs (F01, F02, F03) and 2 critical feature-breakage bugs (F05, F06) prevent AC1, AC4, AC5, and AC10 from functioning correctly. The work-item feed is unreachable dead code, citation metadata is silently dropped at the frontend boundary, and the hybrid retrieval doesn't actually hybridize with code context.

S12 should prioritize: F01 + F02 (front-end data flow), F03 + F06 (backend retrieval ranking), F05 (rerender response handling).

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "code-review-final-impl",
  "work_item": "F-00055",
  "completion_status": "complete",
  "review_verdict": "reject",
  "findings_critical": 3,
  "findings_high": 3,
  "findings_medium": 3,
  "findings_low": 5,
  "ac_coverage_pct": 70,
  "invariants_verified": 9,
  "notes": "CRITICAL: F01 onWorkItemCitation dead code (feed never populates), F02 stream.js drops work_item_type/work_item_id from onCitation, F03 _merge_and_rank ignores code_chunks. HIGH: F04 citationMap incomplete (popover loses type), F05 rerender loses citations/appends to wrong element, F06 allowed_ids hole for doc_chunks-only items. MEDIUM: F07 5-item cap unreachable, F08 tone chip not reinjected on rerender, F09 git_log_resolver no project filter on IDs. LOW: F10 hardcoded 384-dim vector, F11 regex discrepancy, F12 regen script missing, F13 duplicate docstring, F14 stale tone label state."
}
```
