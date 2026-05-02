# F-00077_S03_Backend_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY container/volume/network management command. Allowed: `docker ps/inspect/logs`, testcontainer fixtures, `./ai-core.sh`/`make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do NOT run alembic upgrade/downgrade/stamp against the live orch DB (port 5433). Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md` — sections: Description, Scope, AC1, AC2, AC7, AC8, Invariants 4/6/8, Boundary Behavior (condense LLM failure, tiktoken-missing-tokenizer)
- `ai-dev/active/F-00077/reports/F-00077_S01_Database_report.md`
- `orch/rag/qa.py` — current implementation. Key references:
  - `MAX_HISTORY_TURNS` constant at line 59 (DELETE)
  - `_truncate_history()` at lines 309-318 (REWRITE for token budget)
  - `_build_system_prompt()` at lines 234-307 (ADD hardening lines)
  - `answer_stream()` at lines 76-187 (modify retrieval to use condensed query)
  - `answer_stream_v2()` at lines 521-633 (work-item-aware path; same condense + summary integration)
  - Message stack assembly at lines 169-174 (PREPEND rolling_summary as system note)
- `orch/rag/CLAUDE.md` — RAG pipeline, embedding model, TOP_K
- `orch/db/models.py` — new ORM classes from S01

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S03_Backend_report.md`
- `orch/rag/chat_repo.py` — NEW
- `orch/rag/condense.py` — NEW
- `orch/rag/summarize.py` — NEW
- `orch/rag/qa.py` — MODIFIED
- `orch/rag/CLAUDE.md` — MODIFIED (document the new pieces)
- Test files (see Tests section)

## Context

You are implementing the RAG-side memory and query-rewriting logic for F-00077. The ORM models from S01 are in `orch/db/models.py`. The daemon poller (S04) and API surface (S07) build on top of your work; do not assume they're done — your changes must be self-contained and testable in isolation.

Read the design FIRST. Then read `orch/rag/CLAUDE.md` for RAG conventions, `orch/CLAUDE.md` for SQLAlchemy patterns.

## Requirements

### 1. `orch/rag/chat_repo.py` — Repository

Provide a thin module with these functions, each accepting `db: Session` as first arg:

```python
def get_or_create_conversation(
    db: Session,
    *,
    project_id: str,
    session_id: str,
    conversation_id: str | None,
    module_path: str | None,
    context_level: str,
    first_question: str | None = None,
) -> ChatConversation:
    """If conversation_id is None or stale (archived/cross-session/cross-project),
    create a new ChatConversation. Otherwise return the existing one and bump
    last_active_at. The triple filter (project_id, session_id, NOT archived)
    is mandatory on the lookup — see Invariant 7."""

def append_message(
    db: Session,
    *,
    conversation_id: str,
    role: str,           # 'user' | 'assistant' | 'system'
    content: str,
    metadata: dict | None = None,
    token_count: int | None = None,  # if None, computed via count_tokens()
) -> ChatMessage:
    """Insert a chat_messages row. Computes token_count if not supplied.
    Bumps chat_conversations.last_active_at in the same transaction."""

def list_messages_for_context(
    db: Session,
    *,
    conversation_id: str,
    soft_budget_tokens: int,
) -> tuple[list[dict[str, str]], str | None]:
    """Returns (kept_messages, rolling_summary). Loads chat_messages newer
    than chat_conversations.summary_through_message_id (or all if no summary
    yet), drops oldest until cumulative token_count <= soft_budget_tokens
    while ALWAYS preserving the last 2 messages (correctness over budget).
    rolling_summary is the conversation's stored summary (or None)."""

def list_conversations_for_session(
    db: Session,
    *,
    project_id: str,
    session_id: str,
    limit: int = 50,
) -> list[ChatConversation]:
    """Returns non-archived conversations for the (project, session), ordered
    by last_active_at DESC. Used by GET /conversations endpoint in S07."""

def get_conversation(
    db: Session,
    *,
    conversation_id: str,
    project_id: str,
    session_id: str,
) -> ChatConversation | None:
    """Strict triple-filter; returns None on any mismatch. Never raises."""

def archive_conversation(
    db: Session,
    *,
    conversation_id: str,
    project_id: str,
    session_id: str,
) -> datetime | None:
    """Sets archived_at = now() if found and not already archived; returns
    the timestamp or None."""

def count_tokens(text: str, model_name: str | None = None) -> int:
    """Uses tiktoken with cl100k_base if model name is unknown, else best-match
    encoding. Falls back to len(text) // 4 + 1 if tiktoken raises. Logs a
    warning ONCE per unknown model name."""
```

Notes:
- All writes use the standard `db.add` + `db.flush` pattern (no `db.commit` — that's the caller's responsibility). The router (S07) commits.
- `count_tokens` caches the encoding object module-level for performance.
- `append_message`'s `last_active_at` bump uses `UPDATE chat_conversations SET last_active_at = now() WHERE id = :cid` — single statement, no SELECT.

### 2. `orch/rag/condense.py` — Query Rewriting

```python
def condense_query(
    history: list[dict[str, str]],
    question: str,
    llm: BaseLLM,
    *,
    max_tokens: int = 256,
) -> str:
    """If len(history) < 2, returns question unchanged (no LLM call).
    Otherwise calls llm.complete() with the CONDENSE_PROMPT (below).
    On any LLM exception, logs a daemon_event of type 'condense_failed'
    via orch.db.session and returns the original question (graceful
    degradation per Boundary Behavior).
    Returns the stripped LLM output."""
```

The condense prompt — store as a module-level constant:

```python
CONDENSE_PROMPT = """\
Given the conversation below and a follow-up question, rephrase the follow-up
question into a self-contained search query that captures the user's full
intent including any implicit references to earlier turns. Return ONLY the
rewritten query, no preamble, no quotes.

Conversation history:
{history}

Follow-up question: {question}

Standalone search query:"""
```

`{history}` is rendered as `User: ...\nAssistant: ...\n` for the last 4 turns at most (drop older for the condense step — we don't need full context here, just the immediate referent).

### 3. `orch/rag/summarize.py` — Compaction

```python
def summarize_history(
    messages: list[ChatMessage],
    llm: BaseLLM,
    previous_summary: str | None = None,
) -> str:
    """Produces a compact prose summary preserving named entities (file
    paths, function names, work-item IDs like F-00055), user-stated facts
    (names, preferences, project they're on), and decisions reached.

    If previous_summary is non-None, the prompt instructs the LLM to
    extend/refine it (avoiding wholesale replacement). On LLM exception,
    raises — the caller (daemon poller) marks the job 'failed'."""
```

The summarize prompt — module-level constant:

```python
SUMMARIZE_PROMPT = """\
Summarize the conversation below into a compact note that PRESERVES:
- Named entities (file paths, function names, work-item IDs like F-00055,
  module names, error messages quoted verbatim).
- Specific facts the user stated about themselves or their project (names,
  goals, preferences).
- Decisions reached or conclusions drawn.
- The user's current investigative thread (what they're trying to figure out).

DROP: pleasantries, rephrasing, the assistant's reasoning chain. Keep it
factual.

If a "Previous summary" is provided, EXTEND or REFINE it; don't restart.

Output 3-8 sentences.

{previous_section}

Conversation:
{conversation}

Summary:"""
```

### 4. `orch/rag/qa.py` — Modifications

a) **Delete** `MAX_HISTORY_TURNS = 5` (line 59) and `_truncate_history` (lines 309-318) — replace with token-budget version.

b) **Add** module-level constants:
```python
HISTORY_SOFT_BUDGET_TOKENS: int = 3000
HISTORY_HARD_BUDGET_TOKENS: int = 6000
SYSTEM_PROMPT_HARDENING: str = (
    "On contradictions in the user's statements, trust the most recent one. "
    "Do not claim to remember anything not present in the provided "
    "conversation history."
)
```

c) **Replace** `_truncate_history` with a thin wrapper that delegates to `chat_repo.list_messages_for_context` (the budget logic moved there) — OR keep a local pure helper if the caller already has loaded messages. Prefer the repo function for the live path; keep a small pure helper `_truncate_messages_to_budget(messages, budget)` for unit tests. Both must produce identical results given the same input.

d) **Modify** `answer_stream` (lines 76-187):
   - Accept new keyword arg `db: Session` and `conversation_id: str` (instead of `conversation_history`). Backwards-compat shim: if `conversation_history` is passed and `conversation_id` is None, USE the passed-in history (legacy test path), but log a deprecation warning.
   - Load messages from DB via `list_messages_for_context()` if `conversation_id` provided, else use `conversation_history` (legacy).
   - Call `condense_query(history, question, llm)` BEFORE `OllamaEmbedding.get_query_embedding(...)`. Use the condensed query for embedding + LanceDB retrieval. Retain the original `question` for the final user-message turn.
   - Fetch `rolling_summary` from `ChatConversation` (if `conversation_id`); when present, prepend it as a synthetic system message:
     ```python
     ChatMessage(role="system", content=f"Earlier in this conversation:\n{rolling_summary}")
     ```
     Insert this BETWEEN the main system prompt and the kept-verbatim history.
   - Append `SYSTEM_PROMPT_HARDENING` to the main system prompt (last paragraph).

e) **Modify** `answer_stream_v2` (lines 521-633) — apply the SAME treatment (condense before retrieval, summary prepend, hardening). The work-item-aware classification path uses different retrieval; that's fine — only the `_retrieve_evidence_bundle` call's query argument changes.

f) **Modify** `_build_system_prompt` (lines 234-307) — append `SYSTEM_PROMPT_HARDENING` to the final assembled prompt. Apply unconditionally (no flag).

### 5. `orch/rag/CLAUDE.md` — Doc update

Add a section at the bottom titled "Conversation memory (F-00077)" describing:

- Where conversations live (DB tables: chat_conversations, chat_messages, chat_summarization_jobs).
- The condense → retrieve → answer flow.
- The token-budget truncation strategy (soft = sliding window; hard = enqueue summarization).
- The hardening lines in the system prompt (and why).
- Where the daemon poller lives (`orch/daemon/chat_summarization_poller.py`, S04).

### 6. Tests

`tests/unit/rag/test_token_budget.py`:
- `_truncate_messages_to_budget` drops oldest first.
- Always preserves the last 2 messages even if they exceed the budget alone.
- Empty input → empty output.
- Below-budget input → unchanged.

`tests/unit/rag/test_condense.py`:
- `<2` history turns → returns question verbatim, no LLM call (mock LLM, assert call_count==0).
- `>=2` history turns → calls LLM with the documented prompt; returns stripped output.
- LLM raises → returns original question; emits a `daemon_event` of type `condense_failed` (assert via DB query against the testcontainer).

`tests/unit/rag/test_summarize.py`:
- Produces non-empty text given a fixture conversation with named entities.
- Asserts the prompt template injects entities into the rendered prompt (string-match).
- LLM raises → function re-raises (caller handles).

`tests/integration/rag/test_qa_with_conversation.py`:
- Insert a `ChatConversation` + 4 messages.
- Stub LanceDB retrieval (return a known chunk).
- Stub Ollama LLM with deterministic responses.
- Call `answer_stream(..., conversation_id=conv.id)`.
- Assert: condense was invoked with prior history; retrieval saw the condensed query; the answer message was streamed; the system prompt contained the hardening lines AND the rolling_summary (when set on conversation).

`tests/integration/rag/test_chat_repo.py`:
- get_or_create_conversation: cross-session lookup returns None → creates new.
- append_message updates last_active_at in the same transaction.
- list_messages_for_context skips messages older than `summary_through_message_id`.
- archive_conversation is idempotent (calling twice returns the original timestamp).

## Project Conventions

Read `orch/CLAUDE.md`, `orch/rag/CLAUDE.md`, `tests/CLAUDE.md`. Specifically:

- Sync SQLAlchemy 2.0; no async session.
- Module-level loggers via `logging.getLogger(__name__)`.
- LLM calls go through the existing Ollama client (don't introduce a second LLM client).
- `daemon_events` writes use the `event_metadata` Python attribute (NOT `metadata` — see Gotcha).

## TDD Requirement

RED phase: write `test_token_budget.py` and `test_condense.py` first. They must fail. Then write the implementations.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

1. `make test-unit`
2. `make test-integration`
3. Do NOT report `tests_passed: true` unless all pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/chat_repo.py",
    "orch/rag/condense.py",
    "orch/rag/summarize.py",
    "orch/rag/qa.py",
    "orch/rag/CLAUDE.md",
    "tests/unit/rag/test_token_budget.py",
    "tests/unit/rag/test_condense.py",
    "tests/unit/rag/test_summarize.py",
    "tests/integration/rag/test_qa_with_conversation.py",
    "tests/integration/rag/test_chat_repo.py"
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
