# CR-00008 S01 — API: SSE wire format rework

**Work Item**: CR-00008 — Code module chat: docked panel, streaming markdown, beautiful diagrams (MVP)
**Step**: S01
**Agent**: api-impl

---

## Input Files (read first)

- `CLAUDE.md` and `dashboard/CLAUDE.md` — hard rules, SSE conventions
- `ai-dev/active/CR-00008/CR-00008_CR_Design.md` — full design (source of truth). See AC3.
- `docs/research/R-00048-code-module-chat-ux.md` — F6 (SSE newline gotcha, base64 workaround)
- `dashboard/routers/code_qa.py` — the file to modify
- `orch/rag/qa.py` — `QAEngine.answer_stream()` (do NOT modify — read only)

## Output Files

- **Modified**: `dashboard/routers/code_qa.py`
- **New**: `ai-dev/active/CR-00008/reports/CR-00008_S01_Api_report.md`

## Context

The current SSE wire format on `POST /api/projects/{project_id}/code/qa` is plain JSON: `data: {"token": "..."}` and `data: {"event": "done", "full_response": "..."}`. It breaks when a token contains a `\n` (SSE uses newlines as record separators), lacks citation events, and lacks explicit `event:` field names. Replace it with a named-event format using base64-encoded token payloads — the client side is being rewritten in S03/S05/S07 and will consume the new shape.

## Tasks

### Task 1 — Reshape the SSE wire format

Emit **named events** using the `event:` SSE field plus `data:` payload. Keep the endpoint path, request body, HTTPException behaviour, and `StreamingResponse` headers unchanged.

```
event: token
data: {"b64": "<base64 of utf-8 bytes of the delta>"}

event: citation
data: {"n": 1, "label": "orch.rag.qa:answer_stream", "url": "/project/<pid>/code/module/orch.rag.qa#answer_stream", "snippet": "first ~240 chars of the cited symbol"}

event: done
data: {"ok": true}

event: error
data: {"message": "Local AI unavailable. Check that Ollama is running."}
```

Rules:
- `token` payload uses `"b64"` as the key. Encode with `base64.b64encode(token.encode("utf-8")).decode("ascii")`.
- `citation` events are **cumulative** and **ordered by `n`** (1-indexed). It is valid for citations to arrive mid-stream; the client will deduplicate by `n`.
- Exactly one terminal event: either `done` or `error`. Never both. After either, the generator returns.
- Keep the upstream call to `QAEngine.answer_stream(...)` unchanged. The base64 encoding happens at the SSE boundary.
- Preserve the existing response headers (`Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`) and the 404 check on the LanceDB index path.

### Task 2 — Citation extraction hook (best-effort)

`QAEngine.answer_stream` does not currently yield citations. For MVP, emit citations **only if** the engine exposes them — do not modify the engine.

- Probe the engine for an attribute or method that exposes retrieved symbols (e.g., `engine.last_retrieved`, `engine.citations`, a yielded `dict` sentinel, or a field on a structured token). If a clean integration point exists, use it; otherwise **emit zero citation events** for MVP and record the gap in the report notes (tracked as follow-up).
- Implement a small `_CitationTracker` dataclass in the same module that de-dupes by `(symbol_id_or_label)` and assigns monotonic 1-based indices. Only emit a `citation` event when a **new** entry is added.

### Task 3 — Image-attachment stub

Add a **second** handler for `POST /api/projects/{project_id}/code/qa` that accepts `multipart/form-data` and returns HTTP **501 Not Implemented** with `{"detail": "Image attachments coming soon"}`. This is a contract boundary for a future CR and is tested in S09. Implementation notes:

- Use FastAPI's ability to route by Content-Type, OR add a distinct path like `POST /api/projects/{project_id}/code/qa-with-image` if content-type routing is awkward. Prefer whichever is **simpler and cleaner** in FastAPI — document the choice in your report.
- No image is saved. No multipart body is parsed beyond recognition.

### Task 4 — Tests you write (RED → GREEN)

Write these failing first, then implement:

- `tests/dashboard/test_code_qa_sse_wire.py::test_token_event_shape` — a short stream with a token containing `\n` arrives as `event: token` + valid `data: {"b64": "..."}`; decoding gives back the exact bytes.
- `test_done_event_emitted_once` — at most one `done` event is emitted, and the stream ends immediately after.
- `test_error_event_on_connection_refused` — upstream `ConnectionRefusedError` yields `event: error` with a message, no `done`, and the generator returns.
- `test_citation_event_monotonic_if_any` — if citations are emitted, their `n` values are strictly increasing starting from 1, with no duplicates.
- `test_image_attachment_stub_returns_501` — multipart POST returns 501 with the expected detail.

Mock `QAEngine.answer_stream` — do not hit real Ollama.

## Hard rules

- **NEVER** change the request body shape.
- **NEVER** store image bytes server-side in this CR.
- Keep the module under 250 lines.
- Ruff + mypy must be clean.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run ruff check dashboard/routers/code_qa.py
uv run mypy dashboard/routers/code_qa.py
uv run pytest tests/dashboard/test_code_qa_sse_wire.py -v
```

All three must be zero-failure before you report `tests_passed: true`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "api-impl",
  "work_item": "CR-00008",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/code_qa.py", "tests/dashboard/test_code_qa_sse_wire.py"],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Note whether QAEngine exposed a clean citation hook; if not, confirm citations deferred."
}
```
