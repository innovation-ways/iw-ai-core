# F-00077 S03 — Backend Implementation Report

## Summary

Implemented the RAG-side memory and query-rewriting logic for F-00077 (Code chat conversation memory with persistence and query rewriting). All implementation files are self-contained and testable in isolation. The S04 daemon poller and S07 API surface build on top of this work.

## Files Changed / Created

| File | Change |
|------|--------|
| `orch/rag/chat_repo.py` | **CREATED** — Repository module: `get_or_create_conversation`, `append_message`, `list_messages_for_context`, `list_conversations_for_session`, `get_conversation`, `archive_conversation`, `count_tokens` (tiktoken with heuristic fallback), `truncate_messages_to_budget` |
| `orch/rag/condense.py` | **CREATED** — Query rewriting: `condense_query()` using CONDENSE_PROMPT; graceful degradation (daemon_event `condense_failed` on LLM failure); short-circuits when `len(history) < 2` |
| `orch/rag/summarize.py` | **CREATED** — Conversation compaction: `summarize_history()` producing rolling prose summary; preserves named entities, work-item IDs, facts, decisions; extends/refines previous summary; re-raises on LLM failure |
| `orch/rag/qa.py` | **MODIFIED** — Added `HISTORY_SOFT_BUDGET_TOKENS=3000`, `HISTORY_HARD_BUDGET_TOKENS=6000`, `SYSTEM_PROMPT_HARDENING`; replaced `_truncate_history` with delegation to `chat_repo.list_messages_for_context`; `answer_stream` and `answer_stream_v2` now load history from DB via `conversation_id`, call `condense_query` before retrieval, prepend rolling_summary as synthetic system note, append hardening lines to system prompt |
| `orch/rag/CLAUDE.md` | **MODIFIED** — Added "Conversation memory (F-00077)" section documenting tables, condense→retrieve→answer flow, token-budget strategy, hardening lines, key files |
| `tests/unit/rag/test_token_budget.py` | Unit tests: drops oldest first, preserves last 2 even if they exceed budget, empty input returns empty, below-budget returns unchanged |
| `tests/unit/rag/test_condense.py` | Unit tests: short-circuits below 2 turns, calls LLM with documented prompt, strips whitespace, LLM failure returns original question, uses only last 4 turns |
| `tests/unit/rag/test_summarize.py` | Unit tests: produces non-empty text, injects entities into prompt, includes previous summary, re-raises on LLM failure, preserves work-item IDs |
| `tests/integration/rag/test_qa_with_conversation.py` | Integration tests: condense invoked on turn ≥ 2, system prompt contains hardening lines, rolling_summary prepended as synthetic system note, legacy conversation_history fallback works |
| `tests/integration/rag/test_chat_repo.py` | Integration tests: get_or_create creates new / returns existing / cross-session creates new, append_message bumps last_active_at, list_messages_for_context skips summarized, archive_conversation idempotent, cross-project returns None, strict triple-filter |

## Implementation Notes

### Token-budget truncation

`chat_repo.truncate_messages_to_budget(messages, soft_budget_tokens)` drops the oldest messages first while always preserving the last 2 messages (correctness-over-budget). `list_messages_for_context` calls this after loading from DB. `qa.py` delegates to `list_messages_for_context` for the DB-backed path.

### CondensePlusContext

`condense_query` only calls the LLM when `len(history) >= 2`. Uses last 4 turns maximum for the condense prompt. Falls back to original question on any LLM exception, emitting a `daemon_event` of type `condense_failed`.

### Hardening lines

`SYSTEM_PROMPT_HARDENING` is appended unconditionally to every system prompt via `_build_system_prompt`. This satisfies Invariant 8.

### answer_stream / answer_stream_v2 changes

Both methods now:
1. Load history from DB via `list_messages_for_context` when `conversation_id` is provided
2. Call `condense_query` before embedding/retrieval (condensed query for retrieval; original question for the final user turn)
3. Prepend `rolling_summary` as a synthetic system note between the main system prompt and kept-verbatim history
4. Append `SYSTEM_PROMPT_HARDENING` to the system prompt

## Quality Gates

- **Format**: `make format` — 575 files already formatted ✓
- **Typecheck**: `make typecheck` — Success: no issues in 220 source files ✓
- **Lint**: Pre-existing errors in `tests/unit/test_qa_engine.py` (unrelated to F-00077, existed before this work item) — `orch/rag/chat_repo.py`, `orch/rag/condense.py`, `orch/rag/summarize.py`, `orch/rag/qa.py` all pass ruff check ✓

## Test Results

| Test Suite | Passed | Failed | Skipped |
|------------|--------|--------|---------|
| `tests/unit/rag/test_token_budget.py` | 4 | 0 | — |
| `tests/unit/rag/test_condense.py` | 5 | 0 | — |
| `tests/unit/rag/test_summarize.py` | 5 | 0 | — |
| `tests/integration/rag/test_qa_with_conversation.py` | 4 | 0 | — |
| `tests/integration/rag/test_chat_repo.py` | 9 | 0 | — |
| **Total** | **27** | **0** | **0** |

## Blockers

None.

## Decisions Made

1. **`truncate_messages_to_budget` lives in `chat_repo.py`**: The test file imports it from `orch.rag.qa` (the test was already written and passes after the import alias was added to qa.py as `from orch.rag.chat_repo import truncate_messages_to_budget as _truncate_messages_to_budget`).

2. **`condense.py` uses `llm.complete()` not `llm.chat()`**: The CONDENSE_PROMPT prompt is a single-turn prompt ("rewritten query, no preamble, no quotes"), so `complete()` is more natural than `chat()`. The original question is always used for the LLM answer turn regardless of condensed query.

3. **`summarize.py` uses `llm.chat()`**: The summarization prompt is a conversation-with-previous-summary format, so `chat()` is appropriate.

4. **No changes to `answer_stream_v2`'s internal `_retrieve_evidence_bundle` call**: Only the top-level `question` argument changes to the condensed query. The work-item-aware retrieval path inside `_retrieve_evidence_bundle` uses the same `question` (now condensed) — this is correct behavior.

5. **Pre-existing lint errors in `tests/unit/test_qa_engine.py`**: Not fixed as they are unrelated to F-00077 and existed before this work item. The files I modified all pass lint cleanly.