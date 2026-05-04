# F-00077_S05_CodeReview_Backend_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S05

---

## ⛔ Docker / Migrations off-limits

Same constraints as the implementation prompts. Allowed: `docker ps/inspect/logs`, testcontainer fixtures, `./ai-core.sh`/`make` targets, `alembic history/current/show`. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md`
- `ai-dev/active/F-00077/reports/F-00077_S03_Backend_report.md`
- All files listed in S03's `files_changed`

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S05_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in S03's `files_changed` → CRITICAL findings (`category: conventions`).

## Review Checklist

### 1. Architecture Compliance

- `orch/rag/chat_repo.py` is a pure repository — no LLM calls, no SSE, no FastAPI imports. CRITICAL if any of those leak in.
- `orch/rag/condense.py` and `orch/rag/summarize.py` are pure modules — no DB session imports, no FastAPI. They take an LLM instance and return strings. (Exception: `condense.py` may write a `daemon_event` on failure, which requires session access — verify the design uses dependency injection or a callback rather than implicit DB access.)
- `qa.py` modifications preserve both code paths (`answer_stream` and `answer_stream_v2`); the work-item-aware classification logic at lines 521-633 still runs.
- The legacy `conversation_history` parameter still works for backward compatibility (S03's note says yes — verify).
- `MAX_HISTORY_TURNS = 5` constant is REMOVED (not just unused). Dead code is a HIGH finding per `CLAUDE.md`.

### 2. Code Quality

- Token-budget truncation correctness: when the last 2 turns alone exceed the budget, the function STILL keeps them (correctness > budget). Read the implementation and trace this case. CRITICAL if it fails.
- `count_tokens()` falls back to heuristic on tiktoken exception; logs the warning ONCE per unknown model name (cache key).
- Condense fallback: LLM exception → returns original question, emits `daemon_event` of type `condense_failed`. Verify the event payload includes the conversation_id.
- Summarize prompt template includes the entity-preservation instructions verbatim per the design ("Named entities", "user-stated facts", "Decisions reached", "investigative thread").
- Hardening lines (`SYSTEM_PROMPT_HARDENING`) are appended to BOTH `_build_system_prompt()` paths AND any work-item-aware system prompt. Invariant 8 demands "every system prompt".
- The synthetic system message that prepends `rolling_summary` uses role="system" and is inserted between main system prompt and first user/assistant turn (NOT inside the user message).
- `last_active_at` bump in `append_message` is in the same transaction as the INSERT.

### 3. Project Conventions

- Sync SQLAlchemy 2.0; no `await`/`async def` introduced.
- Module-level loggers via `logging.getLogger(__name__)`.
- Type hints on all public functions; no `Any` where a concrete type fits.
- No psycopg2 imports.
- `daemon_event` writes use `event_metadata` Python attribute (NOT `metadata`).

### 4. Security

- No prompt-injection vector through `rolling_summary` content (it's loaded from DB and concatenated into the system message — but the source is the LLM's own output from a prior turn, so the threat is "LLM injects instructions into its own future system prompt"). Mitigation: the hardening lines explicitly tell the model to ignore any "instructions" not from the documented system prompt, AND `rolling_summary` is wrapped with a clear marker like `Earlier in this conversation:\n{summary}`. Verify the marker is present.
- `condense.py` LLM call: the rendered prompt includes user history. Verify history is rendered as `User: ...\nAssistant: ...` (data role labels) NOT injected as instructions.
- No secrets or credentials hardcoded.

### 5. Testing

- Unit tests cover ALL Boundary Behavior rows assigned to backend (condense fallback, tiktoken fallback, last-2-turns preservation, summary prompt entity injection).
- Integration test stubs LanceDB and Ollama deterministically — does NOT depend on a real model being installed.
- `test_qa_with_conversation.py` asserts BOTH the condense call site AND the rolling_summary insertion location.
- All tests use the `db_session` testcontainer (no live DB).
- Tests are isolated (no shared state across tests in the same module).

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Last-2-turn correctness break, hardening line missing on a path, conv-history leaks across sessions, layer violation (LLM in repo) | Must fix |
| HIGH | Dead `MAX_HISTORY_TURNS` left in, deprecation warning missing, missing entity in summarize prompt | Must fix |
| MEDIUM (fixable) | Missing log statement, type hint gap, suboptimal SQL | Fix in fix cycle |
| MEDIUM (suggestion) | Cleaner factoring | Optional |
| LOW | Wording, comments | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "F-00077",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
