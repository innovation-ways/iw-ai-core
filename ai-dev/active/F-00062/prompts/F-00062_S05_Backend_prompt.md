# F-00062_S05_Backend_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step**: S05
**Agent**: backend-impl

---

## ⛔ Docker is off-limits — with one narrow exception

You MUST NOT execute docker state-changing commands FROM CODE OUTSIDE `orch/daemon/worktree_compose.py` (the module created in S03). This step's reaper code is allowed to invoke `docker ps -a --filter label=iwcore.role=...` (read-only label query) and call `worktree_compose.down(batch_item_id)` to perform reaping — the actual docker subprocess lives in the S03 module.

Read-only `docker ps|inspect|logs` allowed elsewhere for debugging. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You do NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc (ACs 4, 5, 6, 7)
- S01-S04 reports
- `orch/daemon/worktree_compose.py` — the module you call into (S03)
- `orch/daemon/batch_manager.py` — where the lifecycle hooks are inserted
- `orch/daemon/main.py` — daemon entry point (where startup reaper hook goes)
- `orch/daemon/browser_env.py` — reference for the existing per-step lifecycle pattern (yours is per-batch-item)
- `orch/db/models.py` — `BatchItem` and `BatchItemStatus`

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S05_Backend_report.md`

## Context

S03 built the per-worktree compose lifecycle primitives. This step wires them into the daemon's batch lifecycle: invoke `up()` after the worktree is created (after `executor/worktree_setup.sh` completes), invoke `down()` on terminal-state transitions, and add a label-based reaper that classifies all `iwcore-*` containers and reaps the orphans/stale ones on daemon startup and on a periodic schedule.

You are NOT modifying executor bash scripts. The hook into the lifecycle goes through `orch/daemon/batch_manager.py` (or wherever `executor/worktree_setup.sh` is invoked).

## Requirements

### 1. Lifecycle hooks in `orch/daemon/batch_manager.py`

Locate the function that invokes `executor/worktree_setup.sh` (likely something like `_setup_worktree` or `_create_worktree`). Immediately AFTER `worktree_setup.sh` returns successfully:

- Call `worktree_compose.has_iw_config(worktree_path)`. If False, set `BatchItem.worktree_*` fields to NULL and return (legacy mode — AC7).
- Call `worktree_compose.load_config(...)` then `worktree_compose.up(cfg)`.
- On `UpResult.success=True`: persist `worktree_db_port`, `worktree_app_port`, `worktree_compose_path` to the BatchItem; commit.
- On `UpResult.success=False`: transition `BatchItem.status = setup_failed`, persist the failure metadata to a DaemonEvent with the seed_stderr_tail, do NOT proceed to step launch.

**Terminal-state set (correction — read carefully):** `BatchItemStatus` does NOT include `archived` or `restarted_discarded` (those are `BatchStatus` values, batch-level only — verified in `orch/db/models.py:141`). The actual terminal `BatchItemStatus` values are:

```
{merged, failed, stalled, skipped, migration_invalid, migration_rolled_back, migration_rebase_failed, setup_failed}
```

(`setup_failed` is added by S01.) Define ONE source of truth:

```python
# in orch/db/models.py (or orch/daemon/batch_manager.py if cross-cutting placement is preferred — match precedent):
TERMINAL_BATCH_ITEM_STATUSES: frozenset[BatchItemStatus] = frozenset({
    BatchItemStatus.merged,
    BatchItemStatus.failed,
    BatchItemStatus.stalled,
    BatchItemStatus.skipped,
    BatchItemStatus.migration_invalid,
    BatchItemStatus.migration_rolled_back,
    BatchItemStatus.migration_rebase_failed,
    BatchItemStatus.setup_failed,
})

def is_terminal_batch_item_status(status: BatchItemStatus) -> bool:
    return status in TERMINAL_BATCH_ITEM_STATUSES
```

Use `git grep -n "BatchItemStatus\.\(merged\|failed\|stalled\|skipped\|migration_invalid\|migration_rolled_back\|migration_rebase_failed\|setup_failed\)"` to find EVERY transition site (currently in `merge_queue.py`, `batch_manager.py`, `migration_pipeline.py`, etc.). Immediately BEFORE each terminal-state transition is committed (or immediately after, matching the existing code style — be consistent across sites), call:

```python
worktree_compose.down(batch_item.id, batch_item.worktree_compose_path)
```

`down()` is idempotent and tolerates `compose_path=None` (legacy items). If a single helper makes the wiring cleaner, add `worktree_compose.down_if_terminal(batch_item, prior_status, new_status)` and route every transition through it.

### 2. Container reaper

Add a new module `orch/daemon/worktree_reaper.py` (or a `Reaper` section within `worktree_compose.py` if your judgment says cohesion wins — discuss in your report). API:

```python
@dataclass(frozen=True)
class ReaperFinding:
    container_id: str
    batch_item_id: str | None  # parsed from label; None if malformed
    classification: Literal["active", "stale", "orphan", "malformed"]
    labels: dict[str, str]

def scan() -> list[ReaperFinding]: ...
    # `docker ps -a --filter label=iwcore.role` (NOT --filter status=running — we want all)
    # Parse output, build findings.

def classify(finding: ReaperFinding, db: Session) -> Literal["active", "stale", "orphan"]: ...
    # Look up BatchItem by id from label.
    # - If no row: orphan
    # - If row.status in {merged, archived, restarted_discarded}: stale
    # - Else: active

def reap(db: Session) -> list[ReaperFinding]: ...
    # scan() -> classify() each -> for stale|orphan|malformed call worktree_compose.down(...)
    # Return list of reaped findings (not active).
    # Each reap emits a DaemonEvent(event_type='worktree_compose', metadata={phase:'reap', classification:..., labels:...}).
```

### 3. Reaper invocation: startup + periodic

In `orch/daemon/main.py`:
- On daemon startup, BEFORE the main poll loop, call `worktree_reaper.reap()` once. Log the count and classifications.
- Add a periodic schedule (e.g., every 5 poll cycles, or every N seconds matching the existing daemon's tick) that calls `worktree_reaper.reap()` again. Reuse the daemon's existing scheduling primitive — do NOT introduce a new threading mechanism.

### 4. Daemon-restart re-attach

In the daemon-startup path (`orch/daemon/main.py` or a startup helper):

- Query `BatchItem` rows WHERE `status NOT IN (merged, archived, restarted_discarded)` AND `worktree_compose_path IS NOT NULL`
- For each, call `worktree_compose.is_alive(batch_item.id)`:
  - If True: log "re-attached to existing stack for <id>" and DO NOT call `up()` again
  - If False: log "stack missing for non-terminal <id>; will re-setup on next poll"; the next batch poll's lifecycle path handles re-creation via the existing setup logic
- AC5 specifies this MUST NOT result in a second `phase='up'` DaemonEvent for re-attached items

### 5. Tests

Extend `tests/unit/daemon/test_worktree_compose.py` with reaper tests:
- `test_classify_running_with_active_batchitem_is_active`
- `test_classify_running_with_terminal_batchitem_is_stale`
- `test_classify_running_with_no_batchitem_is_orphan`
- `test_classify_with_malformed_label_is_malformed_and_reaped_as_orphan`
- `test_reap_only_acts_on_stale_and_orphan` (mock `worktree_compose.down`; assert call count and arguments)
- `test_reaper_idempotent_on_already_torn_down_stack`
- `test_reattach_recognizes_alive_stack_and_skips_recreate` (mock `is_alive=True`; assert `up()` is NOT called)

For batch_manager hook tests, add `tests/unit/daemon/test_batch_manager_worktree_hooks.py`:
- `test_setup_calls_compose_up_when_iw_config_present`
- `test_setup_skips_compose_when_iw_config_absent_legacy_mode`
- `test_setup_failure_transitions_to_setup_failed_status`
- `test_terminal_transition_calls_compose_down`

## Project Conventions

- Read `CLAUDE.md`, `orch/CLAUDE.md`
- The daemon is a single-threaded sync poller — no `asyncio`, no `threading`
- DaemonEvent uses `event_metadata` (Python attribute) not `metadata` (gotcha noted in `orch/CLAUDE.md`)
- Append-only tables (`step_runs`, `daemon_events`) — never UPDATE

## TDD Requirement

RED → GREEN → REFACTOR for every new function. Reaper classification is critical — write the classification tests first.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all pass
2. `make lint` and `make quality`
3. Manually trace: when does `up()` fire? when does `down()` fire? Are there any code paths to terminal states that miss the `down()` hook?

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "F-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/worktree_reaper.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/main.py",
    "tests/unit/daemon/test_worktree_compose.py",
    "tests/unit/daemon/test_batch_manager_worktree_hooks.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Decision: reaper as separate module vs section within worktree_compose; lifecycle hook insertion points and the precedent they match"
}
```
