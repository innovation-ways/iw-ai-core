# F-00077_S09_CodeReview_API_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step Being Reviewed**: S07 (api-impl)
**Review Step**: S09

---

## ⛔ Docker / Migrations off-limits

Same constraints. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md`
- `ai-dev/active/F-00077/reports/F-00077_S07_API_report.md`
- All files in S07's `files_changed`

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S09_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in S07's files → CRITICAL.

## Review Checklist

### 1. Architecture Compliance

- Routers stay thin: business logic is in `orch/rag/chat_repo.py`. CRITICAL if SQLAlchemy queries appear directly in router files.
- Session middleware is registered in `dashboard/app.py` and runs BEFORE the router stack.
- The 4 conversation endpoints all triple-filter by `(project_id, session_id, conversation_id)`. CRITICAL if any single one omits a filter — that's a session-isolation bug.
- The deprecated `conversation_history` field in `QARequest` is accepted but the value is NEVER consumed in `code_qa.py` — verify by grep for `request.conversation_history` post-S07.

### 2. SSE Correctness

- The `event: meta` frame is emitted FIRST, before any token. Trace the generator code path. CRITICAL if a token can ever precede the meta event.
- The `meta` JSON payload is `{"conversation_id": "<uuid>"}` — exactly that shape. No extras for v1.
- The user message is persisted SYNCHRONOUSLY before the worker thread spawns; if the thread crashes, the user-message row exists.
- The assistant message is persisted ON `__DONE__` in a fresh DB session (not the request's session, because the worker thread is in a thread pool and the request session isn't safe across threads).
- On stream error mid-flight, partial content is written with `metadata.error=true` and `error_reason` set.
- After persistence, `enqueue_summarization_if_needed` is called and returns gracefully on race (None on IntegrityError).

### 3. HTTP Semantics

- `GET /conversations` returns 200 + list (empty if none).
- `POST /conversations` returns 201 with new id.
- `GET /conversations/{id}/messages` returns 200 OR 404 (NOT 403 — leak prevention).
- Archived conversations return 404 from `GET /messages` (consistent with stranger-id behavior).
- Cross-session, cross-project, cross-archived all collapse to 404 — no observable difference. Verify the 4 paths individually.
- `POST /archive` is idempotent (returns the existing `archived_at` on second call).

### 4. Cookie Security

- Cookie `iw_chat_session` set with `SameSite=Lax`, `Max-Age=7776000`, `HttpOnly=False`.
- Cookie value is generated via `uuid.uuid4()` (cryptographically random — NOT `random.random()` or sequential).
- Cookie is set ONLY when missing (does not regenerate on every request — verify the middleware short-circuits).
- The middleware does not log or expose the cookie value in error responses.

### 5. Project Conventions

- Pydantic schemas declared at module top, used in `response_model=`.
- `get_db` dependency from `dashboard/dependencies.py` — same pattern as adjacent routers.
- Routers register at the same path style as adjacent routers.
- No async functions where sync would suffice (matches the rest of the codebase).

### 6. Security

- No way to leak conversation existence cross-session — ALL not-found paths return 404 with the same body.
- Session cookie issued securely; cookie value is treated as opaque.
- The deprecated `conversation_history` body field is ignored — a malicious client cannot inject arbitrary "prior turns" into the system prompt by replaying it.

### 7. Testing

- All 4 conversation endpoints have happy-path AND cross-session 404 tests.
- The `meta`-frame ordering test: assert the SSE stream's first event is `meta`, not `token`.
- Stream-disconnect test verifies the partial assistant message persists with `metadata.error=true`.
- Session-cookie middleware test: cookie attributes match the design.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Missing triple-filter, meta event after token, leakage of conversation existence (403 vs 404), worker thread sharing main DB session, cookie not crypto-random | Must fix |
| HIGH | Deprecated field still consumed, idempotency missing, inconsistent error responses | Must fix |
| MEDIUM (fixable) | Style drift, missing log statement | Fix in fix cycle |

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-impl",
  "work_item": "F-00077",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
