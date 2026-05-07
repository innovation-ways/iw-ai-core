# F-00080_S03_frontend-impl_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. See template boilerplate. Allowed exceptions: testcontainers, read-only docker probes, `./ai-core.sh` / `make`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch migrations.

## Input Files

- Runtime step state: `uv run iw item-status F-00080 --json`.
- `ai-dev/active/F-00080/F-00080_Feature_Design.md`
- `ai-dev/work/F-00080/reports/F-00080_S01_api_report.md`
- `dashboard/CLAUDE.md`
- Existing vendored asset for pattern reference: `dashboard/static/vendor/htmx/`
- Existing base template: `dashboard/templates/base.html`

## Output Files

- `dashboard/static/vendor/driver/driver.js.iife.js` — vendored Driver.js (MIT) with upstream license header
- `dashboard/static/vendor/driver/driver.css` — vendored Driver.js stylesheet
- `dashboard/static/vendor/driver/LICENSE` — MIT license text
- `dashboard/static/help/help.js` — popover + tour glue code
- `dashboard/static/help/tours.js` — per-page tour definitions (3-5 steps each)
- `dashboard/templates/macros/help_button.html` — `?` button macro
- `dashboard/templates/macros/empty_state.html` — empty state macro
- `dashboard/templates/_partials/help/<slug>.html` × 22 — help fragments
- `dashboard/templates/base.html` — add page-header help slot, load help.js (deferred), lazy-load driver.css on first popover render
- `dashboard/static/styles.css` — append plain CSS for help button, popover, focus ring, ✓ tour-seen indicator
- `THIRD_PARTY_LICENSES` — append Driver.js entry
- `ai-dev/work/F-00080/reports/F-00080_S03_frontend_report.md`

## Context

You are building the entire frontend surface for the help system: vendored Driver.js, the popover JS, the macros, all 22 help fragments, the per-page tour definitions, the CSS, and the page-header slot in base.html. This is a large step — break it into the sub-deliverables below and verify each before moving on.

The router from S01 already exists and serves `GET /_help/<slug>`. Your fragments must match the slug allow-list it builds at startup.

## Requirements

### 1. Vendor Driver.js (MIT) into `dashboard/static/vendor/driver/`

- Source: https://github.com/kamranahmedse/driver.js — pin to the latest stable release tagged on npm (use whatever the current `latest` tag is when you do this work; record the exact version in your report).
- Files to vendor:
  - `driver.js.iife.js` — the IIFE bundle (a single file you can load with `<script src=...>` without a module system).
  - `driver.css`
  - `LICENSE` — copy the upstream MIT license text verbatim into `dashboard/static/vendor/driver/LICENSE`.
- At the top of `driver.js.iife.js`, ensure the upstream MIT header comment is preserved. If the upstream file already has it, leave it; if missing, prepend a comment block of the form:
  ```js
  /*!
   * Driver.js vX.Y.Z
   * https://driverjs.com
   * Copyright (c) Kamran Ahmed
   * Licensed under MIT — see ./LICENSE
   */
  ```
- Append an entry to the project's `THIRD_PARTY_LICENSES` file (create one if missing — match the format used elsewhere if any). Format:
  ```
  -------------------------------------------------------------------------------
  Driver.js vX.Y.Z
  Copyright (c) Kamran Ahmed
  License: MIT
  Source: https://github.com/kamranahmedse/driver.js
  Vendored at: dashboard/static/vendor/driver/driver.js.iife.js
  -------------------------------------------------------------------------------
  <full MIT license text>
  ```
- Do **not** download via `npm install`. Either fetch the published artefact directly from the GitHub release page or copy from a known-good source. Document the exact source URL and SHA256 in your step report.

### 2. Create `dashboard/templates/macros/help_button.html`

A Jinja macro `help_button(slug)` that renders:

```html
<button type="button"
        class="help-trigger"
        aria-label="Help for this page"
        aria-haspopup="dialog"
        aria-expanded="false"
        data-help-slug="{{ slug }}">
  <span class="help-trigger__mark" aria-hidden="true">?</span>
  <span class="help-trigger__seen" aria-hidden="true" data-tour-seen-marker>✓</span>
</button>
<div class="help-popover" role="dialog" aria-modal="true" aria-label="Page help" data-help-popover hidden></div>
```

The `data-tour-seen-marker` element is hidden by default; CSS reveals it when the parent button has `data-tour-seen="true"`. The popover container is empty until htmx fills it.

### 3. Create `dashboard/templates/macros/empty_state.html`

A Jinja macro `empty_state(slug, heading, body, primary_label, primary_href, secondary_label, secondary_href)` that renders:

```html
<div class="empty-state" data-empty-state="{{ slug }}">
  <h3 class="empty-state__heading">{{ heading }}</h3>
  <p class="empty-state__body">{{ body }}</p>
  <div class="empty-state__actions">
    <a href="{{ primary_href }}" class="empty-state__cta-primary">{{ primary_label }}</a>
    {% if secondary_label and secondary_href %}
      <a href="{{ secondary_href }}" class="empty-state__cta-secondary">{{ secondary_label }}</a>
    {% endif %}
  </div>
</div>
```

### 4. Create all 22 help fragments under `dashboard/templates/_partials/help/<slug>.html`

Each fragment MUST follow the exact 4-section structure below — the orphan-check test in S07 verifies the four headings exist:

```html
<section class="help-content">
  <header class="help-content__header">
    <h2 class="help-content__title">{{ page_title }}</h2>
    <button type="button" class="help-content__close" data-help-close aria-label="Close help">×</button>
  </header>

  <h3>What is this page?</h3>
  <p>{{ one-sentence description }}</p>

  <h3>What can I do here?</h3>
  <ul>
    <li>{{ action 1 }}</li>
    <li>{{ action 2 }}</li>
    <li>{{ action 3 }}</li>  <!-- max 3 -->
  </ul>

  <h3>Vocabulary</h3>
  <dl>
    <dt>Term 1</dt><dd>One-line definition.</dd>
    <dt>Term 2</dt><dd>One-line definition.</dd>
  </dl>

  <footer class="help-content__footer">
    <button type="button" class="help-content__tour" data-tour-start>Take the 30-second tour →</button>
    <a class="help-content__docs-link" href="{{ docs_href }}">Open full docs →</a>
  </footer>
</section>
```

Slug list and concrete copy guidance (write good first-draft copy yourself; the goal is "explains in seconds"):

| Slug | Page | Doc link target |
|---|---|---|
| `projects` | `/projects` landing (project_selector.html) | `/docs` |
| `queue` | project queue | `docs/IW_AI_Core_CLI_Spec.md#approve` |
| `history` | project history | `docs/IW_AI_Core_CLI_Spec.md` |
| `batches` | project batches | `docs/IW_AI_Core_Daemon_Design.md#batches` |
| `batch_detail` | one batch | same |
| `item_detail` | one work item | `docs/IW_AI_Core_Architecture.md` |
| `jobs` | project jobs (unified) | `docs/IW_AI_Core_Daemon_Design.md` |
| `job_detail` | one job | same |
| `code` | project code (RAG) | `orch/rag/CLAUDE.md` |
| `docs` | project docs library | `docs/implementation/00_INDEX.md` |
| `research` | project research library | `docs/IW_AI_Core_Architecture.md` |
| `tests` | tests runner | `docs/IW_AI_Core_Tech_Stack.md` |
| `quality` | quality runner | same |
| `search` | project search | `docs/IW_AI_Core_Architecture.md` |
| `status` | system status | `docs/IW_AI_Core_DB_Setup.md` |
| `worktrees` | system worktrees | `docs/IW_AI_Core_Daemon_Design.md` |
| `containers` | system containers | `docs/IW_AI_Core_Worktree_Isolation.md` |
| `all_active` | system all-active | `docs/IW_AI_Core_Daemon_Design.md` |
| `config` | system config | `docs/IW_AI_Core_Tech_Stack.md` |
| `keep_alive` | keep-alive | `docs/IW_AI_Core_Daemon_Design.md` |
| `coverage` | coverage | `docs/IW_AI_Core_Tech_Stack.md` |
| `running` | currently running | `docs/IW_AI_Core_Daemon_Design.md` |

Vocabulary terms to define somewhere across the fragments (cover at least once per term): "work item", "feature/incident/CR", "batch", "fix cycle", "step", "worktree", "daemon", "RAG / Code Understanding", "stale doc", "fragment", "approval", "job".

### 5. Create `dashboard/static/help/help.js`

Plain ES module-free script (no bundler). Behaviour:

- Use **event delegation** on `document` for clicks on `[data-help-slug]` (the `?` button) so it works even before `defer` finishes (clicks queued before the listener attaches still fire).
- On click, read the slug from `data-help-slug`, locate the sibling `[data-help-popover]` mount, htmx-load `/_help/<slug>` into it (or use plain `fetch` + `innerHTML`; do NOT use `eval`), set `aria-expanded="true"`, set `hidden=false`, and move focus to the close button inside the loaded fragment.
- **Focus trap** while popover is open: keep focus inside the popover when Tab is pressed; ESC closes the popover and returns focus to the originating `?` button.
- Only one popover may be open at a time — clicking another `?` button closes the previous popover first.
- A click on `[data-help-close]`, on the page background outside the popover, or ESC closes the popover.
- On click of `[data-tour-start]` inside the popover, lazy-load `dashboard/static/vendor/driver/driver.css` (inject `<link>` once) and then call into Driver.js (the IIFE exposes `driver` on `window.driver` — confirm the exact global name by reading the upstream IIFE bundle and use whatever it exports). Pass the tour steps for the current slug from `tours.js`. Driver.js options:
  ```js
  {
    allowKeyboardControl: true,
    showProgress: true,
    showButtons: ["next", "previous", "close"],
    onDestroyStarted: function () { /* mark tour seen */ }
  }
  ```
- On tour `onDestroyed` (or `onDestroyStarted` after final step), set `localStorage.setItem("iw.tour." + slug + ".completedAt", new Date().toISOString())`.
- On every `DOMContentLoaded`, walk all `[data-help-slug]` buttons. For each, if `localStorage` has a `iw.tour.<slug>.completedAt` key, set `data-tour-seen="true"` on the button.
- If `localStorage` is unavailable (private mode), every operation must catch the exception and continue silently (no console error to the user).
- If `tours.js` defines no entries for the current slug, hide `[data-tour-start]` (`button.hidden = true`).
- If the Driver.js script fails to load, set `[data-tour-start]` to `aria-disabled="true"` and `disabled` and add a `title="Tour unavailable"`.

### 6. Create `dashboard/static/help/tours.js`

```js
// Tour definitions, one per page slug. 3-5 steps each.
window.IW_TOURS = {
  queue: [
    { element: "[data-tour='queue-table']", popover: { title: "Your queue", description: "Approved work items wait here..." } },
    { element: "[data-tour='queue-create']", popover: { title: "Create from selection", description: "..." } },
    /* ... */
  ],
  // entries for every slug that has a meaningful guided tour (omit pages where there's nothing to point at)
};
```

You decide which pages get a tour and which only get the `?` popover. As a guideline: queue, batches, jobs, item_detail, code, docs, worktrees, status SHOULD have tours; the rest can have only the `?` popover (the "Take the tour" button is hidden when no tour is defined).

When you reference selectors like `[data-tour='queue-table']` in tour steps, S05 (template-impl) is responsible for adding the corresponding `data-tour="..."` attributes to the actual page templates. **Document the list of `data-tour` attribute names you used in each tour in your step report** so S05 has a clean checklist.

### 7. Append plain CSS to `dashboard/static/styles.css`

`make css` is broken in worktrees (I-00067), so styles.css is currently 0 lines and serves only as a placeholder for plain CSS rules. Append a `/* ===== F-00080 help system ===== */` section with rules for:

- `.help-trigger` — small circular `?` button, fits next to an `<h1>` page title
- `.help-trigger__mark`, `.help-trigger__seen` — base + ✓-when-seen state (use `[data-tour-seen='true'] .help-trigger__seen { display: inline; }` and hidden by default)
- `.help-popover` — fixed-position panel anchored near the button (use absolute + JS-positioning logic in help.js, or simple CSS-only positioning relative to the button — your call but document the choice)
- `.help-content__*`, `.empty-state__*`
- Focus-visible ring on the `?` button (`outline: 2px solid var(--ring); outline-offset: 2px;`)
- Reduced-motion respect: any popover/tour transitions wrapped in `@media (prefers-reduced-motion: no-preference)` so users with reduced-motion get instant transitions.
- High-contrast support: ensure focus rings and the popover border are visible in both light and dark modes (the existing `--ring`, `--background`, `--foreground` CSS variables in `theme.css` are available).

### 8. Update `dashboard/templates/base.html`

- Add **two new blocks** in the page-header location (find the `{% block content %}` start — but the `?` button must be visible at the **top of the page**; you may need a wrapper around `{% block content %}` or, if the existing layout puts the title inside `{% block content %}`, define a small inline JS hook that re-positions the help button next to the first `<h1>` in the content area on `DOMContentLoaded`):
  - `{% block page_help_slug %}{% endblock %}`
  - The macro is auto-rendered if and only if the slug block is non-empty:
    ```jinja
    {% set _help_slug = self.page_help_slug() %}
    {% if _help_slug %}
      {% from "macros/help_button.html" import help_button %}
      <div class="page-help-mount">{{ help_button(_help_slug) }}</div>
    {% endif %}
    ```
  - Place this `<div class="page-help-mount">` such that the JS in help.js can position it next to the first `<h1>` of `{% block content %}`. The cleanest way is to put it inside the content wrapper but with `position: relative` so JS can move it.
- Add `<script src="/static/help/tours.js" defer></script>` and `<script src="/static/help/help.js" defer></script>` near the existing htmx script tags. **Do not load `driver.js.iife.js` eagerly** — help.js lazy-loads it on first tour start.
- Do **not** preload `driver.css`; help.js lazy-injects a `<link>` on first tour mount.

### 9. RED tests for help.js (light)

Add a tiny dashboard test stub at `tests/dashboard/test_help_js_smoke.py` (you create it; S07 will expand) that asserts the rendered base.html on a known help-slug page contains both `data-help-slug=` and the `<script src=".../help.js"` tag.

## Project Conventions

Read `dashboard/CLAUDE.md`. Note:
- Routers are thin; you are NOT writing router code here.
- Static assets live under `dashboard/static/`.
- All vendored libs go in `dashboard/static/vendor/<lib>/` and ship with their license file.
- `make css` is broken in worktrees → append plain CSS directly to `dashboard/static/styles.css`.
- `dashboard/static/clipboard.js` shows the existing pattern for plain-JS helpers — match its style (no ES modules, no bundler).

## TDD Requirement

Frontend assets are largely declarative; the testable behaviour is mostly covered by S07. For this step:

1. Write the small `tests/dashboard/test_help_js_smoke.py` first (RED).
2. Implement everything else.
3. Re-run; the smoke test passes (GREEN).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`:

1. `make format`
2. `make typecheck` (no Python file in this step, but the make target must still pass clean against existing files)
3. `make lint` — note that CLAUDE.md says lint includes `node --check` on `dashboard/static/**/*.js`. Run `node --check dashboard/static/help/help.js dashboard/static/help/tours.js` locally to catch JS syntax errors.

Populate `preflight` in the result contract.

## Test Verification

`make test-unit` and the smoke test you added must pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "F-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/vendor/driver/driver.js.iife.js",
    "dashboard/static/vendor/driver/driver.css",
    "dashboard/static/vendor/driver/LICENSE",
    "dashboard/static/help/help.js",
    "dashboard/static/help/tours.js",
    "dashboard/templates/macros/help_button.html",
    "dashboard/templates/macros/empty_state.html",
    "dashboard/templates/_partials/help/<slug>.html (×22)",
    "dashboard/templates/base.html",
    "dashboard/static/styles.css",
    "THIRD_PARTY_LICENSES",
    "tests/dashboard/test_help_js_smoke.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "1 passed",
  "blockers": [],
  "notes": "Driver.js version: vX.Y.Z; data-tour selectors used: [list for S05]"
}
```
