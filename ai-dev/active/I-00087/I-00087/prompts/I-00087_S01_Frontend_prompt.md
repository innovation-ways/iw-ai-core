# I-00087_S01_Frontend_prompt

**Work Item**: I-00087 — AI Assistant chat panel does not render model responses (wire-protocol drift)
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations. The full alembic policy still applies:
You MUST NOT run `alembic upgrade head`, `alembic upgrade <rev>`,
`alembic downgrade <anything>`, or `alembic stamp` against the live
orchestration DB (port 5433) from an agent context.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list and status, prefer `uv run iw item-status I-00087 --json`. The `workflow-manifest.json` is a design-time snapshot (CR-00023).
- `ai-dev/active/I-00087/I-00087_Issue_Design.md` — read this in full BEFORE editing anything
- `ai-dev/active/I-00087/evidences/pre/I-00087-opencode-events.log` — proof that the model does respond; the bug is purely on the rendering side
- `dashboard/static/chat_assistant/chat.js` — the file you will modify
- `orch/chat/filters.py` — `INTERESTING_EVENTS` is the canonical Python list of opencode event names; pin yourself to it
- `.opencode/node_modules/@opencode-ai/sdk/dist/gen/types.gen.d.ts` — opencode SDK types; the source of truth for payload shapes. Grep for `EventMessagePartUpdated`, `EventMessageUpdated`, `EventPermissionUpdated`, `EventToolExecuteBefore`, `EventToolExecuteAfter`, `EventSessionStatus`, `EventSessionError`, `EventSessionUpdated`, `SessionMessagesResponses` — those are the shapes you need.

## Output Files

- `ai-dev/active/I-00087/reports/I-00087_S01_Frontend_report.md` — step report

## Context

You are fixing the AI Assistant chat panel so it renders opencode 1.15's actual event stream. The dashboard already receives the events (opencode log proves it; the relay forwards them verbatim per `orch/chat/filters.py`). The frontend listener list and payload extraction logic are written against an older, mismatched contract — that is the only thing broken.

Read `ai-dev/active/I-00087/I-00087_Issue_Design.md` first — the **Root Cause Analysis**, **Concrete event handling table**, and **Session continuity invariants that MUST be preserved** sections are your spec. Then read `dashboard/CLAUDE.md` and `CLAUDE.md` for project conventions.

## Requirements

### 1. Rewrite `_connectStream` listener registration (`dashboard/static/chat_assistant/chat.js:187-191`)

Replace the `namedEvents` array with a list that:

- Includes every name from `orch.chat.filters.INTERESTING_EVENTS` (it is currently: `message.part.updated`, `tool.execute.before`, `tool.execute.after`, `permission.asked`, `permission.replied`, `session.idle`, `session.updated`, `session.error`).
- Also includes `message.updated`, `message.part.removed`, `message.removed`, `session.status` (these are emitted by opencode and you may want to render them — see the table in the design doc).
- Keeps the existing relay-synthesised events: `gap`, `reconnecting`, `error`.

If opencode's `INTERESTING_EVENTS` constant gains a new value tomorrow, the new test `test_chat_js_registers_every_interesting_event` (S03) will fail until this list is updated. That is by design — do not work around it.

Add a one-line comment on the line above the array literal pointing to `orch/chat/filters.py` so the next contributor knows where the source of truth lives.

### 2. Rewrite `_handleEvent` payload extraction (`dashboard/static/chat_assistant/chat.js:209-298`)

Opencode-native events wrap their payload under `properties`. Relay-synthesised events (`gap`, `reconnecting`, `error`) use the flat `data` shape. The handler must distinguish them.

Implement each row of the **Concrete event handling table** in the design doc. Highlights:

- **`message.part.updated`** — extract text via `properties.delta || (properties.part && properties.part.text) || ''`. Use `_appendOrUpdateAssistantMessage(<part.id or message.id>, text, false)` for in-flight streaming; that function already supports incremental updates. Use a stable dedup key per message (prefer `properties.part.messageID` so multiple parts on the same message coalesce into one bubble).
- **`message.updated`** — read `properties.info` (a full `Message`). If `info.role === 'assistant'` and `info.time.completed` is set, mark the bubble final (`_appendOrUpdateAssistantMessage(info.id, undefined, true)` or equivalent). If `info.error` is set, render an error bubble using the error's `data.message` field (see `ProviderAuthError` / `UnknownError` / `MessageOutputLengthError` in the SDK types).
- **`message.removed`** / **`message.part.removed`** — locate and remove the corresponding DOM nodes if they exist.
- **`tool.execute.before`** — append a system-style bubble with the tool name (e.g., `🔧 read`). Use `_appendSystemMessage` or add a new helper if needed.
- **`tool.execute.after`** — mark the matching tool bubble complete (add a `✓` or strip a spinner).
- **`permission.updated`** — re-wire the existing approval-modal path (currently triggered by the non-existent `permission.asked`) to fire on this event instead. Confirm the actual field names against `EventPermissionUpdated` in the SDK types — if the SDK uses `properties.id` rather than `properties.request_id`, adapt accordingly and update `_replyPermission` (around `chat.js:374`) so the URL still resolves to `/api/chat/sessions/{sid}/permissions/{rid}` with the correct rid.
- **`permission.replied`** — dismiss the approval modal (it may already be dismissed by the user clicking Allow/Deny; this event is informational + handles the case where another tab replied).
- **`session.idle`** — preserve existing behaviour but read from `properties` first, falling back to `data` for backwards compatibility with the relay shape. Specifically: `properties && properties.permission_denied` / `properties && properties.aborted`.
- **`session.status`** — no visible bubble; use it only to update streaming indicators if helpful.
- **`session.error`** — render an error bubble with `properties.error` content.
- **`session.updated`** — no-op or refresh metadata.
- **`gap`**, **`reconnecting`**, **`error`** — keep existing behaviour; these arrive in the flat `{event, data, id}` shape from the relay (see `orch/chat/filters.py:_RELAY_GAP_EVENT` / `_RELAY_ERROR_EVENT`).

Add a comment block at the top of `_handleEvent` documenting the asymmetry: opencode-native events use `properties.*`, relay-synthesised events use `data.*`. The comment should reference `orch/chat/filters.py`.

### 3. Rewrite `_loadHistory` (`dashboard/static/chat_assistant/chat.js:513-535`)

The opencode endpoint `GET /session/{id}/message` returns `Array<{info: Message, parts: Part[]}>`. The current code reads `m.role` / `m.content` which do not exist.

Implement the loop shown in the design doc's **History reload** subsection. Specifically:

- Iterate `data.messages` (the chat router proxies the response through — the array's element shape is `{info, parts}`).
- For each entry, read `entry.info.role` and concatenate every `parts[i]` whose `type === 'text'` into a single rendered string.
- Pass `entry.info.id` as the dedup key to `_appendOrUpdateAssistantMessage` for assistant messages so an in-flight stream does not double-render after a reconnect.
- Skip entries with no `info` or with a role other than `user`/`assistant`.

### 4. Preserve session-continuity invariants

The user explicitly requires that "when the user interacts with the LLM it keeps the same session and context." Confirm in your step report that you did NOT regress any of these:

1. `sessionStorage['iw-chat-session-' + _tabId]` is still set on session create and read on panel open (`_ensureSession` around `chat.js:134-143`).
2. `_connectStream(sid)` still appends `?last_event_id=<id>` when `_lastSeenId` is set (around `chat.js:173-175`).
3. After a stream reconnect, `_loadHistory(sid)` is still called so the user sees prior turns (existing call at `chat.js:139`).
4. `newSession()` still wipes `sessionStorage`, message log, and `_seenIds`.
5. `switchSession(sid)` still loads history + reconnects the stream.
6. The context chip (`_renderChip`) is still rendered and dismissable (around `chat.js:543-559`).

A grep at the end of your work for each of these markers (`'iw-chat-session-' + _tabId`, `last_event_id=`, `_loadHistory(`, `sessionStorage.removeItem`, etc.) is a cheap way to confirm.

### 5. Out of scope (do NOT do these)

- Do NOT add a JavaScript test framework.
- Do NOT change `orch/chat/filters.py`, `orch/chat/relay_manager.py`, `orch/chat/opencode_client.py`, or any backend code. The bug is entirely frontend.
- Do NOT regenerate Tailwind CSS — your changes are JS-only. (Per `CLAUDE.md`, if you do touch templates, plain CSS in `dashboard/static/styles.css` is fine; you should not need to.)
- Do NOT rewrite `_appendOrUpdateAssistantMessage`, `_appendUserMessage`, `_appendSystemMessage` or the rest of the message rendering machinery unless absolutely required to wire in `tool.execute.before/after` rendering. If you need a new helper, add it; do not refactor existing helpers gratuitously.

## Project Conventions

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` in full. Key rules that apply here:

- The CSS file `dashboard/static/styles.css` is plain CSS and served as-is (do not run Tailwind if you need a new class — append a rule directly).
- Use the shared `window.iwClipboard.copy` helper for any copy buttons (not relevant here, but worth knowing).
- No new JS frameworks — vanilla JS only, matching the existing style of `chat.js`.

## TDD Requirement

This step is the *fix*; the dedicated `tests-impl` step (S03) writes the failing tests. However, you SHOULD still verify your changes against the existing chat tests before reporting completion:

```bash
uv run pytest tests/dashboard/test_chat_router.py tests/unit/test_chat_client.py -v --no-cov
```

These tests should remain green — your changes don't touch the router or client. If they go red, you've accidentally edited the wrong file or the test harness picked up a stale cache.

You may ALSO sanity-check that your `chat.js` parses cleanly with `node --check dashboard/static/chat_assistant/chat.js` — this is what `make lint` runs and catches typos before they hit downstream gates.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run these and fix any issues:

1. **`make format`** — auto-fixes formatting drift on Python/templates. JS is not auto-formatted by this project; rely on `make lint` for JS syntax check.
2. **`make typecheck`** — must report zero errors involving any file you touched.
3. **`make lint`** — must report zero errors. This runs `ruff check`, `node --check dashboard/...`, and the Jinja2 template checker.

If a tool is unavailable, STOP and raise a blocker.

In your Subagent Result Contract, populate the `preflight` object recording each result.

## Test Verification (NON-NEGOTIABLE)

Run only the targeted tests:

```bash
uv run pytest tests/dashboard/test_chat_router.py tests/unit/test_chat_client.py -v --no-cov
```

Do NOT run `make test-integration` or `make test-unit` — those are the QV gate steps' job (S09, S10).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/chat_assistant/chat.js"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — production fix only; dedicated tests-impl step (S03) writes and runs the failing tests",
  "blockers": [],
  "notes": "Session-continuity grep audit results: {paste the grep output for each of the 6 invariants}"
}
```
