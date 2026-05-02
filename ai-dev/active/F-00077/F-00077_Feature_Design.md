# F-00077: Code chat conversation memory with persistence and query rewriting

**Type**: Feature
**Priority**: High
**Created**: 2026-05-02
**Status**: Draft

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

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

The Code module chat (`/project/{id}/code`) currently has no working memory across turns. Two distinct gaps cause the failure: (1) the frontend always sends `conversation_history: []` (`dashboard/static/chat/composer.js:281`), so even though the backend at `orch/rag/qa.py:309-318` accepts a history list, no prior turn ever reaches the LLM; (2) even with history, RAG retrieval embeds the raw user question, so a follow-up like "explain how it works" produces near-random LanceDB chunks. This feature persists conversations in PostgreSQL, adds an LLM-based query-rewriting step (CondensePlusContext pattern), enforces a token-budget on history, and adds rolling-summary compaction for long sessions via a new `ChatSummarizationJob` daemon poller.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Critical companions for this feature:

- `orch/CLAUDE.md` — daemon module map, SQLAlchemy/Alembic conventions, append-only table list
- `orch/rag/CLAUDE.md` — RAG pipeline (LanceDB + LlamaIndex CodeSplitter + Ollama), TOP_K, embedding model
- `dashboard/CLAUDE.md` — htmx fragment patterns, SSE conventions, router thinness
- `tests/CLAUDE.md` — testcontainer rules and FTS-trigger requirements

## Scope

### In Scope

- Two new tables: `chat_conversations` (per-conversation row, includes `rolling_summary` and `summary_through_message_id` for compaction state) and `chat_messages` (append-only, one row per turn). Plus a new `chat_summarization_jobs` table modelled on `code_index_jobs` for the background compaction worker.
- One Alembic migration creating the three tables, indexes, and a Postgres ENUM for `chat_messages.role`.
- New repositories `orch/rag/chat_repo.py` for conversation/message CRUD; thin, returns ORM rows.
- New module `orch/rag/condense.py` exposing `condense_query(history, question, llm) -> str`. When `len(history) >= 2` it calls the same Ollama LLM with a fixed condense prompt to produce a self-contained search query; otherwise returns the question unchanged. Used by `qa.py` for the embedding/retrieval call only — the original question still goes to the answer turn.
- New module `orch/rag/summarize.py` exposing `summarize_history(messages, llm) -> str` that produces a compact prose summary preserving named entities (file paths, function names, work-item IDs), user-stated facts, and decisions reached.
- Modifications to `orch/rag/qa.py`:
  - Replace `MAX_HISTORY_TURNS = 5` message-count truncation with a token-budget truncation (`HISTORY_SOFT_BUDGET_TOKENS = 3000`, `HISTORY_HARD_BUDGET_TOKENS = 6000`).
  - Load history from DB instead of trusting the client's `conversation_history` array.
  - When `rolling_summary` exists, prepend it as a synthetic system note before the kept-verbatim turns.
  - Call `condense_query` before embedding/retrieval when prior turns exist.
  - Add hardening lines to the system prompt: "On contradictions in the user's statements, trust the most recent one." and "Do not claim to remember anything not present in the provided conversation history."
- New daemon poller `orch/daemon/chat_summarization_poller.py` — polls `chat_summarization_jobs` (status='queued'), invokes `summarize_history()`, writes `chat_conversations.rolling_summary` + `summary_through_message_id`, transitions job to 'completed'/'failed'. Modeled on `orch/daemon/doc_job_poller.py`. Job is enqueued by `qa.py` after the assistant message persists, when `len(history) > HARD_BUDGET` and no in-flight summarization job exists for the conversation.
- Modifications to `dashboard/routers/code_qa.py`:
  - `QARequest` adds optional `conversation_id: str | None` field; `conversation_history` field becomes deprecated (still accepted but ignored — server is the source of truth).
  - `_sse_generator()` resolves or creates a conversation, persists the user message synchronously on request arrival, emits a new `event: meta` SSE preamble with `{"conversation_id": "..."}` BEFORE any token, persists the assistant message after `__DONE__` (or partial on error with `metadata.error=true`), enqueues a `ChatSummarizationJob` if hard budget exceeded.
- New router `dashboard/routers/conversations.py`:
  - `GET /api/projects/{project_id}/conversations` — list recent (last 30 days, not archived) for the current browser session.
  - `GET /api/projects/{project_id}/conversations/{conv_id}/messages` — replay messages in order; returns `{conversation_id, messages, rolling_summary, last_active_at}`.
  - `POST /api/projects/{project_id}/conversations` — explicit new conversation (`{conversation_id}`).
  - `POST /api/projects/{project_id}/conversations/{conv_id}/archive` — soft-delete (sets `archived_at`).
- Frontend changes (`dashboard/static/chat/composer.js`, `panel.js`, `stream.js`, `dashboard/templates/chat/panel.html`):
  - Track `conversation_id` in localStorage keyed `iw_chat_conv_<projectId>_<modulePathOrArch>`.
  - On chat panel open (or page load when previously expanded), if a recent (<4h) conversation_id exists for this `(project_id, module_path)`, fetch its messages and render them as static history.
  - "New chat" button in the chat panel header — clears the active conversation_id, resets the DOM to the empty state.
  - Send `conversation_id` (nullable on first turn) in `QARequest`; capture `conversation_id` from the SSE `meta` preamble and persist to localStorage; subsequent sends carry it.
  - Auto-rotate: if the stored `last_active_at` is >4h old, clear before send → server creates a new conversation.
  - Stop sending `conversation_history` from the client; the field is kept on the request schema for backwards compatibility but ignored.
- Browser-session identity: a session cookie `iw_chat_session` (UUID, HttpOnly=false because JS reads it for localStorage scoping, SameSite=Lax, 90-day Max-Age) is set by a new FastAPI middleware in `dashboard/app.py` if absent. Conversations are scoped `(project_id, session_id)`. No authenticated user model is introduced.
- Tests: unit (token-budget truncation, condense returns question unchanged with <2 turns, summarize-prompt entity preservation), integration (full multi-turn round-trip against testcontainer + LanceDB stub, name-recall, follow-up retrieval against a seeded module, refresh persistence, TTL rotation, hard-budget triggers job, summarization preserves identity facts), dashboard router tests (TestClient-based).
- Browser verification: name-recall, follow-up retrieval, refresh persistence, "New chat" reset, no regressions on existing chat features (architecture vs module, slash commands, citations).

### Out of Scope

- Cross-session user profile / preferences memory (Mem0/Zep-style fact extraction). Conversations are session-scoped only.
- Conversation list / picker UI in the dashboard. The `GET /conversations` endpoint exists for future v2 use; v1 only auto-resumes the latest one for the current `(project_id, module_path)`.
- Sharing conversations between users (no multi-user model exists yet).
- Streaming partial assistant chunks to the DB. Persistence happens on `__DONE__` (single write) or on error (with partial content + `metadata.error=true`).
- Migrating any pre-existing in-DOM "history" — there is none to migrate (it was browser-only and never persisted).
- Replacing the existing `MAX_HISTORY_TURNS` constant with a config knob. The token-budget constants are module-level constants for v1.
- Per-message edit/regenerate UI. Append-only.
- Citation re-mapping across summarized history. Citations remain per-answer; the rolling summary may textually reference work-item IDs (e.g. "F-00055") but not as numbered citations.

## Impacted Paths

Globs declared here populate `WorkItem.impacted_paths` (per F-00076 convention) and are mirrored to `workflow-manifest.json:scope.allowed_paths`. Parser rules: gitignore-style globs only; no absolute paths; no `..`; no whitespace.

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/rag/qa.py`
- `orch/rag/condense.py`
- `orch/rag/summarize.py`
- `orch/rag/chat_repo.py`
- `orch/rag/CLAUDE.md`
- `orch/daemon/main.py`
- `orch/daemon/chat_summarization_poller.py`
- `dashboard/app.py`
- `dashboard/routers/code_qa.py`
- `dashboard/routers/conversations.py`
- `dashboard/static/chat/composer.js`
- `dashboard/static/chat/stream.js`
- `dashboard/static/chat/panel.js`
- `dashboard/templates/chat/panel.html`
- `tests/**`
- `pyproject.toml`
- `uv.lock`

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration creating `chat_conversations`, `chat_messages`, `chat_summarization_jobs`; ORM models; role ENUM; indexes; pyproject `tiktoken` dep for token counting. | — |
| S02 | code-review-impl | Review S01 (database) | — |
| S03 | backend-impl | `orch/rag/chat_repo.py`, `orch/rag/condense.py`, `orch/rag/summarize.py`, modifications to `orch/rag/qa.py` (token-budget truncation, DB-loaded history, condense call, summary prepend, hardening prompt lines). Update `orch/rag/CLAUDE.md`. | S04 |
| S04 | pipeline-impl | `orch/daemon/chat_summarization_poller.py`, registration in `orch/daemon/main.py`, enqueue helper consumed by `qa.py`. | S03 |
| S05 | code-review-impl | Review S03 (backend) | — |
| S06 | code-review-impl | Review S04 (pipeline) | — |
| S07 | api-impl | `dashboard/routers/conversations.py` (4 endpoints), modifications to `dashboard/routers/code_qa.py` (`conversation_id` field, `meta` SSE preamble, persistence on request + `__DONE__`, summarization-job enqueue), session-cookie middleware in `dashboard/app.py`, router registration. | S08 |
| S08 | frontend-impl | `dashboard/static/chat/composer.js` (send conversation_id, ignore client-history), `dashboard/static/chat/stream.js` (parse `meta` event, capture conversation_id), `dashboard/static/chat/panel.js` (replay on open, "New chat" button, TTL rotation), `dashboard/templates/chat/panel.html` ("New chat" button). | S07 |
| S09 | code-review-impl | Review S07 (api) | — |
| S10 | code-review-impl | Review S08 (frontend) | — |
| S11 | tests-impl | Coverage gap fill: full multi-turn integration, summarization preserves identity, hard-budget enqueues exactly one job, condense fallback when LLM unavailable, session-cookie scoping, archive endpoint, TTL rotation. | — |
| S12 | code-review-impl | Review S11 (tests) | — |
| S13 | code-review-final-impl | Global cross-agent review | — |
| S14 | qv-gate (lint) | `make lint` | — |
| S15 | qv-gate (format) | `make format-check` | — |
| S16 | qv-gate (typecheck) | `make type-check` | — |
| S17 | qv-gate (unit-tests) | `make test-unit` | — |
| S18 | qv-gate (integration-tests) | `make test-integration` | — |
| S19 | qv-browser | Browser verification of memory + follow-up retrieval + refresh + "New chat" + no regressions | — |

### Database Changes

- **New tables**: `chat_conversations`, `chat_messages`, `chat_summarization_jobs`
- **Modified tables**: None
- **Migration notes**:
  - One new revision; `down_revision` is the current head (run `alembic history` to discover).
  - Create Postgres ENUM `chat_message_role` with values `('user', 'assistant', 'system')`.
  - `chat_conversations` columns: `id TEXT PK (gen_random_uuid()::text)`, `project_id TEXT NOT NULL`, `session_id TEXT NOT NULL`, `module_path TEXT NULL`, `context_level TEXT NOT NULL DEFAULT 'architecture'`, `title TEXT NULL` (auto-generated from first user question, truncated to 80 chars), `rolling_summary TEXT NULL`, `summary_through_message_id TEXT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `last_active_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `archived_at TIMESTAMPTZ NULL`. Indexes: `(project_id, session_id, last_active_at DESC) WHERE archived_at IS NULL` (covers the "find recent active conversation for this session" lookup).
  - `chat_messages` columns: `id TEXT PK (gen_random_uuid()::text)`, `conversation_id TEXT NOT NULL FK chat_conversations(id) ON DELETE CASCADE`, `role chat_message_role NOT NULL`, `content TEXT NOT NULL`, `token_count INTEGER NOT NULL DEFAULT 0`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Index: `(conversation_id, created_at)`. **Append-only** per `orch/CLAUDE.md` convention; no UPDATE statements except setting `metadata.error=true` on a partial-error message immediately after insert (which writes within the same transaction as the insert and is the single allowed exception).
  - `chat_summarization_jobs` columns: `id TEXT PK`, `conversation_id TEXT NOT NULL FK`, `status TEXT NOT NULL DEFAULT 'queued'` (`queued|running|completed|failed|cancelled`), `messages_summarized INTEGER NOT NULL DEFAULT 0`, `summary_through_message_id TEXT NULL`, `error_message TEXT NULL`, `triggered_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `started_at TIMESTAMPTZ NULL`, `completed_at TIMESTAMPTZ NULL`, `created_at`/`updated_at`. Unique partial index `(conversation_id) WHERE status IN ('queued', 'running')` to enforce "at most one in-flight summarization per conversation".
  - **No FTS trigger** on these tables — chat content is not searched in v1.
  - `downgrade()` drops the three tables and the ENUM (in reverse order). No data loss concern: this is a new feature with no pre-existing rows to preserve.
- **No multi-project isolation issue** — `chat_conversations.project_id` is a plain `TEXT`, not a composite PK. The current iw-ai-core convention uses composite PKs `(project_id, id)` only for orchestration tables; jobs tables (`code_index_jobs`, `doc_generation_jobs`) use single-column `id` PKs with `project_id` as a regular column. Follow that pattern.

### API Changes

- **New endpoints**:
  - `GET /api/projects/{project_id}/conversations` — list recent (returns `[{conversation_id, title, last_active_at, module_path, message_count}, ...]`)
  - `GET /api/projects/{project_id}/conversations/{conv_id}/messages` — full replay (returns `{conversation_id, title, rolling_summary, last_active_at, messages: [{role, content, created_at, metadata}, ...]}`)
  - `POST /api/projects/{project_id}/conversations` — create explicit new (returns `{conversation_id}`)
  - `POST /api/projects/{project_id}/conversations/{conv_id}/archive` — soft-archive (returns `{archived_at}`)
- **Modified endpoints**:
  - `POST /api/projects/{project_id}/code/qa` — request body adds optional `conversation_id` field; SSE response gains a leading `event: meta` frame with `data: {"conversation_id": "..."}`. The deprecated `conversation_history` field is still accepted (no schema break) but is ignored server-side.

### Frontend Changes

- **New components**:
  - "New chat" header button in `dashboard/templates/chat/panel.html` (between the title and the collapse button).
- **Modified components**:
  - `dashboard/static/chat/composer.js` — send `conversation_id` from localStorage instead of empty `conversation_history`.
  - `dashboard/static/chat/stream.js` — handle `event: meta` frame; emit `onMeta(data)` callback.
  - `dashboard/static/chat/panel.js` — on panel open, fetch and replay last conversation if recent; "New chat" handler; TTL check before send.
  - `dashboard/templates/chat/panel.html` — add "New chat" button + accessible label.

## File Manifest

All files for this work item live under `ai-dev/active/F-00077/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00077_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00077_S01_Database_prompt.md` | Prompt | Migration + ORM models for chat_conversations/messages/jobs |
| `prompts/F-00077_S02_CodeReview_Database_prompt.md` | Prompt | Review S01 |
| `prompts/F-00077_S03_Backend_prompt.md` | Prompt | Repositories, condense, summarize, qa.py modifications |
| `prompts/F-00077_S04_Pipeline_prompt.md` | Prompt | chat_summarization_poller, daemon registration |
| `prompts/F-00077_S05_CodeReview_Backend_prompt.md` | Prompt | Review S03 |
| `prompts/F-00077_S06_CodeReview_Pipeline_prompt.md` | Prompt | Review S04 |
| `prompts/F-00077_S07_API_prompt.md` | Prompt | Conversation endpoints, code_qa.py modifications, session middleware |
| `prompts/F-00077_S08_Frontend_prompt.md` | Prompt | composer.js / stream.js / panel.js / panel.html |
| `prompts/F-00077_S09_CodeReview_API_prompt.md` | Prompt | Review S07 |
| `prompts/F-00077_S10_CodeReview_Frontend_prompt.md` | Prompt | Review S08 |
| `prompts/F-00077_S11_Tests_prompt.md` | Prompt | Coverage fill |
| `prompts/F-00077_S12_CodeReview_Tests_prompt.md` | Prompt | Review S11 |
| `prompts/F-00077_S13_CodeReview_Final_prompt.md` | Prompt | Cross-agent review |
| `prompts/F-00077_S19_BrowserVerification_prompt.md` | Prompt | End-to-end browser verification |

Implementation files referenced (sources of truth; modified by the steps above):

| Path | Layer |
|------|-------|
| `orch/db/models.py` | Database |
| `orch/db/migrations/versions/<new>_F-00077_chat_conversations.py` | Database |
| `orch/rag/chat_repo.py` | Backend |
| `orch/rag/condense.py` | Backend |
| `orch/rag/summarize.py` | Backend |
| `orch/rag/qa.py` | Backend |
| `orch/rag/CLAUDE.md` | Backend (docs) |
| `orch/daemon/chat_summarization_poller.py` | Pipeline |
| `orch/daemon/main.py` | Pipeline |
| `dashboard/app.py` | API (middleware + router registration) |
| `dashboard/routers/code_qa.py` | API |
| `dashboard/routers/conversations.py` | API |
| `dashboard/static/chat/composer.js` | Frontend |
| `dashboard/static/chat/stream.js` | Frontend |
| `dashboard/static/chat/panel.js` | Frontend |
| `dashboard/templates/chat/panel.html` | Frontend |
| `pyproject.toml` | Database (tiktoken dep) |
| `uv.lock` | Database |

Reports are created during execution in `ai-dev/active/F-00077/reports/`.

## Acceptance Criteria

### AC1: Naming recall across turns

```
Given a fresh conversation (no conversation_id in localStorage) on the
      Code page for project iw-ai-core, context_level "architecture"
When  the user sends "my name is sergio" and waits for the answer to
      complete, then sends "what is my name?"
Then  the second answer contains the substring "sergio" (case-insensitive)
And   the second request body included the conversation_id captured
      from the first SSE response's `meta` event
And   the server's qa.py loaded both prior turns from chat_messages
      (not from request.conversation_history)
```

### AC2: Follow-up retrieval is contextualized via condense

```
Given a conversation where turn 1 asks "what does keep_alive do in
      orch/daemon/main.py?" and the assistant has answered with chunks
      from that file
When  the user sends "explain how it works" as turn 2
Then  before retrieval, condense_query() is invoked and produces a
      standalone query containing at least one of the tokens
      "keep_alive" or "orch/daemon/main.py" (case-insensitive)
And   the LanceDB retrieval uses the condensed query (verifiable in
      the qa.py call site)
And   the answer cites at least one chunk from orch/daemon/main.py
And   the original user message "explain how it works" is what appears
      in chat_messages for turn 2 (not the condensed form)
```

### AC3: Refresh persistence within TTL

```
Given an active conversation with three completed turns and
      last_active_at within the last 4 hours
When  the user reloads the browser tab and the chat panel auto-expands
      (or is opened)
Then  the panel.js calls GET /conversations/{id}/messages and renders
      all three prior messages in the message log
And   sending a new message reuses the same conversation_id
```

### AC4: Explicit "New chat" reset

```
Given an active conversation with messages
When  the user clicks the "New chat" header button
Then  the chat-messages DOM is reset to the empty state
And   the localStorage key for this (project_id, module_path) no
      longer contains the prior conversation_id
And   the next sent message creates a NEW conversation_id (different
      from the prior one) — verifiable by inspecting the SSE meta event
And   the prior conversation row remains in the DB (not deleted)
```

### AC5: TTL auto-rotation after 4h

```
Given a conversation_id stored in localStorage where the cached
      last_active_at is more than 4 hours ago
When  the user sends a new message
Then  the client clears the stale conversation_id BEFORE sending so
      the server creates a new conversation
And   the SSE meta preamble returns a new conversation_id
And   the cached last_active_at is updated to "now"
```

### AC6: Hard-budget triggers background summarization

```
Given a conversation whose total chat_messages.token_count for unsummarized
      messages exceeds HISTORY_HARD_BUDGET_TOKENS (6000) after the latest
      assistant message persists
And   no chat_summarization_jobs row for this conversation has status
      'queued' or 'running'
When  qa.py finishes streaming the assistant message
Then  exactly one chat_summarization_jobs row is enqueued with
      status='queued' and conversation_id=<this conversation>
And   within one daemon poll cycle, the job transitions
      queued → running → completed
And   chat_conversations.rolling_summary is non-NULL afterwards
And   chat_conversations.summary_through_message_id points to the
      message at the boundary (last message included in the summary)
```

### AC7: Summarization preserves identity facts

```
Given a long conversation (compaction triggered) where turn 2 was
      "my name is sergio"
When  the summarization job completes and the user sends a new turn
      "what is my name?"
Then  the answer contains "sergio" (case-insensitive)
And   chat_conversations.rolling_summary contains the substring
      "sergio" (verifiable assertion on the summary text)
```

### AC8: Token-budget truncation prevents context overflow

```
Given a conversation with 6 turns where assistant messages are each
      ~1500 tokens (total > HISTORY_SOFT_BUDGET_TOKENS = 3000)
When  the user sends turn 7 BEFORE any summarization job has completed
Then  qa.py's _truncate_history (token-budget version) drops oldest
      messages until cumulative token_count <= 3000
And   the LLM call's input messages array contains the system prompt,
      the rolling_summary (if present, as a system note), the surviving
      kept-verbatim turns, and the new user question — total input
      tokens stay under MODEL_CONTEXT_LIMIT * 0.8
And   the answer streams successfully (no Ollama OOM, no truncation
      mid-stream)
```

### AC9: Existing chat paths keep working

```
Given the architecture-level chat (no module_path), the module-level
      chat (with module_path), and the work-item-aware classification
      path (qa.py:521-633) all currently working on main
When  this feature is merged
Then  each path continues to produce answers indistinguishable in
      shape from before (same SSE event types: token, phase, citation,
      image, error, done) PLUS the new leading meta event
And   slash commands (/explain, /diagram, /why, /findusages, /history)
      continue to work
And   citations render correctly with the per-answer attribution
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| First-ever turn (no conversation_id) | `conversation_id=None` in request | Server creates a new row in `chat_conversations`, returns its id in the SSE meta preamble; `chat_messages` gets one user row + one assistant row |
| `conversation_id` references a row from a different `session_id` | Stolen UUID from another browser session | Server returns 403; SSE never starts; client falls back to creating a new conversation transparently on retry |
| `conversation_id` references an archived row | `archived_at IS NOT NULL` | Server treats as not-found, creates a new conversation; meta preamble returns the new id |
| `conversation_id` references a row from a different `project_id` | URL says project A, body says conv from project B | Server returns 404; client recovers by clearing localStorage |
| Empty conversation (just created, no messages) | First turn races a "New chat" click | The empty conversation is fine; first user-message insert is the first row |
| Condense LLM call fails (Ollama down/timeout) | LLM exception | Fall back to using the raw question for retrieval; log a `daemon_event` of type `condense_failed`; do NOT fail the whole request |
| Summarize LLM call fails | Job exception | Mark job `status='failed'` with `error_message`; on next hard-budget overflow, daemon attempts a fresh job (the unique partial index allows re-enqueue once status is no longer queued/running) |
| Two rapid back-to-back turns when summary not yet ready | User sends turn N+1 while job from turn N is still running | qa.py uses token-budget truncation as the fallback (no summary prepend); behavior is graceful, not blocking |
| User sends a 1MB message | Request body exceeds chat_messages safe size | Reject at the FastAPI request schema (`question` already has `max_length=1000` in current code at `code_qa.py:79-86`); no DB write |
| 0 messages in conversation but `rolling_summary` set | Impossible state but defensive | qa.py treats summary as authoritative; messages array empty is fine |
| Session cookie missing | First-ever request from new browser | Middleware sets the cookie; current request gets the new session_id; conversation_id (if provided) is rejected because session_id won't match |
| `module_path` changes mid-conversation | User navigates from module A to module B with same conversation_id | The conversation continues; the module_path field is stored on the FIRST turn only (snapshot) — answers naturally shift focus per-turn from the new question |
| Browser without localStorage (incognito + privacy mode) | localStorage throws on access | Frontend falls back to in-memory only; no replay on reload (acceptable graceful degradation) |
| Stream interrupted mid-flight | Connection drops after 200 tokens | Partial assistant content is persisted with `metadata.error=true`, `metadata.error_reason="stream_disconnected"`; conversation continues; next turn's history excludes broken assistant message via a server-side filter (status=clean) |
| User asks a question with NO history | `len(history) < 2` | `condense_query` short-circuits and returns the question unchanged; no extra LLM call |
| Conversation with only system-role messages (synthetic case) | History contains no user/assistant pairs | Treated as no history; condense short-circuits |
| `tiktoken` doesn't have a tokenizer for the configured Ollama model | Unknown model name | Use approximate `len(text) // 4` heuristic with a logged warning; do NOT crash |
| Both `conversation_history` (deprecated) and `conversation_id` sent | Legacy client | Server ignores `conversation_history` entirely; uses DB-loaded history scoped to `conversation_id` |

## Invariants

Conditions that **must hold true** after implementation. Each maps to a test.

1. `chat_messages` is append-only — no UPDATE statements outside of the same-transaction `metadata.error=true` flag set immediately after insert.
2. At most one `chat_summarization_jobs` row per conversation has `status IN ('queued', 'running')` — enforced by a UNIQUE partial index.
3. `chat_messages.token_count` is set on insert (computed via `tiktoken` for known models, `len(content)//4` heuristic otherwise) and never updated.
4. The condense step is invoked iff `len(prior_history) >= 2`; with fewer turns the function returns the input question verbatim and makes no LLM call.
5. The `conversation_id` SSE preamble is emitted BEFORE any token event (so the client always captures the id, even on stream-error mid-flight).
6. `conversation_history` field on `QARequest` is accepted (back-compat) but ignored server-side; the server's only history source is `chat_messages`.
7. The cross-project / cross-session isolation NEVER returns a conversation belonging to a different `(project_id, session_id)`; all four conversation endpoints filter by both.
8. The hardening prompt lines ("trust most recent on contradictions", "do not claim memory beyond provided history") are present in every system prompt produced by `qa.py` for code-QA, regardless of context_level.
9. The TTL is enforced client-side (4h since cached `last_active_at` → clear conversation_id before send); the server does NOT delete or hide conversations purely on age — they archive only when the user explicitly archives or 30 days pass without activity (deferred — only the listing endpoint filters; rows persist).
10. The Subagent Result Contract for browser_verification is satisfied with at least 5 verifications (V1..V5) covering AC1, AC2, AC3, AC4, plus a No-Regressions sweep.

## Dependencies

- **Depends on**: None (F-00076's `impacted_paths` field is now standard but already merged — this design follows that convention).
- **Blocks**: None.

## TDD Approach

- **Unit tests**:
  - `orch/rag/condense.py::condense_query()` — short-circuits with <2 turns; with ≥2 turns, calls LLM with the documented prompt; returns the LLM output stripped; falls back to original question on LLM exception.
  - `orch/rag/summarize.py::summarize_history()` — produces text; preserves named-entity tokens injected via fixture (e.g. "sergio", "F-00055", "orch/daemon/main.py"); fails gracefully on LLM exception.
  - `orch/rag/qa.py::_truncate_history()` (token-budget version) — drops oldest first; respects `HISTORY_SOFT_BUDGET_TOKENS`; preserves the last 2 turns even if they alone exceed the budget (correctness over budget); handles empty input.
  - `orch/rag/chat_repo.py` — happy-path CRUD; conversation scoping; conversation_id+project_id+session_id triple-filter on all reads.
- **Integration tests** (testcontainer with FTS triggers wired up per `tests/CLAUDE.md`):
  - Full multi-turn flow: insert conversation, send three turns through the actual `qa.py` (LanceDB stubbed), assert messages persisted, assert condense was called on turns 2 and 3, assert AC1 (name recall) and AC2 (follow-up retrieval).
  - Hard-budget overflow enqueues exactly one `chat_summarization_jobs` row.
  - Daemon poller picks up the job, calls a stubbed `summarize_history`, writes `rolling_summary`, transitions job to 'completed'.
  - Subsequent turn loads `rolling_summary` and includes it in the system message stack.
  - Archive endpoint sets `archived_at`; archived conversations are excluded from `GET /conversations` list.
  - Session-cookie middleware sets the cookie when absent; conversation requests with mismatched session_id return 403.
  - TTL rotation: client-side test (jsdom or similar) verifying clear-before-send when `last_active_at` is stale.
- **Edge cases** (mandatory from Boundary Behavior table):
  - Stolen conversation_id from another session → 403.
  - Archived conversation → treated as not-found.
  - Cross-project conversation_id → 404.
  - Condense LLM failure → falls back to raw question; `daemon_event` of type `condense_failed` emitted.
  - Summarization failure → job marked failed; re-enqueue allowed on next overflow.
  - Stream disconnect → partial assistant message persisted with `metadata.error=true`.
  - Browser without localStorage → no crash; in-memory fallback.
  - tiktoken missing tokenizer → heuristic fallback.

## Notes

- **Why a separate `chat_summarization_jobs` table** rather than reusing `code_index_jobs` or `doc_generation_jobs`: keeping job tables single-purpose matches the project's existing convention (each background job type has its own table — `code_index_jobs` for indexing, `doc_generation_jobs` for AI doc regen, `test_runs` for tests/quality). It also keeps the `status` value vocabulary closed and lets the daemon poller filter by table without WHERE-on-job_type.
- **Why the cookie-based session model rather than a User table**: there is no authenticated-user concept in iw-ai-core today (single-developer dashboard). A persistent cookie gives us per-browser scoping for free without introducing auth. When/if a User model is added, `chat_conversations.session_id` becomes a thin wrapper around `user_id` and the migration is mechanical.
- **Why `tiktoken` for token counting**: it has tokenizers for OpenAI/Anthropic models out of the box and a robust default (`cl100k_base` / `o200k_base`). Ollama doesn't expose a tokenizer over the network, so for local models we use `cl100k_base` as a *close-enough* proxy with documented imprecision (typical drift <10%). The heuristic fallback (`len(text)//4`) is a final guard against a bad model name.
- **Why background summarization rather than synchronous**: the user-perceived latency for the answer turn must stay close to current. Ollama summarization of 5k tokens of history takes 1-3s on the project's local hardware; running synchronously on the trigger turn doubles its perceived latency. Background poller is the cleaner pattern, and the daemon already has the doc_job_poller as a precedent (`orch/daemon/doc_job_poller.py`).
- **Why both soft and hard budgets**: the soft budget (3000 tokens) controls per-turn truncation — it's the cheap path. The hard budget (6000 tokens) is the trigger for compaction. Two thresholds avoid thrashing: a single threshold means we'd compact too eagerly on borderline conversations, and reverse-overflow into the truncation path even after compaction.
- **Why we keep `MAX_HISTORY_TURNS` removable**: the new code reads from DB and applies token-budget truncation, so the existing constant becomes dead. S03 deletes it to avoid dead-code drift. The old `_truncate_history` signature `(history: list[dict[str, str]]) -> list[dict[str, str]]` is preserved for the call sites that already pass dicts (qa.py:167, qa.py:543, qa.py:608) — only the internals change.
- **Why hardening prompt lines on every system prompt**: prompt-injection persistence across turns is a real concern (OWASP LLM01:2025). Keeping history in the `messages` array (already the case) is the structural mitigation; the explicit instruction lines are a belt-and-braces measure that costs ~30 tokens per turn.
- **`code_qa.py` request flow**: the file's `_run_qa_in_thread()` (lines 138-207) already handles dispatch into a thread pool; the persistence calls fit naturally in the SSE generator (`_sse_generator()`, lines 210-327). The user-message persist happens BEFORE the thread spawn (so the row exists if the thread crashes); the assistant-message persist happens after the queue receives the `__DONE__` sentinel.
- **F-00076 has just been merged** introducing the "Impacted Paths" convention. This design follows it; `WorkItem.impacted_paths` will be auto-populated from the section above.
- **`.iw-orch.json`** for the iw-ai-core project does not currently set `browser_verification.enabled=true` for self-builds. Verify with the operator before this work item is approved that the worktree-compose stack will be available; otherwise S19 will report `ENV_DATA_MISSING` and the orchestrator will fail-soft.
