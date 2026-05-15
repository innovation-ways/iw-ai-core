# CR-00054: Add OpenCode stub to worktree E2E stack

**Type**: Change Request
**Priority**: Medium
**Reason**: F-00083 (Dashboard AI Assistant) had to skip its S18 qv-browser step because the worktree browser_verification stack ships no `opencode` binary, so `/api/chat/config` returned 503. F-00083 §316 explicitly tracked this as a follow-up. Without this CR, every future chat-related qv-browser step will hit the same SPEC_MISMATCH.
**Created**: 2026-05-15
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This CR touches `Dockerfile.e2e` and `docker-compose.e2e.yml` as **edits to declarative files** — agents must NOT `docker compose up`/`down`/`build`. Image rebuilds happen on the daemon's next worktree-compose launch (or via the operator running `./ai-core.sh`-equivalent helpers).

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This CR adds NO migrations.** The change is image+compose configuration plus one new Python stub script — no schema impact.

## Description

The per-worktree browser_verification stack (`docker-compose.e2e.yml`, built from `Dockerfile.e2e`) does not install the `opencode` binary that the chat router's `OpencodeRuntime` subprocess-manager invokes. This CR adds a tiny Python stub (`scripts/e2e_opencode_stub.py`) that mimics `opencode serve` v1.15.0's HTTP+SSE wire protocol, installs a `/usr/local/bin/opencode` shim that `exec`s it, and wires the relevant env vars into the e2e-dashboard service. Pattern mirrors the existing `scripts/e2e_ollama_stub.py`. After this CR, chat-related qv-browser steps can pass their pre-flight runtime check and exercise the chat UI end-to-end inside the worktree e2e stack.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key constraints for this CR:

- The e2e-ollama stub at `scripts/e2e_ollama_stub.py` is the canonical pattern to follow for a new stub. Match its style (FastAPI/Starlette server, `--port` CLI flag, deterministic responses).
- `Dockerfile.e2e` runs as a non-root `app` user with `WORKDIR /app`. Anything installed into `/usr/local/bin` must be done **before** `USER app` or made world-executable.
- The production daemon's OpencodeRuntime (`orch/chat/opencode_runtime.py`) spawns `opencode serve --hostname 127.0.0.1 --port N`, sets `OPENCODE_SERVER_PASSWORD` in the child env, then polls `GET /global/health` using an `httpx.AsyncClient` whose default `auth=httpx.BasicAuth("opencode", <password>)` is installed at client construction (see `_wait_healthy` at `orch/chat/opencode_runtime.py:213` and the client setup at `:103-110`). Concretely: every health probe carries the Authorization header. The stub MUST therefore return 200 on `GET /global/health` whether or not an Authorization header is present — it MUST NOT 401 the health probe.
- The dashboard's chat router (`dashboard/routers/chat.py`) returns `503 {"error": "OpenCode runtime unavailable"}` whenever OpencodeRuntime is not healthy. Pre-flight readiness for browser verification is `GET /api/chat/config → 200 {"models": [...], ...}`.
- `httpx-sse` is already a dependency (added by F-00083 S01).

## Current Behavior

1. The IW daemon launches a per-worktree e2e stack via `worktree_compose.py` whenever a `browser_verification` step runs.
2. The stack consists of `e2e-db`, `e2e-ollama` (stub), `e2e-daemon-stub`, and `e2e-dashboard`.
3. The dashboard container's image (`Dockerfile.e2e`) does **NOT** install the `opencode` binary. There is no `opencode` on `PATH` inside the container.
4. The dashboard's `_lifespan` startup calls `OpencodeRuntime.start()`. On a fresh e2e container that fails with `FileNotFoundError: opencode binary not found at 'opencode'`. The runtime stays `unhealthy`; OpencodeClient is never instantiated.
5. Every request to `/api/chat/*` returns `503 {"error": "OpenCode runtime unavailable"}`.
6. qv-browser steps verifying chat UX (e.g. F-00083 S18) detect the 503 at the pre-flight check, classify the result as `SPEC_MISMATCH:`, and exit without running V1..V(n).
7. The daemon's `fix_cycle.handle_spec_mismatch_escalation` keeps the step in `failed` state and emits a `spec_mismatch_escalation` DaemonEvent. Operator must manually `iw step-skip` to unblock the item (as was done for F-00083).

## Desired Behavior

1. `Dockerfile.e2e` installs `/usr/local/bin/opencode` — a tiny shim script that `exec`s `scripts/e2e_opencode_stub.py`.
2. `scripts/e2e_opencode_stub.py` accepts the `serve --hostname H --port N` CLI form **and** a no-port-bind `--selftest` mode (used at image build time to catch shim typos and broken imports) and starts an SSE/HTTP server matching opencode v1.15.0's wire protocol on `H:N`:
   - `GET /global/health` → 200, body empty, accepted **with or without** an Authorization header. (OpencodeRuntime's `httpx.AsyncClient` always carries `Authorization: Basic opencode:<pwd>`, but the stub does NOT validate it on `/global/health` — that keeps the stub forgiving if/when the host runtime starts probing without auth.)
   - All `/session/...`, `/config`, `/event` endpoints honour HTTP Basic with username `opencode` and the password from `OPENCODE_SERVER_PASSWORD` env var.
   - `GET /config` → `{"models": [{"id": "stub/echo", "name": "Stub Echo"}], "default_model": "stub/echo", "default_agent": "build"}`.
   - `POST /session` → `{"id": "ses_<uuid>", "created_at": "<iso>", "title": null}`.
   - `GET /session` → list of created sessions.
   - `GET /session/{sid}` → session metadata.
   - `GET /session/{sid}/messages` → message history list (empty for a new session, growing as prompts arrive).
   - `POST /session/{sid}/prompt_async` → 200 immediately; concurrently enqueues a deterministic SSE event sequence on `/event` for that session: `message.updated` (assistant turn open) → `message.updated` (text delta) → `permission.asked` (synthetic `bash` tool request, exposed so AC tests can exercise the approval modal) → `message.updated` (assistant turn close) → `session.idle`.
   - `POST /session/{sid}/abort` → 200; emits `session.idle` immediately on `/event` and stops streaming further events for the current turn.
   - `POST /session/{sid}/permissions/{rid}` → 200; records the response in-memory (allow / deny / remember). If the request id matches the most-recent synthetic `permission.asked` event for the session, emit one more `message.updated` indicating the agent continued (allow) or aborted (deny).
   - `GET /event` → long-lived SSE stream; honours `Last-Event-ID` header for ring-buffer replay (keep a per-process `deque(maxlen=256)`); auto-flushes every event with an `id:` line so the relay can resume.
3. `docker-compose.e2e.yml` sets on the `e2e-dashboard` service:
   - `IW_CORE_OPENCODE_BIN: /usr/local/bin/opencode`
   - `IW_CORE_OPENCODE_PORT: "4096"`
4. The dashboard healthcheck is extended (or supplemented) so the container is `healthy` only when **both** `/health` and `/api/chat/config` respond 200. This guarantees qv-browser doesn't probe the stub before OpencodeRuntime finishes its startup poll.
5. On a fresh image build, `playwright-cli open ${IW_BROWSER_BASE_URL}/api/chat/config` returns a JSON body with a non-empty `models` array — i.e. the F-00083 S18 pre-flight check passes.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `Dockerfile.e2e` | No `opencode` binary present | Adds `/usr/local/bin/opencode` shim wrapping the Python stub; image build adds ≤ 1 extra layer |
| `docker-compose.e2e.yml` `e2e-dashboard` service | No `IW_CORE_OPENCODE_*` env vars; healthcheck only hits `/health` | Adds `IW_CORE_OPENCODE_BIN` + `IW_CORE_OPENCODE_PORT`; healthcheck gates on `/api/chat/config → 200` |
| `scripts/e2e_opencode_stub.py` | Does not exist | New: SSE/HTTP server mimicking opencode v1.15.0 |
| `tests/integration/test_e2e_opencode_stub.py` | Does not exist | New: direct httpx tests against the stub subprocess |
| `docs/IW_AI_Core_Testing_Strategy.md` | Documents `e2e-ollama` stub; no mention of opencode stub | Adds an "E2E OpenCode stub" subsection describing the new stub, its scope, and how to extend it |

### Breaking Changes

- None. The change is additive to the e2e image only. Production code paths (host-PATH `opencode`, real LLM providers) are unchanged.

### Data Migration

- None. The CR has no DB impact and no migrations.
- Reversibility: trivial — revert the commit; future e2e images rebuild without the stub layer.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | pipeline-impl | `scripts/e2e_opencode_stub.py` — minimal SSE/HTTP server mimicking opencode v1.15.0: 9 HTTP endpoints + `/event` SSE; HTTP Basic auth (`opencode:$OPENCODE_SERVER_PASSWORD`); CLI `serve --hostname H --port N`; deterministic synthetic event stream emitted on `prompt_async`; ring buffer for `Last-Event-ID` replay (`deque(maxlen=256)`). TDD-RED first via direct httpx integration tests. | — |
| S02 | pipeline-impl | `Dockerfile.e2e` — add a `/usr/local/bin/opencode` shim (small POSIX `sh` wrapper that execs `uv run python /app/scripts/e2e_opencode_stub.py "$@"`). Verify `.opencode/config.json` permission block is COPYed in (already covered by existing `COPY . .`; add a comment). Document the stub-vs-real-binary trade-off in a Dockerfile comment block. Keep new layer count to ≤ 1 to preserve image build time. | — |
| S03 | pipeline-impl | `docker-compose.e2e.yml` — add `IW_CORE_OPENCODE_BIN=/usr/local/bin/opencode` and `IW_CORE_OPENCODE_PORT="4096"` to the `e2e-dashboard.environment` block. Extend the healthcheck to gate on `/api/chat/config → 200` (or add a second healthcheck script invoked by the existing `test` command). | — |
| S04 | tests-impl | `tests/integration/test_e2e_opencode_stub.py` — spawn the stub subprocess on a free port, point an httpx client at it with the right basic-auth header, and verify: (a) `/global/health → 200`; (b) `/config` shape; (c) `/session` CRUD; (d) `prompt_async` triggers the deterministic event sequence on `/event`; (e) `Last-Event-ID` replay returns events from the ring buffer; (f) `permissions/{rid}` accepts allow/deny and emits the right follow-up event; (g) basic-auth failure → 401. Per `tests/CLAUDE.md`: assertion strength, no live-DB connection. | — |
| S05 | template-impl | `docs/IW_AI_Core_Testing_Strategy.md` — append a new subsection "E2E OpenCode stub" under the existing E2E stack documentation: explain the stub's purpose, why a stub vs the real binary, and how to extend the event vocabulary when new chat-related qv-browser steps need richer events. | — |
| S06 | code-review-impl | Per-agent review of S01–S05. CRITICAL on: stub running anything other than 127.0.0.1 binding; basic-auth bypass; secret leakage in logs; new dependencies in `pyproject.toml`; modifications to production `orch/chat/*` (this CR must NOT touch them); modifications to F-00083's design-time decisions; running anything that requires network in the stub. HIGH on: missing ring-buffer for `/event` replay; stub returning HTTP shapes that diverge from `OpencodeClient`'s schema expectations; healthcheck regression; Dockerfile image size grew >50 MB; missing assertion-strength in tests. | — |
| S07 | code-review-fix-impl | Apply CRITICAL/HIGH fixes from S06. Re-run only targeted tests for files touched. | — |
| S08 | code-review-final-impl | Cross-agent final review. Inspect `git diff --stat`. Confirm the only files touched are in `scope.allowed_paths`. Run `tests/integration/test_e2e_opencode_stub.py` once locally. Verify Dockerfile.e2e build time stays under ~3 min by inspecting the new RUN command (no heavy package installs). | — |
| S09 | code-review-fix-final-impl | Apply CRITICAL/HIGH fixes from S08. Pass-through no-op when S08 is clean. | — |
| S10 | qv-gate | `make lint` | — |
| S11 | qv-gate | `make test-assertions` | — |
| S12 | qv-gate | `make format-check` | — |
| S13 | qv-gate | `make type-check` | — |
| S14 | qv-gate | `make test-unit` | — |
| S15 | qv-gate | `make test-integration` (900 s timeout) | — |
| S16 | qv-gate | `make diff-coverage` (1800 s timeout) | — |
| S17 | qv-gate | `make security-secrets` (300 s timeout) | — |
| S18 | qv-browser | Browser verification: pre-flight `/api/chat/config → 200` with `models` array; V2 Ctrl+/ toggles chat panel; V3 send a prompt and verify deterministic synthetic streaming; V4 permission.asked approval modal renders; V_no_regressions covers other dashboard pages + the existing right-side Code Q&A regression guard. | — |
| S19 | self-assess-impl | iw-item-analyze postmortem on the CR's execution: did fix-cycles burn on stub shape mismatches; was the SSE replay path tested deeply enough; did S18 surface UX gaps the stub couldn't simulate. Project self_assess=true. | — |

Agent slugs are canonical (per `skills/iw-workflow/SKILL.md`).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: This CR adds no migrations.

### API Changes

- **New endpoints**: None (the stub mimics the existing `/api/chat/*` upstream; the dashboard's `/api/chat/*` endpoints are unchanged).
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00054/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00054_CR_Design.md` | Design | This document |
| `CR-00054_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00054_S01_Pipeline_prompt.md` | Prompt | S01 — stub server implementation |
| `prompts/CR-00054_S02_Pipeline_prompt.md` | Prompt | S02 — Dockerfile.e2e shim |
| `prompts/CR-00054_S03_Pipeline_prompt.md` | Prompt | S03 — docker-compose.e2e.yml wiring |
| `prompts/CR-00054_S04_Tests_prompt.md` | Prompt | S04 — integration tests |
| `prompts/CR-00054_S05_Template_prompt.md` | Prompt | S05 — testing-strategy docs update |
| `prompts/CR-00054_S06_CodeReview_prompt.md` | Prompt | S06 — per-agent review |
| `prompts/CR-00054_S07_CodeReview_FIX_prompt.md` | Prompt | S07 — per-agent fixes |
| `prompts/CR-00054_S08_CodeReview_Final_prompt.md` | Prompt | S08 — cross-agent final review |
| `prompts/CR-00054_S09_CodeReview_FIX_Final_prompt.md` | Prompt | S09 — cross-agent final fixes |
| `prompts/CR-00054_S18_BrowserVerification_prompt.md` | Prompt | S18 — qv-browser verification |
| `prompts/CR-00054_S19_SelfAssess_prompt.md` | Prompt | S19 — iw-item-analyze postmortem |

Reports are created during execution in `ai-dev/active/CR-00054/reports/`.

## Acceptance Criteria

### AC1: Pre-flight runtime check returns 200

```
Given the worktree e2e stack is freshly built from CR-00054's commit
When a qv-browser agent runs: playwright-cli open ${IW_BROWSER_BASE_URL}/api/chat/config
Then the HTTP response is 200 with Content-Type: application/json
And the JSON body contains a "models" array with at least one entry
And the body contains a non-empty "default_model" string
```

### AC2: Chat UI happy path streams through the stub

```
Given the worktree e2e stack is running with the OpenCode stub installed
When a qv-browser agent presses Ctrl+/ to open the chat panel
And types a prompt and clicks Send
Then the panel streams the deterministic synthetic event sequence from the stub
And the approval modal renders when the stub emits a synthetic permission.asked event
And clicking Allow forwards a 200 response back to the stub
And the conversation eventually shows a session.idle indicator
```

### AC3: No regression to existing e2e flows

```
Given any other browser_verification step from a non-chat-touching work item
When that step's qv-browser prompt runs against the new e2e image
Then every page that previously loaded with HTTP 200 still loads with HTTP 200
And no new console errors are introduced on the dashboard's main pages
And the existing e2e-dashboard healthcheck (now extended) reports healthy within the same time budget (≤ 2 min)
```

### AC4: No heavy install steps added to the e2e image (build-time budget unchanged)

```
Given the diff against Dockerfile.e2e at merge time
When a reviewer inspects the new RUN layer(s) added by this CR
Then no layer fetches a large binary (no `curl | sh`, no `apt-get install` of
     new system packages, no `wget` of multi-megabyte assets)
And the only new RUN is the `/usr/local/bin/opencode` shim write plus the
    `--selftest` build-time validation
```

> **Note on the 3-minute build budget.** A literal end-to-end measurement
> requires running `docker build` against `Dockerfile.e2e`, which is off-limits
> to agents under the docker-off-limits policy. The 3-minute target is a
> non-blocking operator-measured budget: the next worktree-compose launch on
> the daemon will time the rebuild incidentally; if it regresses past ~3 min,
> open a follow-up I- to investigate. AC4 above is the in-loop acceptance
> proxy.

### AC5: Production daemon picks up new env vars cleanly

```
Given the production daemon launches a new worktree-compose stack from the merged code
When the dashboard service starts
Then OpencodeRuntime.start() locates /usr/local/bin/opencode inside the container
And the runtime becomes healthy within the existing 10s health-poll timeout
And the dashboard's _lifespan completes without raising
```

### AC6: Stub HTTP shapes match OpencodeClient's expectations

```
Given the new tests/integration/test_e2e_opencode_stub.py suite
When pytest exercises every stub endpoint against the live subprocess
Then JSON shapes match what orch/chat/opencode_client.py raises on
And HTTP Basic auth is enforced (401 on bad credentials)
And /event SSE stream honours Last-Event-ID for ring-buffer replay
```

## Rollback Plan

- **Database**: N/A (no migrations).
- **Code**: Revert the merge commit. Future e2e images rebuild without the stub layer; existing committed work items that depend on the stub (none yet at merge time) become re-blocked on the same SPEC_MISMATCH. The fix-forward path is preferred.
- **Data**: No data loss possible (the stub holds only ephemeral per-process state).

## Dependencies

- **Depends on**: F-00083 (provides `orch/chat/*` and `dashboard/routers/chat.py` that the stub must speak to). F-00083 must be merged before this CR's S18 can verify against a real OpencodeRuntime-driven dashboard.
- **Blocks**: Any future Feature / CR that adds a chat-related qv-browser verification (none currently filed).

## Impacted Paths

- `scripts/e2e_opencode_stub.py`
- `Dockerfile.e2e`
- `docker-compose.e2e.yml`
- `tests/integration/test_e2e_opencode_stub.py`
- `docs/IW_AI_Core_Testing_Strategy.md`

## TDD Approach

- **Unit tests**: None (the stub is small enough that a single integration-style suite is more valuable than mocking the SSE server's internals).
- **Integration tests**: `tests/integration/test_e2e_opencode_stub.py` — spin up the stub subprocess on a free port (per-test fixture), exercise every endpoint with httpx + httpx_sse, verify shapes, auth, and `/event` semantics including `Last-Event-ID` replay. Per `tests/CLAUDE.md`: no live-DB connection, assertion strength enforced by `make test-assertions`.
- **Updated tests**: None (no existing tests assert anything about the absence of an opencode binary).
- **TDD-RED first**: S01's pipeline-impl writes the test file first, runs it to confirm it fails because the stub doesn't exist yet, then implements the stub until green.

## Notes

- **Why a stub vs the real binary**: The real `opencode` binary on the host (~100 MB extracted, with its own state directory and required LLM-provider configuration) would balloon the e2e image and introduce a non-deterministic streaming surface — exactly the same reason `e2e-ollama` is a stub. The stub mimics opencode v1.15.0's wire protocol; bumping the protocol version is a future maintenance task documented in `IW_AI_Core_Testing_Strategy.md`.
- **Version alignment**: The stub targets v1.15.0's wire protocol because that's what the host `opencode` binary that the production daemon runs is pinned to. If the host bumps, the stub's `models` payload and event shapes must be revisited.
- **Risk**: The stub's deterministic event sequence is a fixture, not a behaviour spec. Future chat-related qv-browser steps that depend on richer agent behaviour (e.g., real tool calls reading files) cannot use this stub and must either extend it or run against a real local `opencode serve`. Documented in the testing-strategy doc.
- **Scope discipline**: The CR MUST NOT touch anything under `orch/chat/**`, `dashboard/routers/chat.py`, `dashboard/templates/chat_assistant/**`, or `dashboard/static/chat_assistant/**`. F-00083 owns those.
