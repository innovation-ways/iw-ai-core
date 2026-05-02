# F-00077_S04_Pipeline_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step**: S04
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY container/volume/network management command. Allowed: `docker ps/inspect/logs`, testcontainer fixtures, `./ai-core.sh`/`make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do NOT run alembic upgrade/downgrade/stamp against the live orch DB (port 5433). Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md` — sections: Description, AC6, AC7, Invariant 2, Boundary Behavior (summarize LLM failure)
- `ai-dev/active/F-00077/reports/F-00077_S01_Database_report.md`
- `ai-dev/active/F-00077/reports/F-00077_S03_Backend_report.md`
- `orch/daemon/main.py` — current daemon entry point + poll loop
- `orch/daemon/doc_job_poller.py` — REFERENCE PATTERN. Mirror its shape (poll loop, status transitions, error handling). The `chat_summarization_poller.py` is the same thing for a different table.
- `orch/db/models.py` — `ChatSummarizationJob` from S01
- `orch/rag/summarize.py` — `summarize_history()` from S03
- `orch/rag/chat_repo.py` — `count_tokens()` and the conversation accessor from S03

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S04_Pipeline_report.md`
- `orch/daemon/chat_summarization_poller.py` — NEW
- `orch/daemon/main.py` — MODIFIED (register the new poller)
- `orch/rag/chat_repo.py` — MODIFIED (add `enqueue_summarization_if_needed()` helper consumed by the API in S07)
- Test files (see Tests section)

## Context

You are implementing the daemon-side compaction worker for F-00077. The Backend step (S03) has produced `summarize_history()` and the `chat_repo` module; you wire those into a poll loop modeled on `orch/daemon/doc_job_poller.py`. The API step (S07) will call your `enqueue_summarization_if_needed()` helper.

Read `orch/CLAUDE.md` (daemon module map, append-only conventions) and `orch/daemon/doc_job_poller.py` end-to-end before writing.

## Requirements

### 1. `orch/daemon/chat_summarization_poller.py`

Public function:

```python
def poll_chat_summarization_jobs(
    db: Session,
    *,
    llm: BaseLLM,
    max_jobs_per_cycle: int = 5,
) -> int:
    """Polls chat_summarization_jobs WHERE status='queued' ORDER BY
    triggered_at LIMIT max_jobs_per_cycle. For each job:
      1. Lock with FOR UPDATE SKIP LOCKED (avoids worker collision).
      2. Transition status='running', set started_at = now(). COMMIT.
      3. Load the conversation's messages newer than
         summary_through_message_id (or all if NULL).
      4. Load existing rolling_summary as 'previous_summary'.
      5. Call summarize_history(messages, llm, previous_summary).
      6. Update chat_conversations.rolling_summary AND
         summary_through_message_id (= the latest message.id included).
      7. Transition status='completed', set completed_at = now(),
         messages_summarized = count.
      8. On exception: transition status='failed', set error_message
         (str(exc)[:500]), completed_at = now(). Do NOT re-raise.
    Returns the number of jobs processed."""
```

Logging:
- INFO on each transition (queued→running, running→completed/failed).
- ERROR with traceback on failure.
- DEBUG on no-op cycles (zero queued jobs).

Locking:
- Use `db.execute(select(ChatSummarizationJob).where(...).with_for_update(skip_locked=True).limit(...))`.
- Per the existing daemon convention, the poller runs single-threaded inside the daemon loop; the FOR UPDATE SKIP LOCKED is defensive in case the daemon ever spawns parallel workers.

Error semantics:
- LLM timeout / connection error → status='failed' with `error_message="<exception class>: <truncated>"`. The unique partial index allows a fresh enqueue on the next overflow.
- Conversation deleted between enqueue and run → query returns nothing → mark 'failed' with `error_message="conversation_not_found"`.

### 2. `orch/daemon/main.py` — Registration

Locate the daemon's main poll loop. After the existing `doc_job_poller` invocation (or wherever `code_index_jobs` polling lives), add:

```python
from orch.daemon.chat_summarization_poller import poll_chat_summarization_jobs

# inside the main loop, after other poll_* calls:
try:
    poll_chat_summarization_jobs(db, llm=llm)
except Exception:
    logger.exception("chat_summarization poll failed")
```

Wrap in try/except so a failure here does NOT stop other pollers (consistent with existing pattern for `code_index_jobs` and `doc_generation_jobs`).

The LLM instance: reuse the same Ollama client construction the rest of the daemon uses. If there's a shared accessor (`orch.rag.qa._get_llm()` or similar), use it; otherwise instantiate locally with the same model identifier the QA path uses, read from `config`. Document the choice in your report.

### 3. `orch/rag/chat_repo.py` — Enqueue helper

Add this function (do NOT touch other functions S03 introduced; this is purely additive):

```python
def enqueue_summarization_if_needed(
    db: Session,
    *,
    conversation_id: str,
    hard_budget_tokens: int,
) -> ChatSummarizationJob | None:
    """Inspects chat_messages.token_count totals for messages NEWER than
    chat_conversations.summary_through_message_id (or all if NULL). If sum
    > hard_budget_tokens AND no chat_summarization_jobs row exists for
    this conversation with status IN ('queued', 'running'), inserts a new
    job with status='queued' and returns it. Otherwise returns None.

    Uses the unique partial index from S01 as the source of truth: rely
    on it to handle the race; on IntegrityError, return None gracefully
    (some other request just enqueued)."""
```

This function is called by `dashboard/routers/code_qa.py` (S07) after the assistant message persists.

### 4. Tests

`tests/unit/daemon/test_chat_summarization_poller.py`:
- Empty job table → `poll_chat_summarization_jobs(db, llm=stub) == 0`.
- One queued job, stub LLM returns "summary text" → job transitions queued→running→completed, conversation.rolling_summary == "summary text", `summary_through_message_id` is set to the last message's id.
- Stub LLM raises → job transitions queued→running→failed, error_message non-empty, conversation.rolling_summary unchanged.
- Two queued jobs, max_jobs_per_cycle=1 → only one is processed.

`tests/integration/daemon/test_chat_summarization_e2e.py`:
- Real testcontainer + real summarize.py with a stubbed LLM (returns deterministic text).
- Insert conversation + 6 messages with assistant turns each ~2000 tokens.
- Call `enqueue_summarization_if_needed(..., hard_budget_tokens=6000)` → returns a job.
- Call `poll_chat_summarization_jobs(...)` → job completes; conversation has rolling_summary.
- Call `enqueue_summarization_if_needed(...)` again BEFORE the conversation gets new messages → returns None (the unique index would block AND the budget hasn't been exceeded again from the new boundary).
- Cancel test: create job with status='queued', delete the conversation, run poller → job fails with `error_message="conversation_not_found"`.

`tests/unit/rag/test_chat_repo_enqueue.py`:
- Below budget → returns None, no row inserted.
- Above budget, no in-flight job → returns the job.
- Above budget, in-flight job exists → returns None (idempotency).
- IntegrityError simulated via two concurrent calls — second returns None gracefully.

## Project Conventions

Read `orch/CLAUDE.md`. Specifically:

- Daemon pollers are sync, single-threaded.
- Use `db.execute(...).scalars()` for typed reads.
- `for_update(skip_locked=True)` in poll loops.
- Loggers via `logging.getLogger(__name__)`.

## TDD Requirement

Write `test_chat_summarization_poller.py` first (RED), then implement.

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
  "step": "S04",
  "agent": "pipeline-impl",
  "work_item": "F-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/chat_summarization_poller.py",
    "orch/daemon/main.py",
    "orch/rag/chat_repo.py",
    "tests/unit/daemon/test_chat_summarization_poller.py",
    "tests/integration/daemon/test_chat_summarization_e2e.py",
    "tests/unit/rag/test_chat_repo_enqueue.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "LLM accessor used: <where it came from>"
}
```
