# F-00049_S04_CodeReview_prompt

**Work Item**: F-00049 — Code Understanding: Q&A Panel (SSE Streaming)
**Step Being Reviewed**: S03 (api-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/F-00049/F-00049_Feature_Design.md` — Design document
- `ai-dev/work/F-00049/reports/F-00049_S03_API_report.md` — S03 implementation report
- All files listed in the S03 report's `files_changed`:
  - `dashboard/routers/code_qa.py`
  - `dashboard/app.py`
  - `tests/integration/test_code_qa_routes.py`

## Output Files

- `ai-dev/work/F-00049/reports/F-00049_S04_CodeReview_report.md` — Review report

---

## Context

You are reviewing the API implementation done in S03 by the api-impl agent for **F-00049: Code Understanding Q&A Panel**. Your goal is to ensure the endpoint is correct, the SSE format is right, error handling is complete, and the tests are thorough.

Read the design document and S03 report before reviewing the code.

---

## Review Checklist

### 1. Endpoint Correctness

- Is the endpoint at `POST /api/projects/{project_id}/code/qa`?
- Does it return `StreamingResponse` with `media_type="text/event-stream"`?
- Are the required headers set: `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`?
- Does the endpoint use `AsyncSession` from `get_db()` dependency?

### 2. Request Validation (Pydantic)

- Is there a `QARequest` Pydantic model with:
  - `question: str` with `min_length=1` and `max_length=1000`?
  - `context_level: str` restricted to `"architecture"` or `"module"` (via `pattern` or `Literal`)?
  - `context_doc_id: str | None = None`?
  - `module_path: str | None = None`?
  - `conversation_history: list[ConversationMessage]` defaulting to `[]`?
- Does the endpoint return HTTP 422 for validation failures (Pydantic default, not a custom 400)?
- Is there a `ConversationMessage` model with `role: str` and `content: str`?

### 3. Pre-flight Checks

- Does the endpoint verify the project exists in the DB before streaming? Returns HTTP 404 if not found?
- Does the endpoint verify the LanceDB index directory exists on disk? Returns HTTP 404 with "No code index found for this project" if missing?
- Are both checks done BEFORE the `StreamingResponse` generator starts (so they can return proper HTTP status codes)?

### 4. SSE Format

- Token events: `data: {"token": "..."}\n\n` (double newline as SSE spec requires)?
- Done event: `data: {"event": "done", "full_response": "..."}\n\n`?
- Error event: `data: {"event": "error", "message": "..."}\n\n`?
- Is `"__ERROR__:"` prefix from QAEngine correctly detected and converted to an SSE error event?
- Does the generator always yield either a `done` or `error` event as its final message (never silently closes)?

### 5. QAEngine Integration

- Is `QAEngine` instantiated with `project_id` and `config` (not hardcoded values)?
- Is `answer_stream()` called with all required parameters including `module_path`, `conversation_history` (as list of dicts), and `session`?
- Is `conversation_history` correctly converted from `ConversationMessage` objects to plain dicts (`.model_dump()`)?

### 6. Router Registration

- Is the `code_qa` router imported and registered in `dashboard/app.py`?
- Does it follow the same registration pattern as the existing `code` router?
- Is there no duplicate route prefix?

### 7. Test Quality

- Are all 8 required test cases implemented?
  - `test_qa_project_not_found` → 404
  - `test_qa_no_index_found` → 404
  - `test_qa_validation_empty_question` → 422
  - `test_qa_validation_question_too_long` → 422
  - `test_qa_validation_invalid_context_level` → 422
  - `test_qa_streams_tokens` → SSE token events + done event
  - `test_qa_streams_error_event_on_ollama_down` → SSE error event
  - `test_qa_empty_conversation_history` → 200 streaming
- Do tests use testcontainers (never port 5433)?
- Are Ollama and LanceDB calls mocked (not real)?
- Is the DB itself NOT mocked (uses testcontainers)?
- Do streaming tests parse SSE lines correctly?

### 8. Code Quality

- `from __future__ import annotations` present?
- No hardcoded model names, paths, or ports?
- No bare `except Exception` swallowing all errors without logging?
- No business logic in the router (all RAG logic is in `orch/rag/qa.py`)?
- Imports clean and organized?

### 9. Design Compliance

Verify each acceptance criterion:
- AC5: Ollama unavailable → SSE error event (not HTTP 503)
- AC6: Project not found → HTTP 404
- AC7: No index found → HTTP 404
- AC8: Question > 1000 chars → HTTP 422

---

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run: `uv run pytest tests/integration/test_code_qa_routes.py -v`
2. Run: `uv run ruff check dashboard/routers/code_qa.py tests/integration/test_code_qa_routes.py`
3. Run: `uv run mypy dashboard/routers/code_qa.py`
4. Report actual pass/fail counts — do NOT assume tests pass

---

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

---

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00049",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL, HIGH, or MEDIUM (fixable) findings. `fail` otherwise.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM (fixable) findings.
