# F-00086: Multi-tab AI Assistant on OpenCode

**Type**: Feature
**Priority**: Medium
**Created**: 2026-05-19
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This Feature ships one Alembic migration (DDL: `chat_tabs` table + indexes), refactors `orch/chat/` into a runtime-agnostic shape, rewrites `dashboard/routers/chat.py` to a tab-scoped surface, and adds a tab strip to the AI Assistant panel. No new Docker usage. Testcontainer fixtures in `tests/integration/conftest.py` remain the only allowed exception.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. S01 adds **one** Alembic revision creating `chat_tabs` (a new table — no FK changes to existing tables). S02 (`qv-gate migration-check`) enforces `alembic upgrade base→head + create_all parity + downgrade→upgrade round-trip` against a fresh testcontainer before downstream agents inherit the schema. The daemon applies the revision via the normal pre-merge dry-run + post-merge apply pipeline.

## Description

Refactor the AI Assistant chat panel to support multiple independent, server-persisted tabs. Each tab owns its own OpenCode session, its own model selection, and its own SSE stream. Lays a runtime-agnostic abstraction layer (`ChatRuntime` ABC) so the follow-up Feature (F-B) can plug Pi in as a second runtime without re-touching the JS, RelayManager, or tab CRUD. This Feature is OpenCode-only — the runtime dropdown exists in the create-tab modal but offers only "OpenCode".

## Project Context

Read the project's `CLAUDE.md` for the orchestration architecture, hard rules (testcontainers only for live DB, no `importlib.reload(orch.config)`, no `docker compose up` against the orch DB, FTS DDL hook, `DaemonEvent.event_metadata`, Jinja2 `%`-style `|format` filter calls), and the dashboard build conventions. Read `dashboard/CLAUDE.md` for routing/template/htmx patterns and the **clipboard helper rule** (`window.iwClipboard.copy(...)`, never `navigator.clipboard.writeText`). Read `tests/CLAUDE.md` for fixture rules and the FTS-trigger requirement when calling `Base.metadata.create_all()`. The chat plumbing was introduced by F-00083 (merged) — see `orch/chat/`, `dashboard/routers/chat.py`, `dashboard/templates/chat_assistant/`, `dashboard/static/chat_assistant/`.

## Scope

### In Scope

- **New `chat_tabs` table** (Alembic migration) with: `id` (UUID PK), `title` (text, user-editable, default derived from creation context), `runtime` (text, allowlist enforced in code: currently `{"opencode"}`; column shape supports `"pi"` later), `model` (text), `project_id` (text, FK to `projects.id` ON DELETE CASCADE), `opencode_session_id` (text, nullable), `status` (text, allowlist `{"active","closed"}`), `created_at`, `updated_at`, `last_active_at`, `closed_at` (timestamp, nullable). Indexes: `(status, last_active_at DESC)` and `(project_id, status)`.
- **Runtime-agnostic refactor of `orch/chat/`**:
  - New `orch/chat/runtime_base.py` — `ChatRuntime` ABC with async methods: `create_session(model, agent, directory) -> str`, `prompt(session_id, text, model=None, system=None) -> None`, `abort(session_id) -> None`, `get_messages(session_id) -> list`, `get_session(session_id) -> dict`, `list_sessions() -> list`, `reply_permission(session_id, request_id, response, remember=False) -> None`, `set_model(session_id, model) -> None`, `close_session(session_id) -> None`, `subscribe(session_id, last_event_id=None) -> AsyncIterator[dict]`, `get_config() -> dict`, `get_providers() -> dict`, `health() -> bool`.
  - Move existing OpenCode plumbing into `orch/chat/opencode/` subpackage: `opencode_runtime.py` → `orch/chat/opencode/runtime.py`, `opencode_client.py` → `orch/chat/opencode/client.py`, `relay_manager.py` → `orch/chat/opencode/relay_manager.py`, `filters.py` → `orch/chat/opencode/filters.py`. The OpenCode runtime implements `ChatRuntime`.
  - **Mechanical move only** — no behaviour change to OpenCode plumbing in S03; behaviour-preserving wrappers if any caller depended on the old module paths (none currently exist outside this package, verified by `git grep`).
- **RelayManager rekeyed by `tab_id`** — `relay_manager.get_or_create_relay(tab_id)` becomes the public entry; internally it resolves the tab → opencode_session and forwards events. Event payloads gain a `"tab_id"` field (additive). Ring-buffer semantics preserved exactly (same 256-entry default, same `Last-Event-ID` replay).
- **Tab repository + service** (`orch/chat/tab_service.py`): `create_tab`, `list_tabs(include_closed=False)`, `get_tab(tab_id)`, `update_tab(tab_id, title=..., model=...)`, `close_tab(tab_id)` (soft delete: status='closed', closed_at=now()), `reopen_tab(tab_id)`, `recent_closed_tabs(limit=10)`. **Soft cap of 10 active tabs** enforced in `create_tab`: when count exceeds 10, the new tab is created but a warning header (`X-Tab-Soft-Cap-Exceeded: true`) is added to the response (UI surfaces the warning; no rejection).
- **Default-tab seeding on first load after upgrade** (`orch/chat/migration_helpers.py:bootstrap_default_tab(project_id)`): when **no `chat_tabs` row exists for `project_id` (active OR closed)** AND a discoverable prior OpenCode session exists (any session listed by `runtime.list_sessions()` whose CWD matches the project repo_root), create one tab seeded with that session_id, title `"Default"`, model from the cached `/api/chat/config` `default_model`. Gating on the "no rows at all" condition (rather than "no active rows") is deliberate: once a user has had any tab in the project — even one they later closed — bootstrap MUST NOT re-fire and resurrect an arbitrary prior OpenCode session, because that would override the user's intentional close-all action. Idempotent: re-invocation is a no-op once any row (active OR closed) exists for the project. Race-safety under concurrent first-load is provided by the `uq_chat_tabs_default_per_project` partial unique index (see §Database Changes).
- **Tab-scoped API** (`dashboard/routers/chat.py` rewritten):
  - `POST /api/chat/tabs` — body: `{project_id, runtime?, model?, title?, agent?}` → `{tab}`. Sets soft-cap header when applicable.
  - `GET /api/chat/tabs?project_id=X&include_closed=false` → `{tabs: [...]}` ordered by `last_active_at DESC`.
  - `GET /api/chat/tabs/{tab_id}` → `{tab, session, messages}`.
  - `PATCH /api/chat/tabs/{tab_id}` — body: `{title?, model?}` → `{tab}`.
  - `DELETE /api/chat/tabs/{tab_id}` → 204 (soft-delete; sets `status='closed'`, `closed_at=now()`).
  - `POST /api/chat/tabs/{tab_id}/reopen` → `{tab}` (un-soft-delete).
  - `GET /api/chat/tabs/{tab_id}/stream` — SSE relay (per-tab); honors `Last-Event-ID`.
  - `POST /api/chat/tabs/{tab_id}/prompt` — body: `{text, model?, context?}` → 204.
  - `POST /api/chat/tabs/{tab_id}/abort` → 204.
  - `POST /api/chat/tabs/{tab_id}/permissions/{rid}` — body: `{response, remember?}` → 204.
  - `GET /api/chat/config?project_id=X&runtime=opencode` — same response shape as today (models, default_model, default_agent, project_directory); `runtime` query param defaults to `"opencode"` and is reserved for F-B.
  - `GET /api/chat/skills` — unchanged.
  - `GET /api/chat/tabs/recent-closed?project_id=X&limit=10` → `{tabs: [...]}` ordered by `closed_at DESC`.
  - **Old `/api/chat/sessions/*` endpoints removed in same release.** Backwards-compat is handled by the default-tab seeding on first load, not by keeping deprecated endpoints alive.
- **Frontend** (`dashboard/templates/chat_assistant/panel.html`, `dashboard/static/chat_assistant/chat.js`, `dashboard/static/chat_assistant/chat.css`):
  - Tab strip at the top of the panel, horizontally scrollable when overflow.
  - "+" button at the right end of the strip opens a modal with fields: project (pre-filled from current view; locked when launched from a per-project page), runtime (dropdown, only "OpenCode" populated), model (dropdown filtered by runtime — calls `GET /api/chat/config?runtime=...`), title (optional; default `"New chat"`).
  - Per-tab controls: click-to-activate, double-click to rename, right-click context menu with `Rename`, `Duplicate` (clones runtime+model+title; new opencode_session), `Close`.
  - Soft-cap warning banner: when `X-Tab-Soft-Cap-Exceeded: true` arrives, render a dismissible info banner above the tab strip ("10+ tabs open — consider closing inactive tabs"). Banner does not block creation.
  - "Recent closed tabs" menu accessible from a button at the right of the tab strip; opens dropdown listing last 10 closed tabs with `Reopen` action.
  - Each active tab maintains its own `EventSource` to `/api/chat/tabs/{tab_id}/stream`. Inactive tabs do NOT keep their SSE open (saves browser connections); reactivating opens a fresh subscription using the tab's stored `last_event_id` for ring-buffer replay.
  - Per-tab model dropdown above the composer (read-only displays current model; click to change via `PATCH /api/chat/tabs/{tab_id}`).
- **Test coverage**:
  - Unit: `tests/unit/chat/test_runtime_base.py` (ABC contract), `tests/unit/chat/test_tab_service.py` (CRUD + soft-cap + soft-delete + reopen + bootstrap), `tests/unit/chat/test_opencode_runtime_abc_compliance.py` (existing OpenCode runtime implements every ABC method).
  - Integration: `tests/integration/test_chat_tabs_api.py` (full tab CRUD via TestClient), `tests/integration/test_chat_tabs_multi_session_independence.py` (two tabs with different models stream independently; aborting one leaves the other intact), `tests/integration/test_chat_tabs_reload_persistence.py` (tab list survives across TestClient client recreations), `tests/integration/test_chat_tabs_bootstrap_default.py` (default-tab seeding on empty state).
  - Existing chat tests (`tests/dashboard/test_chat_*`, `tests/integration/test_chat_endpoint_*`) adapted to the tab-scoped surface; no test is deleted, every test continues to assert equivalent behaviour against the new endpoints.

### Out of Scope

- **Pi runtime in chat** — `orch/chat/pi/`, `pi_rpc_client`, `pi_jsonl_reader`, the Pi `.pi/extensions/iw-chat-approvals/` extension. Deferred to F-B (tracked separately).
- **Per-tab runtime dropdown actually offering Pi** — the dropdown is wired but contains only `"OpenCode"`. F-B adds `"Pi"`.
- **Multi-runtime event normalization layer** — the `ChatRuntime` ABC lands here; the OpenCode runtime implements it. The event-shape mapping table for Pi → normalized events is F-B's deliverable.
- **Cron cleanup of old closed tabs** — closed tabs accumulate indefinitely in this Feature; a future minor item adds a retention sweep.
- **Multi-user / per-user ownership** — single-user system today; `chat_tabs` has no `user_id` column. If/when multi-user lands, a column add migration covers it.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `database-impl` | Alembic revision creating `chat_tabs` table + two indexes; no FK changes to existing tables | — |
| S02 | `qv-gate` (`migration-check`) | `make migration-check` (upgrade head + create_all parity + downgrade→upgrade round-trip against fresh testcontainer) | — (after S01) |
| S03 | `backend-impl` | New `orch/chat/runtime_base.py` (ChatRuntime ABC); move OpenCode plumbing into `orch/chat/opencode/` subpackage (mechanical rename — no behaviour change); rekey `RelayManager` by `tab_id`; add tab event payload field; new `orch/chat/tab_service.py` (CRUD + 10-tab soft cap + soft delete + reopen + bootstrap-default); new `orch/chat/migration_helpers.py` (default-tab seed) | — (after S02) |
| S04 | `code-review-impl` | Per-agent review of S03 (ABC contract, package move correctness, soft-cap semantics, soft-delete semantics, bootstrap idempotency, RelayManager tab_id rekey behaviour) | — (after S03) |
| S05 | `code-review-fix-impl` | Apply CRITICAL/HIGH/MEDIUM(fixable) findings from S04 | — (after S04) |
| S06 | `api-impl` | Rewrite `dashboard/routers/chat.py` to tab-scoped surface (11 endpoints listed in §API Changes); add `X-Tab-Soft-Cap-Exceeded` response header; remove old `/api/chat/sessions/*` endpoints in same release; preserve SSE keep-alive semantics and `Last-Event-ID` replay | S07 |
| S07 | `frontend-impl` | Tab strip + create-tab modal + per-tab controls + per-tab `EventSource` lifecycle + soft-cap warning banner + recent-closed-tabs dropdown + per-tab model dropdown in `dashboard/templates/chat_assistant/panel.html` and `dashboard/static/chat_assistant/chat.js` + minimal CSS in `chat.css` (`make css` only if Tailwind classes are added — plain CSS otherwise per CLAUDE.md mitigation rule) | S06 |
| S08 | `tests-impl` | Unit tests (3 files) + integration tests (4 files) + adapt existing chat tests (`tests/dashboard/test_chat_*`, `tests/integration/test_chat_endpoint_*`) to tab-scoped surface — no deletions, equivalent assertions against new endpoints | — (after S06 + S07) |
| S09 | `code-review-final-impl` | Cross-agent global review: DB↔backend↔API↔frontend↔tests integration boundaries; ABC contract honoured; event payload `tab_id` field present at every emit site; default-tab bootstrap fires exactly once per project on first load | — |
| S10 | `code-review-fix-final-impl` | Apply CRITICAL/HIGH/MEDIUM(fixable) findings from S09 | — |
| S11 | `qv-gate` (`lint`) | `make lint` | — |
| S12 | `qv-gate` (`format`) | `make format-check` | — |
| S13 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S14 | `qv-gate` (`unit-tests`) | `make test-unit` | — |
| S15 | `qv-gate` (`integration-tests`) | `make test-integration` (timeout 1800s) | — |
| S16 | `qv-browser` | Browser verification: open 2 tabs with different models, send a prompt in each, abort one, reload page and verify both persist, close one and reopen via recent-closed menu | — |
| S17 | `self-assess-impl` | Self-assessment via `iw-item-analyze` skill (project `iw-ai-core` has `self_assess = true`) | — |

Agent slugs verified against `skills/iw-workflow/SKILL.md`'s canonical agent table and `executor/step_executor_lib.sh`. `self-assess-impl` is the last step deliberately — it must see the full retry/fix-cycle history that QV gates produce.

### Database Changes

- **New tables**: `chat_tabs`
- **Modified tables**: None
- **Migration notes**: Single Alembic revision via `alembic revision --autogenerate -m "f_00086_chat_tabs"` then hand-tune to: (a) UUID PK via `server_default=text("gen_random_uuid()")` (project uses `pgcrypto` per `orch/db/models.py`; if not enabled in test/prod DBs, fall back to client-side `uuid.uuid4()` default — verify by grepping `gen_random_uuid` in `orch/db/migrations/versions/` first), (b) `runtime` and `status` as plain `Text` (no PostgreSQL ENUM — allowlist enforced in `tab_service.py`, matching CR-00062's pattern for `cli_tool`), (c) `(status, last_active_at DESC)` and `(project_id, status)` indexes via `op.create_index()` with explicit names `ix_chat_tabs_status_last_active` and `ix_chat_tabs_project_status`, (d) `project_id` FK with `ON DELETE CASCADE` (a deleted project takes its tabs with it). `downgrade()` drops both indexes then the table. S02 (`make migration-check`) validates upgrade/downgrade round-trip.

### API Changes

- **New endpoints** (`dashboard/routers/chat.py`):
  - `POST /api/chat/tabs`
  - `GET /api/chat/tabs?project_id=X&include_closed=false`
  - `GET /api/chat/tabs/{tab_id}`
  - `PATCH /api/chat/tabs/{tab_id}`
  - `DELETE /api/chat/tabs/{tab_id}`
  - `POST /api/chat/tabs/{tab_id}/reopen`
  - `GET /api/chat/tabs/{tab_id}/stream` (SSE)
  - `POST /api/chat/tabs/{tab_id}/prompt`
  - `POST /api/chat/tabs/{tab_id}/abort`
  - `POST /api/chat/tabs/{tab_id}/permissions/{rid}`
  - `GET /api/chat/tabs/recent-closed?project_id=X&limit=10`
- **Modified endpoints**:
  - `GET /api/chat/config` — now accepts `runtime` query param (default `"opencode"`); response shape unchanged.
- **Removed endpoints**:
  - `POST /api/chat/sessions`, `GET /api/chat/sessions`, `GET /api/chat/sessions/{sid}`, `GET /api/chat/sessions/{sid}/stream`, `POST /api/chat/sessions/{sid}/prompt`, `POST /api/chat/sessions/{sid}/abort`, `POST /api/chat/sessions/{sid}/permissions/{rid}` — replaced by the tab-scoped surface. `GET /api/chat/skills` is retained unchanged.

### Frontend Changes

- **New components**:
  - Tab strip (`templates/chat_assistant/tab_strip.html`)
  - Create-tab modal (`templates/chat_assistant/create_tab_modal.html`)
  - Recent-closed-tabs dropdown (`templates/chat_assistant/closed_tabs_dropdown.html`)
  - Soft-cap warning banner (rendered inline in `panel.html`; no separate template)
- **Modified components**:
  - `templates/chat_assistant/panel.html` — embeds tab strip, modal, dropdown; existing composer/message/approval templates rendered per-active-tab
  - `static/chat_assistant/chat.js` — tab lifecycle, per-tab `EventSource` mount/unmount, per-tab model dropdown, soft-cap warning handling
  - `static/chat_assistant/chat.css` — tab strip styling (plain CSS appended directly per the CLAUDE.md mitigation rule when `make css` is unavailable)
- **Removed components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/F-00086/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00086_Feature_Design.md` | Design | This document |
| `F-00086_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00086_S01_Database_prompt.md` | Prompt | S01 — `database-impl` |
| `prompts/F-00086_S03_Backend_prompt.md` | Prompt | S03 — `backend-impl` |
| `prompts/F-00086_S04_CodeReview_prompt.md` | Prompt | S04 — `code-review-impl` |
| `prompts/F-00086_S05_CodeReviewFix_prompt.md` | Prompt | S05 — `code-review-fix-impl` |
| `prompts/F-00086_S06_API_prompt.md` | Prompt | S06 — `api-impl` |
| `prompts/F-00086_S07_Frontend_prompt.md` | Prompt | S07 — `frontend-impl` |
| `prompts/F-00086_S08_Tests_prompt.md` | Prompt | S08 — `tests-impl` |
| `prompts/F-00086_S09_CodeReview_Final_prompt.md` | Prompt | S09 — `code-review-final-impl` |
| `prompts/F-00086_S10_CodeReviewFix_Final_prompt.md` | Prompt | S10 — `code-review-fix-final-impl` |
| `prompts/F-00086_S16_BrowserVerification_prompt.md` | Prompt | S16 — `qv-browser` |
| `prompts/F-00086_S17_SelfAssess_prompt.md` | Prompt | S17 — `self-assess-impl` |

(S02, S11, S12, S13, S14, S15 are QV gates — command-only, no prompt files.)

Reports are created during execution in `ai-dev/active/F-00086/reports/`.

## Acceptance Criteria

### AC1: Two tabs run independently with different models

```
Given the dashboard is open at /project/iw-ai-core/
And the AI Assistant panel is expanded
When the user clicks "+" and creates Tab A with model "anthropic/claude-sonnet-4-7"
And the user clicks "+" and creates Tab B with model "openai/gpt-5.3-codex"
And the user sends prompt "P_A" in Tab A
And then sends prompt "P_B" in Tab B
Then Tab A's stream shows tokens from "anthropic/claude-sonnet-4-7" answering P_A
And Tab B's stream shows tokens from "openai/gpt-5.3-codex" answering P_B
And neither tab's stream contains events tagged with the other tab's tab_id
And clicking Tab A's "Abort" button aborts only Tab A (Tab B continues streaming)
```

### AC2: Tabs persist across page reload

```
Given two tabs exist in the dashboard (Tab A and Tab B, both with messages)
When the user refreshes the browser (full page reload)
Then both tabs reappear in the tab strip in their original last_active_at order
And clicking each tab re-mounts its EventSource using the persisted opencode_session_id
And the full message history is restored from /api/chat/tabs/{tab_id}
And no message is lost in the reload (every assistant message visible before reload is visible after)
```

### AC3: Per-tab model selection

```
Given Tab A is active with model "anthropic/claude-sonnet-4-7"
When the user opens the per-tab model dropdown above the composer
And selects "openai/gpt-5.3-codex"
Then PATCH /api/chat/tabs/{tab_a_id} is called with body {"model":"openai/gpt-5.3-codex"}
And subsequent prompts in Tab A use the new model
And Tab B's model is unchanged
And Tab A's tab_strip label updates to show the new model (or model short-name) without page reload
```

### AC4: Runtime abstraction landed without behaviour change

```
Given the ChatRuntime ABC is defined and OpenCode runtime implements it
When the full test suite runs (make test-unit + make test-integration)
Then every test in tests/dashboard/test_chat_*.py and tests/integration/test_chat_endpoint_*.py passes
And the OpenCode runtime's public method signatures match the ABC method-by-method (verified by tests/unit/chat/test_opencode_runtime_abc_compliance.py)
And no test that previously exercised /api/chat/sessions/* asserts against the old paths — every such test now asserts against the equivalent /api/chat/tabs/* path
```

### AC5: Backwards-compat — default tab seeded from prior session

```
Given the migration has been applied to a database that has no chat_tabs rows
And the live OpenCode runtime reports a prior session whose CWD matches the iw-ai-core repo root
When the user loads /project/iw-ai-core/ for the first time after upgrade
Then GET /api/chat/tabs?project_id=iw-ai-core returns exactly one tab
And that tab's opencode_session_id equals the prior session's id
And the tab's title is "Default"
And the tab's model equals the cached /api/chat/config default_model
And re-loading the page does NOT create a second default tab (bootstrap is idempotent)
```

### AC6: Runtime dropdown stub present; Pi not selectable

```
Given the create-tab modal is open
When the user clicks the "Runtime" dropdown
Then the dropdown contains exactly one option: "OpenCode"
And no "Pi" option appears
And submitting the form without changing the runtime succeeds and creates an OpenCode tab
And the chat_tabs row has runtime="opencode"
And the API endpoint POST /api/chat/tabs rejects body {"runtime":"pi"} with HTTP 400 and error "runtime 'pi' not in allowlist {'opencode'}"
```

### AC7: Soft cap of 10 tabs warns but does not reject

```
Given 10 active tabs exist for project iw-ai-core
When the user creates an 11th tab via POST /api/chat/tabs
Then the response status is 201
And the response includes header "X-Tab-Soft-Cap-Exceeded: true"
And the tab is persisted in chat_tabs
And the dashboard UI renders a dismissible info banner above the tab strip
And the banner text mentions "10+ tabs open"
And creating a 12th tab also succeeds and also returns the header
```

### AC8: Soft delete + reopen via recent-closed menu

```
Given an active tab exists with id T1 and a message history
When the user closes T1 via DELETE /api/chat/tabs/T1
Then the chat_tabs row for T1 has status='closed' and closed_at IS NOT NULL
And T1 no longer appears in GET /api/chat/tabs (default include_closed=false)
And T1 appears in GET /api/chat/tabs/recent-closed?project_id=iw-ai-core
And POST /api/chat/tabs/T1/reopen returns 200 with status='active' and closed_at=NULL
And T1 reappears in GET /api/chat/tabs
And the full message history is intact (opencode_session_id was never dropped)
```

### AC9: Bootstrap does not resurrect after user closes every tab

```
Given a project has exactly one chat_tabs row and its status='closed'
And the live OpenCode runtime reports a prior session whose CWD matches the project repo root
When the user loads /project/<project_id>/ and the dashboard calls GET /api/chat/tabs?project_id=<id>
Then the response is an empty list (include_closed=false default)
And the chat_tabs table still has exactly one row for the project (the original closed one)
And no new "Default" tab is created
And the UI renders the empty-state ("No chats yet — click + to create one")
```

## Boundary Behavior

Every row becomes a mandatory test case.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| No rows for project, no prior OpenCode session | `chat_tabs` has zero rows for `project_id` (active AND closed), `runtime.list_sessions()` empty for project | Bootstrap creates no tab; UI renders empty-state ("No chats yet — click + to create one") |
| No rows for project, prior OpenCode session present | `chat_tabs` has zero rows for `project_id` (active AND closed), one matching session | Bootstrap creates exactly one tab seeded with that session |
| Bootstrap called twice concurrently | Two requests racing on a project with zero `chat_tabs` rows | Exactly one default tab created. Race-safety enforced by the `uq_chat_tabs_default_per_project` partial unique index (`UNIQUE (project_id) WHERE title='Default' AND status='active'`); the loser of the race catches `IntegrityError` and re-fetches the winner's row |
| Project has only closed tabs (user closed all) | `chat_tabs` has ≥1 row for `project_id` but all `status='closed'` | Bootstrap does NOT fire (gate is "zero rows", not "zero active rows"). UI renders empty-state; user must create a new tab via "+" |
| POST /api/chat/tabs with runtime='pi' | Allowlist `{"opencode"}` | HTTP 400 with `{"error":"runtime 'pi' not in allowlist {'opencode'}"}` |
| POST /api/chat/tabs with unknown model | Model not in `/api/chat/config?runtime=opencode` `models` list | HTTP 400 with `{"error":"model '<name>' not available for runtime 'opencode'"}` |
| GET /api/chat/tabs/{tab_id} for closed tab | Tab status='closed' | Returns the tab object with status='closed' and full message history (the tab still exists, just hidden by default list) |
| DELETE /api/chat/tabs/{tab_id} when already closed | Idempotent | HTTP 204; no-op; `closed_at` unchanged |
| POST /api/chat/tabs/{tab_id}/reopen for never-closed tab | Tab status='active' | HTTP 200; tab returned unchanged |
| PATCH /api/chat/tabs/{tab_id} with empty body | `{}` | HTTP 200; tab returned unchanged; `updated_at` not bumped |
| SSE reconnect with stale Last-Event-ID | Event id beyond ring-buffer head | Resync from current head (existing relay behaviour preserved); no error |
| OpenCode runtime unhealthy at tab creation | `runtime.health()` returns False | HTTP 503 with body `{"error":"OpenCode runtime unavailable"}`; tab is NOT created |
| Project deleted while tabs exist | Cascade FK fires | All tabs for that project removed; orphaned OpenCode sessions left intact (not the FK's responsibility) |
| 11th active tab created | Existing count=10 | HTTP 201 + `X-Tab-Soft-Cap-Exceeded: true`; tab persisted |
| Close all 10 of 10 active tabs | Bulk closure | All move to status='closed'; GET tabs returns []; UI renders empty-state; recent-closed lists 10 |
| Migration applied to DB with `pgcrypto` extension missing | Fresh container, no extension | If S01 used `gen_random_uuid()` server default and extension is missing, migration fails at upgrade — S02 (`make migration-check`) catches this. Resolution: use Python `uuid.uuid4()` default instead, OR `op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")` at top of `upgrade()` (verify pattern by inspecting prior migrations) |

## Invariants

Conditions that **must hold true** after implementation. Each maps to a test.

1. **ABC method parity** — `inspect.getmembers(OpencodeRuntime, predicate=inspect.iscoroutinefunction)` set equals the abstract method set of `ChatRuntime`. (`tests/unit/chat/test_opencode_runtime_abc_compliance.py`)
2. **Tab_id in every relayed event** — every event emitted by `RelayManager.subscribe(tab_id)` has a top-level `"tab_id"` field whose value equals the subscriber's tab_id. (`tests/integration/test_chat_tabs_multi_session_independence.py`)
3. **Runtime allowlist enforcement** — `POST /api/chat/tabs` with `runtime` not in `{"opencode"}` returns HTTP 400; the `chat_tabs` row is NOT created. (`tests/integration/test_chat_tabs_api.py`)
4. **Soft-cap header iff count > 10** — response header `X-Tab-Soft-Cap-Exceeded` is `"true"` when the active-tab count post-insert is > 10, absent otherwise. (`tests/integration/test_chat_tabs_api.py`)
5. **Soft-delete preserves session id** — `close_tab(T)` does NOT clear `opencode_session_id`; `reopen_tab(T)` restores `status='active'` with the original session reachable. (`tests/unit/chat/test_tab_service.py`)
6. **Bootstrap idempotency and intent-preservation** — calling `bootstrap_default_tab(project_id)` twice in a row, including racing concurrent calls, results in exactly one tab. AND bootstrap does NOT fire when `chat_tabs` already has ≥1 row for the project, even if every row is `status='closed'` (i.e., once a user has had any tab in this project — even one they later closed — bootstrap is permanently disabled for that project; the user must create new tabs explicitly). (`tests/unit/chat/test_tab_service.py` and `tests/integration/test_chat_tabs_bootstrap_default.py`)
7. **No old endpoint paths** — `git grep -E "/api/chat/sessions/[^t]"` against the final code returns zero matches outside test fixtures that explicitly assert the removal. (`tests/dashboard/test_chat_router.py`)
8. **Empty-body PATCH does not bump updated_at** — `PATCH /api/chat/tabs/{tab_id}` with `{}` returns the tab with its prior `updated_at`. (`tests/integration/test_chat_tabs_api.py`)

## Dependencies

- **Depends on**: F-00083 (current single-session AI Assistant chat on OpenCode, already merged). Established the OpenCode runtime, client, relay manager, and chat panel that this Feature refactors.
- **Blocks**: F-B (Pi runtime + per-tab runtime selection in chat — to be filed after this Feature's design is approved).

## Impacted Paths

- `orch/chat/__init__.py`
- `orch/chat/runtime_base.py`
- `orch/chat/opencode/**`
- `orch/chat/tab_service.py`
- `orch/chat/migration_helpers.py`
- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `dashboard/routers/chat.py`
- `dashboard/app.py`
- `dashboard/templates/chat_assistant/**`
- `dashboard/static/chat_assistant/**`
- `tests/unit/chat/**`
- `tests/dashboard/test_chat_*.py`
- `tests/integration/test_chat_*.py`
- `ai-dev/active/F-00086/**`

## TDD Approach

- **RED-first evidence** — S03 (Backend) and S06 (API) must capture targeted failing-test output before implementation:
  - S03: `tests/unit/chat/test_tab_service.py::test_soft_cap_warning_header_when_count_exceeds_ten` — calls `tab_service.create_tab(...)` 11 times and asserts the 11th invocation flags the warning. RED run fails with `AttributeError: module has no attribute 'tab_service'` or `ImportError`.
  - S06: `tests/integration/test_chat_tabs_api.py::test_post_tabs_rejects_unknown_runtime` — POST `/api/chat/tabs` with `{"runtime":"pi"}` and asserts HTTP 400. RED run fails with `assert 404 == 400` (endpoint does not exist yet).
- **Unit tests** (S08, plus targeted ones in S03/S06):
  - `tests/unit/chat/test_runtime_base.py` — ABC instantiation fails; concrete subclass must override every abstract method.
  - `tests/unit/chat/test_tab_service.py` — `create_tab` happy path + allowlist rejection + soft-cap header + 11+ tabs all persist; `close_tab` soft-deletes; `reopen_tab` restores; `bootstrap_default_tab` idempotency under concurrent calls (use threading or `asyncio.gather`).
  - `tests/unit/chat/test_opencode_runtime_abc_compliance.py` — `OpencodeRuntime` declares every coroutine method named on `ChatRuntime` with compatible signatures.
- **Integration tests** (S08):
  - `tests/integration/test_chat_tabs_api.py` — full CRUD via TestClient; allowlist rejection; soft-cap header; recent-closed listing; PATCH with empty body.
  - `tests/integration/test_chat_tabs_multi_session_independence.py` — create two tabs with two different models, drive prompts on both, assert event streams are tagged with the correct tab_id, abort one and verify the other continues.
  - `tests/integration/test_chat_tabs_reload_persistence.py` — create tabs, dispose TestClient, recreate, GET /api/chat/tabs returns the same tabs in `last_active_at DESC` order.
  - `tests/integration/test_chat_tabs_bootstrap_default.py` — fresh DB + simulated prior session → first GET creates exactly one default tab; second GET creates none.
- **Adapted existing tests** (S08): `tests/dashboard/test_chat_router.py`, `tests/integration/test_chat_endpoint_session_lifecycle.py`, `tests/integration/test_chat_endpoint_permission_flow.py`, `tests/integration/test_chat_endpoint_reconnect.py`, `tests/dashboard/test_chat_panel_*.py`, `tests/integration/test_chat_config_allowlist_intersection.py`. Each test's path assertions move from `/api/chat/sessions/*` to `/api/chat/tabs/*`; behavioural assertions unchanged.

## Notes

- **No Pi work in this Feature.** The runtime dropdown is wired but contains only `"OpenCode"`. F-B will add `"Pi"`, ship the Pi RPC client + JSONL reader + approval extension, and extend the event-normalization layer. The ABC contract is deliberately shaped to accommodate Pi without re-touching the JS or the tab_service.
- **Why an ABC and not a Protocol?** Two reasons: (a) the ABC's `@abstractmethod` decorator fails subclass instantiation if a method is missing (catches drift at construction, not runtime); (b) `mypy` strict mode flags missing implementations even when callers go through a base-class type. A `Protocol` would also work but has weaker enforcement.
- **CSS strategy.** Tab strip styling appended directly to `dashboard/static/styles.css` per the CLAUDE.md mitigation rule when `make css` is unavailable in worktrees (I-00067). If `make css` is healthy, S07 may use Tailwind utility classes.
- **Relay event payload shape.** Adding `"tab_id"` to every emitted event is additive — existing JS consumers that don't reference `tab_id` are unaffected. The frontend uses `tab_id` to route events to the correct tab's view, replacing today's implicit "panel == session" coupling.
- **Recent-closed retention.** No cleanup in this Feature. If the closed-tab list grows unwieldy in practice, a minor follow-up adds a daily sweep keeping the most recent 100 per project — out of scope here.
- **`browser_verification = true`** — Frontend changes are user-visible. S16 captures pre-state evidence already saved at `evidences/pre/F-00086-before-single-session-chat.png`; S16 captures post-state under `evidences/post/`.
- **Self-assess required.** Project `iw-ai-core` has `self_assess = true` in `projects.toml`; S17 (`self-assess-impl`) is injected as the LAST step (after S16 qv-browser) so it sees the full retry/fix-cycle history.
- **No projects.toml changes.** The chat panel is configured at runtime via the existing `ai_assistant` model allowlist (per-project) — no new keys needed for this Feature.
