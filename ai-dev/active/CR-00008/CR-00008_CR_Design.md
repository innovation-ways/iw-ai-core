# CR-00008: Code module chat — docked panel, streaming markdown, beautiful diagrams (MVP)

**Type**: Change Request
**Priority**: Medium
**Reason**: UX pain — current bottom-pinned chat forces users to scroll away from the reading surface and loses position; markdown rendering is jank-prone (per-token `innerHTML` rewrite); Mermaid output is visually illegible. Consolidates findings from four deep research documents into a tight MVP.
**Created**: 2026-04-17
**Status**: Draft

---

## Description

Replace the bottom-pinned code-module chat with a **resizable docked right panel**, rework the streaming pipeline to be markdown-safe (buffer-level DOMPurify + streaming-aware rendering + base64-encoded SSE tokens + named events), and make Mermaid diagrams beautiful by default (ELK layout + brand themeVariables + sandboxed iframe + parse-validate). Adds table-stakes rich-content support (code blocks with copy, GFM tables, inline citations, per-message actions, image paste) and MVP input affordances (context chip for current module, three slash commands, keyboard shortcuts). All differentiators (D2/Structurizr, math, charts, artifacts, diagram auto-repair, trace-flow/test-gen use cases) are explicitly deferred to follow-up CRs.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Dashboard-specific conventions in `dashboard/CLAUDE.md`: FastAPI + Jinja2 + htmx + Tailwind CDN, **no build step**, routers thin, fragments must not extend `base.html`, SSE via `text/event-stream`.

## Research Foundation

- **R-00048** — Modern LLM chat UX for the code module view (layout, scroll, SSE plumbing)
- **R-00049** — Code-aware LLM chat in real products (killer use cases, expected gains, grounding anti-patterns)
- **R-00050** — Rich content in LLM chat (markdown, code, tables, diagrams, images, citations, accessibility, security)
- **R-00051** — Beautiful LLM-generated diagrams (Mermaid+ELK as highest-ROI fix)

## Current Behavior

- **Chat panel**: `dashboard/templates/fragments/code_qa_panel.html` (284 lines, self-contained; includes ~100 lines of inline `<script>`) is included at the **bottom of `project_code.html`** inside a collapsible card. Conversation area is capped at `max-h-72` (~18rem) with its own internal scroll.
- **Rendering**: `marked.min.js` loaded from `cdn.jsdelivr.net` in `base.html`. On every streamed token, the full accumulated markdown buffer is re-parsed with `marked`, re-sanitized with DOMPurify, and assigned to `responseSpan.innerHTML`. This is the **O(n²) + per-chunk-sanitize** anti-pattern identified by Chrome's LLM-rendering guidance.
- **SSE wire format** (`dashboard/routers/code_qa.py`): plain JSON payloads — `data: {"token": "..."}` and `data: {"event": "done", "full_response": "..."}`. No `event:` SSE field, no base64, no citation events. Tokens containing a `\n` can silently corrupt the SSE framing.
- **Mermaid**: not currently rendered. Fenced ` ```mermaid ` blocks from the model appear as plain code.
- **Citations / sources**: not surfaced in the UI.
- **Per-message actions**: none. No copy button, no thumbs up/down, no regenerate.
- **Image input**: not supported.
- **Slash commands**: none. Single free-form input.
- **Keyboard**: Enter sends. No Shift+Enter newline, no Esc to cancel, no panel toggle, no `/` focus.
- **Scroll behavior**: simple `scrollTop = scrollHeight` on every token — fights the user if they scroll up mid-stream.
- **Accessibility**: conversation container is a plain `<div>`, no `role="log"`, no `aria-live`, buttons styled with tailwind classes but use real `<button>` tags.

## Desired Behavior

- **Chat panel**: docked to the right of the code module reading surface, viewport-height, resizable (drag handle on left edge), width persisted to `localStorage` (default 400px, clamped 320–480). Collapse toggle animates to a 48px icon rail bound to `Cmd+\`. Below a 900px viewport, falls back to a slide-over drawer triggered by a floating button. Reading surface scrolls **independently** of the chat.
- **Rendering**: vendored **Streamdown** (or `streaming-markdown + DOMPurify + Highlight.js` composed a-la-carte if Streamdown gzipped exceeds ~150KB). Rendering strategy: `element.append()` new nodes incrementally; never `innerHTML +=` and never `textContent +=`; sanitize the **accumulated buffer** on each flush (not per chunk). GFM tables, syntax-highlighted code blocks with copy-to-clipboard + language label, GFM task lists, links with `rel="noopener noreferrer"`.
- **SSE wire format**: tokens base64-encoded server-side to eliminate newline-in-SSE corruption. Named events:
  - `event: token` — `data: {"b64": "<base64>"}`  (content delta, base64 of utf-8 bytes)
  - `event: citation` — `data: {"n": 1, "label": "orch.rag.qa:answer_stream", "url": "/project/<id>/code/module/orch.rag.qa#answer_stream", "snippet": "…first N lines…"}` (cumulative, can arrive mid-stream)
  - `event: done` — `data: {"ok": true}`
  - `event: error` — `data: {"message": "…"}`
- **Mermaid**: vendored Mermaid + ELK loader. Every fenced ` ```mermaid ` block is `mermaid.parse()`-validated **before render**; successful blocks render in a sandboxed iframe (`securityLevel: 'sandbox'`) with `layout: elk`, `look: handDrawn`, and `themeVariables` injected from the `iw-brand-config` palette (primary, accent, background, text, line, border colors as hex). Render failure produces a collapsed "Diagram error" chip showing the raw code + a Retry button. No LLM-based auto-repair in this CR.
- **Citations**: inline numbered `[1][2][3]` in-text; each triggers a small popover with label + code snippet + jump-to-source link. An expandable **Sources** section appears at the end of every assistant message listing all cited symbols.
- **Per-message actions**: on hover/focus — Copy (full message), Regenerate (last assistant message only), Thumbs-up, Thumbs-down. Thumbs-down expands a small inline form with categories (Inaccurate / Not relevant / Incomplete / Harmful) + optional free-text.
- **Image input**: clipboard paste, drag-and-drop onto the composer, and a paperclip file-picker. Accepts JPEG/PNG/GIF/WEBP. Renders as a chip above the input (with "remove"), then as a thumbnail attachment on the sent user message. Backend attachment plumbing is **out of scope**; this CR only adds the client-side chip + server-side multipart acceptance stub returning 501 if engaged (tracked as future work in the report).
- **Slash commands**: `/explain`, `/findusages`, `/diagram` — on type, autocomplete menu appears; on accept, the command + the current module context are rendered as two chips above the input; sending dispatches the command to the standard SSE endpoint (server-side dispatch is a single-line prompt-template branch).
- **Keyboard**: `Cmd+Enter` send, `Shift+Enter` newline, `Esc` cancels active stream (aborts `fetch`), `Cmd+\` toggles the panel, `/` focuses the composer from anywhere on the code module page.
- **Context chip**: auto-populated with `#module:<current-module>` when a module page is open, removable by the user; a small scoping control above the input.
- **Scroll behavior**: stick-to-bottom via IntersectionObserver on an invisible anchor; releases stickiness the moment the user scrolls up; surfaces a "scroll to bottom" button when released. `min-height: 50dvh` padding on the last assistant message to prevent bottom-hug jitter. First paint uses `behavior: 'instant'`; subsequent `'smooth'`.
- **Accessibility**: message list is `role="log" aria-live="polite" aria-relevant="additions"`. Streaming tokens are **not** individually announced; assistant messages are announced **on completion** via a hidden live-region pushing a short summary ("Assistant response ready"). All actions are real `<button>` elements with 44×44 hit targets (tailwind `min-h-[44px] min-w-[44px]`) and visible focus rings.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `dashboard/templates/fragments/code_qa_panel.html` | 284-line monolith with inline CSS + `<script>` | Split into docked-panel shell + Jinja partials (message/code_block/table/mermaid/citation_chip/sources_panel/actions/composer) |
| `dashboard/templates/project_code.html` | Panel included at bottom | Panel mounted into a new `<aside>` region; reading surface re-flowed to a 2-column layout via grid |
| `dashboard/routers/code_qa.py` | Plain JSON SSE, no events, no citations | Base64-encoded tokens, named events, citation payloads, optional multipart image input (501-stub) |
| `dashboard/static/` | Only `duration.js`, `theme.css`, `theme-toggle.js`, `favicon.svg`, `logo.png` | Adds `vendor/` tree (Streamdown or streaming-markdown, DOMPurify, Highlight.js, Mermaid+ELK) + `chat/` tree (JS modules for panel, stream, render, mermaid, citations, actions, composer) + `chat.css` |
| `base.html` | `marked.min.js` + DOMPurify from CDN | Removed from `base.html`; new vendored includes scoped to the code page only |
| `dashboard/templates/fragments/item_artifacts.html` | Uses `window.marked` + `viewer.innerHTML = marked.parse(text)` to render markdown artifact previews | Migrated onto the new vendored pipeline via `iwChat.renderMarkdownStatic(text)`; no more raw-HTML assignment |
| `orch/rag/qa.py` (read-only for this CR) | Yields raw text tokens | Unchanged — base64-encoding happens at the SSE boundary in `code_qa.py` |

### Breaking Changes

- **SSE wire format on `POST /api/projects/{id}/code/qa`** changes: named events (`token`/`citation`/`done`/`error`) replace the old `{"token": "..."}` and `{"event": "done"}` shape. Token payload is now `{"b64": "..."}`. No external consumers of this endpoint exist; the only client is the code_qa_panel fragment which is being rewritten in this same CR.
- **Vendored library switch**: `marked` is removed from `base.html`. The one other in-tree consumer identified during design review is `dashboard/templates/fragments/item_artifacts.html` (markdown artifact preview in the work-item detail page); S05 migrates it onto the new vendored pipeline in the same step to avoid a broken-feature window. A grep of all templates for `marked` / `marked.parse` is part of S05's close-out checks.

### Data Migration

- None. No schema changes. No persisted state changes. `conversation_history` payload shape in requests is unchanged.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | api-impl | SSE wire format: base64 tokens, named events (`token`/`citation`/`done`/`error`), citation payload schema, multipart image 501-stub, contract update in `code_qa.py` | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | frontend-impl | Docked right panel shell: resize handle, localStorage width persistence, `Cmd+\` collapse, <900px drawer fallback, 2-column grid reflow of `project_code.html`, scroll-behavior (IntersectionObserver anchor + scroll-to-bottom button), keyboard shortcuts, composer context-chip + slash-command autocomplete + image paste/drop chip | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | frontend-impl | Vendor Streamdown (or streaming-markdown + DOMPurify + Highlight.js) under `dashboard/static/vendor/`; new `dashboard/static/chat/` modules: `stream.js`, `render.js`, `citations.js`, `actions.js`; Jinja partials: `message.html`, `parts/text.html`, `parts/code.html`, `parts/table.html`, `parts/citation_chip.html`, `parts/sources_panel.html`, `parts/actions.html`; per-message actions with thumbs-down categorized form; **migrate `dashboard/templates/fragments/item_artifacts.html` off `window.marked` onto the new pipeline (`iwChat.renderMarkdownStatic`)** so removing the CDN `marked.min.js` from `base.html` is safe | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | frontend-impl | Vendor Mermaid + ELK loader; `dashboard/static/chat/mermaid.js`: `parse()` validation before render, sandboxed iframe (`securityLevel: 'sandbox'`), `layout: elk`, `look: handDrawn`, `themeVariables` sourced from `iw-brand-config` CSS vars; error chip + Retry button partial `parts/mermaid.html` | — |
| S08 | code-review-impl | Review S07 | — |
| S09 | tests-impl | Pytest: SSE wire-format contract (token b64 round-trip, citation ordering, `done` event, `error` on upstream failure); Python unit for `code_qa._sse_generator`; Jinja partial render tests; a11y attribute assertions on template output; JS smoke test via Playwright for panel mount + keyboard shortcuts | — |
| S10 | code-review-impl | Review S09 | — |
| S11 | code-review-final-impl | Cross-agent review — consistency between SSE payload and client rendering; sanitation path reviewed end-to-end; no `innerHTML +=`; all tests tie to acceptance criteria | — |
| S12 | code-review-fix-final-impl | Apply CRITICAL/HIGH fixes from S11 | — |
| S13 | qv-gate | QV: lint — `uv run ruff check .` | — |
| S14 | qv-gate | QV: format — `uv run ruff format --check .` | — |
| S15 | qv-gate | QV: typecheck — `uv run mypy orch/ dashboard/` | — |
| S16 | qv-gate | QV: unit tests — `make test-unit` | — |
| S17 | qv-gate | QV: integration tests — `make test-integration` | — |
| S18 | qv-browser | End-to-end browser verification on the isolated worktree stack | — |

Notes on QV gates:
- Per `iw-workflow` skill, each QV check is a separate `qv-gate` step with `gate` + `command` fields (no prompt). Route-smoke, no-CDN-residue, license-index, and stale-fragment-deleted checks from the earlier aggregate design are instead asserted as pytest cases in S09 (`tests/dashboard/test_chat_security.py` and `test_chat_templates.py`) so they run under the standard `make test-unit` gate.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A

### API Changes

- **New endpoints**: None (reuse `POST /api/projects/{id}/code/qa`). Optional `POST /api/projects/{id}/code/qa` multipart variant returns **501 Not Implemented** for now — reserved slot for image attachments.
- **Modified endpoints**: `POST /api/projects/{id}/code/qa` — SSE response body reshaped to named events (`token` with b64 payload, `citation`, `done`, `error`). Request body unchanged.
- **Removed endpoints**: None.

### Frontend Changes

- **New components / partials** (under `dashboard/templates/chat/`):
  - `panel.html` (docked panel shell; included by `project_code.html`)
  - `composer.html` (input, context chips, slash-command menu, image input)
  - `message.html` (user/assistant message shell)
  - `parts/text.html`, `parts/code.html`, `parts/table.html`, `parts/mermaid.html`, `parts/citation_chip.html`, `parts/sources_panel.html`, `parts/actions.html`
- **New static tree**:
  - `dashboard/static/vendor/` — vendored libraries with LICENSE files alongside each
  - `dashboard/static/chat/panel.js`, `stream.js`, `render.js`, `mermaid.js`, `citations.js`, `actions.js`, `composer.js`
  - `dashboard/static/chat.css` — panel layout + brand theme hooks
- **Modified components**:
  - `dashboard/templates/project_code.html` — 2-column grid layout, mount panel as `<aside>`
  - `dashboard/templates/base.html` — **remove** CDN `marked.min.js`; keep DOMPurify only if not replaced by Streamdown's bundle
- **Removed components**:
  - `dashboard/templates/fragments/code_qa_panel.html` (superseded by `chat/panel.html` and `chat/parts/*`)

### Pipeline / Template / Docs Changes

- None.

### Security Considerations

- **Sanitize accumulated buffer, not per chunk** (Chrome guidance, R-00050 F2/F12).
- **Never render raw SVG from model output** — strip or show as code.
- **Mermaid**: always `securityLevel: 'sandbox'` + strict CSP in the iframe (`default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'`).
- **Pin DOMPurify** to a current patched version; add to dependency watch.
- **All outbound links** in assistant messages get `rel="noopener noreferrer"`.
- **Markdown link scheme allowlist**: `http`, `https`, `mailto`; block `javascript:` and `data:`.
- **Image paste** — no server storage in this CR; chip is client-only and the stub endpoint returns 501. If the user attempts a send with an image attached, the UI explicitly blocks with a "coming soon" toast (no silent drop).
- **Vendored asset licenses** — each vendored library must ship its LICENSE file alongside the source: Mermaid (MIT), ELK loader (EPL-2.0, weak copyleft — preserve notices), streaming-markdown (MIT) or Streamdown (MIT + bundled Shiki MIT + KaTeX MIT), DOMPurify (Apache-2.0 or MPL-2.0), Highlight.js (BSD-3-Clause). All OSS-compatible; no GPL. Add a `dashboard/static/vendor/LICENSES.md` index.

## File Manifest

| Path | Action | Owner Agent |
|------|--------|-------------|
| `ai-dev/active/CR-00008/CR-00008_CR_Design.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/workflow-manifest.json` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S01_Api_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S02_CodeReview_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S03_Frontend_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S04_CodeReview_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S05_Frontend_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S06_CodeReview_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S07_Frontend_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S08_CodeReview_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S09_Tests_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S10_CodeReview_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S11_CodeReview_Final_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S12_CodeReview_Fix_Final_prompt.md` | Create | iw-new-cr |
| `ai-dev/active/CR-00008/prompts/CR-00008_S18_BrowserVerification_prompt.md` | Create | iw-new-cr |
| `dashboard/routers/code_qa.py` | Modify | S01 |
| `dashboard/templates/project_code.html` | Modify | S03 |
| `dashboard/templates/base.html` | Modify | S05 |
| `dashboard/templates/fragments/item_artifacts.html` | Modify | S05 |
| `dashboard/templates/fragments/code_qa_panel.html` | **Delete** | S03 |
| `dashboard/templates/chat/panel.html` | Create | S03 |
| `dashboard/templates/chat/composer.html` | Create | S03 |
| `dashboard/templates/chat/message.html` | Create | S05 |
| `dashboard/templates/chat/parts/text.html` | Create | S05 |
| `dashboard/templates/chat/parts/code.html` | Create | S05 |
| `dashboard/templates/chat/parts/table.html` | Create | S05 |
| `dashboard/templates/chat/parts/mermaid.html` | Create | S07 |
| `dashboard/templates/chat/parts/citation_chip.html` | Create | S05 |
| `dashboard/templates/chat/parts/sources_panel.html` | Create | S05 |
| `dashboard/templates/chat/parts/actions.html` | Create | S05 |
| `dashboard/static/chat.css` | Create | S03 |
| `dashboard/static/chat/panel.js` | Create | S03 |
| `dashboard/static/chat/stream.js` | Create | S03 |
| `dashboard/static/chat/render.js` | Create | S05 |
| `dashboard/static/chat/mermaid.js` | Create | S07 |
| `dashboard/static/chat/citations.js` | Create | S05 |
| `dashboard/static/chat/actions.js` | Create | S05 |
| `dashboard/static/chat/composer.js` | Create | S03 |
| `dashboard/static/vendor/<libs>/*` | Create | S05 (Streamdown/DOMPurify/Highlight.js), S07 (Mermaid+ELK) |
| `dashboard/static/vendor/LICENSES.md` | Create | S05 |
| `tests/dashboard/test_code_qa_sse_wire.py` | Create | S09 |
| `tests/dashboard/test_chat_templates.py` | Create | S09 |
| `tests/dashboard/test_chat_a11y.py` | Create | S09 |

## Acceptance Criteria

**AC1 — Docked right panel**
- **Given** a user viewing `/project/<id>/code` at ≥900px viewport
- **When** the page loads
- **Then** the chat is rendered as a `<aside>` docked to the right at 400px width (or the localStorage-persisted value), with an internal scroll independent of the reading surface, and a drag handle on its left edge

**AC2 — Panel collapse and drawer fallback**
- **Given** the panel is visible on desktop
- **When** the user presses `Cmd+\`
- **Then** the panel animates to a 48px rail; pressing again restores it
- **And when** the viewport is below 900px
- **Then** the panel is hidden by default and replaced by a floating button that opens it as a slide-over drawer

**AC3 — SSE wire format with named events and base64 tokens**
- **Given** a question is sent
- **When** the server streams tokens, each containing newlines inside
- **Then** each token arrives as `event: token\ndata: {"b64": "..."}\n\n`, decodes server-equivalent UTF-8, and the rendered output is byte-identical to the concatenated tokens

**AC4 — Streaming markdown renders without jank or XSS**
- **Given** a 500+ token assistant response containing bold, code fences, tables, and a link
- **When** the stream completes
- **Then** the DOM never contains a literal `**` or half-open fence, no `innerHTML +=` is used, DOMPurify has been called on the buffer (not per chunk), and a payload containing `<script>` in the model output does not execute

**AC5 — Code blocks**
- **Given** an assistant message with a `” ```python ` fenced block
- **When** streaming completes
- **Then** the block is highlighted (Highlight.js or Shiki), has a language label and a copy button, and the copy button places the exact original source on the clipboard

**AC6 — GFM tables**
- **Given** an assistant message with a GFM table
- **When** rendered
- **Then** the table has zebra striping + a "Copy CSV" button that copies the table contents in CSV format

**AC7 — Inline citations and sources panel**
- **Given** the server emits `event: citation` events during the stream
- **When** the assistant message renders
- **Then** each `[N]` in the text is a popover trigger showing `{label, snippet, jump-to-source URL}` and the end of the message shows an expandable Sources panel listing every citation in order

**AC8 — Beautiful Mermaid rendering**
- **Given** a model response containing a `” ```mermaid ` flowchart of ≥8 nodes
- **When** rendered
- **Then** the diagram renders in a sandboxed iframe with `layout: elk` applied, the brand palette injected via `themeVariables`, no overlapping edges are present on an open-source reference diagram used in testing, and the client has called `mermaid.parse()` successfully before render

**AC9 — Mermaid render-failure fallback**
- **Given** the model emits invalid Mermaid syntax
- **When** rendering
- **Then** `mermaid.parse()` rejects, the UI shows a "Diagram error" chip with the raw code and a Retry button; no iframe is mounted

**AC10 — Per-message actions and feedback**
- **Given** an assistant message is rendered
- **When** the user hovers the message
- **Then** Copy / Regenerate / 👍 / 👎 buttons are visible
- **And when** the user clicks 👎
- **Then** a categorized form expands (Inaccurate / Not relevant / Incomplete / Harmful) accepting optional free-text

**AC11 — Scroll behavior**
- **Given** the assistant is streaming
- **When** the user scrolls up mid-stream
- **Then** auto-scroll releases; a "↓ Jump to latest" button appears; clicking it re-locks stick-to-bottom

**AC12 — Keyboard and slash commands**
- **Given** the composer is focused
- **When** the user types `/ex`
- **Then** an autocomplete menu surfaces `/explain`, `/findusages`, `/diagram`
- **And** `Cmd+Enter` sends, `Shift+Enter` inserts a newline, `Esc` cancels an active stream, `Cmd+\` toggles the panel, `/` pressed anywhere on the page focuses the composer

**AC13 — Image input chip (client-only, server stub)**
- **Given** the user pastes a PNG into the composer
- **When** the clipboard event fires
- **Then** a thumbnail chip appears above the composer with a remove button
- **And when** the user sends with a chip attached
- **Then** the server returns 501 and the UI shows a "Image attachments coming soon" toast without losing the typed message

**AC14 — Accessibility**
- **Given** a screen reader is active
- **When** an assistant message completes streaming
- **Then** a hidden `role="log" aria-live="polite"` region announces completion (not per-token), the message list has a real `role="log"`, every action button is a real `<button>` with ≥44×44px hit target and a visible focus state, and all images have alt text

**AC15 — License compliance**
- **Given** the implementation vendors third-party libraries under `dashboard/static/vendor/`
- **When** the CR lands
- **Then** every vendored library ships its LICENSE file alongside the source, `dashboard/static/vendor/LICENSES.md` indexes them all with SPDX IDs, and no GPL-licensed library is included

## Rollback Plan

- **Database**: N/A (no schema changes)
- **Code**: revert the squash-merge commit. No feature flag is added for this CR — the rewrite is atomic. If a regression is found post-merge, revert to the commit immediately preceding the squash; no data cleanup needed.
- **Data**: N/A (no persisted state changes)

## Dependencies

- **Depends on**: F-00049 (Q&A SSE streaming), CR-00006 (jobs view, streaming Q&A, markdown rendering) — both completed
- **Blocks**: future CRs for D2/Structurizr diagram skills, KaTeX math, Vega-Lite charts, artifacts/canvas, server-side image attachment plumbing, `/onboard` slash command, diagram auto-repair loop, Kroki deployment

## TDD Approach

**Unit tests** (new):
- `tests/dashboard/test_code_qa_sse_wire.py` — SSE framing: each `token` event is a valid `event:` block with base64 payload; round-trip decode equals original; multi-line token does not corrupt framing; citation/done/error events emit correctly; error on upstream `ConnectionRefusedError`.
- `tests/dashboard/test_chat_templates.py` — each Jinja partial renders in isolation; `panel.html` contains `role="log"`, `aria-live="polite"`, drag handle, Cmd+\ toggle affordance; `sources_panel.html` renders a list of citation chips; `parts/code.html` has a copy button and language label slot.
- `tests/dashboard/test_chat_a11y.py` — assert real `<button>` on every action; assert `min-h-[44px]` / `min-w-[44px]`; assert `alt` present on every image element; assert no `role="presentation"` on interactive elements.

**Integration tests** (new):
- Playwright smoke: mount the panel, press `Cmd+\`, assert collapse; paste fake image, assert chip appears; type `/ex`, assert slash-command menu.
- Python: mock `QAEngine.answer_stream` to yield tokens containing `\n`, `**bold**`, fenced code, and a Mermaid block; assert the HTTP response is valid SSE and each event decodes cleanly.

**Existing tests that need updating**:
- Any test that asserts the old JSON `{"token": "..."}` shape on `/api/projects/*/code/qa` — must migrate to the named-event format.
- Existing Playwright tests touching the bottom-pinned chat fragment — must target the new `<aside>` selector.

**Test scaffolding**:
- Fixture: small Mermaid ELK "golden" render — compare SVG structurally (node/edge counts) to detect regressions on the ELK layout path.
- Fixture: a synthetic token stream containing edge cases (half-open fence, table mid-stream, citation `[N]` inside a code block).

## Notes

- **Library choice for Streamdown vs. streaming-markdown**: decided in S05 via a bounded spike. Criterion: Streamdown gzipped ≤150KB → adopt; otherwise compose `streaming-markdown + DOMPurify + Highlight.js` a-la-carte. The prompt asks the agent to measure and choose, not to debate.
- **ELK loader license** is EPL-2.0 — weak copyleft. Bundling is allowed; the LICENSE file must be present; modifications (if any) must be released under EPL-2.0. We are using it unmodified; no obligation beyond notice preservation.
- **Shiki is bundled inside Streamdown**. If we go the a-la-carte route, we use Highlight.js (smaller, faster to ship) per R-00050 F3; Shiki upgrade is a future CR.
- **Image input server storage is deliberately stubbed** to avoid conflating the UX work with a multipart-upload + storage backend design. The 501 response is the contract boundary; implementing the server side is a follow-up.
- **No feature flag**: the rewrite is atomic and the path (`/project/<id>/code`) is not user-facing production traffic yet. Risk is bounded.
- **Mermaid brand palette**: sourced from the same CSS variables (`--primary`, `--accent`, `--muted`, `--border`, `--foreground`, `--background`) used by the dashboard's Tailwind theme — no duplication of palette values.
- **Post-merge metrics to track** (not instrumented in this CR but called out for follow-up): time-to-first-token, citation click-through rate, thumbs ratio, `/diagram` invocation rate, repeat-use rate.
- **Browser pre-evidence**: `ai-dev/active/CR-00008/evidences/pre/CR-00008-before.png` captured on a running local dashboard (state: bottom-pinned chat on the iw-ai-core code page).
