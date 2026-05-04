# F-00077_S11_Tests_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step**: S11
**Agent**: tests-impl

---

## ⛔ Docker / Migrations off-limits

Same constraints. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md` — full ACs (1-9), Boundary Behavior (every row is mandatory test), Invariants (each maps to a test)
- All step reports S01..S08
- All files in S01..S08's `files_changed`

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S11_Tests_report.md`
- New / extended test files (see Coverage Gap Fill below)

## Context

You are the coverage backstop. S01..S08 each shipped tests for their own scope; some Boundary Behavior rows and ACs cut across multiple steps and need an end-to-end check. Your job is the gap-fill, not duplication. Read each step's tests first; only add tests for scenarios that nobody else tested.

Read `tests/CLAUDE.md` for testcontainer patterns. Read `orch/CLAUDE.md` for append-only / FTS conventions.

## Coverage Gap Fill

The mandatory new tests:

### 1. Full multi-turn integration (`tests/integration/rag/test_F00077_multi_turn_e2e.py`)

End-to-end exercise of the actual code paths from `dashboard/routers/code_qa.py` through `orch/rag/qa.py` to the DB.

- Stub Ollama LLM for both retrieval/answering AND condensing/summarizing (so the test is deterministic).
- Stub LanceDB to return a known chunk for queries containing "keep_alive".
- Call POST `/api/projects/iw-ai-core/code/qa` with `conversation_id=None` and question "what does keep_alive do in orch/daemon/main.py?". Capture the meta-event conversation_id.
- POST again with that conversation_id and question "explain how it works".
- Assert: the second turn's condense call produced a query containing "keep_alive" or "main.py" (case-insensitive substring on the captured LLM call).
- Assert: the answer streamed; tokens received; `__DONE__` reached; both messages persisted.
- Assert: AC1 — POST a third turn "what's my name?" with prior `[..., "user: my name is sergio", "assistant: ..."]` history → answer contains "sergio".

### 2. Summarization preserves identity (`tests/integration/rag/test_F00077_summary_preserves_identity.py`)

- Insert a 6-turn conversation where turn 2 = "my name is sergio".
- Set the assistant turns each to a fixture content of ~2000 tokens (use a hardcoded long string, no model needed).
- Stub the LLM passed to the daemon poller to a function that calls the actual `summarize_history()` against a stub LLM that returns a deterministic summary BUT echoes any names/file-paths in the input.
- Run `poll_chat_summarization_jobs(...)`.
- Assert: `chat_conversations.rolling_summary` contains "sergio".
- Re-run the QA path with the SAME conversation and question "what is my name?" — the system prompt MUST contain the rolling_summary; the answer MUST cite "sergio" (deterministic via the stub LLM).

### 3. Hard-budget enqueues exactly one job (`tests/integration/dashboard/test_F00077_enqueue_idempotency.py`)

- Seed a conversation with messages totaling 7000 token_count (above HARD_BUDGET=6000).
- Call POST `/api/projects/.../code/qa` with that conversation_id; let the SSE stream finish.
- Assert: exactly ONE row in `chat_summarization_jobs` with status='queued'.
- Call the same endpoint a second time without the daemon running.
- Assert: STILL exactly one row (the unique partial index blocks a duplicate). No exception bubbles up.

### 4. Condense fallback when LLM unavailable (`tests/integration/rag/test_F00077_condense_fallback.py`)

- Stub the LLM to raise `ConnectionError` on `complete()`.
- Call `condense_query(history, "explain how it works", llm)`.
- Assert: returns "explain how it works" verbatim.
- Assert: a `daemon_events` row was inserted with `event_type='condense_failed'`.

### 5. Session-cookie scoping (`tests/dashboard/test_F00077_session_isolation.py`)

- TestClient A sends a request → cookie set; conversation A created.
- TestClient B (no cookie) → middleware sets a different cookie; B tries to GET /messages with A's conversation_id → 404.
- TestClient B archives A's conversation_id → 404 (no leak: cannot tell whether the row exists).

### 6. Archive endpoint (`tests/dashboard/test_F00077_archive.py`)

- POST archive on an active conversation → returns `{archived_at}`.
- Subsequent GET /messages → 404.
- Listing → archived conversation NOT in the result.
- Idempotent: POST archive again → returns the SAME `archived_at` (not updated).
- New POST /code/qa with the archived conversation_id → server creates a NEW conversation; meta event returns the new id.

### 7. TTL rotation (Python-side smoke if no JS runner)

If a JS test runner is configured, write `tests/frontend/test_F00077_ttl_rotation.spec.js` that mocks `Date.now()` and asserts `getCachedConversation` returns null past TTL.

If no JS runner: a Python-side test loading the rendered chat panel HTML and asserting the TTL_MS constant is `4 * 60 * 60 * 1000` (string-grep on the bundled JS file). This is a weaker test but ensures the constant didn't drift.

### 8. Stream interruption persists partial content (`tests/integration/dashboard/test_F00077_stream_disconnect.py`)

- Patch the QA stream generator to raise after the third token.
- Call POST /code/qa.
- Assert: a `chat_messages` row exists for this conversation with `role='assistant'`, partial content, and `metadata={"error": true, "error_reason": "..."}`.
- Subsequent turn loads history — the partial assistant message is NOT included (filter by `metadata.error IS NULL OR metadata.error != true`).

### 9. Hardening lines present on EVERY system prompt (`tests/unit/rag/test_F00077_hardening_invariant.py`)

Per Invariant 8: the hardening lines must appear on every system prompt produced by `qa.py`. Loop over all 3 paths:
- `_build_system_prompt(context_level="architecture", ...)` → assert `SYSTEM_PROMPT_HARDENING in prompt`.
- `_build_system_prompt(context_level="module", ...)` → same.
- The work-item-aware system prompt assembled at qa.py:598 → same.

### 10. AC9 No-Regressions (`tests/integration/dashboard/test_F00077_no_regressions.py`)

- Send a chat with `context_level="module"` and `module_path="orch/daemon"`.
- Assert: SSE event types match prior contract (token, phase, citation, image, error, done) PLUS the new meta event.
- Slash commands `/explain`, `/diagram`, `/why`, `/findusages`, `/history` still produce the prior phase + citation behavior.

## Project Conventions

Read `tests/CLAUDE.md`. Specifically:

- Use `db_session` testcontainer fixture; replace psycopg URL.
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- No `importlib.reload(orch.config)`; use `monkeypatch.delenv()`.
- LLM stubs: prefer `unittest.mock.patch` on the module attributes used by qa.py (e.g. `orch.rag.qa._get_llm`).

## TDD Requirement

Each test in this step is the FIRST test for its scenario, so by definition this is RED. Write each one expecting it to pass against the existing implementation; if it fails, that's a regression in S01-S08 that the per-agent reviews should have caught — file a CRITICAL finding in your report and stop.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

1. `make test-unit`
2. `make test-integration`
3. ALL existing tests must still pass.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "tests-impl",
  "work_item": "F-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/rag/test_F00077_multi_turn_e2e.py",
    "tests/integration/rag/test_F00077_summary_preserves_identity.py",
    "tests/integration/dashboard/test_F00077_enqueue_idempotency.py",
    "tests/integration/rag/test_F00077_condense_fallback.py",
    "tests/dashboard/test_F00077_session_isolation.py",
    "tests/dashboard/test_F00077_archive.py",
    "tests/integration/dashboard/test_F00077_stream_disconnect.py",
    "tests/unit/rag/test_F00077_hardening_invariant.py",
    "tests/integration/dashboard/test_F00077_no_regressions.py"
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
