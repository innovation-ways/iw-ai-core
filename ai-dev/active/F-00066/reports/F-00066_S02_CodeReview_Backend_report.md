# F-00066 S02 Code Review — Backend

## What was reviewed

Reviewed `dashboard/routers/code_qa.py` and `orch/rag/qa.py` against the S02 checklist.

## Files changed (same as S01)

- `dashboard/routers/code_qa.py`
- `orch/rag/qa.py`

## Review findings

All checklist items pass:

| Category | Item | Status |
|----------|------|--------|
| Block detection | `_FENCED_BLOCK_RE` module-level, `re.DOTALL`, correct pattern | PASS |
| Block detection | `_find_new_diagram_blocks` never raises (try/except) | PASS |
| Block detection | `(lang, dsl)` deduplication keys | PASS |
| Block detection | Pure function, no side effects | PASS |
| Import guard | `render_mermaid`/`render_d2` in try/except ImportError | PASS |
| Import guard | `_DIAGRAM_RENDER_AVAILABLE` gates detection | PASS |
| Import guard | Stubs return `str \| None` | PASS |
| SSE generator | Block detection only in `kind=="token"` branch | PASS |
| SSE generator | Both token paths accumulate to `accumulated_text` | PASS |
| SSE generator | `loop.run_in_executor(None, render_func, dsl)` async-safe | PASS |
| SSE generator | `image` event only when `svg` is not None | PASS |
| SSE generator | `emit_counts` per-type dict initialized before loop | PASS |
| SSE generator | `emit_counts[lang]` incremented for ALL blocks (incl. None renders) | PASS |
| Security | SVG base64-encoded, no raw SVG in SSE | PASS |
| Security | `json.dumps` for img_payload construction | PASS |
| System prompt | D2 bullet in `RENDERING_CAPABILITIES_BLOCK` | PASS |
| System prompt | Proactive diagram note added | PASS |
| System prompt | `DIAGRAM_DIRECTIVE_BLOCK` unchanged | PASS |

## Test results

`tests/dashboard/test_code_qa_sse_wire.py`: **12 passed, 1 skipped, 1 xfailed**

## Observations

- The import guard approach (soft dependency on `orch.diagram.render`) is clean and well-implemented
- `emit_counts[lang]` increment placed after the SVG null-check correctly gives stable per-type indices regardless of render success/failure
- No issues found

## Conclusion

**approved: true**
