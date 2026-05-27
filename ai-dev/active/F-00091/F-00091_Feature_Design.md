# F-00091: AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar

**Type**: Feature
**Priority**: High
**Created**: 2026-05-26
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This feature ADDS one Alembic data migration in S04 (backfill of `agent_runtime_options.context_window_tokens` for Pi models currently allow-listed in `projects.toml`). The migration is data-only — no DDL, no new tables, no new columns. The daemon applies it as part of the merge pipeline.

## Description

The dashboard AI Assistant panel is rendered globally in `dashboard/templates/base.html` and derives its project context exclusively from the current page URL (`_currentProjectId()` in `dashboard/static/chat_assistant/chat.js:87`). Every full page navigation re-bootstraps the panel with a different `project_id`, swapping out the tab strip and apparently destroying chat history. The context-usage percentage indicator (CR-00067) is wired but starts hidden and is silently never rendered when the server's lookup chain for the model's context window fails. This feature removes the URL coupling by introducing an in-panel project selector backed by `localStorage`, namespaces the active-tab pointer per project, and replaces the hidden text badge with an always-visible inline progress bar that explicitly surfaces the unknown state.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key constraints relevant here:

- Dashboard uses FastAPI + Jinja2 + htmx; Tailwind CSS is **prebuilt** via `make css` — new utility classes that aren't already in `dashboard/static/styles.css` are NOT picked up automatically. Append plain CSS to `chat_assistant/chat.css` for new styles (this is the documented workaround for I-00067).
- `dashboard/static/chat_assistant/chat.js` is plain ES5-style IIFE — no transpiler. Match the surrounding `var`/`function` idiom.
- `make lint` enforces `scripts/check_templates.py`: Jinja2 `format` filter calls MUST stay `%`-style (`"%dm%02ds"|format(m,s)`), never `str.format`-style.
- Browser automation uses `playwright-cli` exclusively. Never `agent-browser`, never direct `chromium.launch()`.
- Tests never connect to the live DB on port 5433 — testcontainers only (`tests/conftest.py`).

## Scope

### In Scope

- **S01 — API**: A new JSON endpoint `GET /api/chat/projects` returning `[{id, display_name}]` for every registered enabled project. Used by the panel's project dropdown.
- **S02 — Frontend (project selector)**: Project `<select>` in `chat_assistant/panel.html`. New JS accessor `_assistantProjectId()` reads/writes localStorage key `iw-chat-assistant-project`. All call sites of `_currentProjectId()` inside `chat.js` are replaced with the new accessor. The URL is consulted ONLY on first-ever open (when the localStorage key is unset).
- **S03 — Frontend (tab restoration)**: Replace the single sessionStorage key `iw-chat-active-tab-<browserTabId>` with a localStorage key namespaced per project: `iw-chat-active-tab:<projectId>`. On bootstrap and on project-selector change, read the namespaced key; if absent or stale, fall back to `_tabs[0]` (the server already orders by `last_active_at DESC`).
- **S04 — Database**: One Alembic data migration that UPSERTs `context_window_tokens` for the (cli_tool, model) pairs currently allow-listed for Pi across `projects.toml`. The migration is idempotent (NULL-only update via `WHERE context_window_tokens IS NULL`).
- **S06 — Backend**: `dashboard/routers/chat.py:get_tab` extends the `session` payload with `used_tokens`, `window_tokens`, and an explicit `context_pct_status` field that is one of `"known" | "unknown_window" | "unknown_runtime"`. The current behaviour of omitting the key entirely is replaced.
- **S07 — Frontend (progress bar)**: Replace the `<span id="chat-assistant-context-pct">` text badge in `chat_assistant/composer.html` with a small flex container that holds an inline progress bar (~60px × 5px) followed by the numeric percentage. Color states green <70%, amber 70–89%, critical red ≥90%. Render the unknown state as a greyed-out bar showing `—%` with a tooltip explaining the missing piece. Always visible while a tab is active.
- **S08 — Tests**: Dashboard + integration tests for project decoupling, tab restoration, and context-pct unknown state.

### Out of Scope

- "Follow page project" toggle / auto-sync chip — explicitly deferred per user decision.
- SPA conversion of the dashboard — the panel still re-renders on every full page load; the JS just preserves state across those reloads via localStorage.
- Multi-runtime model switching within a tab — already prohibited by CR-00068.
- Any change to the `chat_tabs` DB schema.
- Any change to OpenCode or Pi runtime backends themselves.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. The three issues each get their own implementation pair (or trio). One consolidated CodeReview pass at the end keeps reviewer cost down.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | api-impl | `GET /api/chat/projects` JSON listing endpoint | — |
| S02 | frontend-impl | Project selector dropdown in panel header + `_assistantProjectId()` accessor; replace all `_currentProjectId()` call sites in `chat.js` | — |
| S03 | frontend-impl | Per-project namespaced active-tab pointer in localStorage | — |
| S04 | database-impl | Alembic data migration backfilling `agent_runtime_options.context_window_tokens` for Pi-allow-listed models | — |
| S05 | qv-gate | QV: migration-check (`make migration-check`) | — |
| S06 | backend-impl | Extend session payload with `used_tokens`, `window_tokens`, `context_pct_status` | — |
| S07 | frontend-impl | Inline progress-bar UI replacing the text badge; render unknown state explicitly | — |
| S08 | tests-impl | Dashboard + integration tests covering AC1–AC4 | — |
| S09 | code-review-impl | Per-agent review of S01..S08 in a single consolidated pass | — |
| S10 | code-review-final-impl | Cross-agent final review | — |
| S11 | qv-gate | QV: lint (`make lint`) | — |
| S12 | qv-gate | QV: format (`make format-check`) | — |
| S13 | qv-gate | QV: typecheck (`make type-check`) | — |
| S14 | qv-gate | QV: arch-check (`make arch-check`) | — |
| S15 | qv-gate | QV: security-sast (`make security-sast`) | — |
| S16 | qv-gate | QV: unit-tests (`make test-unit`) | — |
| S17 | qv-gate | QV: frontend-tests (`make test-frontend` → dashboard suite) | — |
| S18 | qv-gate | QV: integration-tests (`make allure-integration`) | — |
| S19 | qv-browser | Browser end-to-end verification of project switching, tab restoration, and the progress bar | — |
| S20 | self-assess-impl | Self-assessment via `iw-item-analyze` skill (`self_assess = true` in `projects.toml`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: `agent_runtime_options` — backfill `context_window_tokens` rows where NULL for the (cli_tool='pi', model) pairs currently allow-listed in `projects.toml`. NO schema change, data only.
- **Migration notes**: Idempotent `UPDATE … WHERE context_window_tokens IS NULL`. The downgrade body should be `UPDATE … SET context_window_tokens = NULL WHERE model IN (…)` ONLY for the rows the upgrade touched (no row-deletion). This is a data-only migration; `make migration-check`'s `Base.metadata.create_all()` drift check is unaffected.

### API Changes

- **New endpoints**: `GET /api/chat/projects` — returns `{"projects": [{"id": str, "display_name": str}]}`. Reads from the `Project` table with `enabled=true`. Sorted alphabetically by `display_name`. Same auth posture as the rest of `dashboard/routers/chat.py` (no auth in this dashboard).
- **Modified endpoints**: `GET /api/chat/tabs/{tab_id}` — the `session` object gains three optional fields: `used_tokens: int | None`, `window_tokens: int | None`, `context_pct_status: "known" | "unknown_window" | "unknown_runtime"`. The existing `context_pct` field is preserved unchanged for `"known"` cases. Additive only — pre-existing clients that ignore the new fields continue to work.

### Frontend Changes

- **New components**: Project selector `<select id="chat-assistant-project-select">` in `panel.html` (sits in the header next to the title). New inline progress-bar markup in `composer.html` replacing the current `<span id="chat-assistant-context-pct">`.
- **Modified components**: `chat.js` — new `_assistantProjectId()` / `_setAssistantProjectId()` accessors; all `_currentProjectId()` call sites updated. New `_activeTabKey(projectId)` helper for the namespaced localStorage key. `_applyContextPct` rewritten to render the bar element with three visual states.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00091_Feature_Design.md` | Design | This document |
| `F-00091_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00091_S01_API_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/F-00091_S02_Frontend_prompt.md` | Prompt | S02 implementation instructions |
| `prompts/F-00091_S03_Frontend_prompt.md` | Prompt | S03 implementation instructions |
| `prompts/F-00091_S04_Database_prompt.md` | Prompt | S04 implementation instructions |
| `prompts/F-00091_S06_Backend_prompt.md` | Prompt | S06 implementation instructions |
| `prompts/F-00091_S07_Frontend_prompt.md` | Prompt | S07 implementation instructions |
| `prompts/F-00091_S08_Tests_prompt.md` | Prompt | S08 implementation instructions |
| `prompts/F-00091_S09_CodeReview_prompt.md` | Prompt | S09 per-agent review |
| `prompts/F-00091_S10_CodeReview_Final_prompt.md` | Prompt | S10 cross-agent final review |
| `prompts/F-00091_S19_BrowserVerification_prompt.md` | Prompt | S19 browser end-to-end verification |
| `prompts/F-00091_S20_SelfAssess_prompt.md` | Prompt | S20 self-assessment |

## Acceptance Criteria

### AC1: Navigation never changes the Assistant's project

```
Given the user selected "InnoForge" in the Assistant's project dropdown
  And the Assistant is showing two tabs scoped to InnoForge
When the user clicks the sidebar link to "IW AI Core Platform"
  Then the page navigates to /project/iw-ai-core/
  And the Assistant dropdown still reads "InnoForge"
  And the tab strip still shows the InnoForge tabs (not iw-ai-core tabs)
When the user then clicks "System Status" in the sidebar
  Then the page navigates to /system/status
  And the Assistant dropdown still reads "InnoForge"
  And the tab strip still shows the InnoForge tabs (composer is enabled)
```

### AC2: Active tab and history are restored per project

```
Given the user is on project A and tab "Chat 3" is the active tab
  And tab "Chat 3" has a chat history of >=2 user messages
When the user switches the dropdown to project B
  Then the panel re-bootstraps with project B's tabs
When the user switches the dropdown back to project A
  Then tab "Chat 3" is the active tab again
  And the full message history of tab "Chat 3" is rendered
When the user closes the browser window and reopens the dashboard
  Then the Assistant restores project A
  And tab "Chat 3" is the active tab with full history
```

### AC3: Context-usage progress bar is always visible

```
Given an active tab whose model has a known context_window_tokens row
When the panel is open
Then a horizontal progress bar (~60px wide × 5px tall) is visible in the composer row
  And a numeric percentage label is rendered to the right of the bar
  And the bar fill width is proportional to (used_tokens / window_tokens)
  And the color is green below 70%, amber between 70% and 89% inclusive, red at or above 90%
  And hovering shows a tooltip containing "<used_tokens> / <window_tokens> tokens (<pct>%)"
```

### AC4: Unknown context-window state is surfaced, never hidden

```
Given an active tab whose model has NO context_window_tokens row
  (or the runtime is unhealthy and providers cannot be reached)
When the panel is open
Then the progress bar is rendered in the greyed unknown state
  And the numeric label reads "—%"
  And the tooltip explains the missing source
    (e.g. "Context window unknown for pi/<model> — set context_window_tokens in agent_runtime_options")
  And the bar element is NEVER hidden (`display: none` is forbidden for this element while a tab is active)
```

## Boundary Behavior

Every row becomes a mandatory test case.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Assistant opened on first-ever load on a project page (`/project/iw-ai-core/`) | localStorage key `iw-chat-assistant-project` absent | Selector seeds from URL → `iw-ai-core`. Key is then persisted. |
| Assistant opened on first-ever load on a non-project page (`/`, `/system/status`) | localStorage key `iw-chat-assistant-project` absent; no URL project | Selector defaults to the first project returned by `/api/chat/projects` (alphabetical by display_name). |
| Selected project no longer exists | localStorage value points to a project_id no longer in `/api/chat/projects` | Selector resets to the first available project and clears the stale localStorage entry. |
| `/api/chat/projects` returns empty list | DB has no enabled projects | Selector renders disabled with placeholder "No projects available"; composer is disabled; no error toast. |
| Active-tab pointer stale | localStorage `iw-chat-active-tab:<projectId>` references a tab id not in the server response | Pointer is cleared, panel falls back to `_tabs[0]`. |
| `localStorage` unavailable (private-mode quota) | `localStorage.setItem` throws | Selector still works in-memory for the session; no exception bubbles up; key is silently not persisted. |
| Pi tab whose model has no `context_window_tokens` row | `session.context_pct_status = "unknown_window"` | Progress bar rendered greyed, `—%` label, tooltip references `agent_runtime_options`. |
| OpenCode tab when OpenCode runtime is unhealthy | `session.context_pct_status = "unknown_runtime"` | Progress bar rendered greyed, `—%` label, tooltip says "OpenCode runtime unavailable". |
| Stream events during project switch | Active stream on project A's tab #3 while user switches to project B | Per existing semantics (chat.js comments at lines 240-246), the EventSource is left open and Tab #3's `_tabStreaming[id]` remains correct. Project switch MUST NOT abort the stream. |
| New project registered while session is open | DB gains a new project after page load | The selector's project list is refreshed lazily — next time the user opens the dropdown or the panel is re-bootstrapped on page navigation. Not a v1 SSE concern. |

## Invariants

1. After this feature, `chat.js` does NOT call `window.location.pathname` for project derivation (only for the one-time seed when localStorage is unset). The string `_currentProjectId` is gone from `chat.js` entirely.
2. `_assistantProjectId()` returns the SAME value across every read within a single page load until the dropdown is changed.
3. The `chat-assistant-context-pct` element is NEVER `display:none` or `.hidden` while a tab is active. The unknown state is rendered, not hidden.
4. `GET /api/chat/projects` returns ONLY rows with `Project.enabled = true`.
5. The Alembic data migration in S04 is idempotent: running it twice on a clean DB produces the same end state as running it once.
6. The active-tab localStorage key format is exactly `iw-chat-active-tab:<projectId>` (colon, not dash) so existing `iw-chat-active-tab-<browserTabId>` keys are not accidentally reused.
7. `GET /api/chat/tabs/{tab_id}` returns `context_pct_status: "known"` IFF both `used_tokens` and `window_tokens` are non-null integers and `context_pct` is a finite float.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/templates/chat_assistant/panel.html`
- `dashboard/templates/chat_assistant/composer.html`
- `dashboard/static/chat_assistant/chat.js`
- `dashboard/static/chat_assistant/chat.css`
- `dashboard/static/styles.css`
- `dashboard/routers/chat.py`
- `dashboard/routers/projects.py`
- `orch/chat/context_usage.py`
- `orch/db/migrations/versions/**`
- `tests/dashboard/**`
- `tests/integration/**`
- `tests/unit/**`
- `ai-dev/active/F-00091/**`
- `ai-dev/archive/F-00091/**`

## TDD Approach

- **Unit tests** (`tests/unit/`):
  - `test_context_usage_status.py` — `compute_context_pct` + status resolution: known/unknown/unknown_runtime branches return the documented shape; window/used token integers round-trip; missing window yields `unknown_window`; nonexistent provider yields `unknown_runtime`.
  - `test_assistant_project_id_helpers.py` (JS-adjacent, via the dashboard test harness if it exists; otherwise document the helper contract and exercise it through dashboard integration tests).
- **Dashboard tests** (`tests/dashboard/`):
  - `test_api_chat_projects.py` — `GET /api/chat/projects` returns only enabled projects, sorted alphabetically; empty list when DB has none; 200 status; response shape matches the contract.
  - `test_chat_tabs_status_payload.py` — `/api/chat/tabs/{id}` returns the new `context_pct_status`, `used_tokens`, `window_tokens` fields; verifies all three branches (known / unknown_window / unknown_runtime).
- **Integration tests** (`tests/integration/`):
  - `test_chat_panel_project_decoupling.py` — fixture-loaded chat_tabs across two projects; assert that hitting the tabs API for one project does not affect the other; assert the new endpoint shape end-to-end against a real testcontainer DB.
  - `test_alembic_chat_context_backfill.py` — apply only the new migration onto a fresh testcontainer with synthetic `agent_runtime_options` rows; assert that NULL rows for the targeted Pi models are filled while pre-existing non-NULL rows are untouched; assert downgrade restores the pre-upgrade snapshot.
- **Browser verification** (S19): see the V1..V5 spec in the BrowserVerification prompt.
- **Edge cases**: every row in the Boundary Behavior table is covered by at least one of the above tests.

## Notes

- **Why no SPA refactor**: the dashboard's full-page-reload model has worked for every other panel (sidebar, footer, etc.) — the right fix here is to make the AI Assistant *resilient* to those reloads, not to migrate the whole app to client-side routing.
- **Why localStorage vs sessionStorage**: the user explicitly chose "shared across all browser windows" (see conversation 2026-05-26). localStorage gives that behaviour; sessionStorage would be per-tab.
- **Why backfill rather than a fallback heuristic**: a fallback (e.g., "assume 200k tokens for unknown Pi models") silently lies to the user when an unfamiliar model is added. An explicit unknown state with an actionable tooltip is harder to misread, and the backfill covers the 90% case.
- **Why no `arch-check` worry**: this work touches dashboard + orch/chat layers only and adds no new module boundaries.
- **Why one consolidated CodeReview** (S09): all impl steps share the same code locality (`dashboard/static/chat_assistant/**` + `dashboard/routers/chat.py` + a tiny migration). Per-step reviewers would re-read the same files redundantly.
- **Pre-investigation evidence**: three "before" screenshots are checked into `evidences/pre/` showing the current URL-driven swap, the missing context-pct, and the empty Assistant state on `/system/status`.
