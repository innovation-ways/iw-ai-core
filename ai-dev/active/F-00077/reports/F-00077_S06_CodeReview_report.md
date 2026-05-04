# F-00077 S06 — Code Review Report (Pipeline / S04)

## What Was Reviewed

Step S04 (`pipeline-impl`) implemented:
- `orch/daemon/chat_summarization_poller.py` — daemon poller for `ChatSummarizationJob`
- Registration of the poller in `orch/daemon/main.py` Phase 5
- `enqueue_summarization_if_needed()` in `orch/rag/chat_repo.py`
- `BaseLLM` type alias added to `orch/rag/summarize.py`
- Unit and integration tests for the poller and enqueue helper

## Architecture Compliance

| Check | Result |
|-------|--------|
| `chat_summarization_poller.py` matches shape of `doc_job_poller.py` | ✅ Same import style, same try/except at loop boundary, same logging cadence, single-threaded sync |
| Poller registered in `main.py` AFTER existing job pollers, inside same try/except shape | ✅ Phase 5 (lines 574–578), wrapped in try/except that logs but does not propagate |
| LLM accessor consistent with rest of daemon — no fresh Ollama client | ✅ `_make_chat_llm(config)` reuses `TIER_DEFAULTS[IndexTier.BALANCED]["llm_model"]` (`gemma4:26b`) and `http://localhost:11434`, instantiated once at `Daemon.__init__` as `self._chat_llm` and passed to `poll_chat_summarization_jobs` |
| `enqueue_summarization_if_needed` lives in `orch/rag/chat_repo.py`, NOT in daemon module | ✅ Correct — it's called from the API path (S07), not from the daemon |

## Locking & Concurrency Correctness

| Check | Result |
|-------|--------|
| `with_for_update(skip_locked=True)` on SELECT | ✅ Line 55: `.with_for_update(skip_locked=True)` |
| `queued → running` transition committed BEFORE LLM call | ✅ Lines 81–87: `job.status = "running"`, `db.commit()` — commit happens before `summarize_history()` is called |
| `running → completed/failed` committed at end | ✅ `_complete_job` (lines 144–161) and `_fail_job` (lines 164–173) both call `db.commit()` |
| Unique partial index enforcement via `IntegrityError` catch in `enqueue_summarization_if_needed` | ✅ Lines 388–394: `IntegrityError` → `db.rollback()` → `return None` |

## Error Handling

| Check | Result |
|-------|--------|
| LLM exception → `status='failed'`, `error_message` set (truncated to 500 chars) | ✅ Lines 139–141: catches all exceptions, calls `_fail_job(db, job, str(exc)[:500])` |
| Outer poll loop caught at registration site in `daemon/main.py` — does NOT crash daemon | ✅ Lines 574–578: try/except logs via `logger.exception("chat_summarization poll failed")` but does not re-raise |
| Conversation deleted → `error_message="conversation_not_found"`, `status='failed'` | ✅ Lines 98–100: `conv is None` → `_fail_job(db, job, "conversation_not_found")` |
| `summary_through_message_id` set on partial completion (messages_summarized=0) | ✅ Line 121: `_complete_job(db, job, messages_summarized=0)` — `summary_through_message_id` not set when no messages (correct semantics) |

## Project Conventions

| Check | Result |
|-------|--------|
| Sync SQLAlchemy | ✅ |
| Loggers via `logging.getLogger(__name__)` | ✅ |
| INFO-level on transitions, ERROR with traceback on failures, DEBUG on no-op | ✅ `logger.info` on queued→running and running→completed, `logger.error` with traceback on failure, `logger.debug` on empty queue |
| No psycopg2 | ✅ Only psycopg v3 via SQLAlchemy |
| No emoji in log messages | ✅ |

## Security

| Check | Result |
|-------|--------|
| No SQL injection — parameterized queries via SQLAlchemy core | ✅ All queries use `select()`, `func.coalesce()`, `func.sum()` with bound parameters |
| LLM input (`messages` list) contains no secrets | ✅ Messages are `ChatMessage` ORM objects with `role` and `content` — no API_KEY or password fields flow through |

## Testing

| Test | File | Result |
|------|------|--------|
| Empty queue → returns 0 | `tests/unit/daemon/test_chat_summarization_poller.py::test_empty_job_table_returns_zero` | ✅ PASS |
| Success path → job completes, conversation updated, summary_through_message_id set | `tests/unit/daemon/test_chat_summarization_poller.py::test_one_queued_job_completes_successfully` | ✅ PASS |
| LLM failure → job fails with error_message | `tests/unit/daemon/test_chat_summarization_poller.py::test_llm_failure_transitions_to_failed` | ✅ PASS |
| max_jobs_per_cycle limit | `tests/unit/daemon/test_chat_summarization_poller.py::test_max_jobs_per_cycle_limits_processing` | ✅ PASS |
| Below budget → returns None | `tests/unit/rag/test_chat_repo_enqueue.py::test_below_budget_returns_none` | ✅ PASS |
| Above budget, no in-flight → inserts job | `tests/unit/rag/test_chat_repo_enqueue.py::test_above_budget_no_inflight_job_returns_job` | ✅ PASS |
| Above budget, in-flight exists → returns None | `tests/unit/rag/test_chat_repo_enqueue.py::test_above_budget_inflight_job_returns_none` | ✅ PASS |
| IntegrityError race → returns None gracefully | `tests/unit/rag/test_chat_repo_enqueue.py::test_integrity_error_handled_gracefully` | ✅ PASS |
| Integration: enqueue returns job (above budget) | `tests/integration/daemon/test_chat_summarization_e2e.py::test_enqueue_summarization_if_needed_returns_job` | ✅ PASS |
| Integration: poll completes, rolling_summary + summary_through_message_id set | `tests/integration/daemon/test_chat_summarization_e2e.py::test_poll_completes_and_updates_conversation` | ✅ PASS |
| Integration: second enqueue returns None (no new messages) | `tests/integration/daemon/test_chat_summarization_e2e.py::test_second_enqueue_returns_none_when_no_new_messages` | ✅ PASS |
| Integration: conversation deleted → `error_message="conversation_not_found"` | `tests/integration/daemon/test_chat_summarization_e2e.py::test_conversation_deleted_job_fails_with_not_found` | ✅ PASS |

**Test summary**: 12 passed, 0 failed (8 unit + 4 integration).

## Pre-Flight Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ⚠️ 13 pre-existing errors (unrelated to S04): `T201` in `scripts/arch_check.py` (3 print stmts) + `I001` in `tests/unit/test_qa_engine.py` (import order). S04's 6 new files have 0 lint errors. |
| `make format` | ✅ All files formatted (579 files already formatted) |
| `make typecheck` | ✅ No type errors |

**Note**: The pre-existing lint errors are not introduced by S04 and are tracked separately.

## Findings

No mandatory fixes. The implementation is compliant with all specification requirements, project conventions, and the review checklist.

## Notes

- The `func.coalesce(func.sum(...), 0)` pattern in `enqueue_summarization_if_needed` correctly handles the case where no rows match the token-sum query (returns 0 instead of raising `scalar_one_or_none`).
- The integration test `test_conversation_deleted_job_fails_with_not_found` uses `patch.object(db_session, "get", ...)` to simulate conversation deletion since CASCADE removes the job row from the DB too.
- LLM accessor uses `gemma4:26b` (same model as `IndexTier.BALANCED` for QA/classifier/module_gen) — consistent with the rest of the daemon.

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00077",
  "reviewed_agent": "pipeline-impl",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "tests_passed": true,
  "test_summary": "12 passed, 0 failed (8 unit + 4 integration)",
  "notes": "Pre-existing lint errors (T201 in scripts/arch_check.py, I001 in tests/unit/test_qa_engine.py) are unrelated to S04. New files: 0 lint errors. All specification requirements satisfied."
}
```