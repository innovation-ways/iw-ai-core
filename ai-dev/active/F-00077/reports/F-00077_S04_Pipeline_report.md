# F-00077 S04 — Pipeline Report

## What Was Done

Implemented the daemon-side compaction worker for F-00077 (code chat conversation memory with persistence and query rewriting).

### Components Added/Modified

| File | Change |
|------|--------|
| `orch/daemon/chat_summarization_poller.py` | NEW — poll loop for `ChatSummarizationJob`, modeled on `doc_job_poller.py` |
| `orch/daemon/main.py` | MODIFIED — added `_make_chat_llm()` helper, registered poller in `_poll_cycle()` Phase 5 |
| `orch/rag/chat_repo.py` | MODIFIED — added `enqueue_summarization_if_needed()` |
| `orch/rag/summarize.py` | MODIFIED — added `BaseLLM` type alias for type-safe LLM annotations |
| `tests/unit/daemon/test_chat_summarization_poller.py` | NEW — 4 unit tests |
| `tests/unit/rag/test_chat_repo_enqueue.py` | NEW — 4 unit tests |
| `tests/integration/daemon/test_chat_summarization_e2e.py` | NEW — 4 integration tests |

### `poll_chat_summarization_jobs()` Details

- Polls `chat_summarization_jobs WHERE status='queued' ORDER BY triggered_at LIMIT max_jobs_per_cycle`
- Uses `FOR UPDATE SKIP LOCKED` for defensive locking
- Status transitions: `queued → running → completed/failed`
- Loads messages newer than `summary_through_message_id` (or all if NULL)
- Calls `summarize_history(messages, llm, previous_summary)` and updates `chat_conversations.rolling_summary` + `summary_through_message_id`
- On conversation-not-found: transitions to `failed` with `error_message="conversation_not_found"`

### `enqueue_summarization_if_needed()` Details

- Sums `token_count` for messages newer than `summary_through_message_id` using `func.coalesce(func.sum(...), 0)`
- If sum > `hard_budget_tokens` AND no in-flight job exists: inserts new `ChatSummarizationJob`
- On `IntegrityError` (unique partial index race): rolls back and returns `None` gracefully

### LLM Accessor

`_make_chat_llm(config)` in `main.py` constructs an `Ollama` instance using:
- Model: `gemma4:26b` (same as `TIER_DEFAULTS[IndexTier.BALANCED]["llm_model"]`, consistent with QA, classifier, and module_gen paths)
- URL: `http://localhost:11434` (same default as `CodeUnderstandingConfig.ollama_url`)

This is a single shared instance per `Daemon`, avoiding repeated construction overhead.

### Test Results

```
tests/unit/daemon/test_chat_summarization_poller.py     4 passed
tests/unit/rag/test_chat_repo_enqueue.py              4 passed
tests/integration/daemon/test_chat_summarization_e2e.py 4 passed
Total: 12 passed, 0 failed
```

### Pre-flight Quality Gates

- `make format`: ✅ All files formatted
- `make typecheck`: ✅ No type errors
- `make lint`: ⚠️ 13 pre-existing lint errors in `tests/unit/test_qa_engine.py` (unrelated to this step); all NEW files pass with 0 errors

### Notes

- The `func.coalesce(func.sum(...), 0)` pattern was used to handle `scalar_one_or_none()` failing when no rows match (returns 0 instead of raising)
- The integration test `test_conversation_deleted_job_fails_with_not_found` uses `patch.object(db_session, "get", ...)` to simulate a deleted conversation since CASCADE delete removes the job row from DB too
- The lint error `I001` in `tests/unit/test_qa_engine.py` is pre-existing and unrelated to this step

## Files Changed

```
orch/daemon/chat_summarization_poller.py   [NEW]
orch/daemon/main.py                       [MODIFIED]
orch/rag/chat_repo.py                     [MODIFIED]
orch/rag/summarize.py                    [MODIFIED]
tests/unit/daemon/test_chat_summarization_poller.py  [NEW]
tests/unit/rag/test_chat_repo_enqueue.py            [NEW]
tests/integration/daemon/test_chat_summarization_e2e.py [NEW]
```
