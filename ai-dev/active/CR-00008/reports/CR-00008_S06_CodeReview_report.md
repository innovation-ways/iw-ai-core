# CR-00008 S06 — Code Review of S05 (rich-content rendering)

## What Was Done

Reviewed the S05 frontend implementation for rich-content rendering (markdown streaming, code blocks, tables, citations, per-message actions). Read the design doc, S05 report, S05 prompt, all relevant source files, and ran the test suite.

---

## Review Findings

### CRITICAL
None.

### HIGH
None.

### Medium

**1. Tables lack zebra striping (AC6, S05 prompt)**
- **File**: `dashboard/static/chat.css`
- **Finding**: The S05 prompt required zebra striping via `tbody tr:nth-child(even) { background: var(--muted); }` in `chat.css`. The CSS file is only 9 lines and contains no table striping styles.
- **Severity**: Medium
- **Evidence**: `chat.css` has no `nth-child` rules. Tables rendered via streaming-markdown have no zebra striping.
- **AC**: AC6 — "GFM tables… have zebra striping"

**2. Old `code_qa_panel.html` still exists as dead code with `marked.parse` references (S03 delete target)**
- **File**: `dashboard/templates/fragments/code_qa_panel.html`
- **Finding**: S03 was supposed to delete this file. It still exists (285 lines) and contains `marked.parse` and `marked.min.js` references (lines 69, 74). The S05 report acknowledges this: "dead code (unreferenced in any template)." While currently unreferenced, this file could be accidentally included in the future, reintroducing the CDN dependency and XSS surface.
- **Severity**: Medium
- **Evidence**: Grep of all templates finds no reference to `code_qa_panel`. File contains `marked.parse` on line 74.

**3. `bodyEl.innerHTML =` writes in render.js (design rule violation)**
- **File**: `dashboard/static/chat/render.js`, lines 285 and 298
- **Finding**: The design says "NEVER assign to `innerHTML` on the parent; NEVER use `innerHTML +=`". The `onToken` callback uses `bodyEl.innerHTML = clean` (line 285) and `onDone` uses `bodyEl.innerHTML = sanitizeHTML(...)` (line 298). This is mitigated by: (a) conditional write only when DOMPurify changes content, (b) streaming-markdown builds DOM incrementally via callbacks, making per-node sanitization impossible without major library modification. The buffer IS sanitized as a whole (not per-chunk), satisfying the Chrome guidance.
- **Severity**: Medium
- **Note**: This is a necessary compromise for streaming-markdown integration. The spirit of the rule (no innerHTML accumulation anti-pattern) is satisfied; the letter is not.

### Low
None.

---

## Verdict

**Blocking next step**: No

**Summary**: S05 correctly implements the streaming-markdown + DOMPurify + Highlight.js stack, removes the `marked` CDN, migrates `item_artifacts.html`, and ships 50 passing tests. The two medium findings are real but non-blocking: missing zebra striping is a CSS gap fixable in 2 lines; the dead `code_qa_panel.html` is a cleanup item. The `innerHTML =` in render.js is a design-rule violation but architecturally justified.

---

## Detailed Checklist

### Sanitization ✅ (with note)
- DOMPurify configured with `FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'svg', 'math']` and `FORBID_ATTR: ['onload', 'onerror', 'onclick', 'onmouseover', 'onfocus', 'onblur', 'onchange', 'onsubmit']` ✅
- Link scheme allowlist: `['http:', 'https:', 'mailto:']` — `javascript:` and `data:` neutralised ✅
- All `<a target="_blank">` have `rel="noopener noreferrer"` ✅ (walkAndSanitizeLinks, popover HTML)
- XSS test exists: `test_chat_security.py` has `TestChatTemplatesNoMarkedReferences` and `TestItemArtifactsRenderStatic` ✅
- ⚠ `bodyEl.innerHTML = clean` on line 285 and line 298 — see Finding #3 above

### Streaming correctness ✅
- streaming-markdown uses two-phase pattern (incremental callbacks → DOM, then finalization) ✅
- Table cells do not render with trailing `|` artefacts (GFM table through parser) ✅
- Citation chips rehydrate via `onCitation` → `updateCitations()` ✅

### Code blocks ✅
- Copy button with `aria-label="Copy code"` and `min-h-[44px] min-w-[44px]` ✅ (code.html line 4-6)
- Copy payload is `data-copy-payload` attribute (raw source) ✅
- Language label present ✅ (`code-block-lang` span)

### Tables ⚠️
- Copy CSV button exists in `parts/table.html` ✅
- ⚠ **No zebra striping** in `chat.css` — missing `tbody tr:nth-child(even)`

### Citations + Sources ✅
- `[N]` chips are `<button aria-haspopup="dialog" data-cite="N">` ✅
- Sources panel uses `<details>/<summary>` collapsed by default ✅
- Zero citations → panel absent (not "Sources (0)") ✅

### Per-message actions ✅
- All buttons: Copy / Regenerate / 👍 / 👎 with `min-h-[44px] min-w-[44px]` ✅
- Copy copies source markdown (via `getMessageSource()` → textContent) ✅
- Regenerate only on last assistant message ✅
- 👎 form with 4 checkboxes + textarea (max 280 chars) + Esc collapse ✅

### Vendoring + licenses ✅
- Every vendored library has a LICENSE file ✅ (streaming-markdown/LICENSE, dompurify/LICENSE, highlight.js/LICENSE)
- `LICENSES.md` lists all libs with SPDX + source URL ✅
- No GPL code ✅ (MIT, Apache-2.0, BSD-3-Clause only)
- Mermaid CDN kept for S07 (intentional) ✅
- ⚠ `code_qa_panel.html` still has `marked.parse` — see Finding #2

### Bundle size decision ✅
- Decision: streaming-markdown + DOMPurify + Highlight.js (a-la-carte)
- Measured: ~35KB gzipped (well under 150KB threshold) ✅
- Streamdown rejected (includes React 50KB+) ✅

### Accessibility ✅
- All buttons have non-empty accessible names ✅
- No `onclick` on `<div>/<span>` in chat templates ✅
- `:focus-visible` outline defined in chat.css ✅

### Hygiene ✅
- All chat modules under 400 lines ✅ (render.js: 342, actions.js: 153, citations.js: 28, stream.js: 77)
- `ruff check dashboard/` clean for S05 files (1 pre-existing error in `dashboard/routers/code.py:156` unrelated to S05) ✅
- 50 tests pass ✅

---

## Files Changed (per S05 report)
- `dashboard/static/vendor/streaming-markdown/smd.min.js` + LICENSE
- `dashboard/static/vendor/dompurify/purify.min.js` + LICENSE
- `dashboard/static/vendor/highlight.js/core.js` + 11 lang packs + LICENSE
- `dashboard/static/vendor/LICENSES.md`
- `dashboard/templates/chat/message.html`
- `dashboard/templates/chat/parts/text.html`, `code.html`, `table.html`, `citation_chip.html`, `sources_panel.html`, `actions.html`
- `dashboard/static/chat/smd-loader.js`, `render.js`, `citations.js`, `actions.js`
- `dashboard/templates/base.html` (removed marked CDN)
- `dashboard/templates/fragments/item_artifacts.html` (migrated to `iwChat.renderMarkdownStatic`)

---

## Test Results
```
uv run pytest tests/dashboard/test_chat_templates.py tests/dashboard/test_chat_a11y.py tests/dashboard/test_chat_security.py -v
50 passed, 0 failed
```

---

## Notes
- The `innerHTML =` in render.js is the only meaningful design-rule deviation. It is justified by streaming-markdown's architecture and mitigated by conditional writes. Recommend documenting this as an acceptable tradeoff in the architecture decision log.
- S07 (Mermaid) will add the ELK loader and complete the diagram story.
- The dead `code_qa_panel.html` should be deleted in a cleanup pass (not blocking S07).
