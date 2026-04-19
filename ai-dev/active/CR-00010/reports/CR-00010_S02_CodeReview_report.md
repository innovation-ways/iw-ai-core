# CR-00010 S02 Code Review Report

## Summary

Reviewed S01 backend-impl changes for CR-00010 (Research items auto-complete without manual approval). All checklist items pass.

## Files Reviewed

| File | Verdict |
|------|---------|
| `orch/daemon/state_machine.py` | PASS |
| `orch/cli/item_commands.py` | PASS |
| `orch/cli/doc_commands.py` | PASS |
| `orch/cli/batch_commands.py` | PASS |
| `skills/iw-research/SKILL.md` | PASS |

## Checklist Findings

### 1. State Machine Correctness (AC7)
- `_RESEARCH_WORK_ITEM_STATUS` table: `{draft: {completed}, completed: {}}` — exactly correct
- `can_transition_work_item_status(item_type=None)` routes to `_WORK_ITEM_STATUS` — 2-arg calls unchanged
- Routing uses `item_type == WorkItemType.Research` (explicit equality, not truthy check)
- `WorkItemType` imported from `orch.db.models` — no duplicate import

### 2. Validator Rejection (AC1, AC2)
- Research check fires BEFORE status check in both validators — correct order
- `validate_approve_transition` returns `"Cannot approve research items — ..."` substring present
- `validate_unapprove_transition` returns `"Cannot unapprove research items — ..."` substring present
- `approve`/`unapprove` commands pass `item.type` (ORM attribute, not `item.item_type`)
- Exit code `1` matches existing invalid-transition paths

### 3. `doc-update` Auto-Complete (AC3, AC4, AC5)
- Trigger: `doc.doc_type == DocType.research` AND `work_item is not None` AND `work_item.type == WorkItemType.Research` AND `work_item.status == WorkItemStatus.draft` — all four conditions present
- `status == draft` guard provides idempotency (AC4)
- Non-research safety: `doc.doc_type == DocType.research` gate prevents non-research mutation
- Transaction scope: work-item update inside same `with get_session() as session:` block as doc upsert
- `validate_work_item_status` invoked before mutation
- `phase = WorkItemPhase.done` with comment `# research items skip phase 'work' — see CR-00010`
- `completed_at = datetime.now(UTC)` — no hardcoded date
- `work_item_auto_completed` key present in JSON output

### 4. `batch-create` Rejection (AC6)
- Research check BEFORE `status != approved` check — correct order
- Error message contains `"research item"` AND `"cannot be added to a batch"` — both substrings present
- Exit code `1`
- `WorkItemType` imported in module

### 5. Skill Documentation (AC10)
- Step 6 does not instruct `iw approve` — no `iw approve` active instruction found
- Callout present: `"Do NOT run `iw approve` on research items — the command will error"`
- `--status draft` flag removed from doc-update example
- `skills/iw-research-quick/` untouched (confirmed via `git diff`)

### 6. Code Quality / Conventions
- No dead code, no print statements, no commented-out lines
- Type hints: PEP 484 style consistent with module
- `datetime.now(UTC)` used throughout
- `output_error(ctx, msg, exit_code)` used for errors

### 7. Regression Surface
- 2-arg calls to `can_transition_work_item_status` / `validate_work_item_status` route to existing `_WORK_ITEM_STATUS` via `item_type=None` default
- Non-research items: `iw approve F-00001` / `iw approve I-00001` / `iw approve CR-00011` unaffected
- `doc-update` for non-research doc does NOT mutate work item

## Test Results

| Check | Result |
|-------|--------|
| `uv run ruff check orch/` | PASS |
| `uv run ruff format --check orch/` | PASS |
| `uv run mypy orch/` | PASS |
| `make test-unit` | 818 passed, 5 warnings (pre-existing) |

## Notes

- All acceptance criteria (AC1–AC7, AC10) satisfied by code inspection
- No pre-existing tests failed
- S05 will add unit/integration tests for new research flow
