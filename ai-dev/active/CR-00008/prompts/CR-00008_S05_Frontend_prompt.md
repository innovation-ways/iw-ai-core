# CR-00008 S05 — Frontend: rich-content rendering (markdown / code / tables / citations / per-message actions)

**Work Item**: CR-00008
**Step**: S05
**Agent**: frontend-impl

---

## Input Files (read first)

- `CLAUDE.md`, `dashboard/CLAUDE.md`
- `ai-dev/active/CR-00008/CR-00008_CR_Design.md` — AC4, AC5, AC6, AC7, AC10, AC14, AC15
- `docs/research/R-00050-rich-content-chat-patterns.md` — message parts taxonomy (F1), streaming markdown (F2), code rendering (F3), tables (F4), citations (F11), actions (F10), security (F12)
- `ai-dev/active/CR-00008/reports/CR-00008_S03_Frontend_report.md` — renderer hook layout
- `dashboard/static/chat/stream.js` (S03) — callbacks you plug into
- `dashboard/templates/chat/panel.html` (S03) — message list container

## Output Files

- **New templates** under `dashboard/templates/chat/`:
  - `message.html`
  - `parts/text.html`, `parts/code.html`, `parts/table.html`, `parts/citation_chip.html`, `parts/sources_panel.html`, `parts/actions.html`
- **New vendored assets** under `dashboard/static/vendor/`:
  - Either **Streamdown** (MIT) OR **streaming-markdown (MIT) + DOMPurify (Apache-2.0 or MPL-2.0) + Highlight.js (BSD-3-Clause)** — see Task 1.
- **New static modules** under `dashboard/static/chat/`:
  - `render.js`, `citations.js`, `actions.js`
- **Modify**: `dashboard/templates/base.html` — **remove** the CDN `marked.min.js` script tag and any orphaned DOMPurify CDN reference; keep nothing stale.
- **Modify**: `dashboard/templates/fragments/item_artifacts.html` — migrate off `window.marked` onto the vendored pipeline (Task 9).
- **New**: `dashboard/static/vendor/LICENSES.md`
- **New report**: `ai-dev/active/CR-00008/reports/CR-00008_S05_Frontend_report.md`

## Scope

Content rendering. Does **not** cover Mermaid (S07). Mermaid fences should be passed through as `<pre>` blocks with a `data-lang="mermaid"` attribute that S07 upgrades.

## Tasks

### Task 1 — Choose the markdown rendering library (bounded spike, then decide)

Evaluate Streamdown vs. hand-rolled a-la-carte. Decision criterion:

- Download the latest stable Streamdown gzipped bundle.
- Measure: if gzipped total (markdown parser + Shiki + KaTeX + sanitization integration, only the pieces we need) **≤ 150KB**: adopt Streamdown.
- Otherwise: compose **streaming-markdown (thetarnav) + DOMPurify + Highlight.js** and skip KaTeX for this CR.

Record the measurement and choice in your report (bundle byte count + decision).

Whichever path is chosen, vendor the source (not minified-only if the source is comparable in size; otherwise ship minified + license file). Copy the LICENSE file for every library alongside its folder. Write `dashboard/static/vendor/LICENSES.md` listing every vendored lib with SPDX ID and source URL. **No GPL.**

### Task 2 — `dashboard/templates/chat/message.html`

Message shell used for both user and assistant roles:

```html
<article data-role="{{ role }}" data-msg-id="{{ id }}" class="chat-message">
  <header class="text-xs text-muted-foreground">{{ role_label }}</header>
  <div class="chat-message-body">{{ content | safe }}</div>
  {% if role == "assistant" %}
    {% include "chat/parts/actions.html" %}
    {% include "chat/parts/sources_panel.html" %}
  {% endif %}
</article>
```

Client-side code mirrors this structure when rendering incrementally.

### Task 3 — `parts/text.html` + `render.js` (markdown pipeline)

`render.js` exports a small API used by `stream.js`:

```js
window.iwChat.createAssistantRenderer = function (messageEl) {
  return {
    onToken(deltaText) { /* append DOM */ },
    onCitation({n, label, url, snippet}) { /* add chip to sources, register popover */ },
    onDone() { /* finalize */ },
    onError({message}) { /* replace body with error chip */ },
  };
};
```

Rules (CRITICAL):

- **Sanitize the accumulated buffer, not each chunk.** Maintain `this.buffer += delta`; on each render pass, run the streaming parser on the *cumulative* buffer and pass the resulting HTML through DOMPurify **as a whole**, then update the DOM via targeted appends. NEVER assign to `innerHTML` on the parent; NEVER use `innerHTML +=`; NEVER use `textContent +=`. Use `element.append(newChild)` or the streaming-markdown incremental DOM API.
- Link scheme allowlist: `http`, `https`, `mailto`. Block `javascript:`, `data:`, `file:`. Add `rel="noopener noreferrer"` on all `<a target="_blank">`.
- Raw `<script>`, `<iframe>`, inline event handlers, `<object>`, `<embed>`, and inline SVG from the model output are **stripped**. Explicitly configure DOMPurify's `FORBID_TAGS` / `FORBID_ATTR` lists.
- GFM extensions enabled: tables, strikethrough, task lists.

### Task 4 — `parts/code.html` + code rendering

- On a completed fence, replace the partial `<pre>` with a highlighted block. Stream state machine (per R-00050 F3): detect open fence (` ``` ` and optional language), hold a partial `<pre><code>` with `data-partial="true"` and plain text; on close, swap in highlighted content.
- Wrap each code block in a container with: language label (top-left), copy button (top-right; `aria-label="Copy code"` + 44×44 hit target; `data-copy-payload` attribute with the raw source; on click copy via `navigator.clipboard.writeText` with a success toast).
- Highlight via the chosen library (Shiki if Streamdown path, Highlight.js otherwise). Preserve scroll position during highlight swap.

### Task 5 — `parts/table.html` + table rendering

- GFM tables rendered through the markdown parser; zebra striping via `tbody tr:nth-child(even) { background: var(--muted); }` in `chat.css`.
- After render, append a "Copy CSV" button above each `<table>`. Copy logic: build CSV rows with proper escaping (quotes, commas, newlines inside cells).
- Accessible: `<table>` has a `<caption>` if the first row is a heading row, else the copy-CSV button has `aria-label="Copy table as CSV"`.

### Task 6 — `parts/citation_chip.html` + `citations.js`

- Each inline `[N]` in the rendered text is replaced **after** rendering by an interactive `<button class="citation-chip" aria-haspopup="dialog" data-cite="N">[N]</button>`. The Python-templated partial is for server-rendered cases (not used in streaming); the client-side replacement is the primary path.
- Click opens a small popover (or `<dialog>`) with: label, snippet (first ~240 chars of the cited symbol), "Open source" link.
- Register each citation in a Map keyed by `n`; `onCitation` updates the map and re-rehydrates chips as they arrive.

### Task 7 — `parts/sources_panel.html` + Sources block

- An expandable `<details>` at the end of each assistant message: summary = "Sources (N)", body = ordered list of cited symbols, each a link to its source. Opens on user click; not auto-expanded.

### Task 8 — `parts/actions.html` + `actions.js`

Four actions per assistant message: Copy / Regenerate / 👍 / 👎 — all real `<button>`, 44×44 hit targets, visible focus.

- Copy: copies the **source markdown** (not rendered HTML), not the citation chip markup.
- Regenerate: visible only on the **last** assistant message; re-dispatches the last user question, replacing the assistant message with a fresh stream. Disables itself while streaming.
- 👍: POST feedback to a local endpoint stub (or stash to `localStorage.iw_chat_feedback`) — for MVP, persist to `localStorage` under key `iw_chat_feedback.<msg_id>` with value `{rating: 'up' | 'down', ts, reason?, categories?}`.
- 👎: expands an inline form with checkboxes (Inaccurate / Not relevant / Incomplete / Harmful) + a small textarea (max 280 chars). Submit persists to the same `localStorage` key.

Accessibility: form is keyboardable; Esc collapses it.

### Task 9 — Migrate the artifact viewer off CDN `marked`

`dashboard/templates/fragments/item_artifacts.html` currently calls `marked.parse(text)` and assigns the result directly to `viewer.innerHTML` (see ~line 145 — `viewer.innerHTML = marked.parse(text);`). That is the only other in-tree consumer of `window.marked`. Because this CR removes the CDN `marked.min.js` from `base.html`, the artifact viewer **must** be migrated in the same step or the artifact-preview feature breaks in production.

Requirements:

- Add a small one-shot helper to `render.js` exposed as `window.iwChat.renderMarkdownStatic(text)` that:
  - Parses the full `text` through the vendored markdown parser chosen in Task 1 (Streamdown or streaming-markdown — streaming-markdown can operate one-shot by feeding the entire string and calling the finish API).
  - Passes the resulting HTML through DOMPurify with the same `FORBID_TAGS` / `FORBID_ATTR` configuration as the streaming path.
  - Returns a `DocumentFragment` (preferred) or a sanitized HTML string.
- Update `item_artifacts.html`'s inline script: replace `viewer.innerHTML = marked.parse(text);` with a DOM-level insertion that clears `viewer` and appends the fragment from `iwChat.renderMarkdownStatic(text)`. Do NOT use `innerHTML =` for markdown output; `element.replaceChildren(fragment)` is acceptable because the fragment is already sanitized.
- Ensure the vendored library is loaded on any page that includes `item_artifacts.html`. Since `item_artifacts.html` is an htmx fragment rendered into work-item detail pages, add the vendored `<script>` tags to the page template(s) that host the fragment (search `templates/pages/` for `item_artifacts` includes) — or, if simpler, add them to `base.html` **once** (Tailwind-style CDN replacement), carefully measuring the impact.
- Prefer adding the scripts to `base.html` only if the combined bundle is modest; otherwise, scope to the specific pages. Document the choice in the report.

**Tests**:
- `tests/dashboard/test_item_artifacts_render.py` — jsdom-style test or Python-level smoke: render `item_artifacts.html` with a fake tree; assert the inline script no longer references `marked.parse` and does reference `iwChat.renderMarkdownStatic`. The existing `test_no_marked_references_remain` in `test_chat_security.py` will now cover all templates (including `item_artifacts.html`).
- Security: feed `iwChat.renderMarkdownStatic("<script>alert(1)</script>\n**ok**")`; assert the returned fragment contains a `<strong>ok</strong>` node and NO `<script>` element.

### Task 10 — Tests you write (RED → GREEN)

Under `tests/dashboard/`:

- `test_chat_templates.py`:
  - `message.html` renders with expected `data-role`, `data-msg-id`, includes `actions.html` only when role=assistant.
  - `parts/code.html` emits a copy button with `aria-label="Copy code"` and a language label slot.
  - `parts/sources_panel.html` renders zero-citation message as an empty/collapsed block (no "Sources (0)" noise).
- `test_chat_a11y.py`:
  - Every `<button>` in emitted HTML has a non-empty accessible name (text or `aria-label`).
  - No interactive `<div onclick>`.
- `test_chat_security.py`:
  - Feed DOMPurify/renderer a payload `<script>alert(1)</script>\n<p onclick=alert(1)>x</p>` via the renderer's `onToken`; assert no `<script>` tag in the DOM, no `onclick` attribute.
  - `javascript:` link in markdown becomes rendered plain text, not a link.

Playwright smoke (optional but preferred): assert that after a short fake stream, the message DOM contains `<code>` with a copy button and that `navigator.clipboard.writeText` is invoked with the original source on click.

## Hard rules

- **NEVER** call `innerHTML =` on the message body.
- **NEVER** sanitize per-chunk — always accumulate then sanitize.
- **NEVER** render raw SVG from model output.
- Keep each JS module under 400 lines. Split further if needed.
- Do not touch `code_qa.py`. Do not touch Mermaid rendering (S07).
- Before finishing: grep **all** templates and assert no `marked.parse` / `marked.min.js` / `cdn.jsdelivr.net/npm/marked` residue remains. `item_artifacts.html` must be fully migrated (Task 9).

## Test Verification (NON-NEGOTIABLE)

```bash
uv run ruff check dashboard/
uv run pytest tests/dashboard/ -k "chat_templates or chat_a11y or chat_security" -v
```

Zero failures.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "CR-00008",
  "completion_status": "complete|partial|blocked",
  "files_changed": [...],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "State the markdown-library choice and the measured bundle size. Confirm LICENSES.md is present with SPDX IDs."
}
```
