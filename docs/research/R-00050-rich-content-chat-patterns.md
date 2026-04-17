# R-00050 — Rich content in LLM chat: top use cases, implementation patterns, and stack choices

| Field | Value |
|-------|-------|
| ID | R-00050 |
| Date | 2026-04-17 |
| Mode | deep |
| Editorial category | functional |
| Primary question | What rich-content capabilities (beyond plain text) does a code-aware LLM chat need, which are table-stakes vs. differentiators, and how do we implement each cleanly in a FastAPI + Jinja2 + htmx dashboard with SSE streaming? |

---

## Executive Summary

Modern LLM chat UIs have converged on a stable "parts" taxonomy: **text, code, tables, math, images, diagrams, tool calls, citations, and occasionally artifacts/canvas** ([AI Elements — Message](https://elements.ai-sdk.dev/components/message), [shadcn-chatbot-kit rich rendering](https://deepwiki.com/Blazity/shadcn-chatbot-kit/3-ai-integration)). For iw-ai-core's read-first code module view, the **table-stakes set** is markdown + syntax-highlighted code + GFM tables + Mermaid diagrams + images (display and paste-in) + inline citations + per-message actions (copy/regenerate/thumbs). **Differentiators** worth considering are: generated charts via Vega-Lite specs, file/symbol cards, collapsible reasoning blocks, and KaTeX math. **Artifacts/canvas is out of scope for the MVP** — it's a workspace primitive for long-form authoring, not a read-first dashboard affordance. The implementation path is **Streamdown** (or `streaming-markdown` + DOMPurify) with **Shiki-stream** for code, **Mermaid** sandboxed in an iframe with parse-validate-before-render, **KaTeX** for math, and **@robino/md** or hand-rolled SSE fence handlers for partial code/table rendering. One architectural choice dominates everything else: **sanitize the accumulated buffer, not each chunk** ([Chrome for Developers — Rendering LLM responses](https://developer.chrome.com/docs/ai/render-llm-responses)) — this single rule prevents the most common XSS/prompt-injection failure mode. MVP scope: ~6 content types, ~4 libraries, all adoptable without a SPA framework.

---

## Findings

### F1 — A stable "message parts" taxonomy has emerged across the industry [HIGH]

Every serious production chat UI now models messages as **heterogeneous parts** rather than monolithic strings. The `MessagePart` union in Vercel AI Elements is representative:

> "Messages can contain multiple types of content through the MessagePart type system, enabling the display of heterogeneous content within a single message. You switch on `message.parts` and render the respective part within `Message`, `Reasoning`, and `Sources`." ([AI Elements Message docs](https://elements.ai-sdk.dev/components/message))

The common parts list converges across shadcn-chatbot-kit ([Blazity shadcn-chatbot-kit rich rendering](https://deepwiki.com/Blazity/shadcn-chatbot-kit/3-ai-integration)), AWS Cloudscape ([Cloudscape GenAI Chat](https://cloudscape.design/patterns/genai/generative-AI-chat/)), and assistant-ui ([assistant-ui syntax highlighting](https://www.assistant-ui.com/docs/ui/SyntaxHighlighting)):

| Part type | Render requirement | Library candidate |
|---|---|---|
| Text / markdown | GFM + streaming-safe | Streamdown, streaming-markdown, react-markdown+remark-gfm |
| Code block | Syntax highlight, copy button, line numbers, partial-fence tolerance | Shiki-stream, Highlight.js, Prism |
| Table | GFM rendering minimum; interactive (sort/filter) as upgrade | Streamdown (built-in), custom htmx table |
| Image | Zoom/lightbox, alt text, lazy load | Native `<img>` + lightbox JS |
| Diagram (Mermaid) | Parse-validate, iframe sandbox, self-repair | Mermaid.js + iframe sandbox |
| Math | Server- or client-side LaTeX → HTML/SVG | KaTeX (preferred), MathJax |
| Citation / source | Inline numbered link + panel | Custom (Cloudscape-style pattern) |
| Tool-call block | Collapsible with input/output | Custom |
| Reasoning block | Collapsible, optionally delayed-stream | Custom (shadcn's ReasoningBlock) |
| File/symbol card | Structured metadata + link | Custom Jinja partial |
| Artifact / canvas | Side panel or workspace view | Out of MVP scope — see F9 |

For our Jinja+htmx stack this maps cleanly: each part type becomes a **Jinja partial** (`message.html`, `code_block.html`, `mermaid_block.html`, `citation_chip.html`, …) that htmx can swap in independently during streaming.

### F2 — Streaming markdown needs a purpose-built parser, not `marked` + `innerHTML` [HIGH]

Re-covered from R-00048 but foundational for this doc. Chrome's guidance is unambiguous ([Chrome for Developers — Render LLM responses](https://developer.chrome.com/docs/ai/render-llm-responses)):

- **Never** assign parsed markdown to `innerHTML`: *"the moment you assign the parsed Markdown string to the `innerHTML`, you have pwned yourself"*.
- **Never** use `textContent += chunk` or `innerHTML += chunk`: both replace/re-parse the entire node on every chunk, resulting in O(n²) work over the message length.
- **Do** use `element.append(chunk)` or `insertAdjacentText('beforeend', chunk)`.
- **Do** use a streaming parser that appends new DOM nodes incrementally.
- **Do** sanitize the *accumulated buffer*, not each chunk — dangerous sequences can split across chunks.

Three 2025–2026 libraries dominate the streaming-markdown space:

| Library | Design point | Fits iw-ai-core? |
|---|---|---|
| **streaming-markdown** ([GitHub thetarnav](https://github.com/thetarnav/streaming-markdown)) | Tiny, framework-agnostic, recommended by Chrome | Yes — best baseline for htmx |
| **Streamdown** ([streamdown.ai](https://streamdown.ai/)) | Built by/for Vercel AI SDK; GFM tables, Shiki code, KaTeX math, "unterminated block styling" | Yes if we want batteries included |
| **@robino/md** ([vercel/ai discussion #5030](https://github.com/vercel/ai/discussions/5030)) | markdown-it + shiki streaming wrapper | Alternative |

Vercel's own chat SDK recently shipped **table rendering + streaming markdown** as a first-class feature because partial-token rendering of literal `**bold**` syntax *"eliminated the issue where users previously saw literal `**bold**` syntax"* ([Vercel changelog — Chat SDK adds table rendering](https://vercel.com/changelog/chat-sdk-adds-table-rendering-and-streaming-markdown)). This is evidence that streaming markdown is now a shipped, user-visible concern across platforms.

**Recommendation for iw-ai-core**: **Streamdown** (or `streaming-markdown` + DOMPurify if we want minimal dependencies). Both are framework-agnostic; both expose the DOM API we need from htmx.

### F3 — Code rendering under streaming needs a two-phase strategy [HIGH]

The hard problem is that a fenced block opens with ` ```python ` and may stream 100+ chunks before the closing ```. Naive approaches run the highlighter on every chunk (jank) or wait until the fence closes (ugly blank space). The industry-converged pattern is **two-phase**:

1. **Phase 1 (partial)**: render the in-progress fence as a plain monospace `<pre>` with no highlighting. Use `llm-ui`'s `findCompleteCodeBlock()` / `findPartialCodeBlock()` pattern ([llm-ui code blocks](https://llm-ui.com/docs/blocks/code/)).
2. **Phase 2 (complete)**: when the closing fence arrives, swap in a highlighted version asynchronously, preserving scroll position.

**Library choice for streaming** is not obvious. Two camps:

| Camp | Library | Evidence |
|---|---|---|
| **Highlight.js / Prism** (small, runtime regex) | Cheap, 2–10ms per block, no WASM | R-00048's recommendation; [chsm.dev comparison](https://chsm.dev/blog/2025/01/08/comparing-web-code-highlighters) |
| **Shiki + shiki-stream** (TextMate grammars, VS Code quality) | Higher fidelity, supports streaming via `CodeToTokenTransformStream` ([antfu/shiki-stream](https://github.com/antfu/shiki-stream)); ~250KB + WASM | Recent momentum: Astro, Streamdown, AI Elements all default to Shiki |

**Recommendation**: start with **Highlight.js** (faster to ship, low bundle cost, matches R-00048 layout-level recommendation), with Shiki as a documented upgrade path if fidelity becomes a complaint. If we pick Streamdown, Shiki comes bundled — accept that and skip Highlight.js entirely. Either way, **add a copy-to-clipboard button on hover** and a language label in the block header (Streamdown, Cloudscape, and AI Elements all do this by default).

### F4 — GFM tables are enough for ~95% of cases; interactive upgrades rarely pay off [MEDIUM]

The empirical signal is that LLMs produce tables frequently (comparisons, metric summaries, before/after) but rarely long enough to need pagination or complex sort/filter. Cursor's user forum has active requests for *better* markdown tables in chat, not for *interactive* ones ([Cursor forum — Table markdown support](https://forum.cursor.com/t/table-markdown-support-in-ai-chat/83519)). Vercel, Slack, Discord, Teams, and all major vendors render tables through GFM pipelines ([Vercel Chat SDK changelog](https://vercel.com/changelog/chat-sdk-adds-table-rendering-and-streaming-markdown)).

When interactivity pays off:
- Long comparison tables (>20 rows) — add a client-side sort on column headers (vanilla JS, ~30 lines).
- Numeric columns — right-align, add a total row only if the LLM explicitly emits one.
- Tables that are really data — prefer upgrading to a **Vega-Lite chart** (F8) rather than an interactive table.

**Anti-pattern** worth naming: Streamlit has a documented issue where partial-stream tables repeatedly flash half-rendered ([Streamlit discuss thread](https://discuss.streamlit.io/t/streamlit-chat-markdown-tables-from-chatgpt/43712)). Streamdown's "unterminated block styling" specifically handles this by rendering pending rows as styled placeholders.

**Recommendation**: GFM-rendered tables with hover-highlight and a one-line CSS zebra stripe. Add a "copy as CSV" button (trivial, high-signal, low-cost differentiator).

### F5 — Mermaid is the pragmatic diagram default; parse-validate-before-render is the correctness contract [HIGH]

Across `text-to-diagram.com`'s comparison ([text-to-diagram 2025](https://text-to-diagram.com/?example=text)) and practitioner writeups ([simmering.dev — Diagrams as Code: Supercharged by AI](https://simmering.dev/blog/diagrams/), [gleek — Mermaid vs PlantUML](https://www.gleek.io/blog/mermaid-vs-plantuml)):

| Tool | LLM familiarity | Rendering cost | Syntax-error rate | Fit for dashboard |
|---|---|---|---|---|
| **Mermaid** | Very high — GitHub/GitLab default; dominant in LLM training data | Client-side JS, no server | Medium (*"ChatGPT, Claude, Gemini often create Mermaid diagrams with syntax errors"* — [Mermaid Chart blog](https://docs.mermaidchart.com/blog/posts/how-to-choose-the-best-ai-diagram-generator-for-your-needs-2025)) | **Best default** |
| **D2** | Low; better auto-layout | Requires server or WASM | Low | Good secondary |
| **PlantUML** | Medium; verbose syntax | Requires Java server | Medium | Only if Kroki is already deployed |
| **Graphviz/DOT** | High for graphs | WASM works | Low | Nodes/edges only — not UML |

The **error-handling pattern** that has become standard:

1. Receive a ` ```mermaid ` fenced block.
2. Call `mermaid.parse(text, {suppressErrors: true})` to validate *before* render ([Mermaid Usage docs](https://mermaid.ai/open-source/config/usage.html)).
3. On failure, either: (a) show a "rendering error" chip with the raw code in a collapsible, or (b) send the error back to the LLM with a "please fix this syntax" system prompt — the *self-repair loop* described by [Microsoft GenAIScript's "Mermaids Unbroken"](https://microsoft.github.io/genaiscript/blog/mermaids/) and [DEV — Handling Mermaid rendering errors](https://dev.to/geanruca/handling-mermaid-diagram-rendering-errors-1n8i).
4. On success, render in `securityLevel: 'sandbox'` for isolation — **but note a known bug**: a *post*-render parse error in sandbox mode can produce a second iframe with duplicate ID ([mermaid-js issue #3153](https://github.com/mermaid-js/mermaid/issues/3153)). The parse-first step defends against this.

**Recommendation**: Mermaid only for MVP; parse-validate-before-render; auto-repair loop as a stretch goal (nice user experience, cheap to implement). Render in a sandboxed iframe with a strict CSP (`default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'`). Cap diagram node count to ~50 to avoid runaway renders.

### F6 — Image support is bidirectional; prioritize input (paste) over output (generation) [HIGH]

Two distinct image flows:

**Image input (user → chat)**. Industry-standard trio: clipboard paste, drag-and-drop, file picker ([GitHub Changelog — Copilot Chat Vision input](https://github.blog/changelog/2025-03-05-copilot-chat-users-can-now-use-the-vision-input-in-vs-code-and-visual-studio-public-preview/), [MS DevBlogs — Leverage vision in Copilot](https://devblogs.microsoft.com/visualstudio/attach-images-in-github-copilot-chat/)). Supported formats: **JPEG, PNG, GIF, WEBP**. The UX contract is: image appears as a **chip** above the input (not inline) before sending, and once sent becomes a thumbnail attachment on the user message. All three input methods should work — it's become table-stakes enough that GitHub issues get filed when a vision-capable model can't accept pastes ([ollama #13462](https://github.com/ollama/ollama/issues/13462), [CometChat feature request](https://feedback.cometchat.com/p/support-clipboard-paste-and-drag-and-drop-image-upload-in), [manychat request](https://community.manychat.com/ideas/paste-or-drag-and-drop-images-into-the-chat-6031)).

For iw-ai-core specifically: users will paste **screenshots of code errors** and **architecture diagrams from external docs**. These are the two dominant real-world use cases in the Copilot Chat blog.

**Image output (model → chat)**. Two paths:
- **Markdown `![]()`**: LLM emits an image URL, we render an `<img>` with lazy-load. Needs CSP `img-src` allowlist.
- **Generated SVG artifacts**: very dangerous without sandboxing — see F12. We should **explicitly not** support inline SVG from the model in MVP.

**Accessibility**: every image must have alt text. For user-pasted images, we can't get this server-side — use a generic placeholder ("attached image") and offer an edit affordance. For model-generated image outputs, require the LLM to emit a caption alongside.

### F7 — Math: KaTeX over MathJax unless MathML is required [MEDIUM]

For the iw-ai-core use case (LLM explanations sometimes include Big-O notation, set theory in algorithm discussions), math rendering is not table-stakes but a low-cost differentiator. KaTeX beats MathJax on raw performance and server-side rendering:

- *"KaTeX is generally faster than MathJax, making it the better choice if your site requires rendering large quantities of complex equations quickly."* ([KaTeX vs MathJax comparison via katex.org](https://katex.org/))
- *"KaTeX renders its math synchronously and doesn't need to reflow the page."*
- *"KaTeX can produce the same output regardless of browser or environment, so you can pre-render expressions using Node.js and send them as plain HTML."*

Streamdown ships KaTeX by default ([streamdown.ai](https://streamdown.ai/)). If we use Streamdown, math comes for free; if we roll our own, add KaTeX post-stream for completed `$$…$$` and inline `$…$` blocks.

**Recommendation**: include KaTeX only if we adopt Streamdown; otherwise defer — it's not high-signal for code-module Q&A.

### F8 — Charts via Vega-Lite spec generation is the safe, scalable pattern [MEDIUM]

For data-viz in a code-aware chat (e.g., "show me a chart of module complexity scores"), the dominant pattern is **chart2plot**-style: LLM emits a **Vega-Lite JSON spec**, the client renders it ([chat2plot — GitHub](https://github.com/nyanp/chat2plot), [chart-llm — GitHub](https://github.com/hyungkwonko/chart-llm)). Why this and not "let the LLM write matplotlib code":

- **Security**: Vega-Lite is a declarative JSON format; no code execution. matplotlib / plotly require a sandboxed runtime.
- **Accuracy**: LLMs hit ~50% accuracy on few-shot Vega-Lite generation ([Chat2VIS — arXiv 2302.02094](https://arxiv.org/pdf/2302.02094)). Not perfect, but better than arbitrary Python.
- **Ecosystem**: AntV's `mcp-server-chart` offers 27 chart tools, 26+ chart types with 4,000+ stars ([ChatForest — data-viz MCP servers](https://chatforest.com/reviews/data-visualization-mcp-servers/)). Vega-Lite specs are the *lingua franca*.

**Trade-off**: Vega-Lite is ~200KB. Only include if charts become a tested use case — defer past MVP unless we already have a clear data source (code metrics table, job durations).

### F9 — Artifacts/canvas is out of scope for a read-first dashboard [HIGH]

Claude Artifacts and ChatGPT Canvas are **workspace primitives** for long-form authoring and iterative refinement ([XsOne — Canvas vs Artifacts](https://xsoneconsultants.com/blog/chatgpt-canvas-vs-claude-artifacts/), [VentureBeat — ChatGPT Canvas launch](https://venturebeat.com/ai/openai-launches-chatgpt-canvas-challenging-claude-artifacts), [MindStudio — Claude Artifacts vs Canvas vs Generative UI](https://www.mindstudio.ai/blog/what-is-claude-generative-ui-vs-canvas-artifacts)). They excel at:

- Multi-turn document editing (Canvas)
- Standalone interactive React components (Artifacts)
- Running browser-sandboxed code (Claude Generative UI)

**None of these fit a read-first dashboard**. The iw-ai-core user is reading a module, asking about it, and wanting a concise, citable answer — not iterating on a 20-turn document. Adding Artifacts would:

- Duplicate the "main surface" the chat is supposed to coexist with (R-00048's docked panel).
- Break the scroll / read-position constraint the user explicitly complained about.
- Expose us to the well-documented SVG-XSS risk that bit early Artifacts implementations (see F12).

**Recommendation**: explicit NO on artifacts/canvas for MVP. Revisit only if we add an "agent workbench" surface later (e.g., Q&A → "draft an ADR about this module" → editable canvas).

### F10 — Per-message actions are a small but dense UX surface [MEDIUM]

The canonical per-message action set — converged on across AI Elements, shadcn-chatbot-kit, Cursor, Claude, ChatGPT — is:

| Action | Visibility | Evidence |
|---|---|---|
| **Copy** (full message, code block, citation link) | Always visible on hover/focus | Universal |
| **Regenerate** | Last assistant message only | [LangChain — Branching chat](https://docs.langchain.com/oss/python/langchain/frontend/branching-chat); [thefrontkit — Chat UI best practices](https://thefrontkit.com/blogs/ai-chat-ui-best-practices) |
| **Branch** / fork from this point | Hover action, less prominent | [LangChain branching](https://docs.langchain.com/oss/python/langchain/frontend/branching-chat) |
| **Thumbs up/down** | Always visible on assistant messages | [Cloudscape GenAI Chat](https://cloudscape.design/patterns/genai/generative-AI-chat/); [thefrontkit](https://thefrontkit.com/blogs/ai-chat-ui-best-practices) |
| **"Why this answer?"** (context inspector) | Optional, click-to-open | Cody's "context used" pattern; power-user feature |

Two concrete patterns worth stealing:

- **Thumbs-down expands a small categorized form**: "Inaccurate / Not relevant / Incomplete / Harmful" — pre-defined categories are faster than free text and give actionable signal ([thefrontkit](https://thefrontkit.com/blogs/ai-chat-ui-best-practices)).
- **Cloudscape's rule of five**: *"Don't overwhelm users with 5+ inline action buttons simultaneously"* — keep to 4 at most; put the rest behind an overflow menu.

**Recommendation for MVP**: Copy, Regenerate, Thumbs up/down. Branch and context-inspector deferred.

### F11 — Citations: inline numbered + sources panel is the dominant pattern [HIGH]

AWS Cloudscape documents the cleanest pattern ([Cloudscape GenAI Chat](https://cloudscape.design/patterns/genai/generative-AI-chat/)):

- **Inline citations**: sequential `[1] [2] [3]` in-text, each triggering a popover with source title + link.
- **Sources section**: expandable at the bottom of the message, listing all sources with title, URL, optional description.

Cody implements a variation ([Sourcegraph — Cody chat](https://sourcegraph.com/docs/cody/capabilities/chat), [Sourcegraph — Cody VS Code 1.24 context chips](https://sourcegraph.com/blog/cody-vscode-1-24-0-release)): **context chips** above the input showing what the model *used* (repo / file / symbol / webpage). Chips double as scoping controls — the user can remove a chip to re-ask without that context.

For iw-ai-core, the sources are **always internal to the project** (modules, symbols, commits, PRs). Every citation should link to a dashboard route (`/project/<id>/code/<module>#<symbol>`), not a URL. Hover preview on citation chips showing the first N lines of the cited code is a power move and cheap to implement.

### F12 — Security: DOMPurify is necessary but not sufficient for SVG/Mermaid [HIGH]

DOMPurify ([cure53/DOMPurify](https://github.com/cure53/DOMPurify)) is the industry standard for sanitizing HTML, SVG, and MathML output. Known concerns:

- **Historical MathML/SVG namespace bypass**: *"mglyph and malignmark allowed the creation of markup that is in HTML namespace, but on reparsing is in MathML namespace, leading to XSS"* ([PortSwigger — DOMPurify MathML bypass](https://portswigger.net/daily-swig/dompurify-mutation-xss-bypass-achieved-through-mathml-namespace-confusion)). Fixed, but a reminder that sanitizer bugs do ship.
- **LLM-emitted SVG is especially dangerous**: *"when the LLM generates an SVG artifact, the content can be rendered directly into the parent page DOM using unsafe directives without any sanitization (no DOMPurify, no allowlist filtering, no iframe sandboxing)"* ([DOMPurify security analysis](https://dompurify.com/how-does-dompurify-ensure-that-sanitized-html-is-safe-for-injection-into-the-dom-2/)). SVG event handlers (`onload`, `onclick`) can execute with full document scope.
- **Snyk advisory CVE-2024-47875** ([Snyk DOMPurify advisory](https://security.snyk.io/vuln/SNYK-JS-DOMPURIFY-8184974)): keep DOMPurify pinned to a current version; regression-test on upgrades.

**Concrete rules for iw-ai-core** (composing with R-00048's guidance):

1. **Never render raw SVG from model output**. Strip it or render as `<pre>` code. Mermaid-rendered SVG from our trusted pipeline is OK.
2. **Sanitize the accumulated buffer, not each chunk** — see F2.
3. **Mermaid in iframe sandbox** (`securityLevel: 'sandbox'`) with strict CSP.
4. **Allowlist `img-src`** for model-emitted image URLs — whitelist our own domain + well-known doc hosts.
5. **`rel="noopener noreferrer"`** on all outbound links from assistant messages.
6. **Disable `javascript:` and `data:` URLs** in markdown link rendering.
7. **Pin DOMPurify** and follow Snyk advisories.

### F13 — Accessibility: `aria-live="polite"` on the stream, real `<button>` for actions [HIGH]

From MDN + Mozilla's live-region guidance ([MDN — ARIA live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions), [Sara Soueidan — Accessible notifications with ARIA live](https://www.sarasoueidan.com/blog/accessible-notifications-with-aria-live-regions-part-1/)):

- The message list container gets `role="log"` with `aria-live="polite"` — new messages are announced without interrupting the user's current reading.
- Do **not** use `aria-live="assertive"` for streaming tokens — that spams the screen reader with every delta and drives users away.
- Use `aria-atomic="false"` and let `aria-relevant="additions"` announce only new content.
- **Announce completion**, not tokens. The live region should only announce once the message is complete, or summarize (*"Claude responded"*) rather than stream-announce every word.

For action buttons ([accessibilitychecker — Button accessibility](https://www.accessibilitychecker.org/blog/button-accessibility/), [Orange a11y — Chatbot guidelines](https://a11y-guidelines.orange.com/en/articles/chatbot/)):

- Real `<button>` elements, not `<div onclick>`.
- WCAG minimum 44×44px hit target.
- Keyboard accessible (tab + enter); visible focus state.
- Clear labels: *"Copy code"*, not *"Copy"*.

Cloudscape codifies additional rules: `role="region"` with meaningful `aria-label` on the chat container; a hidden `LiveRegion` component for announcements; logical keyboard navigation throughout ([Cloudscape GenAI Chat](https://cloudscape.design/patterns/genai/generative-AI-chat/)).

---

## Table-stakes vs. Differentiators (2026 baseline)

| Capability | Status | Reason |
|---|---|---|
| GFM markdown (bold/italic/lists/links) | **Table-stakes** | Universal |
| Fenced code blocks with syntax highlighting | **Table-stakes** | Universal |
| GFM tables | **Table-stakes** | Shipped by Slack/Teams/Discord/Vercel |
| Inline citations + sources | **Table-stakes for code-aware** | Trust contract (F11, R-00049) |
| Copy-to-clipboard on code/message | **Table-stakes** | Converged across all major products |
| Thumbs up/down feedback | **Table-stakes** | Cloudscape, AI Elements, all |
| Image input (paste / drag / pick) | **Table-stakes** | Copilot Chat, Cursor, Claude |
| Mermaid diagrams | **Differentiator today, becoming table-stakes** | Dominant LLM-diagram format |
| KaTeX math | **Differentiator** | Useful for algorithm / ML contexts |
| Streaming-safe partial code rendering | **Differentiator (quiet)** | Users notice the absence, not the presence |
| Auto-repair for Mermaid syntax errors | **Differentiator** | High quality-of-life payoff |
| Vega-Lite charts | **Niche differentiator** | Great where data exists; skip otherwise |
| Branch / fork conversation | **Differentiator** | Power users; ChatGPT, Claude, LangChain |
| Reasoning / thinking collapsible | **Differentiator** | Matches Claude / OpenAI conventions |
| Artifacts / canvas side pane | **Out of scope** | Workspace primitive; wrong for read-first (F9) |
| Generated SVG artifacts | **Out of scope** | Security risk too high (F12) |
| Voice input / TTS output | **Out of scope** | No use-case evidence for code QA |

---

## Implementation Plan (suggested MVP for iw-ai-core)

### Server side (FastAPI)

- **SSE endpoint** (already exists per F-00049 / CR-00006): stream base64-encoded tokens as `data:` SSE events per R-00048's newline-gotcha workaround.
- **Emit typed events**: `token` (content delta), `tool_call_start/end`, `citation`, `done` — match AI Elements' part taxonomy so the client can switch on event type.
- **Citation enrichment**: when retrieval returns a symbol, include `{id, label, url}` in a `citation` event; client renders a chip.
- **No server-side HTML generation for rich content** — send raw markdown text so the client can stream-render incrementally.

### Client side

| Concern | MVP choice | Rationale |
|---|---|---|
| Markdown parser | **Streamdown** (or `streaming-markdown` + DOMPurify) | GFM + streaming-safe + tables + code + math batteries |
| Code highlighting | **Shiki-stream** (bundled with Streamdown) OR Highlight.js | If Streamdown → Shiki; if roll-our-own → Highlight.js |
| Sanitization | **DOMPurify** pinned | Required per F12 |
| Math | **KaTeX** (Streamdown bundled) | F7 |
| Diagrams | **Mermaid** with `parse()` validation + sandboxed iframe | F5 |
| Copy buttons | Vanilla JS on code blocks, message actions | Accessibility per F13 |
| Image paste | ClipboardEvent + DataTransfer (~30 lines) | F6 |
| Live region | `<div role="log" aria-live="polite" aria-relevant="additions">` | F13 |
| Citations | Inline `[N]` popover + sources panel | Cloudscape pattern (F11) |
| Per-message actions | Copy / Regenerate / Thumbs-up / Thumbs-down | F10 |

### Jinja partials (suggested file layout)

- `dashboard/templates/chat/message.html` — shell with role, avatar, timestamp, actions
- `dashboard/templates/chat/parts/text.html` — markdown rendered via Streamdown client-side
- `dashboard/templates/chat/parts/code.html` — pre + copy button + language label
- `dashboard/templates/chat/parts/mermaid.html` — iframe sandbox wrapper
- `dashboard/templates/chat/parts/image.html` — lazy img + lightbox trigger
- `dashboard/templates/chat/parts/citation_chip.html` — inline numbered citation
- `dashboard/templates/chat/parts/sources_panel.html` — expandable source list
- `dashboard/templates/chat/parts/actions.html` — copy/regen/thumbs

---

## Anti-patterns to avoid (explicit NO list)

- ❌ **`innerHTML = parsedMarkdown`** — ever. Use a streaming parser that appends nodes.
- ❌ **Per-chunk sanitization** — dangerous sequences split across chunks; sanitize the buffer.
- ❌ **Raw SVG from model output** — strip or render as code. Mermaid-rendered SVG only.
- ❌ **`aria-live="assertive"` during streaming** — screen-reader spam; use polite + announce-on-complete.
- ❌ **No alt text on images** — degrades accessibility and SEO of internal docs.
- ❌ **5+ inline per-message actions** — clutter; use overflow menu ([Cloudscape](https://cloudscape.design/patterns/genai/generative-AI-chat/)).
- ❌ **Artifacts/canvas in MVP** — wrong primitive for read-first dashboard (F9).
- ❌ **Interactive tables by default** — GFM is enough; upgrade only on demand.
- ❌ **Model-generated matplotlib/plotly code** — Vega-Lite JSON instead (F8).
- ❌ **Unsandboxed Mermaid** — always `securityLevel: 'sandbox'` + CSP.
- ❌ **Missing copy button on code blocks** — dev users will curse us.
- ❌ **Auto-scroll while user is reading older messages** — [Cloudscape rule](https://cloudscape.design/patterns/genai/generative-AI-chat/); covered in R-00048 F2.
- ❌ **Branching UI in MVP** — worth it, but adds state machine complexity; defer.

---

## Limitations

- **No codebase audit performed** (deep-mode rule). The Jinja partial layout above is a *proposal* — the CR should start by reading the current `dashboard/templates/` structure (especially F-00049's chat fragments) and aligning with established conventions.
- **Streamdown bundle size was not measured** — the landing page mentions "tree-shakeable plugins" but no absolute number. A CR spike should verify this before committing; if >150KB gzipped, prefer `streaming-markdown` + DOMPurify + KaTeX assembled a-la-carte.
- **Shiki-stream is young** (`antfu/shiki-stream`, launched late 2024). Recommend running a two-week soak test on a non-critical path before making it the default. Highlight.js is the safer backstop.
- **Mermaid's self-repair loop requires a second LLM call** — quantify the cost/latency budget before enabling; may be better as a manual "Retry render" button.
- **Cloudscape is React-only** — we're borrowing *patterns* (citations, feedback, stacked bubbles), not components.
- **Math rendering utility in code-module context is speculative** — we haven't measured how often LLM answers include LaTeX. If measured at <1% of messages, skip KaTeX entirely.
- **The "parts" taxonomy is documented across React/SPA libraries** — our htmx translation (one partial per part type) is straightforward but unvalidated at scale. Pilot on message.html first, extend partial-by-partial.
- **Image input privacy**: screenshots of internal code may be posted to third-party LLMs via our backend. This is an organizational concern, not a UI one, but worth flagging: add a "visible to model" disclaimer next to the paste affordance.

---

## Sources

| # | Title | Credibility | URL |
|---|---|---|---|
| 1 | Chrome for Developers — Render streamed LLM responses | Official Chrome team (HIGH) | https://developer.chrome.com/docs/ai/render-llm-responses |
| 2 | Streamdown | Purpose-built library site | https://streamdown.ai/ |
| 3 | thetarnav — streaming-markdown (GitHub) | Library referenced by Chrome | https://github.com/thetarnav/streaming-markdown |
| 4 | Vercel changelog — Chat SDK adds table rendering + streaming markdown | First-party (HIGH) | https://vercel.com/changelog/chat-sdk-adds-table-rendering-and-streaming-markdown |
| 5 | AI Elements — Message component | Official Vercel docs | https://elements.ai-sdk.dev/components/message |
| 6 | shadcn-chatbot-kit — Rich content rendering | Community, widely used | https://deepwiki.com/Blazity/shadcn-chatbot-kit/3-ai-integration |
| 7 | Cloudscape Design System — Generative AI chat pattern | AWS design system (HIGH) | https://cloudscape.design/patterns/genai/generative-AI-chat/ |
| 8 | assistant-ui — Syntax highlighting docs | Library docs | https://www.assistant-ui.com/docs/ui/SyntaxHighlighting |
| 9 | antfu — shiki-stream (GitHub) | First-party library | https://github.com/antfu/shiki-stream |
| 10 | chsm.dev — Comparing web code highlighters | Independent benchmark | https://chsm.dev/blog/2025/01/08/comparing-web-code-highlighters |
| 11 | dbushell — Better syntax highlighting | Engineering blog | https://dbushell.com/2024/03/14/better-syntax-highlighting/ |
| 12 | llm-ui — Code block docs | Library docs | https://llm-ui.com/docs/blocks/code/ |
| 13 | Cursor forum — Table markdown support in AI chat | Community feature request | https://forum.cursor.com/t/table-markdown-support-in-ai-chat/83519 |
| 14 | text-to-diagram — 2025 comparison (Mermaid / D2 / PlantUML / Graphviz) | Independent comparison | https://text-to-diagram.com/?example=text |
| 15 | simmering.dev — Diagrams as Code: Supercharged by AI | Practitioner blog | https://simmering.dev/blog/diagrams/ |
| 16 | gleek — Mermaid vs PlantUML | Vendor comparison | https://www.gleek.io/blog/mermaid-vs-plantuml |
| 17 | Mermaid — Usage docs (parse, sandbox) | Official docs (HIGH) | https://mermaid.ai/open-source/config/usage.html |
| 18 | mermaid-js — Issue #3153 (sandbox parse-error bug) | Upstream issue | https://github.com/mermaid-js/mermaid/issues/3153 |
| 19 | Microsoft GenAIScript — Mermaids Unbroken (self-repair loop) | First-party engineering blog | https://microsoft.github.io/genaiscript/blog/mermaids/ |
| 20 | DEV — Handling Mermaid rendering errors | Practitioner blog | https://dev.to/geanruca/handling-mermaid-diagram-rendering-errors-1n8i |
| 21 | MermaidChart blog — How to choose the best AI diagram generator (2025) | First-party | https://docs.mermaidchart.com/blog/posts/how-to-choose-the-best-ai-diagram-generator-for-your-needs-2025 |
| 22 | GitHub Changelog — Copilot Chat Vision input (March 2025) | First-party (HIGH) | https://github.blog/changelog/2025-03-05-copilot-chat-users-can-now-use-the-vision-input-in-vs-code-and-visual-studio-public-preview/ |
| 23 | Microsoft DevBlogs — Leverage vision in Copilot Chat | First-party | https://devblogs.microsoft.com/visualstudio/attach-images-in-github-copilot-chat/ |
| 24 | ollama — Issue #13462: Enable image input for vision-capable models | Community feature request | https://github.com/ollama/ollama/issues/13462 |
| 25 | CometChat — Clipboard paste & drag-drop image upload | Community feature request | https://feedback.cometchat.com/p/support-clipboard-paste-and-drag-and-drop-image-upload-in |
| 26 | Manychat — Paste or drag-and-drop images into the chat | Community feature request | https://community.manychat.com/ideas/paste-or-drag-and-drop-images-into-the-chat-6031 |
| 27 | KaTeX — Homepage | Official (HIGH) | https://katex.org/ |
| 28 | chat2plot (GitHub) | Academic reference impl | https://github.com/nyanp/chat2plot |
| 29 | chart-llm (GitHub) | Academic benchmark | https://github.com/hyungkwonko/chart-llm |
| 30 | Chat2VIS (arXiv 2302.02094) | Peer-reviewed | https://arxiv.org/pdf/2302.02094 |
| 31 | ChatForest — Data Visualization MCP Servers | Vendor review | https://chatforest.com/reviews/data-visualization-mcp-servers/ |
| 32 | cure53 — DOMPurify (GitHub) | Official sanitizer (HIGH) | https://github.com/cure53/DOMPurify |
| 33 | PortSwigger — DOMPurify MathML namespace bypass | Security research (HIGH) | https://portswigger.net/daily-swig/dompurify-mutation-xss-bypass-achieved-through-mathml-namespace-confusion |
| 34 | Snyk advisory — DOMPurify CVE-2024-47875 | Security vendor (HIGH) | https://security.snyk.io/vuln/SNYK-JS-DOMPURIFY-8184974 |
| 35 | MDN — ARIA Live Regions | Mozilla (HIGH) | https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions |
| 36 | Sara Soueidan — Accessible notifications with ARIA live | Authoritative practitioner (HIGH) | https://www.sarasoueidan.com/blog/accessible-notifications-with-aria-live-regions-part-1/ |
| 37 | Accessibility Checker — Button accessibility | Editorial | https://www.accessibilitychecker.org/blog/button-accessibility/ |
| 38 | Orange a11y — Chatbot guidelines | Design system | https://a11y-guidelines.orange.com/en/articles/chatbot/ |
| 39 | XsOne — ChatGPT Canvas vs Claude Artifacts deep-dive | Editorial | https://xsoneconsultants.com/blog/chatgpt-canvas-vs-claude-artifacts/ |
| 40 | MindStudio — Claude Generative UI vs Canvas vs Artifacts | Editorial | https://www.mindstudio.ai/blog/what-is-claude-generative-ui-vs-canvas-artifacts |
| 41 | VentureBeat — ChatGPT Canvas launch | Press (HIGH) | https://venturebeat.com/ai/openai-launches-chatgpt-canvas-challenging-claude-artifacts |
| 42 | Sourcegraph — Cody chat docs (citations, context chips) | Official docs | https://sourcegraph.com/docs/cody/capabilities/chat |
| 43 | Sourcegraph blog — Cody VS Code 1.24 (context chips) | First-party | https://sourcegraph.com/blog/cody-vscode-1-24-0-release |
| 44 | thefrontkit — AI Chat UI Best Practices | Editorial | https://thefrontkit.com/blogs/ai-chat-ui-best-practices |
| 45 | LangChain — Branching chat docs | Official docs | https://docs.langchain.com/oss/python/langchain/frontend/branching-chat |
| 46 | vercel/ai discussion #5030 — Stream with syntax highlighting | Community thread | https://github.com/vercel/ai/discussions/5030 |
| 47 | DOMPurify security analysis (SVG / LLM output) | Vendor docs | https://dompurify.com/how-does-dompurify-ensure-that-sanitized-html-is-safe-for-injection-into-the-dom-2/ |
