# CR-00065_S04_Api_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S04
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No schema changes in this step.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00065 --json`
- `ai-dev/active/CR-00065/CR-00065_CR_Design.md` — Design document
- `orch/db/models.py` — StepRun (session_file column), WorkflowStep, WorkItem
- `orch/daemon/session_reader.py` — session reader module (implemented in S03)
- `dashboard/routers/items.py` — existing items router (Pydantic models + endpoints)
- `dashboard/CLAUDE.md` — dashboard conventions

## Task

Add a new htmx-fragment endpoint to `dashboard/routers/items.py` that returns rendered log content for a specific step run.

---

### New endpoint

```
GET /project/{project_id}/api/item/{item_id}/step/{step_id}/session-log
```

**Query params**:
- `run_number: int | None = None` — if omitted, use the most recent run (highest `run_number`)

**Logic**:
1. Validate `project_id`, `item_id`, `step_id` exist; return 404 if not found.
2. Query `StepRun` rows for the given `WorkflowStep` DB id; select the requested run (or latest).
3. Call `session_reader.read_session_content(run)` to get the segment list.
4. Determine `is_live: bool = run.status in (RunStatus.running, RunStatus.stalled)`.
5. Render and return the `fragments/session_log_popup_content.html` template with:
   - `segments: list[dict]` — rendered segments from session_reader
   - `is_live: bool` — controls whether htmx polling is enabled
   - `step_id: str` — e.g. "S01"
   - `run_number: int`
   - `cli_tool: str | None` — "pi", "claude", "opencode", or None
   - `item_id: str`, `project_id: str`
   - `error_message: str | None` — from `run.error_message`

**Error handling**:
- 404 if step not found
- 200 with a single error segment if `read_session_content` fails (do not 500)

### Pydantic model (optional, for type safety)

Add a `SessionLogSegment` dataclass or TypedDict to the router:
```python
class SessionLogSegment(TypedDict):
    type: str   # "assistant" | "tool_call" | "tool_result" | "thinking" | "error" | "compaction" | "log"
    text: str
    collapsible: bool
```

### TDD (RED → GREEN → REFACTOR)

Write tests in `tests/dashboard/test_items_session_log.py`:

```python
def test_session_log_endpoint_pi_run_200():
    """GET returns 200 with rendered fragment for pi run with session_file."""

def test_session_log_endpoint_claude_run_200():
    """GET returns 200 with rendered fragment for claude run with log_content."""

def test_session_log_endpoint_not_found_404():
    """GET returns 404 for unknown step_id."""

def test_session_log_endpoint_no_run_returns_empty():
    """GET with no StepRun rows returns 200 with 'no content' message."""

def test_session_log_endpoint_latest_run_default():
    """GET without run_number param returns content for highest run_number."""
```

Use the test database (testcontainer), not mocks. Fixture: create a WorkItem + WorkflowStep + StepRun with `cli_tool="pi"`, `session_file=<path to a fixture .jsonl>` and `cli_tool="claude"`, `log_content="test log content"`.

### Quality gates

```bash
make format
make lint
make typecheck
make test-unit
```

## Output Files

- `dashboard/routers/items.py` — new endpoint appended
- `tests/dashboard/test_items_session_log.py` — new integration tests

## Subagent Result Contract

```bash
uv run iw step-done CR-00065 --step S04 \
  --report ai-dev/work/CR-00065/reports/CR-00065_S04_Api_report.md
```

```json
{
  "step": "S04",
  "agent": "api-impl",
  "work_item": "CR-00065",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/routers/items.py",
    "tests/dashboard/test_items_session_log.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "5 new dashboard integration tests pass",
  "blockers": [],
  "notes": ""
}
```
