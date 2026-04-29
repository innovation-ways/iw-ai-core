# F-00066: Proactive diagram rendering in QA chat — server-side intercept + image SSE events

**Type**: Feature
**Priority**: High
**Created**: 2026-04-28
**Status**: Approved

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

When the LLM emits a ` ```mermaid ` or ` ```d2 ` fenced block in the QA chat stream,
the backend intercepts the complete block, renders it server-side via
`orch.diagram.render` (F-00064), and emits an `image` SSE event carrying a
base64-encoded SVG. The frontend inserts the SVG inline immediately instead of waiting
for `onDone`. If server-side rendering is unavailable (binary absent), the existing
client-side Mermaid fallback applies transparently. D2 diagrams, which have no
client-side renderer, are also surfaced this way.

## Project Context

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, and `orch/rag/CLAUDE.md`. Key patterns:
- SSE stream: `dashboard/routers/code_qa.py` `_sse_generator` yields SSE strings
- Frontend event loop: `dashboard/static/chat/stream.js` dispatches `onToken`, `onCitation`, `onPhase`, `onWorkItemCitation`, `onDone`, `onError`
- Rendering: `dashboard/static/chat/render.js` `createAssistantRenderer` implements callbacks; `onDone` calls `upgradeAllMermaidBlocks`
- Render module: `orch/diagram/render.py` (F-00064) — `render_mermaid(dsl) -> str | None`, `render_d2(dsl) -> str | None`

## Scope

### In Scope

- `dashboard/routers/code_qa.py` — add `_FENCED_BLOCK_RE` + `_find_new_diagram_blocks()` helper; in `_sse_generator`, after each token event, detect new complete fenced blocks and emit `image` SSE events (base64 SVG + source type + block index)
- `orch/rag/qa.py` — update `RENDERING_CAPABILITIES_BLOCK` to mention D2 and proactive diagram emission; add `_PROACTIVE_DIAGRAM_NOTE` to encourage the LLM to use diagrams when they aid explanation
- `dashboard/static/chat/stream.js` — handle `event: image` SSE type; call `onImage` callback (new, defaults to no-op)
- `dashboard/static/chat/render.js` — implement `onImage(data)` handler: create `<figure>` with `<img>` (SVG data URI) and a "Download SVG" link; mark the corresponding `<pre data-lang="mermaid|d2">` as `data-iw-server-rendered="1"`; in `onDone`, skip `upgradeAllMermaidBlocks` for marked elements
- New: `dashboard/templates/chat/parts/` is NOT used — the SVG insertion is handled entirely in JS (no server-rendered fragment needed for inline images)

### Out of Scope

- PDF/export rendering (separate feature)
- D2 client-side renderer library
- Image resizing or zoom-to-fit controls (can be a future CR)
- Intercepting image uploads (that's the `/code/qa-with-image` stub, separate concern)

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `code_qa.py`: block interceptor + image SSE events; `qa.py`: D2 + proactive prompt update | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | frontend-impl | `stream.js` onImage callback; `render.js` onImage handler + onDone skip logic | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | tests-impl | Unit tests: block detection, image event emission, render-failure fallback | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | code-review-final-impl | Global review of all F-00066 changes | — |
| S08 | qv-gate | lint — `make lint` | — |
| S09 | qv-gate | format — `make format-check` | — |
| S10 | qv-gate | typecheck — `make typecheck` | — |
| S11 | qv-gate | unit-tests — `make test-unit` | — |
| S12 | qv-gate | integration-tests — `make test-integration` | — |
| S13 | qv-browser | Browser verification | — |

### Database Changes

None.

### API Changes

No new endpoints. The existing `POST /api/projects/{project_id}/code/qa` SSE stream gains a new event type:

```
event: image
data: {"svg_b64": "<base64-encoded SVG>", "alt": "Diagram", "source_type": "mermaid"|"d2", "block_index": 0}
```

`block_index` is a 0-based counter of diagram blocks processed so far in this response — used by the frontend to locate and mark the corresponding `<pre>` element in the DOM.

### Backend Changes

**`dashboard/routers/code_qa.py`**:
- Add module-level constant `_FENCED_BLOCK_RE = re.compile(r"```(mermaid|d2)\n(.*?)```", re.DOTALL)`
- Add `_find_new_diagram_blocks(text: str, processed: set[tuple[str, str]]) -> list[tuple[str, str]]` — returns list of `(lang, dsl)` tuples for newly completed blocks
- In `_sse_generator`, add:
  ```python
  accumulated_text = ""
  processed_diagram_blocks: set[tuple[str, str]] = set()
  block_emit_index = 0
  ```
  After each token event yield, check for new complete blocks. For each new block:
  1. Add `(lang, dsl)` to `processed_diagram_blocks`
  2. Call `await loop.run_in_executor(None, render_func, dsl)` — `render_mermaid` for mermaid, `render_d2` for d2
  3. If SVG returned: base64-encode, yield `event: image\ndata: {...}\n\n`
  4. Increment `block_emit_index`

**`orch/rag/qa.py`**:
- Update `RENDERING_CAPABILITIES_BLOCK` to add a D2 bullet and reinforce that diagrams should be emitted proactively when helpful
- Do NOT change the `DIAGRAM_DIRECTIVE_BLOCK` (it's for the explicit `/diagram` chip — keep it separate)

### Frontend Changes

**`dashboard/static/chat/stream.js`**:
- Add `onImage` parameter (defaults to no-op) to `streamAnswer`
- In the event loop, handle `eventType === "image"`: parse `{svg_b64, alt, source_type, block_index}` and call `onImage(data)`

**`dashboard/static/chat/render.js`**:
- `createAssistantRenderer` — add `onImage` to the renderer returned, implemented as:
  1. Base64-decode `svg_b64` → SVG string
  2. Find `<pre data-lang="${source_type}">` elements in `bodyEl` that are NOT already marked — pick the one at position `block_index`
  3. Mark it: `preEl.dataset.iwServerRendered = "1"` 
  4. Create a `<figure class="chat-diagram-figure">` containing:
     - `<img src="data:image/svg+xml;base64,${svg_b64}" alt="${alt}" class="chat-diagram-img">`
     - `<figcaption>` with a "Download SVG" `<a>` link (href = data URI, download attr)
  5. Insert the `<figure>` immediately after `preEl` in the DOM
- In `onDone`: change `upgradeAllMermaidBlocks(bodyEl)` call to skip marked elements:
  ```js
  bodyEl.querySelectorAll('pre[data-lang="mermaid"]:not([data-iw-server-rendered])').forEach(...)
  // OR keep upgradeAllMermaidBlocks but it already checks for rendered state via mermaid.js
  ```
  The cleanest approach: call `upgradeAllMermaidBlocks(bodyEl)` as before but add a guard inside `upgradeMermaidBlock` (or filter before calling). Since `mermaid.js` is upstream code, the safer path is to hide/collapse the `<pre>` instead of skipping it — `<pre data-iw-server-rendered="1">` elements are hidden with CSS `display: none` so they don't appear as code blocks.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00066/F-00066_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00066/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00066/prompts/F-00066_S01_Backend_prompt.md` | Prompt | S01: interceptor + image SSE |
| `ai-dev/active/F-00066/prompts/F-00066_S02_CodeReview_Backend_prompt.md` | Prompt | S02: review S01 |
| `ai-dev/active/F-00066/prompts/F-00066_S03_Frontend_prompt.md` | Prompt | S03: stream.js + render.js |
| `ai-dev/active/F-00066/prompts/F-00066_S04_CodeReview_Frontend_prompt.md` | Prompt | S04: review S03 |
| `ai-dev/active/F-00066/prompts/F-00066_S05_Tests_prompt.md` | Prompt | S05: unit tests |
| `ai-dev/active/F-00066/prompts/F-00066_S06_CodeReview_Tests_prompt.md` | Prompt | S06: review S05 |
| `ai-dev/active/F-00066/prompts/F-00066_S07_CodeReview_Final_prompt.md` | Prompt | S07: global review |
| `ai-dev/active/F-00066/prompts/F-00066_S13_BrowserVerification_prompt.md` | Prompt | S13: browser QV |
| `dashboard/routers/code_qa.py` | Modified | Block interceptor + image SSE event emission |
| `orch/rag/qa.py` | Modified | D2 + proactive diagram in system prompt |
| `dashboard/static/chat/stream.js` | Modified | Handle `image` SSE event type |
| `dashboard/static/chat/render.js` | Modified | `onImage` handler + mark server-rendered blocks |

## Acceptance Criteria

### AC1: Mermaid block intercepted and rendered server-side

```
Given mmdc binary is available on the PATH
And the LLM emits a complete ```mermaid ... ``` block in its response
When the QA SSE stream is consumed
Then an `image` SSE event is emitted after the closing ``` of the Mermaid block
     with svg_b64 containing a valid SVG, source_type="mermaid", and block_index=0
```

### AC2: SVG appears inline without waiting for onDone

```
Given AC1 conditions
When the image event arrives at the frontend
Then a <figure class="chat-diagram-figure"> with an <img> is inserted
     immediately after the corresponding <pre data-lang="mermaid"> element
     (not waiting for the stream to end)
```

### AC3: Client-side fallback when mmdc absent

```
Given mmdc is NOT available (shutil.which("mmdc") returns None)
And the LLM emits a ```mermaid block
When the QA SSE stream is consumed
Then NO `image` SSE event is emitted
And upgradeAllMermaidBlocks renders the block client-side after onDone
     (existing behavior preserved)
```

### AC4: D2 blocks rendered server-side

```
Given d2 binary is available on the PATH
And the LLM emits a complete ```d2 ... ``` block
When the QA SSE stream is consumed
Then an `image` SSE event is emitted with source_type="d2"
     and the SVG is displayed inline in the chat
```

### AC5: Multiple blocks in one response handled

```
Given the LLM emits two separate diagram blocks in one response
When the stream is consumed
Then two image SSE events are emitted with block_index=0 and block_index=1
And both SVGs appear inline at the correct positions in the message
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Binary absent | `shutil.which("mmdc")` returns None | No `image` event; client-side fallback |
| Render timeout | `mmdc` takes > 10 seconds | No `image` event (render returns None); client-side fallback |
| Invalid DSL | Mermaid syntax error | `mmdc` returns non-zero; render returns None; no `image` event |
| Partial block | Stream ends mid-fenced-block | Block never detected as complete; no `image` event; `<pre>` left as text |
| Multiple blocks | Two diagrams in one response | Two `image` events with block_index 0 and 1 |
| D2 binary absent | `d2` binary not found | No `image` event for D2 blocks; D2 `<pre>` displayed as code |
| Same DSL twice | Identical block emitted twice | Only the first occurrence triggers a render (processed set deduplicates) |

## Invariants

1. `_find_new_diagram_blocks` MUST never raise — returns empty list on any error.
2. The render call (`render_mermaid` / `render_d2`) MUST be wrapped in `run_in_executor` to avoid blocking the async SSE generator.
3. The `image` SSE event MUST NOT be emitted when `render_mermaid`/`render_d2` returns `None`.
4. `<pre data-lang="mermaid">` blocks that receive an `image` event MUST be hidden via CSS (`data-iw-server-rendered` attribute + CSS rule `pre[data-iw-server-rendered] { display: none; }`) so they don't duplicate content.
5. The existing `upgradeAllMermaidBlocks` call in `onDone` MUST still run on un-rendered blocks (graceful fallback when server rendering is unavailable).

## Dependencies

- **Depends on**: F-00064 (provides `orch.diagram.render` with `render_mermaid` and `render_d2`)
- **Depends on**: F-00065 (establishes `<pre data-lang="mermaid">` pattern used by `upgradeAllMermaidBlocks`)
- **Blocks**: nothing

## TDD Approach

New test file: `tests/unit/dashboard/test_code_qa_diagram_intercept.py`

- `test_find_new_diagram_blocks_detects_mermaid` — assert complete mermaid block is detected
- `test_find_new_diagram_blocks_ignores_partial` — assert incomplete block (no closing ```) returns empty list
- `test_find_new_diagram_blocks_deduplicates` — same DSL in `processed` set is not returned again
- `test_find_new_diagram_blocks_detects_d2` — D2 blocks also detected
- `test_sse_generator_emits_image_event_when_render_succeeds` — mock `render_mermaid` to return SVG; assert `image` event appears in stream after the mermaid block tokens
- `test_sse_generator_no_image_event_when_render_returns_none` — mock `render_mermaid` to return None; assert no `image` event

## Notes

- `_FENCED_BLOCK_RE` uses `re.DOTALL` to match multi-line DSL content. The pattern is `r"```(mermaid|d2)\n(.*?)```"` — greedy `*?` matches the minimal content, so nested backticks in the DSL don't cause issues in practice (Mermaid/D2 DSL doesn't use triple backticks internally).
- The `processed_diagram_blocks` set uses `(lang, dsl)` as the key. If the same diagram is repeated verbatim in the same response, only the first occurrence triggers a render — this is intentional to avoid duplicate images.
- `stream.js` must guard `onImage` with `typeof onImage === "function"` before calling, since it's a new parameter that callers may not provide.
- The `block_index` sent in the `image` event is **per-type** (i.e., the index of this block among all blocks of the same `lang` processed so far in this response). `emit_counts = {"mermaid": 0, "d2": 0}` tracks these separately; the value at `emit_counts[lang]` is used as `block_index` and then incremented regardless of whether render succeeded. The frontend selects `pre[data-lang="${source_type}"]` elements (all of them, including already-marked ones) and uses `block_index` as the absolute position within that list — this is stable because `<pre>` elements are inserted into the DOM before the image event arrives (all tokens for the block have already streamed).
- If `mmdc` is available but the `mmdc --input-file -` flag is needed vs. stdin: use the existing pattern from `orch/diagram/render.py` — DSL is piped via stdin with `input=dsl.encode()`. No temp files needed.
