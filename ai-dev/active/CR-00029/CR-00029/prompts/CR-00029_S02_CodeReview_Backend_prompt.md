# CR-00029_S02_CodeReview_Backend_prompt

**Work Item**: CR-00029 -- Add Restart button to the synthetic Worktree Setup (S00) row
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00029 --json`
- `ai-dev/active/CR-00029/CR-00029_CR_Design.md`
- `ai-dev/active/CR-00029/reports/CR-00029_S01_Backend_report.md`
- All files in S01's `files_changed`

## Output Files

- `ai-dev/active/CR-00029/reports/CR-00029_S02_CodeReview_Backend_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files = CRITICAL findings.

## Review Checklist

### 1. `StepDetail.restartable` & `_synthetic_setup_step`

- New `restartable: bool = False` field defaults False so non-synthetic rows are unaffected.
- Computation matches the design: `bi.status in {setup_failed, failed}` AND no WorkflowStep with status != pending. Verify by reading the diff against the design doc's AC1 / AC2.
- Inline comment present, references CR-00029.

### 2. Helper extraction (`_reset_item_to_approved`)

- **CRITICAL — no behavior change in `full_restart_item`**: read the original body and the new helper. They MUST be functionally identical except for the parametrized event_type/event_message. Common sources of accidental drift: reorder of `db.delete(run)` vs filesystem unlink; missed `db.commit()`; missed `_delete_worktree` call.
- Helper signature accepts the parametrized event fields and is private (leading underscore).
- No dead `_FULL_RESTART_ALLOWED` checks duplicated in the helper.

### 3. New `restart_setup` endpoint

- Precondition #1: BatchItem exists in `setup_failed` or `failed` → else 422.
- Precondition #2: no WorkflowStep with status != pending → else 422.
- Both precondition error messages are clear and actionable.
- Success path calls `_reset_item_to_approved` with the right event_type (`setup_restarted`) and message.
- Response shape matches existing endpoints (htmx-friendly).

### 4. `_ITEM_ACTION_LABELS` registration

- A new `restart-setup` entry is added to `_ITEM_ACTION_LABELS` (4-tuple: title, description, confirm_label, danger).
- `danger=True` (destructive — wipes worktree + steps).
- **NO** new GET handler is added. The existing dispatcher `confirm_item_dialog` at `/confirm-item/{action}/{item_id}` handles routing — calling the dispatcher for action="restart-setup" should produce the right title/description and a `confirm_url` of `/project/{project_id}/api/item/{item_id}/restart-setup`.
- If S01 added a custom GET handler instead of (or in addition to) the dict entry — flag as MEDIUM (duplicates the generic pattern).

### 5. Caller compatibility

- Did `_synthetic_setup_step`'s signature change? If so, all callers were updated. Check `dashboard/routers/items.py:430` or wherever the synthetic factory is invoked.

### 6. Project Conventions

- Router prefixes correct (search top of `actions.py` for `APIRouter(prefix=...)`)
- `_emit` helper used for daemon events
- Sync SQLAlchemy

### 7. Code Quality

- No magic strings — use `BatchItemStatus.X` and `StepStatus.X`.
- The select statements use SQLAlchemy 2.0 style.
- Error messages don't leak sensitive info.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00029",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
