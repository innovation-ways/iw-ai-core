# F-00001_S03_API_prompt

**Work Item**: F-00001 -- Batch Archive with Post-Merge Actions
**Step**: S03
**Agent**: API

---

## Input Files

- `ai-dev/design/active/F-00001/F-00001_Feature_Design.md` -- Design document
- `ai-dev/work/F-00001/reports/F-00001_S01_Backend_report.md` -- Backend step report

## Output Files

- `ai-dev/work/F-00001/reports/F-00001_S03_API_report.md` -- Step report

## Context

You are implementing the dashboard archive endpoint for **Batch Archive with Post-Merge Actions**.

Read the design document first to understand the full scope and your step's deliverables. Then read `CLAUDE.md` for project-specific patterns and conventions.

The batch archiver service was implemented in S01 at `orch/archive/batch_archiver.py`. You will call `archive_batch()` from a background thread.

## Requirements

### 1. Add `archive` to `_BATCH_ACTION_LABELS` in `dashboard/routers/actions.py`

Add an entry to the existing `_BATCH_ACTION_LABELS` dict:

```python
"archive": (
    "Archive batch?",
    "Archives this batch: runs post-merge commands (alembic migrations, docker rebuilds) and archives all work items. This runs in the background.",
    "Archive",
    False,  # not danger — this is a normal completion action
),
```

The existing `confirm_batch_dialog()` GET endpoint at `/project/{project_id}/api/confirm-batch/{action}/{batch_id}` already reads from `_BATCH_ACTION_LABELS`, so adding this entry automatically wires up the confirmation dialog.

### 2. Add POST endpoint for batch archive

Add a new endpoint in `dashboard/routers/actions.py`:

```python
@router.post("/batch/{batch_id}/archive", response_class=Response)
def archive_batch_endpoint(
    project_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> Any:
```

This endpoint must:

1. Load the batch using `_get_batch()`.
2. Validate status is in `completed` or `completed_with_errors`. Return 422 if not.
3. Emit an immediate `batch_archiving` daemon event (so SSE can show "Archiving started..." toast).
4. Launch `archive_batch()` in a background thread using `threading.Thread(target=..., daemon=True).start()`.
5. Return `_action_response("Batch {batch_id} archiving started...", toast_type="info", reload=True)`.

The background thread handles the actual archive work, DB state transition, and emits `batch_archived` or `batch_archive_failed` events when done.

### 3. Add SSE event types

In `dashboard/routers/sse.py`:

- Add `"batch_archived"` and `"batch_archive_failed"` to `_TOAST_EVENTS`
- Add severity mappings to `_TOAST_SEVERITY`:
  - `"batch_archived": "success"`
  - `"batch_archive_failed": "error"`
- Add `"batch_archiving"` to `_TOAST_EVENTS` with severity `"info"`

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Framework-specific patterns (ORM style, API patterns, etc.)
- Test organization and fixtures
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first that define the expected behavior
2. **GREEN**: Write the minimal implementation to make tests pass
3. **REFACTOR**: Improve code structure while keeping all tests green

Do not skip the RED phase. Tests must exist before implementation code.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run the project's unit test command (check Makefile or `CLAUDE.md` for the exact command)
2. Run lint and type checking (check Makefile or `CLAUDE.md` for the exact command)
3. Do **NOT** report `tests_passed: true` unless ALL unit tests pass with zero failures
4. If tests fail, fix them before reporting completion

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "API",
  "work_item": "F-00001",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/actions.py",
    "dashboard/routers/sse.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
