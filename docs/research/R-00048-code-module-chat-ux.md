# R-00048 — Modern LLM Chat UX for the Code Module View

| Field | Value |
|-------|-------|
| ID | R-00048 |
| Date | 2026-04-17 |
| Mode | deep |
| Editorial category | functional |
| Primary question | How should we redesign the code module chat so it stays accessible while reading long pages, supports rich markdown/code/image/table rendering, and feels modern — using htmx + FastAPI + Jinja2 rather than a SPA framework? |

---

## Executive Summary

The dashboard's code module page currently pins the chat at the bottom, which forces users to leave their reading position to ask a question. The dominant pattern in modern LLM products (Cursor, Copilot Chat, Claude Projects, Notion AI, Linear AI) is a **persistent, collapsible side panel** — typically docked right and resizable — that coexists with the primary reading surface. For iw-ai-core, the recommended target is a **resizable docked right panel** for desktop widths with a **slide-over drawer fallback** on narrow widths, backed by **SSE streaming over htmx's `sse` extension**, a **buffered streaming-markdown parser** with DOMPurify, and **Highlight.js** (not Shiki) for browser-side code highlighting during streams. This gives the user the "read + ask" workflow they want without introducing a SPA framework. Estimated implementation complexity is moderate: ~1 feature-sized design with clear vendor dependencies and a known integration path in the existing FastAPI + htmx + Jinja2 stack.

---

## Findings

### F1 — Docked right panel (resizable) is the dominant pattern for "read + ask" contexts [HIGH]

Across the industry, chat assistants that accompany a primary reading or editing surface have converged on a **persistent side panel** pattern rather than a bottom-pinned chat or floating bubble. Walia's 2026 taxonomy classifies this as the "Embedded Assistant" pattern and recommends it when the AI integrates into an existing workflow tool rather than being the product itself ([Walia, AI Chat Layout Patterns, 2026](https://medium.com/@anastasiawalia/ai-chat-layout-patterns-when-to-use-them-real-examples-d03f04a19194)). Cursor 2.x ships an agent sidebar that slides in/out and is resizable ([Cursor forum — Agent side panel 2.3](https://forum.cursor.com/t/agent-sidebar-keeps-popping-from-the-right-even-after-hiding-it/143955?page=2), [Cursor forum — configurable sidebar width](https://forum.cursor.com/t/allow-configurable-minimum-width-for-the-right-sidebar/156036)). VS Code Copilot Chat uses the same model with a dedicated view container ([VS Code Copilot Chat docs](https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context)).

Trade-offs documented in PatternFly's drawer design guidelines ([PatternFly Drawer](https://www.patternfly.org/components/drawer/design-guidelines/)):

- **Docked (sidebar)** — both areas always visible; best for multitasking, IDEs, documentation. Recommended starting width **320–480px**.
- **Slide-over drawer** — hides off-canvas until triggered; saves screen real estate; good for narrow widths.
- **Split pane with draggable splitter** — gives the user control; matches expectations from Retool, VS Code, and IDEs ([Retool Split Pane](https://docs.retool.com/apps/guides/layout-structure/frames), [react-resizable-panels](https://www.npmjs.com/package/react-resizable-panels)).
- **Floating bubble** — best for support/handoff, not for co-reading ([Sharma — Where should AI sit in your UI?](https://uxdesign.cc/where-should-ai-sit-in-your-ui-1710a258390e)).

**Bottom-pinned chat is explicitly an anti-pattern for long pages**: once content scrolls, the chat is either too small to be useful or forces the user to leave their reading position ([Muzli — How to Design an AI Assistant](https://medium.muz.li/how-to-design-an-ai-assistant-users-actually-use-81b0fc7dc0ec)).

### F2 — Streaming scroll behavior must stick-to-bottom but release on user scroll-up [HIGH]

The canonical pattern for streaming chat is "stick to bottom while tokens arrive, but release stickiness the moment the user scrolls up, and surface a scroll-to-bottom button":

- Track an **invisible anchor element** at the bottom and observe it with `IntersectionObserver` to know whether the user is at the bottom ([tuffstuff9 — Intuitive Scrolling](https://tuffstuff9.hashnode.dev/intuitive-scrolling-for-chatbot-message-streaming)).
- Distinguish **user scroll** from **programmatic scroll** so auto-scroll doesn't fight the user; velocity-based spring animations handle variable-sized streaming chunks better than fixed-duration easing ([use-stick-to-bottom README](https://github.com/stackblitz-labs/use-stick-to-bottom)).
- Use `behavior: 'instant'` on first paint to avoid a jarring animation when the page loads with existing messages ([jhakim — Handling Scroll Behavior](https://jhakim.com/blog/handling-scroll-behavior-for-ai-chat-apps)).
- Add viewport-height padding to the last message (e.g. `min-height: 50dvh`) so streaming content doesn't sit awkwardly against the bottom edge ([jhakim, same source](https://jhakim.com/blog/handling-scroll-behavior-for-ai-chat-apps)).

These techniques are framework-agnostic and map cleanly to vanilla DOM + htmx.

### F3 — Streaming markdown must be buffered to prevent "raw-syntax flash" [HIGH]

The #1 visible bug in naive streaming markdown is that partial sequences (`**bol`, half-open code fences, incomplete tables) render as raw characters before the closing marker arrives. Two compatible solutions:

1. **Selective buffering state machine** — hold suspicious character sequences until they either complete a markdown element or are confirmed not to. Shopify's Sidekick implements this in a Node.js Transform stream and calls it "eliminating markdown rendering jank" ([Shopify Engineering — Sidekick Streaming](https://shopify.engineering/sidekicks-improved-streaming)).
2. **Streaming markdown parser** — a parser that appends DOM nodes incrementally rather than re-parsing the whole document on every chunk. The Chrome team specifically recommends [streaming-markdown](https://github.com/thetarnav/streaming-markdown) combined with `DOMPurify` for safety ([Chrome for Developers — Rendering LLM responses](https://developer.chrome.com/docs/ai/render-llm-responses)).

Two additional non-negotiables from the same Chrome guide:

- **Never assign parsed markdown to `innerHTML`** without a sanitizer — model output is untrusted.
- **Use `element.append()` rather than `textContent +=`** — the `+=` form replaces all children and is O(n²) over the message length.

Skovy's Vercel AI write-up confirms the same pipeline works in React via `unified` + `remark-parse` + `remark-rehype` + `rehype-react` + `rehype-highlight`, with `useMemo` re-processing on each delta ([Skovy — Rendering Markdown](https://www.skovy.dev/blog/vercel-ai-rendering-markdown)).

**htmx-specific gotcha**: the browser's native `EventSource` treats newlines as record separators, so raw markdown streamed as SSE `data:` lines gets corrupted. The community workaround is **base64-encoding chunks server-side** and decoding client-side before feeding them to the markdown parser ([Thought Eddies — LM Streaming With SSE](https://www.danielcorin.com/posts/2024/lm-streaming-with-sse/)).

### F4 — Partial code blocks need their own render path [HIGH]

Code fences are the most common markdown element that spans many streaming chunks. `llm-ui` handles this with a two-function approach — `findCompleteCodeBlock()` and `findPartialCodeBlock()` — so the UI can render code attractively even before the closing ``` arrives ([llm-ui code blocks](https://llm-ui.com/docs/blocks/code/)). Practical rules:

- Render the partial fence in a monospace `<pre>` without highlighting until complete.
- Highlight once complete using an **async highlighter call**, preserving scroll position.
- For streaming contexts, prefer **Highlight.js or Prism** over **Shiki**: Shiki runs ahead-of-time via WASM and is designed for static, server-rendered highlighting, not dynamic/streaming content; its ~250KB + WASM bundle is also heavy for a dashboard ([chsm.dev — Comparing web code highlighters](https://chsm.dev/blog/2025/01/08/comparing-web-code-highlighters), [dbushell — Better Syntax Highlighting](https://dbushell.com/2024/03/14/better-syntax-highlighting/)).

### F5 — Input affordances: context pills, slash commands, attachments are table-stakes [MEDIUM]

Modern chat inputs have converged on a small, predictable set of affordances:

- **Context pills / chips** — small removable badges directly above or inside the input showing what context is attached (file, module, URL, image). The ShapeOfAI pattern catalog documents this as the dominant presentation ([ShapeofAI — Attachments](https://www.shapeof.ai/patterns/attachments)).
- **`#`-mentions** for structured references (files, folders, symbols, tools) — as shipped by VS Code Copilot Chat ([VS Code Copilot Chat Context](https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context)).
- **`@`-mentions** for agents/participants (e.g. `@workspace`, `@terminal`).
- **`/`-slash commands** for well-known actions (`/compact`, `/init`, `/review`) — now the de-facto standard across Claude Code, Copilot Chat, and ChatGPT ([Claude Code slash commands guide](https://learn-prompting.fr/blog/claude-code-slash-commands-reference)).
- **Drag-and-drop** files, images, and URLs directly onto the chat surface ([VS Code Copilot Chat docs](https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context)).
- **Token/context indicator** — a small meter near the input showing context window usage, with a hover breakdown by source ([VS Code Copilot Chat docs](https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context)).
- **Keyboard shortcuts** — `Cmd/Ctrl+Enter` to send, `Shift+Enter` for newline, `Esc` to cancel streaming, `Cmd+K` to open/focus the panel.

Assistant-ui documents the same feature set as its baseline production checklist: "streaming, auto-scroll, retries, attachments, markdown, code highlighting, voice input, keyboard shortcuts, accessibility" ([assistant-ui README](https://github.com/assistant-ui/assistant-ui)).

### F6 — htmx + SSE is a viable streaming pipeline with one known sharp edge [HIGH]

The htmx SSE extension provides everything needed for token-by-token streaming without a SPA framework ([htmx SSE extension](https://htmx.org/extensions/sse/)):

- `sse-connect="/chat/stream/{id}"` — opens the EventSource.
- `sse-swap="token"` — appends each named event's payload to the target using the parent's `hx-swap` mode (e.g. `beforeend`).
- `sse-close="done"` — graceful termination.
- Lifecycle events: `htmx:sseOpen`, `htmx:sseBeforeMessage` (preventable), `htmx:sseMessage`, `htmx:sseError`, `htmx:sseClose`.
- Reconnection uses exponential backoff on top of the browser's native retry.

FastAPI pairs naturally via `StreamingResponse` or `sse-starlette`'s `EventSourceResponse`, yielding `ServerSentEvent` objects with named events ([FastAPI SSE tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/), [HackerNoon — SSE with FastAPI](https://hackernoon.com/how-to-use-server-sent-events-sse-with-fastapi)). A working reference exists in [vlcinsky/fastapi-sse-htmx](https://github.com/vlcinsky/fastapi-sse-htmx).

**Sharp edge**: because `EventSource` delimits records by newlines, markdown containing `\n` inside a single token will be split across events and corrupt rendering unless:

- Chunks are **base64-encoded** server-side and decoded in a small client-side handler that then feeds the streaming-markdown parser, **or**
- The server sends pre-parsed HTML fragments per chunk (letting htmx swap them directly), trading client-side state for server CPU.

### F7 — Long conversations need virtualization or pagination [MEDIUM]

At high message counts (hundreds to thousands), rendering every message is the dominant source of jank. The standard mitigation is **windowed rendering** — only DOM nodes near the viewport are kept ([Virtuoso](https://virtuoso.dev/), [TanStack Virtual](https://blog.logrocket.com/speed-up-long-lists-tanstack-virtual/)). For htmx without a SPA, the pragmatic equivalents are:

- **Load-more pagination** with `hx-get` on scroll-up (intersection observer on a sentinel at the top).
- **Server-side clipping** of older messages once a conversation crosses a threshold, surfaced as an "Older messages →" link.
- **Collapse long individual messages** behind a "Show more" control — assistant outputs can easily exceed 10k characters.

For the code-module chat's expected volume (tens of messages per conversation, not thousands), full virtualization is overkill; load-more pagination is sufficient.

### F8 — Assistant-ui / shadcn-ai sets a useful "feature checklist" even though we won't use them [MEDIUM]

Both [assistant-ui](https://github.com/assistant-ui/assistant-ui) and [shadcn AI Elements](https://www.shadcn.io/ai) are React-only and therefore not direct options for a Jinja2+htmx dashboard. But they're the most complete public specification of what a "modern, helpful" chat UI *contains*, and they're converging on the same primitives:

- **Thread** + **Message** + **MessageContent** + **Composer** + **Attachment** + **ContextPill** + **Scrollback** + **ScrollToBottom**.
- Radix-style composable primitives rather than one monolithic widget.
- Built-in streaming, auto-scroll, retries, markdown, syntax highlighting, file attachments, and keyboard shortcuts.

This gives us a clean parts list to map onto Jinja partials: `thread.html`, `message.html`, `composer.html`, `attachment_chip.html`, `scroll_to_bottom.html` — each an htmx swap target.

---

## Recommendations for iw-ai-core Code Module View

### Layout
1. **Ship a resizable docked right panel** pinned to the viewport height on the code module page, replacing the bottom-pinned chat.
2. Default width **400px** (inside the 320–480px band from F1), persisted per-user in `localStorage`.
3. Add a **collapse toggle** (keyboard `Cmd+\`) that animates to a 48px rail with just an icon, to match IDE conventions.
4. Below a ~900px viewport, fall back to a **slide-over drawer** triggered by a floating action button, so mobile/narrow use still works.
5. Keep the reading surface **fully scrollable independently** of the chat — do not link scroll.

### Streaming pipeline
6. Stream with **SSE via the htmx `sse` extension**, using named events: `token` (content delta), `tool` (tool-call announcement), `done` (close).
7. **Base64-encode each token server-side** and decode client-side in a small handler before passing to a streaming markdown parser — closes F6's newline gotcha.
8. Use **`streaming-markdown` + `DOMPurify`** client-side (tiny, framework-agnostic, recommended by Chrome) per F3.
9. Use **Highlight.js** for code-block highlighting on fence-complete events (not Shiki) per F4.
10. Buffer partial markdown with the FSM approach (Shopify pattern) to avoid raw-syntax flash.

### Scroll behavior
11. Implement **stick-to-bottom with intersection-observer anchor**, releasing on user scroll-up, with a **visible scroll-to-bottom button** when released (F2).
12. Add `min-height: 50dvh` padding to the last message to prevent bottom-hug jitter.
13. Use `behavior: 'instant'` on first paint; `behavior: 'smooth'` thereafter.

### Input affordances (MVP scope)
14. **Context pills** above the input, pre-populated with `#module:<current-module>` so the chat knows what the user is reading.
15. **Slash commands** for common actions: `/explain`, `/summarize`, `/find`, `/diagram`.
16. **`#`-mentions** for module references, with autocomplete from the project's module list.
17. **Drag-and-drop images** onto the input (screenshots of code) — store as attachments and show as chips.
18. **Keyboard shortcuts**: `Cmd+Enter` send, `Shift+Enter` newline, `Esc` stop streaming, `Cmd+\` toggle panel, `/` focus composer from anywhere on the page.
19. A **small context-usage meter** near the send button (F5, VS Code Copilot parity).

### Rendering (message content)
20. Render **tables** via GFM tables through the markdown parser — no extra work beyond choosing a GFM-capable streaming parser.
21. Render **images** from model output as responsive `<img>` with lazy-load; clicking opens a lightbox.
22. Render **Mermaid diagrams** when a fenced ` ```mermaid ` block completes, validating before rendering (matches Skovy pattern).
23. Add per-message actions on hover: **Copy**, **Regenerate**, **Branch**, **Mark helpful**.

### Scope deferrals (out of MVP)
- Voice input, conversation branching UI, and message virtualization — add only when message counts or usage patterns justify them (F7).
- Canvas/artifact split-pane (per F1, "Chat + Workbench") — considered but premature for the code-module context.

### Suggested next step
Create a Change Request (`/iw-new-cr`) titled **"Code module chat: docked resizable panel with streaming markdown"**, with the above 23 items scoped across three milestones: (a) layout + SSE plumbing, (b) markdown/code rendering pipeline, (c) input affordances and polish.

---

## Limitations

- **No codebase analysis** was performed per deep-mode tool rules; current implementation specifics of `dashboard/routers/code.py`, `dashboard/templates/project_code.html`, and the chat fragment templates were not examined. The "next step" CR should start by auditing the existing templates.
- **Accessibility** (ARIA roles for live region, screen-reader announcements of streaming tokens, focus management on panel open/close) was touched on via assistant-ui's feature list but not researched in depth — a separate accessibility pass is recommended before ship.
- One primary source ([Sharma — Where should AI sit in your UI?](https://uxdesign.cc/where-should-ai-sit-in-your-ui-1710a258390e)) returned a 403 via WebFetch; its content was inferred from the WebSearch summary and should be re-validated if any specific quote is used in implementation docs.
- **No benchmark numbers** were produced for the Highlight.js vs Prism choice; the recommendation rests on qualitative sources (chsm.dev, dbushell) which agree but are not load-tested against our specific token rates.
- **2026 dates in several sources** (Medium articles, Muzli) reflect publication year but may still draw on pre-2026 product state; Cursor 2.x behavior was cited from forum posts rather than official Cursor docs.

---

## Sources

| # | Title | Credibility | URL |
|---|-------|-------------|-----|
| 1 | Walia — AI Chat Layout Patterns (2026) | Medium article, taxonomy | https://medium.com/@anastasiawalia/ai-chat-layout-patterns-when-to-use-them-real-examples-d03f04a19194 |
| 2 | Sharma — Where should AI sit in your UI? | UX Collective | https://uxdesign.cc/where-should-ai-sit-in-your-ui-1710a258390e |
| 3 | Muzli — How to Design an AI Assistant | Design publication | https://medium.muz.li/how-to-design-an-ai-assistant-users-actually-use-81b0fc7dc0ec |
| 4 | PatternFly — Drawer design guidelines | Red Hat design system (HIGH) | https://www.patternfly.org/components/drawer/design-guidelines/ |
| 5 | Cursor forum — Agent sidebar 2.3 behavior | Community (product-specific) | https://forum.cursor.com/t/agent-sidebar-keeps-popping-from-the-right-even-after-hiding-it/143955?page=2 |
| 6 | Cursor forum — configurable sidebar width | Community | https://forum.cursor.com/t/allow-configurable-minimum-width-for-the-right-sidebar/156036 |
| 7 | VS Code Copilot Chat — Context docs | Official Microsoft docs (HIGH) | https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context |
| 8 | Retool — Split Pane frame | Official product docs | https://docs.retool.com/apps/guides/layout-structure/frames |
| 9 | react-resizable-panels | npm package (MIT) | https://www.npmjs.com/package/react-resizable-panels |
| 10 | Chrome for Developers — Render streamed LLM responses | Official Chrome team (HIGH) | https://developer.chrome.com/docs/ai/render-llm-responses |
| 11 | Shopify Engineering — Sidekick streaming | First-party engineering blog (HIGH) | https://shopify.engineering/sidekicks-improved-streaming |
| 12 | streaming-markdown (thetarnav) | GitHub library | https://github.com/thetarnav/streaming-markdown |
| 13 | Skovy — Rendering Markdown with Vercel AI | Engineering blog | https://www.skovy.dev/blog/vercel-ai-rendering-markdown |
| 14 | llm-ui — Code block docs | Library docs | https://llm-ui.com/docs/blocks/code/ |
| 15 | chsm.dev — Comparing web code highlighters | Independent comparison | https://chsm.dev/blog/2025/01/08/comparing-web-code-highlighters |
| 16 | dbushell — Better Syntax Highlighting | Engineering blog | https://dbushell.com/2024/03/14/better-syntax-highlighting/ |
| 17 | htmx SSE extension docs | Official htmx (HIGH) | https://htmx.org/extensions/sse/ |
| 18 | FastAPI — Server-Sent Events tutorial | Official FastAPI (HIGH) | https://fastapi.tiangolo.com/tutorial/server-sent-events/ |
| 19 | HackerNoon — SSE with FastAPI | Tutorial | https://hackernoon.com/how-to-use-server-sent-events-sse-with-fastapi |
| 20 | vlcinsky/fastapi-sse-htmx | Reference implementation | https://github.com/vlcinsky/fastapi-sse-htmx |
| 21 | Thought Eddies — LM streaming with SSE | Engineering blog (newline gotcha) | https://www.danielcorin.com/posts/2024/lm-streaming-with-sse/ |
| 22 | tuffstuff9 — Intuitive Scrolling for Chat | Engineering blog | https://tuffstuff9.hashnode.dev/intuitive-scrolling-for-chatbot-message-streaming |
| 23 | use-stick-to-bottom (StackBlitz) | Library + pattern reference | https://github.com/stackblitz-labs/use-stick-to-bottom |
| 24 | jhakim — Handling scroll behavior for AI chat | Engineering blog | https://jhakim.com/blog/handling-scroll-behavior-for-ai-chat-apps |
| 25 | ShapeofAI — Attachments pattern | UX pattern catalog | https://www.shapeof.ai/patterns/attachments |
| 26 | Claude Code — Slash commands reference (2026) | Community reference | https://learn-prompting.fr/blog/claude-code-slash-commands-reference |
| 27 | assistant-ui (GitHub) | TypeScript/React chat library | https://github.com/assistant-ui/assistant-ui |
| 28 | shadcn AI Elements | Component catalog | https://www.shadcn.io/ai |
| 29 | React Virtuoso | Virtualized list library | https://virtuoso.dev/ |
| 30 | TanStack Virtual (LogRocket overview) | Library overview | https://blog.logrocket.com/speed-up-long-lists-tanstack-virtual/ |
