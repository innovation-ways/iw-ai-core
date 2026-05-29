# I-00117 S03 — Reproduction + Regression Tests

## What was done
- Added new integration test file `tests/integration/test_recovery_exhausted_escalation.py`.
- Implemented:
  - `test_exhausted_implementation_step_escalates_visibly`
  - `test_spec_mismatch_still_routes_to_its_own_handler`
- Repro test seeds an `implementation` step in `failed` with two failed `StepRun`s and a non-`SPEC_MISMATCH:` latest reason, then invokes `BatchManager._check_executing_item(...)` and asserts:
  - `work_item.status == WorkItemStatus.failed`
  - `batch_item.status == BatchItemStatus.failed`
  - exactly one `step_recovery_exhausted` event exists for the item
  - event metadata `step_id` matches the failed step
  - structural guard: work item is terminal (`not in_progress`)
- Regression test verifies `SPEC_MISMATCH:` still emits `spec_mismatch_escalation` and does not emit `step_recovery_exhausted`.

## Files changed
- `tests/integration/test_recovery_exhausted_escalation.py`

## Test results
- Command run: `uv run pytest tests/integration/test_recovery_exhausted_escalation.py -v`
- Result: **2 passed, 0 failed**

## Issues / observations
- Tests are green on current branch (post-fix behavior).
- No separate RED run was executed in this step.

## Subagent result contract
```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00117",
  "completion_status": "complete",
  "files_changed": ["tests/integration/test_recovery_exhausted_escalation.py"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed (targeted)",
  "tdd_red_evidence": "not captured in this step (tests executed on post-fix branch)",
  "blockers": [],
  "notes": "Targeted integration tests added per AC1-AC3."
}
```
