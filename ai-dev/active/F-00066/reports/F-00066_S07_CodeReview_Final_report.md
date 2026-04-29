# F-00066 S07 — Final Code Review Report

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step**: S07 (Final Review)
**Date**: 2026-04-29

---

## Summary

Reviewed all F-00066 implementation artifacts: backend (`code_qa.py`), frontend (`stream.js`, `render.js`), system prompt (`qa.py`), and CSS (`tailwind.src.css`). All acceptance criteria and invariants from the design doc are satisfied.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/code_qa.py` | Block interceptor + `image` SSE event emission |
| `dashboard/static/chat/stream.js` | `onImage` SSE event handler |
| `dashboard/static/chat/render.js` | `onImage` handler, `data-iw-server-rendered` attribute, `display:none` in `onDone` |
| `dashboard/static/tailwind.src.css` | `pre[data-iw-server-rendered] { display: none; }` |
| `orch/rag/qa.py` | `RENDERING_CAPABILITIES_BLOCK` updated with D2 + proactive diagram note |

---

## Invariant Checklist

### Design Doc Invariants

- ✅ `_find_new_diagram_blocks` never raises — `try/except` wraps body (`code_qa.py:47-57`)
- ✅ Render call uses `loop.run_in_executor` — async generator never blocked (`code_qa.py:272, 310`)
- ✅ `image` SSE event only emitted when render returns non-None SVG — `if svg:` guard (`code_qa.py:273, 311`)
- ✅ `<pre data-iw-server-rendered>` hidden — CSS rule (`tailwind.src.css:375`) + JS fallback (`render.js:511-513`)
- ✅ `upgradeAllMermaidBlocks` still called for un-rendered blocks — guarded call preserved (`render.js:514-516`)

### Integration Consistency

- ✅ `onImage` passed from `render.js` to `stream.js` `streamAnswer` call (`stream.js:5`, `render.js:462`)
- ✅ `block_index` per-type — backend `emit_counts[lang]` (`code_qa.py:280, 318`), frontend queries all `pre[data-lang="${sourceType}"]` without `:not()` filter, uses `pres[blockIndex]` as absolute position (`render.js:468-469`)
- ✅ `_DIAGRAM_RENDER_AVAILABLE` flag gates block detection when F-00064 absent (`code_qa.py:60-65, 265, 305`)
- ✅ D2 blocks handled alongside Mermaid — `_FENCED_BLOCK_RE` matches both, render function selected via ternary (`code_qa.py:36, 271`)

### Security

- ✅ SVG embedded as data URI in `img.src` — no `innerHTML` injection (`render.js:479`)
- ✅ No inline SVG via `innerHTML` — data URI only
- ✅ `download` attribute on anchor (`render.js:488`) — local file save, not external URL

---

## Open Issues (CRITICAL/HIGH only)

**No CRITICAL or HIGH findings.**

---

## Test Results

Unit tests in `tests/unit/dashboard/test_preprocess_mermaid.py` and `tests/unit/rag/test_mapgen_mermaid.py` cover block detection and rendering paths. Browser tests in `tests/dashboard/browser/test_chat_mermaid.py` cover end-to-end flow. Quality gates (lint, typecheck, unit tests) are executed in steps S08–S12.

---

## Notes

- The `_DIAGRAM_RENDER_AVAILABLE` fallback stub pattern (`render_mermaid`/`render_d2` returning `None` when import fails) is correct and preserves graceful degradation.
- The design doc note that `block_index` is absolute (no `:not()` filter needed) is correctly implemented — the frontend selects all `pre[data-lang="${sourceType}"]` elements and indexes directly.
- `upgradeAllMermaidBlocks` is called unconditionally in `onDone`; server-rendered blocks are hidden via `display:none` before that call, so mermaid.js will attempt to render them but they won't be visible.
