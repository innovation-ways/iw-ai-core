# CR-00009_S03_Api_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Step**: S03
**Agent**: api-impl

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md` — design document
- `ai-dev/active/CR-00009/reports/CR-00009_S01_Backend_report.md` — S01 result (QAEngine.answer_stream now accepts `module_name`)
- `dashboard/routers/code_qa.py` — file to modify

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S03_Api_report.md`

## Context

S01 extended `QAEngine.answer_stream` with an optional `module_name: str | None = None` parameter. This step wires the router to accept `module_name` in the request body and forward it. Read the design doc's **Desired Behavior** item 4 and AC7 before coding.

## Requirements

### 1. Add `module_name` to `QARequest`

In `dashboard/routers/code_qa.py`, the `QARequest` Pydantic model currently has (approximately):

```python
class QARequest(BaseModel):
    question: str
    context_level: str = Field(pattern="^(architecture|module)$")
    context_doc_id: str | None = None
    module_path: str | None = None
    conversation_history: list[ConversationMessage] = []
```

Add `module_name: str | None = None` directly after `module_path`. Match the existing field style (no `Field(...)` wrapper unless one is already in use on `module_path`).

### 2. Forward `module_name` to the engine

The handler currently calls something like:

```python
engine.answer_stream(
    question=body.question,
    context_level=body.context_level,
    context_doc_id=body.context_doc_id,
    conversation_history=[m.model_dump() for m in body.conversation_history],
    session=session,
    module_path=body.module_path,
)
```

Add a `module_name=body.module_name` kwarg in the matching position.

### 3. Do not change the response shape, SSE events, or error contracts

This step is strictly additive: one new request field, one new kwarg. Do not touch:

- Streaming SSE event names or payload shapes
- Multipart image 501-stub
- Citation payload
- `ConversationMessage` shape
- Authentication or session dependency wiring

### 4. Backwards compatibility (AC7)

A POST without `module_name` must still succeed. Since the field defaults to `None`, this is automatic — but verify by exercising the endpoint (existing integration test or manual curl) that omission does not trigger a 422.

## Project Conventions

- Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Routers are thin: validation + delegation only. No business logic here.
- Pydantic v2 style (`model_dump()`, `Field(...)` if needed). Match whatever the file already uses.
- Type hints everywhere.

## TDD Requirement

1. **RED**: `tests/integration/test_code_qa_routes.py` exists — you MAY add an inline failing test there that posts a body with `module_name="Orchestration Daemon"` and asserts it reaches `QAEngine.answer_stream` (via a spy / mock). Alternatively, defer the RED phase to S07 and record in your report that you added no inline test.
2. **GREEN**: Implement the changes above.
3. **REFACTOR**: None expected — the change is a 2-line addition.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration` (if the router test file exists and was touched)
3. `uv run ruff check dashboard/routers/code_qa.py`
4. `uv run mypy dashboard/routers/code_qa.py`

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "api-impl",
  "work_item": "CR-00009",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/code_qa.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
