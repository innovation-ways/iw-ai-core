# F-00077_S06_CodeReview_Pipeline_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step Being Reviewed**: S04 (pipeline-impl)
**Review Step**: S06

---

## ⛔ Docker / Migrations off-limits

Same constraints. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md`
- `ai-dev/active/F-00077/reports/F-00077_S04_Pipeline_report.md`
- All files listed in S04's `files_changed`
- `orch/daemon/doc_job_poller.py` — reference shape

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S06_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in S04's `files_changed` → CRITICAL.

## Review Checklist

### 1. Architecture Compliance

- `chat_summarization_poller.py` matches the shape of `doc_job_poller.py`: same import style, same try/except patterns at the loop boundary, same logging cadence, single-threaded sync.
- The poller is registered in `orch/daemon/main.py` AFTER the existing job pollers and inside the same try/except shape so a failure here doesn't crash the daemon.
- LLM accessor is consistent with the rest of the daemon — does NOT instantiate a fresh Ollama client when one is already available in the daemon scope.
- `enqueue_summarization_if_needed` lives in `orch/rag/chat_repo.py` (not in the daemon module) — it's called from the API path. Verify NOT in the daemon module.

### 2. Locking & Concurrency Correctness

- The poller uses `with_for_update(skip_locked=True)` on the SELECT — required for safety even though the daemon is single-threaded today.
- Status transition queued→running is COMMITTED before the LLM call (so a crash during LLM doesn't leave a stuck 'running' row that competing workers can't pick up).
- Status transition running→completed/failed is committed at the end.
- The unique partial index from S01 is the SOLE enforcement of "at most one in-flight job per conversation". The enqueue helper relies on it (catches IntegrityError gracefully) — verify the catch-and-return-None path exists.

### 3. Error Handling

- LLM exception → status='failed', `error_message` set (truncated to 500 chars per the design).
- Exception in the outer poll loop is caught at the registration site in `daemon/main.py` — does NOT propagate to crash the daemon.
- Conversation deleted between enqueue and poll → `error_message="conversation_not_found"`, status='failed'.
- `summary_through_message_id` is set even on partial summaries — verify the chosen message-boundary semantics (the LAST message included in the summary).

### 4. Project Conventions

- Sync SQLAlchemy.
- Loggers via `logging.getLogger(__name__)`.
- INFO-level on each transition; ERROR with traceback on failures; DEBUG on no-op.
- No psycopg2.
- No emoji in log messages or code (project convention — only when the user asks).

### 5. Security

- No SQL injection vector in the queue queries (parameterized via SQLAlchemy core, not f-strings).
- LLM input (`messages` list) does not include any secrets — verify no `API_KEY` or `password` style keys flow through.

### 6. Testing

- Unit test: empty queue, success path, failure path, max_jobs_per_cycle limit — all present.
- Integration test runs against testcontainer with stubbed LLM.
- Race-condition test (two concurrent enqueues) verifies the IntegrityError fallback in `enqueue_summarization_if_needed`.
- `summary_through_message_id` is asserted in the success-path test.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Status transition not committed before LLM call, daemon crash on poll failure, missing FOR UPDATE SKIP LOCKED, missing IntegrityError catch | Must fix |
| HIGH | Wrong LLM accessor, missing summary_through_message_id update, missing max-cycle limit | Must fix |
| MEDIUM (fixable) | Log levels wrong, deprecation warnings | Fix in fix cycle |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00077",
  "step_reviewed": "S04",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
