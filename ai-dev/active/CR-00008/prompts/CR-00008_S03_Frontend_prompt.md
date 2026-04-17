# CR-00008 S03 — Frontend: docked panel shell, scroll, composer, keyboard, image paste

**Work Item**: CR-00008
**Step**: S03
**Agent**: frontend-impl

---

## Input Files (read first)

- `CLAUDE.md`, `dashboard/CLAUDE.md` — htmx + Jinja + Tailwind CDN, no build step
- `ai-dev/active/CR-00008/CR-00008_CR_Design.md` — AC1, AC2, AC11, AC12, AC13, AC14
- `docs/research/R-00048-code-module-chat-ux.md` — layout, scroll, input affordances
- `docs/research/R-00050-rich-content-chat-patterns.md` — accessibility (F13), image input (F6)
- `dashboard/templates/project_code.html` — where the panel mounts
- `dashboard/templates/fragments/code_qa_panel.html` — the file being deleted
- `dashboard/static/chat.css` (does not exist yet — create)
- `ai-dev/active/CR-00008/reports/CR-00008_S01_Api_report.md` — wire format you will consume

## Output Files

- **Delete**: `dashboard/templates/fragments/code_qa_panel.html`
- **Modify**: `dashboard/templates/project_code.html`
- **New**: `dashboard/templates/chat/panel.html`
- **New**: `dashboard/templates/chat/composer.html`
- **New**: `dashboard/static/chat.css`
- **New**: `dashboard/static/chat/panel.js`
- **New**: `dashboard/static/chat/stream.js`
- **New**: `dashboard/static/chat/composer.js`
- **New report**: `ai-dev/active/CR-00008/reports/CR-00008_S03_Frontend_report.md`

## Scope

This step covers **layout, scroll, input, keyboard, and image paste chip**. It does **NOT** cover markdown/code/table/citation rendering (S05) or Mermaid (S07). Leave the rendering call site as a TODO hook that a later step wires up; for streaming, `stream.js` should parse SSE events but delegate content rendering to a placeholder function that S05 replaces.

## Tasks

### Task 1 — `project_code.html` reflow to 2-column grid

Convert the page body to a CSS grid: left = reading surface, right = `<aside id="chat-panel-slot">{% include "chat/panel.html" %}</aside>`. Use Tailwind utilities only (no new build).

- Desktop (≥900px viewport): grid with `grid-cols-[1fr_var(--chat-width)]`. `--chat-width` is a CSS variable updated by `panel.js`.
- Mobile / narrow (<900px): single column; panel hidden; a floating button opens a slide-over drawer.
- Reading surface has its own scroll container (`overflow-y-auto h-[calc(100vh-<headerOffset>)]`). Chat panel has its own scroll container. **Do not link scroll.**

Remove the existing `{% include "fragments/code_qa_panel.html" %}` line and delete the file.

### Task 2 — `chat/panel.html`: docked panel shell

Structure:

```html
<div id="chat-panel"
     class="h-screen sticky top-0 border-l border-border bg-card flex flex-col"
     data-collapsed="false"
     role="region"
     aria-label="Code module chat">
  <div id="chat-resize-handle" aria-hidden="true" class="absolute left-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary/30"></div>
  <header class="flex items-center justify-between px-3 py-2 border-b border-border">
    <h2 class="text-sm font-medium">Chat</h2>
    <button id="chat-collapse-btn" class="min-h-[44px] min-w-[44px] inline-flex items-center justify-center" aria-label="Collapse chat panel (Cmd+\)">…icon…</button>
  </header>
  <div id="chat-messages" role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversation" class="flex-1 overflow-y-auto px-3 py-2 space-y-3">
    <!-- messages appended by render.js (S05) -->
  </div>
  <div id="chat-scroll-to-bottom-wrap" class="relative">
    <button id="chat-scroll-to-bottom" class="hidden absolute bottom-2 right-3 rounded-full bg-primary text-primary-foreground px-3 py-1 text-xs min-h-[44px] min-w-[44px]" aria-label="Jump to latest">↓ Latest</button>
  </div>
  {% include "chat/composer.html" %}
</div>
```

Also emit a separate `<button id="chat-drawer-open" class="lg:hidden fixed bottom-4 right-4 ...">` for the narrow-viewport case.

### Task 3 — `chat/composer.html`: input + context chip + slash menu + image chip rail

Structure:

```html
<form id="chat-composer" class="border-t border-border p-2 flex flex-col gap-2" enctype="multipart/form-data" onsubmit="return false;">
  <div id="chat-context-chips" class="flex flex-wrap gap-1"></div>
  <div id="chat-image-chips"   class="flex flex-wrap gap-1"></div>
  <div class="relative">
    <textarea id="chat-input" rows="2" class="w-full resize-y rounded-md border border-border bg-background p-2 text-sm" placeholder="Ask about this module… (/ for commands)"></textarea>
    <div id="chat-slash-menu" class="hidden absolute bottom-full mb-1 w-full border border-border bg-card rounded-md shadow"></div>
  </div>
  <div class="flex items-center justify-between">
    <label class="inline-flex items-center gap-1 text-xs text-muted-foreground cursor-pointer">
      <input type="file" id="chat-image-picker" class="sr-only" accept="image/png,image/jpeg,image/gif,image/webp" multiple>
      <span class="min-h-[44px] min-w-[44px] inline-flex items-center">📎 Attach image</span>
    </label>
    <button id="chat-send" type="submit" class="bg-primary text-primary-foreground text-sm px-3 py-1.5 rounded min-h-[44px]">Send ⌘↵</button>
  </div>
</form>
```

### Task 4 — `panel.js`: sizing, collapse, drawer, keyboard

Responsibilities:
- On load: read `localStorage.iw_chat_width` (default 400, clamped 320..480) and set `--chat-width` on `:root` (or on `#page-body`).
- Drag handle: on `mousedown` on `#chat-resize-handle`, track mouse, update `--chat-width`, clamp, persist on `mouseup`.
- `Cmd+\` / `Ctrl+\` toggles `data-collapsed`. When collapsed: panel becomes a 48px icon rail; Tailwind class toggling is fine.
- Below 900px viewport: panel hidden; `#chat-drawer-open` button visible. Click opens a slide-over drawer with a CSS transition. Close on Esc or backdrop click.
- Global keydown: `/` when not in an input focuses `#chat-input`. `Esc` cancels any active stream (call `window.__iwChatCancel?.()` which `stream.js` installs).

### Task 5 — `stream.js`: SSE parsing + cancel

Expose:

```js
window.iwChat = window.iwChat || {};
window.iwChat.streamAnswer = function ({projectId, body, onToken, onCitation, onDone, onError}) { ... }
```

- Uses `fetch` with `ReadableStream` (not `EventSource` — we want POST and cancellation).
- Parses `event:` lines and the paired `data:` lines. Decodes `token.b64` via `atob` + `TextDecoder("utf-8")`.
- Installs `window.__iwChatCancel` which aborts the underlying `AbortController`.
- Calls `onToken(utf8String)` with **cumulative** buffer delta; calls `onCitation({n,label,url,snippet})`; calls `onDone({ok:true})` / `onError({message})`.
- For S03: content-rendering callbacks are **placeholders** that print raw text into `#chat-messages` — S05 replaces them with the real renderer.

### Task 6 — `composer.js`: input, slash commands, image paste/drop, scroll behavior

- Keyboard: `Enter` = newline (textarea default) UNLESS `Cmd+Enter` / `Ctrl+Enter` → send.
- Send: append a user bubble, call `iwChat.streamAnswer(...)`, append an assistant bubble placeholder.
- Slash commands: on typed `/`, show `#chat-slash-menu` with `/explain`, `/findusages`, `/diagram`. Arrow keys navigate, Enter accepts; on accept, clear the `/xxx` from the textarea and push an entry into `#chat-context-chips` labelled `cmd:<name>`.
- Context chip: on first load and on htmx `afterSwap` targeting the code module pane, read `data-module-path` from `#code-content-root` and ensure a `module:<path>` chip is present (removable).
- Image input: clipboard paste (`paste` event on `#chat-input`), drag-and-drop (`dragover`/`drop` on `#chat-panel`), and file picker. On any of the three, read image files from the DataTransfer / clipboard items, create a thumbnail chip in `#chat-image-chips` with a remove button. Validate MIME type (JPEG/PNG/GIF/WEBP); reject others with a toast.
- On send with any image chip present: POST as `multipart/form-data` with fields `question`, `context_level`, `context_doc_id`, `module_path`, `conversation_history[]`, and `image[]` files. Expect HTTP 501 — show a toast "Image attachments coming soon" and DO NOT clear the typed text, DO NOT clear image chips. Let the user keep their state.
- Scroll behavior: IntersectionObserver on an invisible `<div id="chat-scroll-anchor">` at the bottom of `#chat-messages`. While in view: auto-scroll-to-bottom on append. While out of view: do not auto-scroll; show `#chat-scroll-to-bottom`. Click it → `scrollIntoView({behavior:"smooth", block:"end"})`. Use `behavior: "instant"` on first paint. Add `min-height: 50dvh` style to the last assistant message via `chat.css`.

### Task 7 — `chat.css`: panel layout hooks

- `:root { --chat-width: 400px; }`
- `#chat-messages > article[data-role="assistant"]:last-child { min-height: 50dvh; }` (targets the assistant message element which S05 will create; use `article[data-role="assistant"]` to future-proof).
- Focus rings: `:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }`
- Hit targets: utility `.tap { min-height: 44px; min-width: 44px; }` used in templates.

### Task 8 — Test scaffolding

Write failing then passing Playwright smoke tests under `tests/dashboard/browser/test_chat_panel_smoke.py` (pytest-playwright):

- Panel mounts on the code page, `<aside id="chat-panel">` is visible.
- `Cmd+\` toggles `data-collapsed`.
- Typing `/e` opens the slash menu; arrow-down + Enter picks `/explain`.
- Pasting a fake PNG puts a chip in `#chat-image-chips`.
- `Esc` after calling `window.__iwChatCancel = () => window.__called = true` sets `window.__called` to `true`.

If Playwright is not straightforward to set up in this project, substitute with a set of Jinja render tests (`tests/dashboard/test_chat_templates.py`) asserting the required `id`/`role`/`aria-*` attributes and a JSDOM-based micro-test — but prefer real Playwright. Document the choice.

## Hard rules

- No build step. No npm. No TypeScript.
- No new CDN references — everything vendored (S05 brings in the big libs).
- Every button is a real `<button>`. 44×44 hit minima. Visible focus ring.
- Do not render model markdown here — that's S05. Put a `TODO(S05)` at each placeholder.
- Do not render Mermaid — that's S07. A Mermaid fence should render as `<pre>` for now.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run ruff check dashboard/
uv run pytest tests/dashboard/ -k "chat_panel or chat_templates" -v
```

Must be zero-failure.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "CR-00008",
  "completion_status": "complete|partial|blocked",
  "files_changed": [...],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Note whether Playwright smoke or JSDOM-fallback was used."
}
```
