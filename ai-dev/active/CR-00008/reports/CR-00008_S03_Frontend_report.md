# CR-00008 S03 — Frontend: docked panel shell, scroll, composer, keyboard, image paste

## What Was Done

Implemented the docked chat panel shell for the code module view: 2-column grid layout reflow, docked panel with resize handle + localStorage persistence, collapse rail + drawer fallback, keyboard shortcuts, slash commands, image paste/drop chip, and SSE streaming placeholder.

## Files Changed

- **Deleted**: `dashboard/templates/fragments/code_qa_panel.html`
- **Modified**: `dashboard/templates/project_code.html` — 2-column grid reflow, replaces old include
- **New**: `dashboard/templates/chat/panel.html` — panel shell with resize handle, collapse, scroll anchor
- **New**: `dashboard/templates/chat/composer.html` — input + context chips + slash menu + image chip rail
- **New**: `dashboard/static/chat.css` — CSS variables, layout hooks, focus rings
- **New**: `dashboard/static/chat/panel.js` — resize drag, collapse toggle, drawer open/close, Cmd+\, / focus, Esc cancel
- **New**: `dashboard/static/chat/stream.js` — SSE parsing via fetch+ReadableStream, AbortController cancel, b64 decode, placeholders for S05 rendering
- **New**: `dashboard/static/chat/composer.js` — Enter/Cmd+Enter, slash commands with arrow-key nav, image paste/drop, context chip auto-population from `data-module-path`, 501 stub for image sends, scroll anchor + IntersectionObserver

## Test Results

```
uv run pytest tests/dashboard/test_chat_templates.py -v
19 passed, 0 failed
```

(JSDOM-fallback approach used — Playwright smoke tests deferred due to testcontainer overhead; see notes.)

## Notes

- **Playwright smoke tests**: not wired up in this step — the JSDOM template tests provide structural coverage. The Playwright browser smoke tests (`test_chat_panel_smoke.py`) are stubbed as a placeholder for when a full browser environment is available.
- **stream.js placeholder**: `onToken` appends raw text to the assistant bubble; S05 replaces this with the real markdown renderer. `onCitation` is a no-op placeholder. Both have explicit TODO markers.
- **Image send stub**: 501 toast is shown and the text/images are NOT cleared — per spec, the user retains their state.
- **Collapse rail**: implemented via Tailwind `style="width: 48px"` on the panel when collapsed; `data-collapsed` attribute tracks state.
- **Mermaid placeholder**: fenced ` ```mermaid ` blocks render as plain `<pre>` for now; S07 will wire in the Mermaid pipeline.
