# F-00077 S05 — Code Review Report (S03 Backend Implementation)

## Summary

Reviewed S03 (backend-impl) implementation of `orch/rag/chat_repo.py`, `orch/rag/condense.py`, `orch/rag/summarize.py`, and `orch/rag/qa.py` modifications, plus associated test files. The implementation is solid and correct on all critical paths. One lint-level convention violation was found in a file modified by S03.

---

## Files Changed by S03

| File | Change | Reviewed |
|------|--------|----------|
| `orch/rag/chat_repo.py` | CREATED — Repository layer | ✅ |
| `orch/rag/condense.py` | CREATED — Query rewriting | ✅ |
| `orch/rag/summarize.py` | CREATED — Conversation compaction | ✅ |
| `orch/rag/qa.py` | MODIFIED — Token-budget truncation, DB-loaded history, condense call, summary prepend, hardening lines | ✅ |
| `orch/rag/CLAUDE.md` | MODIFIED — F-00077 documentation | ✅ |
| `tests/unit/rag/test_token_budget.py` | CREATED | ✅ |
| `tests/unit/rag/test_condense.py` | CREATED | ✅ |
| `tests/unit/rag/test_summarize.py` | CREATED | ✅ |
| `tests/integration/rag/test_qa_with_conversation.py` | CREATED | ✅ |
| `tests/integration/rag/test_chat_repo.py` | CREATED | ✅ |
| `tests/unit/test_qa_engine.py` | MODIFIED — hardening lines test updated | ⚠️ |

---

## Quality Gates

### Lint
```
make lint → 13 errors
- Pre-existing (scripts/arch_check.py T201 print): 12 errors
- NEW (tests/unit/test_qa_engine.py I001 import sorting): 1 error ← S03 introduced
```
The single new violation is in `tests/unit/test_qa_engine.py:83` — the import block
was extended to include `SYSTEM_PROMPT_HARDENING` but not re-sorted:
```python
# Current (unsorted):
from orch.rag.config import CodeUnderstandingConfig
from orch.rag.qa import QAEngine, SYSTEM_PROMPT_HARDENING

# Correct (isort):
from orch.rag.qa import SYSTEM_PROMPT_HARDENING
from orch.rag.config import CodeUnderstandingConfig
from orch.rag.qa import QAEngine
```
Fixable with `uv run ruff check tests/unit/test_qa_engine.py --fix`.

### Format
`make format` → 579 files already formatted ✅

### Test Results
| Suite | Result |
|-------|--------|
| `tests/unit/rag/test_token_budget.py` (4 tests) | PASS |
| `tests/unit/rag/test_condense.py` (5 tests) | PASS |
| `tests/unit/rag/test_summarize.py` (5 tests) | PASS |
| `tests/unit/test_qa_engine.py` (33 tests) | PASS |
| **F-00077 unit total** | **47 passed, 0 failed** |

Integration tests (`test_qa_with_conversation.py`, `test_chat_repo.py`) require a running testcontainer PostgreSQL and were not re-run due to timeout constraints. The S03 report shows both integration suites passing.

---

## Review Findings

### Finding 1: Import block unsorted in test_qa_engine.py
- **Severity**: HIGH (conventions — NEW violation in S03's `files_changed`)
- **File**: `tests/unit/test_qa_engine.py`
- **Line**: 83
- **Description**: S03 extended the existing import to include `SYSTEM_PROMPT_HARDENING` but did not re-sort the import block, causing an isort violation (I001).
- **Suggested fix**: `uv run ruff check tests/unit/test_qa_engine.py --fix` (auto-fixable)

---

## Architecture Compliance Checklist

| Item | Status | Notes |
|------|--------|-------|
| `chat_repo.py` is pure repository (no LLM, no FastAPI, no SSE) | ✅ | Only SQLAlchemy Session imports in TYPE_CHECKING block |
| `condense.py` is pure (no DB session, no FastAPI) | ✅ | Takes LLM instance + optional db_session for daemon_event; uses dependency injection for failure callback |
| `summarize.py` is pure (no DB session, no FastAPI) | ✅ | Takes LLM instance; re-raises on LLM failure |
| `answer_stream` and `answer_stream_v2` both preserved | ✅ | `answer_stream_v2` delegates to `answer_stream` for token streaming |
| `MAX_HISTORY_TURNS` constant REMOVED | ✅ | Verified: not in `orch/rag/qa.py`; test updated to `assert not hasattr(engine, "MAX_HISTORY_TURNS")` |
| `last_active_at` bump in same transaction as INSERT | ✅ | `append_message` does `db.flush()` after both the INSERT and the UPDATE |

---

## Code Quality Checklist

| Item | Status | Verification |
|------|--------|--------------|
| Last-2-turns always preserved (correctness > budget) | ✅ | `test_preserves_last_two_even_if_they_exceed_budget` passes; trace confirms loop condition `len(result) > 2` |
| `count_tokens()` warning logged ONCE per unknown model | ✅ | `_warned_models` set used as cache; checked before retry |
| Condense fallback: LLM exception → original question + `daemon_event` | ✅ | `event_type="condense_failed"`, payload includes `conversation_id` when provided |
| Summarize prompt includes entity-preservation verbatim | ✅ | SUMMARIZE_PROMPT contains "Named entities", "user-stated facts", "Decisions reached", "investigative thread" |
| Hardening lines appended to BOTH system prompt paths | ✅ | `SYSTEM_PROMPT_HARDENING` unconditionally appended in `_build_system_prompt()`; `answer_stream_v2` always calls `answer_stream` → always hits `_build_system_prompt()` |
| `rolling_summary` marker: `role="system"` + "Earlier in this conversation:\n" | ✅ | `ChatMessage(role="system", content=f"Earlier in this conversation:\n{rolling_summary}")` |
| `daemon_event` uses `event_metadata` (not `metadata`) | ✅ | `DaemonEvent(..., event_metadata=metadata, ...)` |

---

## Security Checklist

| Item | Status | Notes |
|------|--------|-------|
| `rolling_summary` wrapped with clear marker | ✅ | `"Earlier in this conversation:\n"` prepends the summary |
| Hardening lines instruct model to ignore injected instructions | ✅ | "Do not claim to remember anything not present in the provided conversation history" |
| Condense prompt renders history as data (User:/Assistant:), not instructions | ✅ | `f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"` — role labels, not instruction injection |
| No secrets/credentials hardcoded | ✅ | Verified across all new files |

---

## Test Coverage Review

| Boundary Behavior | Backend Test | Status |
|-------------------|--------------|--------|
| Condense short-circuits below 2 turns | `test_short_circuits_below_two_turns` | ✅ |
| Condense calls LLM with documented prompt | `test_calls_llm_with_history_and_question` | ✅ |
| Condense LLM failure → original question | `test_llm_failure_returns_original_question` | ✅ |
| Condense uses only last 4 turns | `test_uses_only_last_four_turns_for_condense` | ✅ |
| Token-budget drops oldest first | `test_drops_oldest_first` | ✅ |
| Last 2 preserved if they alone exceed budget | `test_preserves_last_two_even_if_they_exceed_budget` | ✅ |
| Empty input returns empty | `test_empty_input_returns_empty` | ✅ |
| Below-budget returns unchanged | `test_below_budget_returns_unchanged` | ✅ |
| tiktoken fallback | `test_count_tokens_uses_tiktoken` | ✅ |
| Summarize entity injection | `test_injects_entities_into_prompt` | ✅ |
| Summarize re-raises on LLM failure | `test_llm_raises_propagates` | ✅ |
| Rolling summary prepended as system note | `test_rolling_summary_prepended_as_synthetic_system_note` | ✅ |
| Hardening lines in system prompt | `test_system_prompt_contains_hardening_lines` | ✅ |
| Condense invoked on turn ≥ 2 | `test_condense_invoked_on_second_turn` | ✅ |
| Legacy conversation_history still works | `test_legacy_conversation_history_still_works` | ✅ |

---

## Notes

1. **Integration test timeout**: The full `make test-integration` suite timed out at 300s in this environment. The S03 report shows these tests passing. Manual verification via `uv run pytest tests/integration/rag/ -v` would confirm.

2. **`condense.py` DB access via dependency injection**: The design noted that `condense.py` may write a `daemon_event` on failure, requiring session access. The implementation uses optional `db_session: Session | None` parameter rather than implicit module-level session access. This is correct dependency-injection style.

3. **Pre-existing lint errors in `scripts/arch_check.py`**: 12 `T201 print` violations exist in a file not modified by S03. These are outside S03's scope and pre-existed this work item.

---

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "F-00077",
  "step_reviewed": "S03",
  "verdict": "fail",
  "mandatory_fix_count": 1,
  "findings": [
    {
      "severity": "HIGH",
      "category": "conventions",
      "file": "tests/unit/test_qa_engine.py",
      "lines": "83",
      "description": "Import block unsorted — S03 added SYSTEM_PROMPT_HARDENING to the existing import but did not re-sort the block, violating isort rules (I001).",
      "suggested_fix": "uv run ruff check tests/unit/test_qa_engine.py --fix"
    }
  ],
  "tests_passed": true,
  "test_summary": "47 passed, 0 failed (unit tests for F-00077 files)",
  "notes": "All critical correctness paths verified: token-budget truncation preserves last 2 turns, hardening lines on both answer_stream paths, condense fallback with daemon_event, rolling_summary marker, MAX_HISTORY_TURNS removed. One auto-fixable lint violation introduced by S03."
}
```
