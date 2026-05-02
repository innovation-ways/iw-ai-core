# F-00077_S07_API_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step**: S07
**Agent**: api-impl

---

## ⛔ Docker / Migrations off-limits

Same constraints. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md` — sections: API Changes, AC1–AC6, AC8, AC9, Boundary Behavior (cross-session, cross-project, archived, missing-cookie cases)
- `ai-dev/active/F-00077/reports/F-00077_S03_Backend_report.md`
- `ai-dev/active/F-00077/reports/F-00077_S04_Pipeline_report.md`
- `dashboard/routers/code_qa.py` — current implementation. KEY references:
  - `QARequest` and `ConversationMessage` schemas at lines 74-87
  - `_run_qa_in_thread()` at lines 138-207
  - `_sse_generator()` at lines 210-327
  - main endpoint handler at lines 330-379
- `dashboard/app.py` — current FastAPI factory + middleware setup
- `dashboard/CLAUDE.md` — router thinness, htmx + SSE conventions
- `orch/rag/chat_repo.py` from S03 + S04 — repo functions you call
- `orch/rag/qa.py` from S03 — `answer_stream` and `answer_stream_v2` signatures

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S07_API_report.md`
- `dashboard/routers/conversations.py` — NEW (4 endpoints)
- `dashboard/routers/code_qa.py` — MODIFIED
- `dashboard/app.py` — MODIFIED (session-cookie middleware + register conversations router)
- Test files (see Tests section)

## Context

You are wiring up the HTTP surface for F-00077: a session cookie that scopes conversations per browser, a CRUD-ish conversations router, and modifications to the existing `code_qa` SSE endpoint to accept and emit `conversation_id`, persist messages, and trigger summarization.

Read the design FIRST. Then `dashboard/CLAUDE.md` (router thinness — business logic stays in `orch/`).

## Requirements

### 1. Session-Cookie Middleware (`dashboard/app.py`)

Add a FastAPI middleware that, on each request:
- Reads cookie `iw_chat_session`.
- If absent: generate a UUID v4, set as cookie with `Max-Age=7776000` (90 days), `SameSite=Lax`, `HttpOnly=False` (the JS reads it for localStorage scoping), `Secure=False` for localhost (read from config — match other dashboard cookies if any).
- Make `request.state.session_id` always available downstream.

Implementation: a `BaseHTTPMiddleware` subclass or a function-style middleware via `app.middleware("http")`. Match the existing style in `dashboard/app.py`. If no middleware pattern exists yet, prefer the `app.middleware("http")` decorator form.

Add a small helper `dashboard/dependencies.py::get_session_id(request: Request) -> str` that reads `request.state.session_id` and raises `RuntimeError` if absent (defensive — middleware should always set it).

### 2. New Router `dashboard/routers/conversations.py`

```python
router = APIRouter(prefix="/api/projects/{project_id}/conversations", tags=["conversations"])

@router.get("", response_model=list[ConversationListItem])
def list_conversations(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    session_id: str = Depends(get_session_id),
):
    """Returns up to 50 non-archived conversations for (project_id,
    session_id), ordered by last_active_at DESC."""

@router.post("", response_model=NewConversationResponse, status_code=201)
def new_conversation(
    project_id: str,
    body: NewConversationRequest,  # {module_path?: str, context_level?: str}
    db: Session = Depends(get_db),
    session_id: str = Depends(get_session_id),
):
    """Creates a fresh ChatConversation and returns its id."""

@router.get("/{conversation_id}/messages", response_model=ConversationMessagesResponse)
def get_messages(
    project_id: str,
    conversation_id: str,
    db: Session = Depends(get_db),
    session_id: str = Depends(get_session_id),
):
    """Returns full message replay. 404 if not found OR cross-session OR
    cross-project. Does NOT include rolling_summary as a message —
    returns it as a separate field for client-side rendering."""

@router.post("/{conversation_id}/archive", response_model=ArchiveResponse)
def archive(...):
    """Soft-deletes; returns {archived_at}. Idempotent."""
```

Schemas (Pydantic BaseModel) — keep concise:

```python
class ConversationListItem(BaseModel):
    conversation_id: str
    title: str | None
    last_active_at: datetime
    module_path: str | None
    context_level: str
    message_count: int

class NewConversationRequest(BaseModel):
    module_path: str | None = None
    context_level: str = "architecture"

class NewConversationResponse(BaseModel):
    conversation_id: str

class ConversationMessageView(BaseModel):
    role: str
    content: str
    created_at: datetime
    metadata: dict = Field(default_factory=dict)

class ConversationMessagesResponse(BaseModel):
    conversation_id: str
    title: str | None
    rolling_summary: str | None
    last_active_at: datetime
    messages: list[ConversationMessageView]

class ArchiveResponse(BaseModel):
    archived_at: datetime | None
```

Triple-filter EVERY DB read by `(project_id, session_id, conversation_id)`. A mismatch returns 404 (not 403, to avoid leaking conversation existence to other sessions). The exception is when `archived_at IS NOT NULL` — also returns 404.

Register the router in `dashboard/app.py` alongside the other routers.

### 3. Modify `dashboard/routers/code_qa.py`

a) **`QARequest` schema** (lines 79-87):
   - Add `conversation_id: str | None = Field(default=None)`.
   - Keep `conversation_history: list[ConversationMessage] = Field(default_factory=list)` for backward compatibility but add a docstring noting it's deprecated and ignored.

b) **Main endpoint handler** (lines 330-379):
   - Accept `request: Request` so the session_id is reachable.
   - Resolve / create the conversation via `chat_repo.get_or_create_conversation(...)` (this is in S03's repo). Persist the user message via `chat_repo.append_message(role='user', ...)` BEFORE spawning the worker thread. Commit synchronously so the row exists if the thread crashes.
   - Pass `conversation_id` and `db` (via a session factory — see below) into the SSE generator and the QA engine call.

c) **SSE generator** (`_sse_generator` at lines 210-327):
   - Emit a leading `event: meta` frame BEFORE any `event: token`:
     ```
     event: meta
     data: {"conversation_id": "<uuid>"}

     ```
     (newline-newline as the SSE record separator).
   - On `__DONE__` sentinel: persist the full assistant message via `chat_repo.append_message(role='assistant', metadata={...phase + render_id...})`. Commit.
   - After persistence, call `chat_repo.enqueue_summarization_if_needed(db, conversation_id=..., hard_budget_tokens=qa.HISTORY_HARD_BUDGET_TOKENS)`. Log if a job was enqueued.
   - On exception during streaming: persist the partial content with `metadata={"error": True, "error_reason": "<...>"}` so the row is still append-only-with-error-flag.
   - Be careful: the existing `_run_qa_in_thread` runs in a thread pool and the SSE generator is async — the DB session must NOT be shared across the thread boundary. Use a session factory and open a fresh session in the SSE generator after the queue receives `__DONE__`.

d) **Removal**: the `conversation_history` payload conversion at line 367 (`[m.model_dump() for m in request.conversation_history]`) becomes dead. Replace with the DB-loaded history (server-side via `chat_repo.list_messages_for_context()`). Delete the conversion line.

### 4. Tests

`tests/dashboard/routers/test_conversations.py`:
- TestClient sets the cookie via a fixture; the middleware accepts it.
- POST creates a conversation; GET returns it.
- GET /messages returns ordered messages.
- Cross-session: TestClient with a different cookie cannot read the conversation (404).
- Cross-project: project A's conversation_id under project B's URL → 404.
- Archive sets `archived_at`; subsequent GET returns 404.
- Idempotent archive: calling twice returns the same timestamp.
- Listing: archived conversations excluded; ordered by `last_active_at DESC`.

`tests/dashboard/routers/test_code_qa_with_conversation.py`:
- POST `/api/projects/{id}/code/qa` with `conversation_id=None` → SSE stream begins with `event: meta` containing a fresh conversation_id, then tokens.
- POST with the returned conversation_id continues the conversation; the user message persists; the assistant message persists after `__DONE__`.
- POST with a stranger's conversation_id (different session cookie) → SSE meta returns a NEW id (server treats stranger ID as not-found and creates fresh).
- Stream interrupted: simulate an exception during the generator; assert a `chat_messages` row exists with `metadata.error=true`.
- Hard-budget overflow → exactly one `chat_summarization_jobs` row with status='queued'.

`tests/integration/dashboard/test_session_cookie_middleware.py`:
- First request without cookie → response sets `iw_chat_session`.
- Second request with the cookie → middleware reads it; `request.state.session_id` matches.
- Cookie attributes: SameSite=Lax, Max-Age=7776000.

For the QA endpoint tests, you may need to stub `qa.answer_stream_v2` to a deterministic generator so the test doesn't depend on Ollama. Use `unittest.mock.patch` on the qa module functions.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- Routers are thin — business logic in `orch/`.
- htmx fragments under `templates/fragments/` MUST NOT extend `base.html`. (No new fragments here.)
- Use the existing `dependencies.py::get_db()` for DB sessions.
- SSE uses `text/event-stream` content type and writes records as `event: ...\ndata: ...\n\n`.

## TDD Requirement

Write `test_session_cookie_middleware.py` and `test_conversations.py` first. Implement after they fail.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

1. `make test-unit`
2. `make test-integration`

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "api-impl",
  "work_item": "F-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/app.py",
    "dashboard/dependencies.py",
    "dashboard/routers/conversations.py",
    "dashboard/routers/code_qa.py",
    "tests/dashboard/routers/test_conversations.py",
    "tests/dashboard/routers/test_code_qa_with_conversation.py",
    "tests/integration/dashboard/test_session_cookie_middleware.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
