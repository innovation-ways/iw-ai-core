# CR-00028_S03_Backend_prompt

**Work Item**: CR-00028 -- Don't cascade merge-time failures to dependent items
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute Docker mutating commands. Allowed: testcontainers via pytest, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00028 --json`
- `ai-dev/active/CR-00028/CR-00028_CR_Design.md` — design document
- `ai-dev/active/CR-00028/reports/CR-00028_S01_Database_report.md` — DB step report
- `ai-dev/active/CR-00028/reports/CR-00028_S02_CodeReview_Database_report.md` — DB review

## Output Files

- `orch/daemon/merge_queue.py` — modified
- `orch/daemon/batch_manager.py` — modified
- `dashboard/routers/actions.py` — modified
- `dashboard/routers/sse.py` — modified (register new `merge_abandoned` event)
- `ai-dev/active/CR-00028/reports/CR-00028_S03_Backend_report.md` — step report

## Context

You are implementing the backend behavior change for **CR-00028**. The full design is in `ai-dev/active/CR-00028/CR-00028_CR_Design.md` — read it first. Read `CLAUDE.md` and `orch/CLAUDE.md` for architecture and conventions.

The S01 step has added the `BatchItemStatus.merge_failed` enum value. Your job is to wire it into the daemon and the operator action endpoints.

## Requirements

### 1. Update `orch/daemon/merge_queue.py`

**Line 289 (`MergeError` / `subprocess.TimeoutExpired` handler)** — change:
```python
batch_item.status = BatchItemStatus.failed
```
to:
```python
batch_item.status = BatchItemStatus.merge_failed
```

The accompanying `notes`, `_revert_work_item`, `worktree_compose.down`, and `_emit_event("merge_conflict", ...)` calls remain unchanged.

**Line 136 (no-worktree-path branch) — DO NOT CHANGE.** That branch indicates an unrecoverable data-integrity issue and must keep producing `failed` so the cascade fires. Add a brief inline comment explaining why this branch is intentionally different from line 289.

The pre-merge rebase failure (line ~159, `BatchItemStatus.migration_rebase_failed`) and Phase 1 dry-run failure (line ~196, `BatchItemStatus.migration_invalid`) keep their existing status values — the cascade gate in `batch_manager.py` is what changes for them.

### 2. Update `orch/daemon/batch_manager.py`

**Line 59 — `_BLOCKING_TERMINAL_STATUSES`**: extend the exclusion set:
```python
_BLOCKING_TERMINAL_STATUSES = TERMINAL_BATCH_ITEM_STATUSES - {
    BatchItemStatus.merged,
    BatchItemStatus.merge_failed,
    BatchItemStatus.migration_invalid,
    BatchItemStatus.migration_rebase_failed,
}
```

Update or add a comment explaining: these four are non-cascading because they are operator-recoverable (the operator can retry the merge after fixing the underlying issue). All other terminal statuses still cascade.

**Line 1368 — `_current_execution_group`**: add the three new non-terminal-from-the-group's-perspective statuses to the set the function checks:
```python
if item.status in (
    BatchItemStatus.pending,
    BatchItemStatus.setting_up,
    BatchItemStatus.executing,
    BatchItemStatus.completed,
    BatchItemStatus.merging,
    BatchItemStatus.merge_failed,
    BatchItemStatus.migration_invalid,
    BatchItemStatus.migration_rebase_failed,
):
    return item.execution_group
```

The semantic: an item in any of the operator-recoverable merge-failure states keeps its execution_group "open", so dependents in later groups stay paused (not cascaded).

### 3. Update `dashboard/routers/actions.py`

#### 3a. Extend `restart-merge` precondition

Locate the existing `restart-merge` endpoint (search for `restart-merge` or `restart_merge`). Update the precondition to accept the three operator-recoverable statuses:

```python
ALLOWED_RETRY_STATUSES = {
    BatchItemStatus.merge_failed,
    BatchItemStatus.migration_invalid,
    BatchItemStatus.migration_rebase_failed,
}
```

If the existing handler also accepts a legacy `failed` status with merge-failure metadata, preserve that path for back-compat with historical rows (but log a deprecation note).

The handler should (these are the existing behaviors — preserve them; do NOT invent new ones):

- Reset `batch_item.status = BatchItemStatus.completed` so the merge queue re-picks it
- Reset `batch_item.notes = None` and `batch_item.merge_info = {}`
- If parent batch is in `completed_with_errors`, re-open it to `BatchStatus.approved` and clear `batch.completed_at` (matches `actions.py:948-950` exactly — do NOT set to `executing`)
- Emit a `merge_restarted` daemon event (PAST tense — matches the existing event name at `actions.py:954`)

The existing implementation at `actions.py:907-966` already does all of the above. Your edit is purely a precondition-extension job:

1. Replace `BatchItem.status == BatchItemStatus.failed` with a `.in_(...)` check against `{merge_failed, migration_invalid, migration_rebase_failed}`.
2. Drop or relax the `notes.startswith("Merge failed")` discriminator — it was needed only to disambiguate `failed`-from-merge-error from `failed`-from-setup-error. With the new enum values that disambiguation is structural, not textual. Keep a back-compat branch that still accepts a `failed` row whose notes start with `"Merge failed"` (existing rows from before the migration).
3. Verify the rest of the handler body (status reset, notes/merge_info clearing, batch re-open to `approved`, `merge_restarted` event, `_action_response`) is unchanged.

#### 3b. Add new `abandon-merge` endpoint

Add a new POST route `/actions/{project_id}/item/{item_id}/abandon-merge`:

```python
@router.post("/item/{item_id}/abandon-merge", response_class=Response)
def abandon_merge(
    project_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> Any:
    ...
```

Behavior:
- Precondition: `batch_item.status` MUST be one of `{merge_failed, migration_invalid, migration_rebase_failed}`. Otherwise raise `HTTPException(422)`.
- Action:
  - `batch_item.status = BatchItemStatus.failed` (now blocking-terminal → cascade fires next poll)
  - `batch_item.notes = (existing notes or "") + " [operator abandoned via abandon-merge]"`
  - WorkItem.status remains `failed`
- Emit a `merge_abandoned` daemon event with `entity_id=item_id`, `entity_type="work_item"`, message documenting which status was abandoned. Use the existing `_emit` helper (see `actions.py:952-959` for the `merge_restarted` precedent).
- Return an htmx-friendly response via `_action_response(message, toast_type="warning", reload=True)` — match the existing `restart_merge` shape.

Match the project's existing action-handler shape (return type, dependency injection, event emission helper).

#### 3c. Register `abandon-merge` in the item-action labels dict

`actions.py` has a module-level `_ITEM_ACTION_LABELS: dict[str, tuple[str, str, str, bool]]` (around line 80) used by the `confirm_item_dialog` route to render confirmation modals (the dashboard surfaces actions through `hx-get → /confirm-item/<action>/<item_id>` then the modal posts to `/api/item/<item_id>/<action>`). Add an entry:

```python
"abandon-merge": (
    "Abandon merge?",
    "Marks this item as failed and cascade-fails all dependent items in later groups. "
    "This is irreversible without manual SQL. Use only if the merge cannot be recovered.",
    "Abandon Merge",
    True,  # danger=True
),
```

Also extend the existing `restart-merge` entry's description if it currently only mentions `failed` — clarify it now applies to `merge_failed`, `migration_invalid`, `migration_rebase_failed` too.

### 4. Register the new `merge_abandoned` event in the SSE registry

Edit `dashboard/routers/sse.py`:

- Add `"merge_abandoned"` to the `_TOAST_EVENTS` frozenset (next to the existing `"merge_conflict"` entry).
- Add `"merge_abandoned": "warning"` to the `_TOAST_SEVERITY` dict.

Without this, operators will not see a toast when an item is abandoned, and the `_WATCHED_EVENTS` filter will discard the event (the SSE feed only forwards events in the union of those sets).

`merge_restarted` is already an existing event but is not in the toast set today; do NOT add it as part of this CR (that would expand scope unnecessarily).

### 5. Verify the invariant

After your changes, the invariant **"setup of item N+1 runs only after item N's merge is 100% complete"** must still hold. The poll order in `daemon/main.py:_poll_cycle()` is `_process_batch` → `process_merge_queue`. With your changes:

- If item N is `merging`, dependents stay pending (unchanged — `merging` was already non-terminal in the group).
- If item N is `merge_failed`, dependents stay pending (NEW — was previously cascade-failed).
- If item N is `merged`, dependents launch in the next group (unchanged).
- If item N is `failed` (e.g. from worktree_compose down or no-worktree-path), dependents cascade-fail (unchanged).

Add a one-line code comment in `_BLOCKING_TERMINAL_STATUSES` and `_current_execution_group` referencing CR-00028 so future readers understand the rationale.

## Project Conventions

- `orch/daemon/` modules are sync; keep them sync
- Use `_emit_event` helper for daemon_events (see `merge_queue.py:316`)
- Dashboard routes return htmx fragments, not JSON, for action endpoints
- The `actions.py` file has many precedents for the response shape — match them

## TDD Requirement

The full test suite for this CR is authored in S07. For S03:

1. Author the **minimum** unit test(s) needed to validate the new code paths in your file(s) (e.g., a smoke test that `_merge_item` writes `merge_failed`, a smoke test that `abandon-merge` returns 422 for an item in `pending`).
2. Run them. Don't ship code if they fail.
3. The exhaustive coverage (integration tests, all 7 ACs) lives in S07.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format`
2. `make typecheck` — zero errors involving the files you touched
3. `make lint`

Populate the `preflight` object.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — must pass
2. Do NOT mark `tests_passed: true` unless tests pass

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00028",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/merge_queue.py",
    "orch/daemon/batch_manager.py",
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
  "notes": "Any tests pre-existing in unit/integration suites that needed updating because they expected BatchItemStatus.failed after a scope-gate merge — list them so S07 can finalize coverage."
}
```
