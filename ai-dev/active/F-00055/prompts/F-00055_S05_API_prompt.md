# F-00055_S05_API_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S05
**Agent**: api-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` (AC1, AC2, AC6, AC7, AC10; Invariants 3, 4, 6)
- `ai-dev/active/F-00055/reports/F-00055_S03_Backend_report.md`, `F-00055_S04_CodeReview_report.md`
- `dashboard/routers/code_qa.py` — current `_CitationTracker`, `_run_qa_in_thread`, `_sse_generator`, `code_qa` endpoint
- `dashboard/dependencies.py` — `get_db`
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S05_API_report.md`

## Context

Extend the SSE streaming endpoint `POST /api/projects/{project_id}/code/qa` to forward the new dict-shaped outputs from `QAEngine.answer_stream_v2` as structured SSE events. Introduce the `phase` event type; enrich the `citation` event payload with work-item fields; consolidate `/findusages` routing.

## Requirements

### 1. Request-schema extension

`QARequest` (Pydantic) already accepts `context_chips: list[str]` — confirm this field accepts the new values `why`, `history`, `findusages`. No schema change needed if the field is permissive (current regex none); document the expected values in the field description.

### 2. SSE event catalog

Add the `phase` event to the event producer:

```
event: phase
data: {"name": "retrieving|finding_items|reading_docs|composing", "detail": {...}}

event: token
data: {"b64": "..."}          # unchanged

event: citation
data: {"n": 1, "label": "...", "url": "...", "snippet": "...",
       "work_item_type": "feature|incident|change_request",
       "work_item_id": "F-00042"}   # extended with last two fields

event: done
data: {"ok": true}            # unchanged

event: error
data: {"message": "..."}      # unchanged
```

### 3. `_sse_generator` extension

The current generator reads `str` tokens from the thread-bridged queue and formats them as `token` SSE events. Extend:

- Update `_run_qa_in_thread` to consume `dict`-shaped outputs from `QAEngine.answer_stream_v2` (from S03) and push them to the queue as dicts (not strings).
- In `_sse_generator`, branch on `item["kind"]`:
  - `"phase"` → emit `event: phase\ndata: {json}\n\n`.
  - `"token"` → existing base64 token event.
  - `"citation"` → existing citation event, with the two new fields included.
- Preserve the `None`-sentinel-terminates-queue pattern and the error handling.

### 4. Backwards compatibility

For the code-only pipeline (no `context_chips` triggers, classifier returns `code_only`):
- Engine yields only `{"kind": "token"}` dicts.
- No `phase` events are emitted (Invariant 3).
- Legacy clients (that don't know about `phase`) ignore unknown event types by spec; verify the existing `stream.js` does not crash on unknown events (it already only handles known `event:` lines — any new event is silently dropped. Confirm this and note in the review).

### 5. `_CitationTracker` extension

The current tracker de-duplicates by symbol ID and assigns 1-based indices. Extend:
- Store `work_item_type` and `work_item_id` alongside the index.
- Provide `add_work_item(work_item_id: str, work_item_type: str) -> int | None` (symmetric with existing `add(symbol_id)`).
- `work_item_id` format validation: regex `^(F|I|CR)-\d{5}$`; reject otherwise (Invariant 4).

### 6. `/findusages` consolidation (AC7)

- The existing `context_chips` handling for `/findusages` currently has no backend effect. After this step:
  - When `findusages` is in chips, set a new flag on the request to route to the work-item-aware pipeline AND pass the next token in the user question as a `symbol_hint` to the backend retrieval (the frontend already strips the `/findusages` command from the text; the remaining input is the symbol).
  - Engine uses `symbol_hint` to bias the code-LanceDB retrieval toward rows whose text contains the symbol.

### 7. Rerender endpoint (AC5)

Add a new SSE endpoint `POST /api/projects/{project_id}/code/qa/rerender` to back the tone-switch chip:

- Request body: `{"render_id": "<hex>", "tone": "technical|functional"}` (Pydantic model `QARerenderRequest`).
- Handler: calls `engine.rerender(render_id, tone)` (from S03); streams the resulting dict sequence through the same `_sse_generator` branch logic (phase / token / citation / done events).
- On `RenderCacheMiss`: return HTTP 410 Gone with JSON body `{"error": "render_expired"}` so the frontend knows to re-submit the original question with the `tone:<register>` chip instead of a silent failure.
- Emit the `composing` phase with the same `render_id` and include `{"rerendered": true}` in its `detail` so the frontend can distinguish a rerender stream from a fresh retrieval.
- Unit test: `tests/unit/test_code_qa_router_rerender.py` — hit path, 410 on miss, event shapes.

### 8. Error semantics

- Any exception from the new pipeline surfaces as `event: error` (unchanged shape).
- Git-log subprocess errors and LanceDB-doc-table missing errors MUST be handled in the engine, not bubble to the router (verified in S04).

## Project Conventions

Read `dashboard/CLAUDE.md`:
- Routers are thin — validation + delegation only.
- htmx pattern for most endpoints; SSE reserved for real-time feeds (this endpoint is SSE).
- `dependencies.py:get_db()` uses the sync `SessionLocal`.

## TDD Requirement

Red-Green-Refactor. Required tests:

1. `tests/unit/test_code_qa_router_phase.py` — SSE output for a mocked engine that yields all four phases; asserts event ordering and payload.
2. `tests/unit/test_code_qa_router_citations.py` — new work-item citation payload shape; symbol_id-based citations still work.
3. `tests/unit/test_code_qa_router_findusages.py` — `findusages` chip triggers symbol-hint extraction; default flow unaffected.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — must pass.
2. `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy orch/ dashboard/` — must pass.
3. Start dashboard locally (`make dashboard-start` or manual `uv run uvicorn dashboard.app:app`) and curl the SSE endpoint with `context_chips: ["why"]` against a seeded project; confirm event sequence in the terminal.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "api-impl",
  "work_item": "F-00055",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/code_qa.py",
    "tests/unit/test_code_qa_router_phase.py",
    "tests/unit/test_code_qa_router_citations.py",
    "tests/unit/test_code_qa_router_findusages.py",
    "tests/unit/test_code_qa_router_rerender.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
