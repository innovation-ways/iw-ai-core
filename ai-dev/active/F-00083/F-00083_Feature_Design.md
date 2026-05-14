# F-00083: Dashboard AI Assistant — OpenCode-backed chat panel (v1)

**Type**: Feature
**Priority**: High
**Created**: 2026-05-14
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. **This feature adds NO migrations** — OpenCode persists session state on disk; we hold per-session ring buffers in memory only.)

## Description

A persistent left-sidebar chat panel reachable from every dashboard page, backed by a managed `opencode serve` subprocess. Per-tab independent sessions, model selector, skills/commands tray, `/` autocomplete, context % indicator, removable "Currently viewing X" chip, and approval modal for OpenCode's existing `permission.asked` events. The runtime's `permission` block in `.opencode/config.json` is the entire v1 safeguard layer — no new policy code (per R-00074 §1). Toggle with **Ctrl+/**.

This feature **coexists** with the existing right-side Code-view Q&A chat (`dashboard/templates/chat/`, backed by `orch/rag/qa.py`). They answer different questions: Code Q&A is a RAG-backed read-only chat about code understanding; the Dashboard AI Assistant is a coding agent with tools, skills, side effects, and approvals. No edits to the existing `chat/` directory are made by this work item.

## Project Context

Read the project's [`CLAUDE.md`](../../CLAUDE.md) and [`dashboard/CLAUDE.md`](../../dashboard/CLAUDE.md) for architecture, conventions, and hard rules — notably the dashboard SSE patterns in `dashboard/routers/sse.py` and `dashboard/routers/code_qa.py`, the htmx + plain `EventSource` convention, and the Tailwind-prebuilt CSS pipeline.

## Scope

### In Scope

- `orch/chat/` package: `opencode_runtime.py` (subprocess manager), `opencode_client.py` (HTTP+SSE client), `relay_manager.py` (multi-session relay with ring buffers), `filters.py` (event normalisation).
- `dashboard/routers/chat.py`: 8 endpoints — `POST /api/chat/sessions`, `GET /api/chat/sessions`, `GET /api/chat/sessions/{sid}`, `GET /api/chat/sessions/{sid}/stream` (SSE), `POST /api/chat/sessions/{sid}/prompt`, `POST /api/chat/sessions/{sid}/abort`, `POST /api/chat/sessions/{sid}/permissions/{rid}`, `GET /api/chat/config`, `GET /api/chat/skills`.
- Frontend: `dashboard/templates/chat_assistant/` (panel, composer, message, approval modal fragments), `dashboard/static/chat_assistant/` (chat.js, chat.css), `dashboard/templates/base.html` integration + Ctrl+/ keybinding wiring.
- Per-page context injection: small `<script>` calls in `item_detail.html`, `batch_detail.html`, `research_detail.html`, `research_library.html`, `docs_detail.html`, `docs_library.html`, `project_code.html` calling `window.iwChat.setContext({type, id, title})`. Research view's "Create new research" button becomes a deep-link via `window.iwChat.openWith("/iw-research ")`.
- `.opencode/config.json`: add the 6-line `permission` block from R-00074 §5. (This file may not exist yet at repo root; create it if absent.)
- `orch/config.py` + `.env.example`: add `IW_CORE_OPENCODE_PORT` (default `4096`) and `IW_CORE_OPENCODE_BIN` (default `opencode`). Password generated at startup in process memory only.
- `dashboard/app.py` lifespan: start `OpencodeRuntime` before existing daemon startup; stop on shutdown. Register the new router.
- `pyproject.toml`: add `httpx-sse` if not present (verify before assuming).
- Unit tests for runtime / client / relay; integration tests for the full happy path; browser verification for the UX flows.

### Out of Scope (v1)

- **Pi as alternative runtime** (R-00072) — the architecture is shaped to make a future swap cheap (~300 LOC); but this FR ships OpenCode only.
- **Dedicated `/iw-debug` skill** for "debug an item in error" — that's a separate small follow-up; the chat panel is the surface, the skill is its own work.
- **Persisting transcripts to the orch DB** — OpenCode's disk session storage is the v1 audit trail.
- **MCP servers exposed by the dashboard back to the agent** — possible future hook; not in v1.
- **Container-per-session sandboxing** — repo-bounded `directory` + `external_directory: deny` is the v1 boundary. Document the upgrade path.
- **Multi-user / auth** — single-user dashboard constraint stands.
- **Audit-log dashboard view of past chat events** — OpenCode disk session is the trail; UI surface for it is a v2 polish item.
- **R-00073 §14 conservative safeguards** (policy table, plan-only mode, `WAITING_FOR_CONFIRMATION` state, `idempotency_key` migration to `iw next-id` — the last lives in CR-00053). All explicitly deferred per R-00074.
- **Refactor of the existing right-side Code Q&A chat** to share code with the new panel. Zero edits to `dashboard/templates/chat/` or `dashboard/static/chat/` in this FR.
- **Pretty rendering of agent artifacts** (markdown formatting, code-block highlighting, mermaid in chat) beyond what comes for free from streaming text. Polish for v1.5.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `orch/chat/opencode_runtime.py` — subprocess manager (start/stop/health/restart, `PR_SET_PDEATHSIG`, per-startup password); `orch/config.py` + `.env.example` additions; `pyproject.toml` add `httpx-sse` if missing | — |
| S02 | backend-impl | `orch/chat/opencode_client.py` (httpx + httpx-sse), `relay_manager.py` (multi-session relay with `deque(maxlen=256)`), `filters.py` (event-shape normalisation) | — |
| S03 | api-impl | `dashboard/routers/chat.py` (8 endpoints) + `dashboard/app.py` lifespan + router registration | S04 |
| S04 | frontend-impl | Templates under `dashboard/templates/chat_assistant/` (panel.html, composer.html, message.html, approval.html), static JS+CSS under `dashboard/static/chat_assistant/` (chat.js with `window.iwChat`, EventSource + dedup + gap detection, Ctrl+/ toggle), `dashboard/templates/base.html` include + nav toggle, `.opencode/config.json` patch, per-page `setContext` wiring in seven page templates | S03 |
| S05 | tests-impl | Unit tests (runtime lifecycle, client request shapes, relay fan-out + replay), integration tests (full happy path with real `opencode serve` or fully mocked SSE) | — |
| S06 | code-review-impl | Per-agent review of S01–S05 (CRITICAL on: existing-Code-chat regression, scope creep, DOM id collisions, missing permissions config, password leak) | — |
| S07 | code-review-fix-impl | Apply CRITICAL/HIGH fixes from S06 | — |
| S08 | code-review-final-impl | Cross-agent review: independently re-run targeted tests; visually inspect that existing right-side Code chat still works; verify `.opencode/config.json` permission block matches R-00074 §5 verbatim; verify scope discipline | — |
| S09 | code-review-fix-final-impl | Final cross-cutting fixes | — |
| S10–S17 | qv-gate | lint · assertions · format-check · type-check · test-unit · test-integration · diff-coverage · security-secrets | — |
| S18 | qv-browser | Browser verification — full happy path: toggle / prompt / approve / abort / new-chat / history switch / tab-refresh-reconnect / regression-guard for existing Code chat / Ctrl+/ keybinding / per-page chip injection | — |
| S19 | self-assess-impl | Self-assessment via `iw-item-analyze` (project has `self_assess=true`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: This feature adds no migrations. OpenCode disk-persistence + in-memory ring buffers cover all session state.

### API Changes

- **New endpoints** (all under `/api/chat/`):
  - `POST /api/chat/sessions` — create a new OpenCode session; body `{model?, agent?, directory?}`; returns `{session_id}`.
  - `GET /api/chat/sessions` — list past sessions from OpenCode's `GET /session`; returns `[{id, created_at, title}]`.
  - `GET /api/chat/sessions/{sid}` — get session metadata + full message history (passthrough of OpenCode's `GET /session/{sid}/messages`).
  - `GET /api/chat/sessions/{sid}/stream` — SSE relay; honours `Last-Event-ID` header for ring-buffer replay.
  - `POST /api/chat/sessions/{sid}/prompt` — body `{text, model?, context?}`; forwards to OpenCode's `POST /session/{sid}/prompt_async` (`context` is the optional "Currently viewing X" chip metadata, attached to the system message).
  - `POST /api/chat/sessions/{sid}/abort` — forwards to OpenCode's `POST /session/{sid}/abort`.
  - `POST /api/chat/sessions/{sid}/permissions/{rid}` — body `{response, remember?}`; forwards to OpenCode's `POST /session/{sid}/permissions/{rid}`.
  - `GET /api/chat/config` — returns `{models: [...], default_model, default_agent}` from OpenCode's `GET /config` + `app.agents()`. Cached for 30 s.
  - `GET /api/chat/skills` — returns `[{kind: "skill" | "command", name, description}]` from `.opencode/skills/` + `.opencode/commands/`. Cached for 30 s with a filesystem-mtime check.
- **Modified endpoints**: None

### Frontend Changes

- **New components**:
  - `chat_assistant/panel.html` — left-sidebar slide-out, collapsed/expanded states, distinct ids prefixed `chat-assistant-`.
  - `chat_assistant/composer.html` — textarea with `/` autocomplete, "Currently viewing X" chip area, Send + Abort buttons.
  - `chat_assistant/message.html` — message card template (user / assistant / tool-call / tool-result).
  - `chat_assistant/approval.html` — modal fragment rendered on `permission.asked` events.
  - `chat_assistant/skills_tray.html` — collapsible tray listing every skill + command with descriptions.
  - `chat_assistant/history_dropdown.html` — past-sessions list.
- **Modified components**:
  - `base.html` — add the panel include after the existing right-side `chat/` panel; add a left-nav toggle button; add the Ctrl+/ keybinding `<script>`.
  - Seven page templates listed in scope.allowed_paths — each gets a small `<script>` calling `window.iwChat.setContext({...})`.
- **Removed components**: None.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00083_Feature_Design.md` | Design | This document |
| `F-00083_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/F-00083_S01_Backend_prompt.md` | Prompt | S01 — opencode_runtime + config + dep |
| `prompts/F-00083_S02_Backend_prompt.md` | Prompt | S02 — client + relay + filters |
| `prompts/F-00083_S03_API_prompt.md` | Prompt | S03 — router + lifespan |
| `prompts/F-00083_S04_Frontend_prompt.md` | Prompt | S04 — templates + static + per-page wiring + .opencode/config.json |
| `prompts/F-00083_S05_Tests_prompt.md` | Prompt | S05 — unit + integration tests |
| `prompts/F-00083_S06_CodeReview_prompt.md` | Prompt | S06 — per-agent review |
| `prompts/F-00083_S07_CodeReview_FIX_prompt.md` | Prompt | S07 — per-agent fixes |
| `prompts/F-00083_S08_CodeReview_Final_prompt.md` | Prompt | S08 — cross-agent review |
| `prompts/F-00083_S09_CodeReview_FIX_Final_prompt.md` | Prompt | S09 — cross-agent fixes |
| `prompts/F-00083_S18_BrowserVerification_prompt.md` | Prompt | S18 — qv-browser |
| `prompts/F-00083_S19_SelfAssess_prompt.md` | Prompt | S19 — self-assessment |

Reports are created during execution in `ai-dev/work/F-00083/reports/`.

## Acceptance Criteria

### AC1: Ctrl+/ toggles the panel; state persists across navigation

```
Given the dashboard is open on any page
When the user presses Ctrl+/
Then the left-sidebar Dashboard AI Assistant panel toggles open
And the toggle state is persisted in a cookie
And navigating to another page preserves the open/closed state
And the existing right-side Code-view Q&A chat is unaffected
```

### AC2: Prompt → streaming response → approval → abort works end-to-end

```
Given the chat panel is open and the user has typed "list files in dashboard/routers"
When the user clicks Send
Then a new OpenCode session is created if none exists for this tab
And the assistant message streams in token-by-token via SSE
And when the agent attempts a `bash` or `edit` tool, an approval modal renders
And clicking Allow proceeds; clicking Deny blocks the tool
And clicking Abort mid-stream cancels the run via POST /session/{sid}/abort
```

### AC3: Per-tab independent sessions

```
Given two browser tabs are open on the dashboard
When the user starts a prompt in tab A and a different prompt in tab B
Then each tab streams its own response in its own panel
And the transcripts do not interleave
And each tab has its own sessionStorage tab-id mapped to a distinct OpenCode session_id
```

### AC4: Model selector reflects OpenCode's reported config

```
Given the chat panel is open
When the model-selector dropdown is opened
Then it lists every model returned by GET /api/chat/config
And selecting a different model applies to the next prompt
And the previously-streaming response (if any) is unaffected
```

### AC5: Skills and commands tray + / autocomplete

```
Given the chat panel is open
When the user clicks the "?" tray
Then it shows every entry in .opencode/skills/ and .opencode/commands/ with its description
And when the user types "/" in the composer
Then an autocomplete list filters the same set as they type
```

### AC6: Tab-refresh reconnect with Last-Event-ID

```
Given an in-flight /iw-research run is streaming
When the user refreshes the browser tab mid-stream
Then on reconnect the EventSource sends Last-Event-ID
And the relay replays buffered events newer than that ID from its in-memory deque(maxlen=256)
And no events are visibly lost in the transcript
And the agent loop (running upstream in OpenCode) is unaffected
```

### AC7: Research view deep-link

```
Given the user is on the Research view
When the user clicks the "Create new research" button
Then the chat panel opens
And the composer is pre-populated with "/iw-research "
And focus is in the composer
```

### AC8: "Currently viewing X" chip from per-page setContext

```
Given the user is on an item-detail page (e.g., F-00084)
When the user opens the chat panel
Then a removable "Currently viewing: F-00084" chip is rendered above the composer
And the chip is attached to the first prompt as a system-message context unless dismissed
And dismissing the chip removes it from any future prompts in this session
```

### AC9: Context % indicator updates while streaming

```
Given an in-flight run is streaming
When the context % indicator is observed
Then it polls GET /api/chat/sessions/{sid} every 5 seconds while streaming
And updates the rendered percentage based on OpenCode's reported context size
And stops polling within 5 seconds of session.idle
```

### AC10: Existing Code Q&A chat is unchanged (regression guard)

```
Given the user navigates to a project Code view
When the existing right-side Code Q&A chat panel is opened
Then it behaves exactly as before this FR
And uses its existing #chat-panel DOM tree and Cmd+\ keybinding
And no Dashboard AI Assistant code interferes with its EventSource or its message rendering
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| OpenCode subprocess crash mid-stream | runtime SIGKILLed during a prompt | Runtime auto-restarts (max 3 in 60 s); relay reconnects via `aconnect_sse` retry; browser sees a `reconnecting…` pill; transcript continues from `GET /session/{sid}/messages`. If retry budget exhausted, surface error toast and disable Send. |
| Browser tab refresh during streaming | `Last-Event-ID` present on reconnect | Relay replays events with `id > last_event_id` from the in-memory deque. If the requested id has already aged out of the buffer, replay everything in the buffer and emit a one-time `event: gap` warning. |
| Approval modal — user closes browser without responding | session in WAITING_FOR_CONFIRMATION (OpenCode-side) | Relay tracks pending permissions; on reconnect to the same session, modals are re-rendered from the buffered `permission.asked` events. If buffer aged out, the user can re-trigger via the agent's own behaviour (it will re-emit on next progression). |
| Two tabs sharing the same tab-id by accident | sessionStorage collision (very rare; same window cloned) | Each tab on initial load checks if its sessionStorage tab-id maps to a still-existing OpenCode session; if so, it re-uses; if not, allocates a fresh one. UI shows the OpenCode `session_id` in the history dropdown so a duplicate is visible. |
| User dismisses the "Currently viewing X" chip | chip removed | The chip is NOT attached to subsequent prompts in this session. Other pages' navigation re-injects their own chip; the user can dismiss again. |
| `.opencode/config.json` missing or unreadable at startup | runtime startup failure | Runtime logs a clear error and writes the default `permission` block once. Dashboard surfaces a banner: "OpenCode runtime unavailable — chat disabled." Send button is disabled across all tabs. |
| `opencode` binary missing on PATH | `IW_CORE_OPENCODE_BIN` resolution fails | Same banner as above. Health endpoint at `/api/chat/config` returns 503. |
| 5000 ms heartbeat absence on upstream SSE | watchdog triggers | Runtime kills + restarts subprocess; relay reconnects; banner if 3 consecutive watchdog kills inside 60 s. |
| User selects a model the provider doesn't authenticate | OpenCode returns `provider_unauthenticated` on next prompt | Surface the error inline in the chat transcript with a "Configure provider via `/login`" hint. |
| `permission.asked` event for a tool we don't render specifically | unknown tool name | Approval modal still renders with the generic `tool + args` payload; never auto-allow unknown tools. |
| Concurrent prompts to the same session from two tabs (same tab-id share) | OpenCode session is single-threaded | OpenCode queues; UI in both tabs shows "agent busy"; once the current turn finishes, the second prompt streams. |

## Invariants

1. **No edits to `dashboard/templates/chat/` or `dashboard/static/chat/`** — the existing right-side Code Q&A chat must be untouched. Verified by `git diff --stat`.
2. **No new DB tables, no new migrations** — search `orch/db/migrations/versions/**` and `orch/db/models.py` for a CR-00053-shape addition; both must be unchanged by this FR.
3. **The `.opencode/config.json` permission block matches R-00074 §5 verbatim** — `permission."*": "ask"`, `read/glob/grep/webfetch/websearch: allow`, `external_directory: deny`.
4. **No password is logged or persisted** — `OPENCODE_SERVER_PASSWORD` lives only in process memory; grep the code for any disk write or `logger.info(password)` shape.
5. **All new DOM ids are prefixed `chat-assistant-`** — no `chat-panel`, `chat-input`, `chat-composer` etc. that would collide with the existing right-side chat.
6. **No hardcoded ports / URLs in the browser-verification prompt** — must use `$IW_BROWSER_BASE_URL` from the daemon.
7. **The relay's in-memory ring buffer has `maxlen=256` per session** — no DB persistence; tab-refresh replay relies on this.
8. **Per-tab session isolation** — opening two tabs and running prompts in both does NOT interleave transcripts; each tab has its own sessionStorage tab-id mapped to a distinct OpenCode session_id.
9. **Ctrl+/ keybinding does NOT collide with Cmd+\** (the existing Code chat's binding) — verified via browser test.
10. **The Dashboard AI Assistant panel is collapsed by default on first visit** — cookie controls subsequent visits.

## Dependencies

- **Depends on**: None. (CR-00053 is independent and lands in the same batch when both are approved; this FR does not require its idempotency-key support to function for v1, but pairs well with it once both are merged.)
- **Blocks**: None at the platform level. Future follow-ups (`/iw-debug` skill, Pi runtime swap) are scoped after v1 stabilises.

## Impacted Paths

- `orch/chat/**`
- `orch/config.py`
- `.env.example`
- `.opencode/config.json`
- `pyproject.toml`
- `dashboard/app.py`
- `dashboard/routers/chat.py`
- `dashboard/templates/base.html`
- `dashboard/templates/chat_assistant/**`
- `dashboard/templates/pages/project/item_detail.html`
- `dashboard/templates/pages/project/batch_detail.html`
- `dashboard/templates/research_detail.html`
- `dashboard/templates/research_library.html`
- `dashboard/templates/docs_detail.html`
- `dashboard/templates/docs_library.html`
- `dashboard/templates/project_code.html`
- `dashboard/static/chat_assistant/**`
- `dashboard/static/styles.css`
- `tests/unit/test_chat_*.py`
- `tests/integration/test_chat_*.py`
- `tests/dashboard/test_chat_*.py`

## TDD Approach

- **Unit tests** (`tests/unit/test_chat_*.py`):
  - `test_chat_runtime.py`: `OpencodeRuntime` start → health-poll → stop; restart-on-crash; PR_SET_PDEATHSIG presence (Linux); password generation per-startup; missing binary surfaces a clear error. Subprocess is mocked with `asyncio.subprocess` fake or a stub binary that emits a known health payload.
  - `test_chat_client.py`: `OpencodeClient` request shapes (verified with `respx`) — create_session, prompt, abort, reply_permission, get_messages, get_config. Auth header is Basic with the per-startup password.
  - `test_chat_relay.py`: `RelayManager` create-relay → multi-subscriber fan-out → ring-buffer replay on `Last-Event-ID` → ring-buffer wrap (events older than `maxlen=256` aged out). Subscriber detach cleans up.
  - `test_chat_filters.py`: event-shape normalisation from OpenCode bus → `{event, data, id}` triples; unknown events forwarded verbatim.

- **Integration tests** (`tests/integration/test_chat_*.py`):
  - `test_chat_endpoint_session_lifecycle.py`: create session → prompt → stream → abort, against a real `opencode serve` subprocess if the binary exists in the worktree (skip with reason if not). Fully-mocked fallback: spawn a minimal SSE server that mimics OpenCode's event vocabulary.
  - `test_chat_endpoint_permission_flow.py`: emit a synthetic `permission.asked`, verify the API forwards correctly to `POST /session/{sid}/permissions/{rid}` after the client replies.
  - `test_chat_endpoint_reconnect.py`: simulate browser disconnect mid-stream, reconnect with `Last-Event-ID`, assert replayed events are correct.

- **Edge cases** — every row of Boundary Behavior is a test case. The runtime-crash and tab-refresh scenarios are the most important and must have dedicated tests.

- **Browser verification** (S18): driven by `playwright-cli`, exercises every AC (1–10) end-to-end in the isolated worktree stack. The regression-guard AC (existing Code Q&A unchanged) is verified by navigating to the project Code view and confirming the existing right-side chat opens with Cmd+\ and renders correctly.

## Notes

- **Coexistence with existing chat is the highest-risk regression in this FR.** S06 and S08 must explicitly verify that `dashboard/templates/chat/` and `dashboard/static/chat/` are untouched in the diff and that the existing `#chat-panel` DOM tree is not affected by any new CSS in `dashboard/static/chat_assistant/`. The browser-verification prompt has an explicit V(n) section for this.
- **OpenCode's `permission.asked` payload shape is referenced but not wire-level verified.** R-00071 §4 inferred it from the docs but did not capture verbatim payload bytes. S02 should run a 5-minute spike at the start of the step: spawn `opencode serve`, set `bash: ask` in config, send a `bash` prompt, capture the actual `permission.asked` SSE event. Adjust the approval modal contract to the real payload before completing the step.
- **httpx-sse**: if not present in `pyproject.toml`, S01 adds it. Verify before assuming. The library is well-maintained and has the exact `Last-Event-ID` handling we need.
- **The "Currently viewing X" chip injection** has a small UX subtlety: the chip is attached to the **first prompt** in a session unless dismissed. If the user opens the panel, navigates to another page (chip changes), and then sends the first prompt — the chip from the *current* page wins. The previous page's chip is gone (replaced when `setContext` was called). This matches user intent ("the agent should know what I'm looking at *now*") and avoids stale-context attachment.
- **Browser-verification stack already has dashboard, but no `opencode serve`** — the existing IW daemon's e2e compose may or may not include the OpenCode binary. S18's prompt must handle the absence gracefully (skip with a clear reason if not available) and document this as a follow-up for the worktree-compose configuration.
- The decision to ship **OpenCode v1 only** is preserved from R-00074 §8. Pi swap remains a documented future option; the architecture in `orch/chat/` is deliberately runtime-agnostic at the relay layer so a future `pi_runtime.py` + `pi_client.py` can drop in alongside.
- **Pre-evidence captured**: `evidences/pre/F-00083-before-dashboard-baseline.png` — Projects page baseline before the left chat panel exists.
