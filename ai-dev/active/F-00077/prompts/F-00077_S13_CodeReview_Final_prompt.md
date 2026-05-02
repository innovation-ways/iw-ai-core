# F-00077_S13_CodeReview_Final_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Review Step**: S13 (Final Review)
**Implementation Steps Reviewed**: S01..S11

---

## ⛔ Docker / Migrations off-limits

Same constraints. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md` — design document (full)
- All implementation reports: `ai-dev/active/F-00077/reports/F-00077_S{01,03,04,07,08,11}_*_report.md`
- All review reports: `ai-dev/active/F-00077/reports/F-00077_S{02,05,06,09,10,12}_CodeReview_report.md`
- ALL files in any implementation step's `files_changed`

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S13_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of ALL implementation work for F-00077. Per-agent reviews already passed; your job is the cross-cutting issues that no per-step review could catch.

Read the design document FIRST. Then read each implementation report. Then read all changed files holistically.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in any of the implementation `files_changed` → CRITICAL (`category: conventions`).

## Review Checklist

### 1. Completeness vs Design Document

- Every In-Scope bullet has a corresponding implementation file change. Missing → CRITICAL `missing_requirements`.
- Every AC1..AC9 maps to at least one passing test. Missing → CRITICAL.
- Every Invariant 1-10 maps to a test. Missing → HIGH.
- Every Boundary Behavior row has a test or explicit code-level handling. Missing → HIGH per row.
- The hardening prompt lines appear in code (grep for the literal phrase "trust the most recent one" — should appear in `orch/rag/qa.py`).
- The condense prompt template is committed verbatim (grep "Standalone search query").
- The summarize prompt template is committed verbatim (grep "Named entities").

### 2. Cross-Agent Consistency

- The `conversation_id` flows correctly: composer.js sends → code_qa.py receives → chat_repo.get_or_create_conversation creates → SSE meta event emits → composer.js's onMeta caches. Trace this end-to-end and verify no link is broken.
- The `rolling_summary` flow: chat_summarization_poller writes → qa.py reads → system prompt includes. Verify.
- Token counts: chat_repo.append_message computes via tiktoken → chat_messages.token_count stored → list_messages_for_context sums for budget. Verify.
- `enqueue_summarization_if_needed` is called from EXACTLY ONE place (code_qa.py after the assistant message persists). NOT called elsewhere.
- `daemon/main.py` registers the new poller AFTER the existing job pollers in the same try/except style.
- The same Ollama LLM client is used in qa.py and the daemon poller (no second LLM client appears in the codebase).

### 3. Integration Points

- DB session lifecycle: the worker thread does NOT share the request's DB session. Verify by tracing the flow in `_sse_generator()` — fresh session opened post-`__DONE__`.
- The `conversation_history` field is dead in code_qa.py (never read after S07). Grep confirms.
- No circular imports introduced (e.g. `orch/rag/chat_repo.py` ↔ `orch/daemon/chat_summarization_poller.py`).
- `dashboard/app.py` registers the conversations router AND the session middleware in the right order (middleware first).
- Tests across all steps use the SAME `db_session` fixture — no parallel-fixture drift.

### 4. Test Coverage (Holistic)

- Run `make test-integration` and check that `tests/integration/rag/test_F00077_multi_turn_e2e.py` exercises the full pipeline.
- Coverage of unhappy paths: condense fail, summarize fail, stream disconnect, cross-session 404, archived 404, cross-project 404.
- Frontend rendering test verifies `chat-new-btn` is present.
- The `make test-unit` and `make test-integration` suites both pass with 0 failures.

### 5. Architecture Compliance

- Layer boundaries respected: `orch/` modules don't import `dashboard/`. Routers don't run SQL directly.
- Append-only convention on `chat_messages` is honored; the only UPDATE is the same-tx error-flag write (verify by grep for UPDATE-style chat_messages mutations).
- Single-PK pattern (not composite) consistent across the three new tables.
- ENUM is created in the migration, dropped on downgrade.

### 6. Security (Cross-Cutting)

- No hardcoded secrets across any new file.
- All four conversation endpoints triple-filter `(project_id, session_id, conversation_id)`.
- The 404-on-mismatch pattern (NOT 403) is consistent — no endpoint leaks existence.
- Cookie value is from `uuid.uuid4()`, not predictable.
- `rolling_summary` content is wrapped with a clear marker in the system prompt; system prompt itself includes the hardening lines that tell the model to ignore self-injection attempts.
- The deprecated `conversation_history` field cannot be used to inject arbitrary turns: the server ignores it server-side. Verify by grepping for any read-site of `request.conversation_history` post-S07.

### 7. Documentation

- `orch/rag/CLAUDE.md` updated with a new section describing the memory feature.
- The design document's "Notes" section mentions every cross-cutting decision (background summarization, two-tier budgets, why no Mem0/Zep, browser cookie).

## Test Verification (NON-NEGOTIABLE)

Run BOTH:
```bash
make test-unit
make test-integration
```

If integration tests fail → CRITICAL.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Missing AC, missing requirement, integration broken, security gap, append-only violation, layer boundary breach | Must fix |
| HIGH | Missing invariant test, missing boundary case, missing log line, deprecated field still consumed | Must fix |
| MEDIUM (fixable) | Code smell across boundaries, naming inconsistency | Fix in fix cycle |
| MEDIUM (suggestion) | Optional refactor | Optional |
| LOW | Wording | Informational |

## Review Result Contract

```json
{
  "step": "S13",
  "agent": "code-review-final-impl",
  "work_item": "F-00077",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11", "S12"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
