# F-00066_S02_CodeReview_Backend_prompt

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00066/F-00066_Feature_Design.md`
- `ai-dev/active/F-00066/reports/F-00066_S01_Backend_report.md`
- `dashboard/routers/code_qa.py`
- `orch/rag/qa.py`

## Output Files

- `ai-dev/active/F-00066/reports/F-00066_S02_CodeReview_Backend_report.md`

## Review Checklist

### Block detection helper
- [ ] `_FENCED_BLOCK_RE` is module-level; uses `re.DOTALL`; pattern `r"```(mermaid|d2)\n(.*?)```"`
- [ ] `_find_new_diagram_blocks` never raises (try/except wraps the body)
- [ ] Deduplication: `(lang, dsl)` keys correctly prevent re-processing the same block
- [ ] Helper is a pure function (no side effects)

### Import guard
- [ ] `render_mermaid` / `render_d2` imported inside `try/except ImportError`
- [ ] `_DIAGRAM_RENDER_AVAILABLE` flag used to gate block detection in `_sse_generator`
- [ ] Stub functions in the `except` branch have correct return types (`str | None`)

### SSE generator changes
- [ ] Block detection only runs in the `kind == "token"` branch (not phase/citation/error)
- [ ] Both token paths (dict `kind=="token"` AND raw `str` fallback) accumulate to `accumulated_text`
- [ ] `loop.run_in_executor(None, render_func, dsl)` — async-safe, doesn't block the event loop
- [ ] `image` event emitted ONLY when `svg` is not None
- [ ] `block_emit_index` increments for ALL processed blocks (including ones where render returned None)
- [ ] `block_emit_index` is initialized before the while loop, not inside it

### Security
- [ ] SVG content from render is base64-encoded before embedding in JSON — no raw SVG in the SSE payload
- [ ] No user-controlled data interpolated into the `img_payload` JSON except via `json.dumps` (safe)

### System prompt
- [ ] D2 bullet added to `RENDERING_CAPABILITIES_BLOCK`
- [ ] Proactive diagram note added ("If a diagram would make an architectural relationship clearer...")
- [ ] `DIAGRAM_DIRECTIVE_BLOCK` unchanged

### Existing tests
- [ ] All existing `tests/dashboard/test_code_qa_sse_wire.py` tests still pass

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00066",
  "completion_status": "complete|partial|blocked",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}],
  "approved": true,
  "notes": ""
}
```
