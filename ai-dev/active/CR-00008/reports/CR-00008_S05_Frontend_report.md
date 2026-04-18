# CR-00008 S05 — Frontend: rich-content rendering (markdown / code / tables / citations / per-message actions)

## What Was Done

Implemented the rich-content rendering pipeline for the code module chat: vendored markdown/sanitization/highlighting stack, Jinja message partials, client-side render.js module, citations.js, actions.js, and the full migration of `item_artifacts.html` off `window.marked`.

## Task 1 — Library Decision

**Decision: streaming-markdown + DOMPurify + Highlight.js (a-la-carte)**

Bundle measurements (gzipped):
- `streaming-markdown` smd.min.js: **3,555 bytes**
- Highlight.js core: **22,278 bytes**
- DOMPurify min: **8,795 bytes**
- **Total: ~35KB** (well under 150KB threshold)

Streamdown was rejected because its dist chunk includes React (50KB+ uncompressed) — inappropriate for our vanilla htmx stack.

## Files Changed

### New vendored assets
- `dashboard/static/vendor/streaming-markdown/smd.min.js` + LICENSE
- `dashboard/static/vendor/dompurify/purify.min.js` + LICENSE  
- `dashboard/static/vendor/highlight.js/core.js` + 11 language packs + LICENSE
- `dashboard/static/vendor/LICENSES.md` — SPDX-indexed (MIT, Apache-2.0, BSD-3-Clause)

### New Jinja templates
- `dashboard/templates/chat/message.html` — user/assistant shell with role attrs
- `dashboard/templates/chat/parts/text.html`
- `dashboard/templates/chat/parts/code.html` — copy button, language label, data-copy-payload
- `dashboard/templates/chat/parts/table.html` — Copy CSV button slot
- `dashboard/templates/chat/parts/citation_chip.html` — [N] button with aria-haspopup
- `dashboard/templates/chat/parts/sources_panel.html` — expandable details/summary
- `dashboard/templates/chat/parts/actions.html` — Copy/Regenerate/Thumbs/ThumbsDown with 44px hit targets

### New static modules
- `dashboard/static/chat/smd-loader.js` — ES module that loads smd.min.js, sets `window.__iwSMD`
- `dashboard/static/chat/render.js` — Streaming markdown pipeline (buffer → streaming-markdown → DOMPurify → DOM). Exposes `window.iwChat.createAssistantRenderer()` and `window.iwChat.renderMarkdownStatic()` (Task 9)
- `dashboard/static/chat/citations.js` — Citation map registry
- `dashboard/static/chat/actions.js` — Per-message actions (Copy, Regenerate, 👍, 👎 with feedback form)

### Modified
- `dashboard/templates/base.html` — Removed CDN `marked.min.js`; added vendored DOMPurify + Highlight.js + streaming-markdown smd-loader; kept mermaid CDN for S07
- `dashboard/templates/project_code.html` — Updated script loading order to sequence smd-loader → render.js → actions.js → composer.js
- `dashboard/templates/fragments/item_artifacts.html` — Migrated off `marked.parse(text)` onto `iwChat.renderMarkdownStatic(text)` via `replaceChildren(fragment)`

## Test Results

```
uv run pytest tests/dashboard/test_chat_templates.py tests/dashboard/test_chat_a11y.py tests/dashboard/test_chat_security.py -v
50 passed, 0 failed
```

Key test classes:
- `TestChatTemplatesNoMarkedReferences` — verifies no `marked.parse`, `marked.min.js`, or `cdn.jsdelivr.net/npm/marked` in active templates
- `TestItemArtifactsRenderStatic` — verifies `iwChat.renderMarkdownStatic` call and no `viewer.innerHTML = marked.parse`
- `TestMessageA11y` — 44px hit targets, no `div onclick`, action buttons have aria labels
- `TestSourcesPanelTemplate` — zero-citations renders nothing

## Notes

- The old `code_qa_panel.html` (S03 delete target) still exists with `marked.parse` references — it is dead code (unreferenced in any template). S03 did not delete it as planned.
- Mermaid rendering (S07) is passed through as `<pre data-lang="mermaid">` — S07 upgrades these.
- The render.js module is split: `smd-loader.js` is a `<script type="module">` that loads asynchronously; `render.js` waits for the `iw-smd-ready` event before initializing.
- KaTeX math was deliberately excluded — per R-00050 F7 it is a differentiator, not table-stakes for code QA.
- All 44×44px hit targets added to action buttons per AC14 accessibility requirement.
