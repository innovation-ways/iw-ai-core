# CR-00029_S01_Backend_prompt

**Work Item**: CR-00029 -- Add Restart button to the synthetic Worktree Setup (S00) row
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute Docker mutating commands. Allowed: testcontainers via pytest, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00029 --json`
- `ai-dev/active/CR-00029/CR-00029_CR_Design.md` — design document

## Output Files

- `dashboard/routers/items.py` — modified (StepDetail, _synthetic_setup_step)
- `dashboard/routers/actions.py` — modified (new endpoints + helper extraction)
- `ai-dev/active/CR-00029/reports/CR-00029_S01_Backend_report.md`

## Context

Read the design doc at `ai-dev/active/CR-00029/CR-00029_CR_Design.md` first. Read `CLAUDE.md` and `dashboard/CLAUDE.md` for conventions.

This step has four coupled pieces of work:

1. Extend the `StepDetail` dataclass with a `restartable: bool` field, and compute it in `_synthetic_setup_step`.
2. Refactor `full_restart_item`'s body into a private helper so the new `restart_setup` endpoint can share it.
3. Add the new `restart_setup` POST endpoint.
4. Register the dialog wording for the new action by adding a `restart-setup` entry to the existing `_ITEM_ACTION_LABELS` dispatcher (do **not** add a custom GET handler — the existing `confirm_item_dialog` at `/confirm-item/{action}/{item_id}` already routes by action slug).

## Requirements

### 1. Extend `StepDetail` and `_synthetic_setup_step`

In `dashboard/routers/items.py`:

- **`StepDetail` dataclass** (around line 46–63): add `restartable: bool = False` (defaults to False so non-synthetic rows are unaffected).
- **`_synthetic_setup_step`** (line 562): compute and set `restartable`. Definition:
  - True iff: `bi is not None` AND `bi.status in {BatchItemStatus.setup_failed, BatchItemStatus.failed}` AND no `WorkflowStep` for this work_item has `status != StepStatus.pending`.
  - False otherwise.

To check the WorkflowStep states efficiently, the function may need to accept a `db` session or a pre-computed list of WorkflowStep statuses. Look at how `_synthetic_setup_step` is called (search for callers) and pick the cleaner signature. A common pattern in this file is to pass the steps list to the synthetic-step factories.

Add a brief inline comment referencing CR-00029 explaining the purpose of `restartable`.

### 2. Refactor `full_restart_item` (extract helper)

In `dashboard/routers/actions.py:1042–1138`, extract the body (worktree-path discovery + log-file unlink + StepRun delete + WorkflowStep reset + WorkItem→approved + BatchItem reset + Batch re-open + worktree filesystem delete) into a private function:

```python
def _reset_item_to_approved(
    db: Session,
    project_id: str,
    item_id: str,
    *,
    event_type: str,
    event_message: str,
) -> None:
    """Shared reset logic for full_restart_item and restart_setup.

    Returns nothing; commits the DB changes and best-effort deletes the worktree.
    """
    ...
```

Then `full_restart_item`'s remaining body becomes:
- precondition check (`item.status not in _FULL_RESTART_ALLOWED` → 422)
- call `_reset_item_to_approved(db, project_id, item_id, event_type="item_full_restarted", event_message="Item ... fully restarted by user (worktree deleted, logs cleared)")`
- return `_action_response(...)`

The helper MUST behave **identically** to the current `full_restart_item` body — no behavior change. The only difference is parametrized event type/message.

### 3. New `restart_setup` endpoint

Add to `dashboard/routers/actions.py`:

```python
@router.post("/item/{item_id}/restart-setup", response_class=Response)
def restart_setup(
    project_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> Any:
    item = _get_item(db, project_id, item_id)

    # Precondition: item failed at setup specifically
    batch_item = db.scalar(
        select(BatchItem).where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
            BatchItem.status.in_(
                [BatchItemStatus.setup_failed, BatchItemStatus.failed]
            ),
        )
    )
    if batch_item is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot restart setup: no BatchItem in setup_failed/failed status "
                f"for {item_id}"
            ),
        )

    # No WorkflowStep may have progressed past pending
    has_progressed = db.scalar(
        select(WorkflowStep)
        .where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.status != StepStatus.pending,
        )
        .limit(1)
    )
    if has_progressed is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot restart setup: at least one step has progressed past pending "
                f"for {item_id}. Use the full restart action instead."
            ),
        )

    _reset_item_to_approved(
        db,
        project_id,
        item_id,
        event_type="setup_restarted",
        event_message=f"Setup restarted by user for {item_id} (worktree deleted, all steps reset)",
    )

    return _action_response(
        f"Setup restarted for {item_id} — daemon will re-run worktree setup.",
        toast_type="success",
        reload=True,
    )
```

### 4. Register the dialog in `_ITEM_ACTION_LABELS`

Do **NOT** add a new GET handler. The router (`prefix="/project/{project_id}/api"`) already exposes a generic dispatcher at `/confirm-item/{action}/{item_id}` (see `confirm_item_dialog` ~line 692) that looks up the dialog text from `_ITEM_ACTION_LABELS` and renders `fragments/confirm_action.html`. To plug into it, add an entry to the dict (top of the file, near `restart-merge`):

```python
_ITEM_ACTION_LABELS: dict[str, tuple[str, str, str, bool]] = {
    ...
    "restart-merge": (
        "Restart merge?",
        ...
    ),
    "restart-setup": (
        "Restart setup?",
        "This deletes the worktree and resets every step. The daemon will re-run setup from scratch.",
        "Restart Setup",
        True,  # destructive — show as danger
    ),
}
```

The dispatcher will produce: title `"Restart setup {item_id}?"`, description as above, confirm button label `"Restart Setup"`, and `confirm_url = f"/project/{project_id}/api/item/{item_id}/restart-setup"` — automatically matching the POST endpoint.

Do **NOT** introduce a new template or a new GET handler.

### 5. Caller updates for `_synthetic_setup_step`

If you changed the signature in step 1, update the caller around `dashboard/routers/items.py:430`. Re-run the unit tests to confirm the change isn't breaking anything else.

## Project Conventions

- FastAPI routers: items.py uses `prefix="/project/{project_id}"`; actions.py uses `prefix="/project/{project_id}/api"` (verify by reading the top of the file)
- htmx fragments returned via `templates.TemplateResponse`
- Daemon events emitted via `_emit` helper (see existing usage in actions.py)
- No async — sync SQLAlchemy throughout

## TDD Requirement

Author the **minimum** smoke tests in this step:

1. `_synthetic_setup_step` returns `restartable=True` for the documented happy path
2. `restart-setup` endpoint returns 422 for an item where a step is `in_progress`
3. `restart-setup` endpoint succeeds for the happy path

Full coverage is in S05.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

`make test-unit` must pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00029",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/items.py",
    "dashboard/routers/actions.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Helper signature, any caller updates, confirm-dialog template context shape"
}
```
