# CR-00056 S06 API Report

## What was done

**S06 (API implementation)** adds the server-side plumbing for the step-prompt modal feature:

1. **`has_prompt` field on `StepDetail`** (`dashboard/routers/items.py`)
   - Added `has_prompt: bool = False` dataclass field
   - Populated via a single SQL aggregation query in `_get_steps()`:
     - `MAX(CASE WHEN prompt_text IS NOT NULL OR fix_prompt_text IS NOT NULL THEN True ELSE False)` per `step_id`
     - This avoids the N+1 trap — one query for all steps alongside the existing run-count / last-run queries
   - Synthetic steps (S00/MERGE) are never reached by this code path — they have no `WorkflowStep` row, so the prompt-modal route returns 404 for them (as designed)

2. **`GET /project/{project_id}/item/{item_id}/step/{step_id}/prompt-modal`** route
   - Added at `dashboard/routers/items.py:1336`
   - 404 if `WorkItem(project_id, item_id)` does not exist
   - 404 if `WorkflowStep(project_id, work_item_id=item_id, step_id=step_id)` does not exist
   - Queries all StepRuns for the step ordered by `run_number ASC`
   - Builds sections: first run with non-null `prompt_text` → "Initial Prompt"; each subsequent run with non-null `fix_prompt_text` → "Fix Prompt (cycle N)" (using `run_number - 1` as cycle number)
   - Returns 404 if no sections (no run has prompt_text or fix_prompt_text)
   - Returns rendered `fragments/prompt_text_modal.html`

3. **Placeholder fragment template** (`dashboard/templates/fragments/prompt_text_modal.html`)
   - Minimal valid HTML matching the required context keys
   - Renders `step.step_id`, loops over `sections`, shows `section.label` and `section.text`
   - Does NOT extend `base.html` (fragment contract)
   - S08 (frontend) will replace with the full styled/accessible modal

## Files changed

| File | Change |
|------|--------|
| `dashboard/routers/items.py` | Added `has_prompt` to `StepDetail`, query in `_get_steps()`, new `get_prompt_modal` route |
| `dashboard/templates/fragments/prompt_text_modal.html` | New placeholder fragment (S08 replaces) |
| `tests/dashboard/test_prompt_modal_route.py` | New test file: 6 tests covering 200, 404s, fix-prompt sections, synthetic steps |

## Test results

```
tests/dashboard/test_prompt_modal_route.py 6 passed
- test_returns_200_with_prompt_text
- test_404_unknown_item
- test_404_unknown_step
- test_404_no_prompt_text
- test_fix_prompt_text_sections
- test_synthetic_step_returns_404
```

## Quality gates

| Check | Result |
|-------|--------|
| `make format` | ok (auto-formatted) |
| `make typecheck` | ok (no issues in 251 source files) |
| `make lint` | ok |

## Approach for `has_prompt` population

Added a single aggregation query alongside the existing run-count / last-run queries in `_get_steps()`:

```python
has_prompt_rows = db.execute(
    select(
        StepRun.step_id,
        func.max(
            case(
                (StepRun.prompt_text.isnot(None), True),
                (StepRun.fix_prompt_text.isnot(None), True),
                else_=False,
            )
        ).label("has_prompt"),
    )
    .where(StepRun.step_id.in_(step_db_ids))
    .group_by(StepRun.step_id)
).all()
```

This is efficient (one query, no N+1), correctly handles steps with zero runs (returns False), and mirrors the existing patterns in `_get_steps()`.

## Blockers

None.

## Notes

- The `case(...)` SQLAlchemy import is aliased as `sql_case` to avoid shadowing the existing `case` variable in the `_aggregate_step_spans` function (which uses `from sqlalchemy import case`).
- `StepType.implementation` used in tests (not `StepType.agent` which does not exist).
- `WorkItemType.Feature` used in tests (not the lowercase string `"feature"` which the SQLAlchemy enum rejects). |
