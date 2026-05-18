# I-00093_S01_Frontend_prompt

**Work Item**: I-00093 — Auto-merge event detail modal hides the most useful fields
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies — see `docs/IW_AI_Core_Agent_Constraints.md`.
No docker commands except testcontainers in pytest fixtures. No
alembic.

## Input Files

- `uv run iw item-status I-00093 --json`
- `ai-dev/active/I-00093/I-00093_Issue_Design.md`
- `ai-dev/active/I-00093/I-00093_Functional.md`
- `dashboard/templates/fragments/auto_merge_event_detail.html`
- `dashboard/routers/auto_merge_ui.py`
- `orch/auto_merge_aggregator.py` (EventRow shape — has `message`,
  `metadata`, `verdict`, `verdict_notes`, `verdicted_by`,
  `verdicted_at`)
- `dashboard/CLAUDE.md`
- `dashboard/static/clipboard.js` (the shared `window.iwClipboard.copy`
  helper)

## Output Files

- `ai-dev/active/I-00093/reports/I-00093_S01_Frontend_report.md`

## Context

The modal at `/auto-merge/events/<id>` already receives the full
`EventRow` (with `message`, `metadata` JSON, etc.) but the template
renders only 4 boilerplate fields. Make the modal informative.

## Requirements

### 1. Humanized heading

Replace `<h3>Event #{{ event.id }}</h3>` with a heading that contains
the event type + formatted timestamp. Compute the human title either:

- **Inline in Jinja2**:
  ```jinja
  <h3 id="auto-merge-event-title" class="text-sm font-semibold">
    {{ event.event_type }} — {{ event.created_at | localdt('%Y-%m-%d %H:%M:%S') }}
  </h3>
  ```
- **Or server-side**: in `auto_merge_event_detail` route handler, build
  `humanized_title` and pass it into the template context. Slightly
  cleaner; minor refactor.

Either is acceptable. Pick one and stay consistent.

### 2. Render the event message

Add a section under the summary `<dl>`:

```jinja
{% if event.message %}
<section class="text-xs">
  <h4 class="text-muted-foreground uppercase tracking-wide mb-1">Message</h4>
  <p class="auto-merge-modal__message">{{ event.message }}</p>
</section>
{% endif %}
```

The `{{ event.message }}` is auto-escaped by Jinja2 — no `| safe`.

### 3. Render entity_type alongside entity_id

Add a `<div>` to the existing summary `<dl>`:

```jinja
<div><dt class="text-muted-foreground">entity_type</dt><dd>{{ event.entity_type or '—' }}</dd></div>
```

Note: `EventRow` may not currently carry `entity_type` — verify against
`orch/auto_merge_aggregator.py:EventRow`. If absent, either:
- Extend `EventRow` to include `entity_type` (small dataclass +
  aggregator function change). OR
- Pass the raw `DaemonEvent` model alongside as `raw_event` and read
  `raw_event.entity_type` from the template.

Pick whichever is cleaner; document the choice in your report.

### 4. Render the full metadata as collapsible JSON

```jinja
{% if event.metadata %}
<section class="text-xs space-y-1">
  <div class="flex items-center justify-between">
    <h4 class="text-muted-foreground uppercase tracking-wide">Metadata</h4>
    <button type="button"
            class="auto-merge-modal__copy-btn"
            onclick="window.iwClipboard.copy({{ event.metadata | tojson | tojson }}, this)">
      Copy as JSON
    </button>
  </div>
  <details {% if (event.metadata | tojson)|length < 400 %}open{% endif %}>
    <summary class="cursor-pointer text-muted-foreground">
      {{ event.metadata.keys() | list | length }} key{{ 's' if event.metadata|length != 1 else '' }}
    </summary>
    <pre class="auto-merge-modal__metadata">{{ event.metadata | tojson(indent=2) }}</pre>
  </details>
</section>
{% endif %}
```

Notes:
- `event.metadata | tojson` produces a JSON string; the outer `tojson`
  re-encodes it for safe inclusion as a JS string literal in the
  `onclick` attribute.
- `<details open>` is decided by payload size (<400 chars = expanded;
  larger = collapsed by default).
- Use `window.iwClipboard.copy(...)` per `dashboard/CLAUDE.md` —
  NEVER call `navigator.clipboard.writeText(...)` directly (this
  dashboard runs on plain HTTP `iw-dev-01` where `navigator.clipboard`
  is `undefined`).

### 5. Render verdict info if present (any event_type)

```jinja
{% if event.verdict %}
<section class="text-xs space-y-1 border-t border-border pt-3">
  <h4 class="text-muted-foreground uppercase tracking-wide mb-1">Verdict</h4>
  <dl class="grid grid-cols-2 gap-2">
    <div><dt class="text-muted-foreground">value</dt><dd>{{ event.verdict }}</dd></div>
    <div><dt class="text-muted-foreground">by</dt><dd>{{ event.verdicted_by or '—' }}</dd></div>
    <div><dt class="text-muted-foreground">at</dt><dd>{{ event.verdicted_at | localdt('%Y-%m-%d %H:%M:%S') if event.verdicted_at else '—' }}</dd></div>
  </dl>
  {% if event.verdict_notes %}
  <p>{{ event.verdict_notes }}</p>
  {% endif %}
</section>
{% endif %}
```

This section renders for ANY event_type that happens to have a verdict
recorded. For `merge_auto_resolved` events it sits BEFORE the existing
verdict-update form (which still lets the operator change the verdict).

### 6. Preserve existing diff + verdict form for merge_auto_resolved

The current template's diff section (lines 28-46) and verdict form
(lines 48-69) must continue to render unchanged for resolved events.
Don't refactor them in this step.

### 7. CSS rules

Append to `dashboard/static/styles.css` (plain CSS — `make css` is
broken in worktrees per CLAUDE.md / I-00067):

```css
.auto-merge-modal__message{white-space:pre-wrap;word-break:break-word}
.auto-merge-modal__metadata{background:var(--muted);padding:.5rem;border-radius:.25rem;max-height:24rem;overflow:auto;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.75rem;white-space:pre}
.auto-merge-modal__copy-btn{border:1px solid var(--border);border-radius:.25rem;padding:.1rem .4rem;font-size:.7rem;cursor:pointer;background:var(--card)}
.auto-merge-modal__copy-btn:hover{background:var(--muted)}
```

### 8. No new JavaScript module

The `window.iwClipboard.copy(...)` helper already exists in
`dashboard/static/clipboard.js` and is loaded by the base layout.
Don't add `<script>` blocks or new files under `static/scripts/`.

### 9. Heading IDs / aria

Keep `aria-labelledby="auto-merge-event-title"` valid by retaining the
`id="auto-merge-event-title"` on the `<h3>`.

## Project Conventions

- `dashboard/CLAUDE.md` — fragment templates do NOT extend `base.html`;
  htmx fetches them and swaps into a target id; use
  `window.iwClipboard.copy(...)` for clipboard buttons.
- Jinja2 `format`-filter calls MUST stay `%`-style (I-00075).
- Plain CSS appended to `styles.css` is correct; do NOT run `make css`.

## TDD Requirement

Frontend step — behavioural tests live in S03. For your own
pre-completion check, run existing dashboard tests:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint` (includes the template Jinja2 validator)

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

Do NOT run the full suite.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00093",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/auto_merge_event_detail.html",
    "dashboard/static/styles.css",
    "dashboard/routers/auto_merge_ui.py"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — template + minor route context-extension; behavioural tests live in S03",
  "blockers": [],
  "notes": "Note where entity_type came from (extended EventRow vs passed raw event) and where humanized_title was computed."
}
```
