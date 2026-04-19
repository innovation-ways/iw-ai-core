# F-00055_S11_CodeReview_Final_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S11
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` — all sections
- `ai-dev/active/F-00055/reports/*` — every previous step report (S01–S10)
- ALL files changed or created in S01–S09:
  - `orch/rag/job.py`, `orch/rag/indexer.py`, `orch/rag/qa.py`, `orch/rag/evidence.py`, `orch/rag/git_log_resolver.py`, `orch/rag/classifier.py`
  - `dashboard/routers/code_qa.py`
  - `dashboard/static/chat/stream.js`, `render.js`, `composer.js`, `citations.js`
  - `dashboard/static/chat.css`
  - `dashboard/templates/chat/parts/work_item_chip.html`, `work_item_feed.html`, `phase_strip.html`
  - Every test file created in S01–S09
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S11_CodeReview_Final_report.md`

## Review Focus

This is the **global cross-agent review**. Previous reviews (S02, S04, S06, S08, S10) evaluated each layer in isolation. This review inspects the SEAMS between layers, end-to-end feature correctness, and regression risk. Findings with CRITICAL/HIGH/MEDIUM/LOW severities — CRITICAL and HIGH findings MUST be fixed in S12.

### Cross-layer seam checks

1. **Pipeline ↔ Backend**: `docs_{project_id}` schema matches what `QAEngine._retrieve_evidence_bundle` reads — same column names, same embedding dimension, same chunking assumptions.
2. **Backend ↔ API**: dict shapes yielded by `QAEngine.answer_stream_v2` match the shapes consumed by `_sse_generator`; no field mismatch.
3. **API ↔ Frontend**: SSE event payloads produced by the router match the structures consumed by `stream.js` / `render.js`; `work_item_type`, `work_item_id`, `n` fields travel end-to-end.
4. **Frontend ↔ Backend**: slash-chip values sent by `composer.js` (`why`, `history`, `findusages`, `tone:technical`, `tone:functional`) are all handled by the classifier / pipeline.
5. **Tests ↔ All layers**: integration tests exercise the full stack (not just mocks); eval set is actually runnable in CI.

### End-to-end AC verification

Walk through every Acceptance Criterion in the design doc and trace how each layer contributes. Explicitly verify:
- AC1: full happy path (phase events, citations, feed, chronological ordering).
- AC2: slash overrides classifier.
- AC3: classifier auto-detects and routes; pure code queries stay default.
- AC4: hallucinated citations structurally impossible.
- AC5: tone switch re-renders without refetch (verify by inspecting the re-fire path in composer.js).
- AC6: phase strip visible before first token, collapsed after.
- AC7: `/findusages` consolidation.
- AC8: eval set runs green.
- AC9: no regression to default code-only chat.
- AC10: citation chip links to item detail page.

### Invariant checks

Verify each of the 10 invariants is enforced by code (not just claimed in docs):

1. Citation-allowlist enforcement is structural (scan `qa.py` for the filter function; confirm it's called on every token batch).
2. Phase-sequence order is fixed (grep for phase-emitting code; confirm no alternate order exists).
3. Code-only pipeline emits zero phase events (trace the `code_only` branch end-to-end).
4. Work-item citation payload regex validation (`^(F|I|CR)-\d{5}$`).
5. LanceDB `docs_` recreated on full mode; incremental-only on reindex.
6. `/why`, `/history`, `/findusages` all share the same pipeline.
7. History truncation preserved (`MAX_HISTORY_TURNS`).
8. Null `design_doc_content` renders `(no design document)`.
9. Per-project isolation in every retrieval layer.
10. Existing `code_{project_id}` behavior unchanged (diff `answer_stream` path for code-only case; assert untouched).

### Risk areas (from the design Notes)

- **Classifier accuracy** — do the eval-set negative controls actually catch misrouting?
- **Latency** — does phase-event emission fire early enough for AC6? Look for blocking operations before the first phase event.
- **Citation overload** — is the 5-item cap enforced in the feed renderer? What happens at 10+?
- **`docs_` rebuild cost** — does incremental mode actually skip unchanged items?

### Documentation and self-consistency

- Every prompt file references the design doc and CLAUDE.md.
- The `workflow-manifest.json` step count matches the prompt-file count (plus QV gates).
- The feature design doc's File Manifest matches the files actually created.

## Review Output Format

```markdown
# F-00055 S11 Final Cross-Agent Review

## Summary
{N} findings: {critical} CRITICAL, {high} HIGH, {medium} MEDIUM, {low} LOW
Overall assessment: approve | approve-with-fixes | reject

## Cross-Layer Seam Analysis
{summary of how layers integrate; any mismatches}

## AC Coverage Matrix
| AC | Implemented | Test | Notes |
|----|-------------|------|-------|
| AC1 | ✅ | ✅ | ... |
| ... | ... | ... | ... |

## Invariant Verification
| Inv | Enforced | Test | Notes |
|-----|----------|------|-------|
| 1 | ✅ | ✅ | ... |
| ... | ... | ... | ... |

## Findings
### F01 [SEVERITY]: {title}
**Layer**: {pipeline|backend|api|frontend|tests|cross-layer}
**File**: `path/to/file.py:line`
**Issue**: ...
**Fix**: ...

## Regression Risk
{any identified regressions to existing behavior}

## Recommendation
{proceed | fix blockers in S12 | escalate}
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "code-review-final-impl",
  "work_item": "F-00055",
  "completion_status": "complete",
  "review_verdict": "approve|approve-with-fixes|reject",
  "findings_critical": 0,
  "findings_high": 0,
  "findings_medium": 0,
  "findings_low": 0,
  "ac_coverage_pct": 100,
  "invariants_verified": 10,
  "notes": ""
}
```
