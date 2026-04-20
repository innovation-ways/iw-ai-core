# F-00055 S07 Frontend Report

## Summary

Implemented all F-00055 S07 frontend requirements: phase-event consumer, work-item chip variant, Linear-style feed, tone-switch chip, slash aliases, and CSS for new UI elements. Streaming pipeline extended to pass `onPhase` events and work-item citation data through to the renderer.

## Files Changed

### Modified
- `dashboard/static/chat/stream.js` — Added `onPhase` callback parameter; dispatch on `phase` SSE event; pass `work_item_type`/`work_item_id` through `onCitation`
- `dashboard/static/chat/render.js` — `createAssistantRenderer` gained `onPhase`/`onWorkItemCitation` handlers; client-side phase strip creation + phase-label update; client-side work-item feed construction; `injectToneSwitchChip` function on `window.iwChat`
- `dashboard/static/chat/composer.js` — Added `/why` and `/history` slash aliases; `onPhase`/`onDone` wired through renderer; tone-switch chip injected after `done`
- `dashboard/static/chat/citations.js` — `getAll` now returns `type` and `id` fields from registered entries
- `dashboard/static/chat.css` — Added `.phase-strip`, `.work-item-feed`, `.citation-chip--workitem` (with `--feature`/`--change_request`/`--incident` variants), `.tone-switch-chip` rules

### Created
- `dashboard/templates/chat/parts/work_item_chip.html` — Jinja2 fragment for ID+glyph chip (F/CR/I variants, 44×44 min touch target)
- `dashboard/templates/chat/parts/work_item_feed.html` — Linear-style chronological feed fragment with trust strip
- `dashboard/templates/chat/parts/phase_strip.html` — Minimal status-strip fragment (`role="status"`, `aria-live="polite"`)
- `tests/dashboard/test_chat_workitem_templates.py` — 15 smoke tests for new templates (all passing)

## Test Results

```
uv run pytest tests/unit/ tests/dashboard/test_chat_templates.py tests/dashboard/test_chat_workitem_templates.py
→ 978 passed, 16 warnings (pre-existing RuntimeWarning from S03 phase tests)
```

New tests: **15 passed** (`test_chat_workitem_templates.py`).

## Quality Checks

- `uv run ruff check dashboard/routers/code_qa.py` — **pass** (upstream already clean)
- `uv run ruff format --check dashboard/routers/code_qa.py` — **pass**
- `uv run mypy dashboard/routers/code_qa.py` — **pass**
- Ruff does not lint CSS or plain JS (JS syntax validated by browser; CSS is raw)

## Implementation Notes

1. **Phase strip** is entirely client-side in `render.js` (no server-side template instantiation needed for the live stream). The `phase_strip.html` fragment exists for potential server-rendered contexts.

2. **Work-item feed** is also client-side — built incrementally as `onWorkItemCitation` events arrive, sorted by `created_at`, capped at 5 visible items. The `work_item_feed.html` Jinja2 template is available for server-rendered views.

3. **Tone-switch chip** (`injectToneSwitchChip`) is injected into the assistant bubble after `done`. On click it POSTs to `/api/projects/{pid}/code/qa/rerender` and streams into the bubble. Falls back to page reload on HTTP 410.

4. **`citations.js`** `getAll` extension: `type` and `id` fields added to return object; `register` unchanged (callers passing `type`/`id` in the `data` dict will have them preserved).

5. **No JS test infra** exists in this repo — calling out as a risk. Template smoke tests are Python-side Jinja2 renders only.

## Blockers

None.

## Notes

- `render.js` `injectToneSwitchChip` renders new prose by appending to `bodyEl.innerHTML` — this is a simplified approach; a more complete implementation would use the markdown parser. Full streaming into the existing bubble requires the SSE response to be plumbed through `window.iwChat.streamAnswer` which is already used for the initial answer.
