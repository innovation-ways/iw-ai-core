# CR-00028_S04_CodeReview_Backend_prompt

**Work Item**: CR-00028 -- Don't cascade merge-time failures to dependent items
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute Docker mutating commands. Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00028 --json`
- `ai-dev/active/CR-00028/CR-00028_CR_Design.md` — design
- `ai-dev/active/CR-00028/reports/CR-00028_S03_Backend_report.md` — implementation report
- All files in S03's `files_changed`

## Output Files

- `ai-dev/active/CR-00028/reports/CR-00028_S04_CodeReview_Backend_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files = CRITICAL findings (`category: conventions`).

## Review Checklist

### 1. Architecture & Invariant Preservation

- **CRITICAL — invariant check**: with the changes, does setup of item N+1 still wait until item N's merge is 100% complete? Trace `daemon/main.py:_poll_cycle` to confirm `_process_batch` is called in the same poll as `process_merge_queue` and that `_current_execution_group` correctly returns the group containing a `merge_failed`/`migration_invalid`/`migration_rebase_failed` item (so launching of group N+1 is gated).
- **CRITICAL — cascade preservation**: legacy `failed` (e.g. from `merge_queue.py:136` no-worktree-path) MUST still cascade. Verify `_BLOCKING_TERMINAL_STATUSES` still contains `failed`.
- Are the four exclusions (`merged`, `merge_failed`, `migration_invalid`, `migration_rebase_failed`) cleanly justified by a code comment referencing CR-00028?

### 2. `merge_queue.py` Changes

- **Line ~289**: status writes `merge_failed`, not `failed`. Confirm.
- **Line ~136**: status STILL writes `failed`. Confirm. Does the inline comment explain the rationale (data-integrity vs. operator-recoverable)?
- The `_revert_work_item`, `worktree_compose.down`, and event-emission paths are unchanged.

### 3. `batch_manager.py` Changes

- `_BLOCKING_TERMINAL_STATUSES` extended correctly.
- `_current_execution_group` now treats the three new statuses as group-non-terminal (returns the group, not advances past it).
- The cascade block (lines ~312–325) is unchanged in logic — it just sees a different `_BLOCKING_TERMINAL_STATUSES` and naturally ignores the recoverable statuses. Verify by reading the diff.

### 4. `actions.py` Changes

- `restart-merge` precondition now accepts the three recoverable statuses. Behavior on each:
  - `merge_failed` → reset to `completed` so merge queue picks it up
  - `migration_invalid` → same
  - `migration_rebase_failed` → same
- The handler still resets `batch.status` from `completed_with_errors` to `BatchStatus.approved` (NOT `executing`) — verify the existing pattern is preserved (the implementation prompt's earlier draft mistakenly said `executing`; the correct target is `approved`).
- The event emitted on retry remains `merge_restarted` (past tense — matches the pre-existing event name; the prompt's earlier draft mistakenly said `merge_restart`).
- `abandon-merge` is a new POST endpoint:
  - 422 on disallowed status (anything other than the three recoverable statuses)
  - flips status to `failed` (cascade fires next poll)
  - emits `merge_abandoned` event
  - returns htmx-friendly response via `_action_response(toast_type="warning", reload=True)`
- `_ITEM_ACTION_LABELS["abandon-merge"]` is registered (with `danger=True`) so the confirm-modal route can render the dialog.
- `dashboard/routers/sse.py`: `merge_abandoned` is added to BOTH `_TOAST_EVENTS` and `_TOAST_SEVERITY`. Without both, the SSE feed silently drops the event.

### 5. Code Quality

- Magic strings? Should be `BatchItemStatus.X` enum members, not raw strings.
- Are events emitted with the same key naming style as the rest of `merge_queue.py` and `actions.py`?
- Any duplication between `restart-merge` and the legacy `failed`-handling branch? If so, refactor or accept (note in review).

### 6. Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`. Daemon = sync SQLAlchemy. Dashboard actions = htmx fragments.

### 7. Tests

S03 was expected to author smoke tests only. Verify they exist and pass. Full coverage is S07.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

Must pass. Run integration tests if affordable (`make test-integration`) and report.

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00028",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
