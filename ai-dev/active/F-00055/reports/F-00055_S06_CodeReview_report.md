# F-00055 S06 Code Review Report

## Summary

Reviewed S05 (SSE protocol extension) implementation against the feature design, invariants, and acceptance criteria. **APPROVE** — all must-check items pass.

## Files Reviewed

### Modified
- `dashboard/routers/code_qa.py` — SSE generator extensions, `_CitationTracker` work-item tracking, `/findusages` symbol-hint extraction, rerender endpoint
- `orch/rag/qa.py` — `_emit_phase`, `_emit_citation`, `_emit_token` helpers; `symbol_hint` parameter flow

### New (test files)
- `tests/unit/test_code_qa_router_phase.py` — 243 lines
- `tests/unit/test_code_qa_router_citations.py` — 148 lines
- `tests/unit/test_code_qa_router_findusages.py` — 78 lines
- `tests/unit/test_code_qa_router_rerender.py` — 79 lines

## Findings

| # | Severity | Item | Status |
|---|----------|------|--------|
| 1 | CRITICAL | Event shape compliance (Invariant 4) — citation events carry `work_item_type` + `work_item_id` with regex enforcement | ✅ PASS |
| 2 | CRITICAL | Backward compatibility (Invariant 3) — code-only pipeline emits zero `phase` events | ✅ PASS |
| 3 | HIGH | Thread-bridge queue — dicts with None sentinel | ✅ PASS |
| 4 | HIGH | Symbol-hint flow (AC7) — findusages chip extracts symbol and passes to engine | ✅ PASS |
| 5 | HIGH | Router thinness — no business logic in router | ✅ PASS |
| 6 | HIGH | Error handling — engine exceptions emit `event: error` without corrupting SSE stream | ✅ PASS |
| 7 | MEDIUM | Test coverage — three dedicated test files covering phase events, citation shapes, findusages routing | ✅ PASS |
| 8 | LOW | No regression to `/api/projects/{id}/code/qa-with-image` — 501 stub untouched | ✅ PASS |

### Detail

**1. Event shape compliance (Invariant 4)**  
`_CitationTracker.add_work_item()` validates `work_item_id` format via `WORK_ITEM_ID_RE = re.compile(r"^(F|I|CR)-\d{5}$")` (line 35, 89-90). `_sse_generator` citation branch serialises `work_item_type` and `work_item_id` from `item` dict into the SSE payload (lines 233-244). The regex rejects lowercase prefixes, short digit counts, and unknown prefixes. ✅

**2. Backward compatibility (Invariant 3)**  
`QAEngine.answer_stream` (original, non-phase-aware) yields bare strings. The `_sse_generator` handles these via `isinstance(item, str)` at line 201 — wrapping as base64 token events with **no** phase event ever emitted for the code-only path. Only `answer_stream_v2` produces phase events. ✅

**3. Thread-bridge queue**  
`queue.Queue[object]` declared at line 176 carries `dict | str | None`. Error path (`ConnectionRefusedError`, `OSError`) puts `{"kind": "error", ...}` dicts (lines 146-148). `_sse_generator` routes all dicts by `kind` key (lines 212-244). `None` sentinel breaks the loop at line 198-199. ✅

**4. Symbol-hint flow (AC7)**  
`findusages` in `request.context_chips` triggers `symbol_hint = request.question.strip()` at line 281. This is passed to `_sse_generator` → `_run_qa_in_thread` → `engine.answer_stream_v2(..., symbol_hint=symbol_hint)`. In `qa.py` the hint is injected into the LanceDB code query at line 462 (`text LIKE '%{safe_symbol}%'`). ✅

**5. Router thinness**  
`code_qa` router (lines 252-303): validates project existence, checks index path, extracts `symbol_hint`, delegates entirely to `_sse_generator`. No retrieval logic, no citation allowlist enforcement, no LLM interaction. ✅

**6. Error handling**  
`_run_qa_in_thread` catches `ConnectionRefusedError` and `OSError` at lines 145-148, pushes an error dict. The `_sse_generator` emits `event: error` and returns cleanly (lines 214-217). Connection errors from the thread also generate error tokens prefixed `__ERROR__:` (lines 225-229) which are similarly routed. No unhandled exceptions escape the SSE stream. ✅

**7. Test coverage**  
- `test_code_qa_router_phase.py`: `_CitationTracker` work-item extension (all 3 types + regex), phase/token/citation event payload structures, `QARequest` context_chips schema, `QARerenderRequest` tone validation  
- `test_code_qa_router_citations.py`: duplicate deduplication, invalid format raises `ValueError`, symbol/work-item ID shared tracker, all `work_item_type` values  
- `test_code_qa_router_findusages.py`: symbol_hint extraction, multi-word preservation, multiple chips, absence without findusages  
- `test_code_qa_router_rerender.py`: tone enum validation, cache miss returns `None`, cache hit returns bundle  
**42 passed**, 0 failed ✅

**8. No regression to `qa-with-image`**  
Endpoint unchanged at lines 306-317, still returns 501. ✅

## Quality Gates

| Check | Result |
|-------|--------|
| `uv run ruff check dashboard/routers/code_qa.py` | ✅ All checks passed |
| `uv run ruff format --check dashboard/routers/code_qa.py` | ✅ Pass |
| `uv run mypy dashboard/routers/code_qa.py` | ✅ Success: no issues |

## Verdict

**APPROVE**

All must-check items pass. S05 is a clean implementation of the SSE protocol extension. The 18 pre-existing mypy errors in `orch/rag/qa.py` (noted in S04 report) remain and are out of scope for this step.

## Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00055",
  "completion_status": "complete",
  "review_verdict": "approve",
  "findings_critical": 0,
  "findings_high": 0,
  "findings_medium": 0,
  "findings_low": 0,
  "notes": "All 8 must-check items pass. 42 unit tests pass. ruff/mypy clean on router. Backward compatibility preserved for code-only pipeline. Pre-existing mypy errors in orch/rag/qa.py (18 errors, noted in S04) remain and are out of scope for S05."
}
```
