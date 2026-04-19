# F-00055_S07_Frontend_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S07
**Agent**: frontend-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` (AC1, AC2, AC5, AC6, AC10; Invariants 4, 6, 7, 8)
- `ai-dev/active/F-00055/reports/F-00055_S05_API_report.md`
- `dashboard/static/chat/stream.js` — current SSE consumer (target: add `onPhase`)
- `dashboard/static/chat/render.js` — assistant renderer (target: work-item chip variant)
- `dashboard/static/chat/composer.js` — slash commands registry (target: `/why`, `/history` aliases; tone-switch chip)
- `dashboard/static/chat/citations.js` — citation map
- `dashboard/static/chat/panel.js` — panel lifecycle (no changes expected)
- `dashboard/templates/chat/panel.html`, `dashboard/templates/chat/composer.html`
- `dashboard/templates/chat/parts/citation_chip.html` — existing citation chip (keep as-is; new variant is additive)
- `dashboard/templates/chat/parts/sources_panel.html` — existing sources panel
- `docs/research/R-00059-work-item-narrative-presentation.md` — answer shape rules
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S07_Frontend_report.md`

## Context

Extend the chat UI to render phase events, work-item citation chips, the Linear-style work-item feed, and the per-answer tone-switch chip. All rendering happens via the existing streaming-markdown pipeline; no build step, no bundler — vanilla JS + Tailwind CDN + Jinja2 partials.

## Requirements

### 1. `stream.js` — `onPhase` callback

Extend `window.iwChat.streamAnswer` to accept a new `onPhase` callback and dispatch on the `phase` SSE event:

```javascript
} else if (data.name !== undefined && eventType === 'phase') {
  onPhase({ name: data.name, detail: data.detail || {} });
}
```

Default no-op when omitted (mirror existing callback defaults).

### 2. Phase strip template — `chat/parts/phase_strip.html`

New Jinja2 fragment (server-rendered only when needed; can also be created client-side in render.js since this is a dynamic element). Create a **client-side** version inside `render.js` — the assistant renderer mounts a `<div class="phase-strip">` above the message body when the first `phase` event arrives. Each phase event replaces the strip's content with the human-readable label:

| Phase name | Label |
|------------|-------|
| `retrieving` | `Looking up related code…` |
| `finding_items` | `Finding related items… ({count})` |
| `reading_docs` | `Reading design documents… ({count})` |
| `composing` | `Writing answer…` |

On the `composing` phase, transition the strip from a spinner-state to a quiet checkmark; on the first `token`, collapse the strip into a single-line note that reads `Based on {count} work items.` (from the `reading_docs` count). Keep the strip visible and non-collapsible after answer completes (the feed below provides the detail).

Style: small height (24px), muted text, matches the existing chat design tokens (`text-muted-foreground`, `bg-muted/50`). Accessibility: role="status", aria-live="polite".

### 3. Work-item chip template — `chat/parts/work_item_chip.html`

Create a new Jinja2 fragment for the ID-first work-item chip. It is used via `render.js` (server-side rendering only happens for the static `sources_panel.html` summary; live streaming inserts chips via DOM):

```html
<button class="citation-chip citation-chip--workitem citation-chip--{{ work_item_type }}"
        aria-haspopup="dialog"
        data-cite="{{ n }}"
        data-workitem-id="{{ work_item_id }}"
        data-workitem-type="{{ work_item_type }}"
        aria-label="Work item {{ work_item_id }}">
  <span class="citation-chip-glyph" aria-hidden="true">{{ "F" if work_item_type == "feature" else ("CR" if work_item_type == "change_request" else "I") }}</span>
  <span class="citation-chip-id">{{ work_item_id }}</span>
</button>
```

Style via CSS in `dashboard/static/chat.css` (or inline Tailwind classes if the existing citation chip uses Tailwind):
- `F` glyph: blue-tinted
- `CR` glyph: amber-tinted
- `I` glyph: red-tinted
- Maintain 44×44 minimum touch target per existing accessibility rules.

### 4. `render.js` — chip variant + popover link

When the work-item-aware pipeline emits `[F-NNNNN]`, `[CR-NNNNN]`, or `[I-NNNNN]` in the streaming answer, render it as the new chip variant instead of the generic `[1]` numbered chip. Detection: a single `data-cite` attribute can resolve to either — check the citation map entry and pick the template based on whether the entry has `work_item_id`.

The popover for a work-item citation shows:
- Bold: `{work_item_type_label} {work_item_id}` — e.g., "Feature F-00042"
- Title line: `{title}`
- Snippet line: first 240 chars of summary/design-doc-excerpt
- Link: `Open item →` → `/project/{project_id}/item/{work_item_id}`

Keep the generic symbol-based citation popover (existing) for code-only citations.

### 5. Work-item feed fragment — `chat/parts/work_item_feed.html`

Linear-style chronological feed, rendered **below the streaming answer** once the `done` event arrives (or incrementally: feed scaffold created on `reading_docs` phase, populated as `citation` events arrive). Structure:

```html
<section class="work-item-feed" aria-label="Work item history">
  <header class="work-item-feed-header">
    <h3 class="text-sm font-medium">History</h3>
    <div class="work-item-feed-trust-strip text-xs text-muted-foreground">
      Based on {{ count }} work items merged up to {{ retrieval_cutoff|dateformat }}. Confidence: {{ confidence }}
    </div>
  </header>
  <ol class="work-item-feed-list">
    {% for item in items %}
    <li class="work-item-feed-item" data-workitem-id="{{ item.id }}">
      <div class="work-item-feed-meta">
        <time datetime="{{ item.created_at }}">{{ item.created_at|dateformat('YYYY-MM-DD') }}</time>
        <a href="/project/{{ project_id }}/item/{{ item.id }}" class="work-item-feed-id">{{ item.id }}</a>
      </div>
      <h4 class="work-item-feed-title">{{ item.title }}</h4>
      <p class="work-item-feed-summary">{{ item.summary or "(no summary available)" }}</p>
    </li>
    {% endfor %}
  </ol>
</section>
```

- Render client-side from the accumulated `citation` event payloads (no server-side template needed for the live stream; the template file can remain for potential server-rendered views).
- Sort ascending by `created_at`.
- Cap visible items at 5; add a "Show N more" link to the sources panel if more.
- Clicking an item row also opens the item detail page.

### 6. `composer.js` — slash aliases and tone-switch chip

- Extend `slashCommands` to include:
  ```js
  { label: '/why', name: 'why', description: 'Answer with work-item history' },
  { label: '/history', name: 'history', description: 'Show history of changes' },
  { label: '/findusages', name: 'findusages', description: 'Find usages + history' },
  ```
  Keep `/explain` and `/diagram`.
- After `done`, inject a tone-switch chip into the assistant bubble reading either `Show implementation details` (if the answer was functional) or `Show functional summary` (if technical). Disable the chip during streaming.
- **Tone-switch click behavior (AC5 "without refetching")**: the bubble stashes the `render_id` received in the `composing` phase `detail`. On click:
  1. POST to `/api/projects/{project_id}/code/qa/rerender` with `{render_id, tone: "technical"|"functional"}` and stream the SSE response into the same bubble (replace prose, keep the feed below stable — feed items are re-emitted identically).
  2. On HTTP 410 Gone (render-cache expired), fall back to re-firing the original query with the `tone:<register>` context chip appended (the old behavior). Show a brief `Re-running…` status in the phase strip so the user knows it's not instant.
  3. Flip the chip label after `done`.

### 7. `citations.js` — extended map entries

Extend the `register(n, data)` signature to accept optional `type` and `id` fields; `getAll` returns them; `sources_panel.html` already consumes `{n, label, url, snippet}` — if you render work-item citations into the sources panel, include a type-glyph pill next to the label.

### 8. CSS

Add or extend `dashboard/static/chat.css` (or create if missing) with:
- `.phase-strip` rules (height, flex, muted text).
- `.work-item-feed` rules (Linear-style spacing, typography hierarchy).
- `.citation-chip--workitem` + `.citation-chip--feature|change_request|incident` variants.
- `.tone-switch-chip` rules.

No Tailwind class purge — Tailwind is CDN-loaded; use custom CSS for new classes.

## Project Conventions

Read `dashboard/CLAUDE.md`:
- FastAPI + Jinja2 + htmx + Tailwind CDN; **no build step**.
- Fragments under `templates/chat/parts/` must NOT extend `base.html`.
- htmx is NOT used for the chat panel's streaming — that's vanilla JS + SSE. Do not introduce htmx where it isn't currently used.
- Accessibility: min touch target 44×44, aria-live for dynamic content, keyboard navigation for popovers.

## TDD Requirement

Frontend tests live in `tests/frontend/` (if the dir exists) or as unit-style Jest/Vitest/pytest-playwright tests. Confirm the current project's convention by reading existing tests in the repo. If no frontend test infra exists, add Python-side unit tests for the Jinja2 templates (render with a test context) and call out the missing JS test infra as a risk in the step report.

Required tests:
- Template rendering for `work_item_chip.html` and `work_item_feed.html` with fixture data.
- JS: when the SSE consumer receives a `phase` event, `onPhase` is invoked with the correct args (use a harness that feeds mock events into `streamAnswer`).

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — must pass.
2. `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy orch/ dashboard/` — must pass.
3. Manual browser check: open dashboard → Code page of a project with indexed docs → ask "why does X do Y" → verify phase strip appears, work-item chips render with type glyphs, feed appears below answer, clicking chip/feed row navigates to item page, tone-switch chip flips register.
4. No console errors in browser dev tools.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "frontend-impl",
  "work_item": "F-00055",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/chat/stream.js",
    "dashboard/static/chat/render.js",
    "dashboard/static/chat/composer.js",
    "dashboard/static/chat/citations.js",
    "dashboard/static/chat.css",
    "dashboard/templates/chat/parts/work_item_chip.html",
    "dashboard/templates/chat/parts/work_item_feed.html",
    "dashboard/templates/chat/parts/phase_strip.html"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
