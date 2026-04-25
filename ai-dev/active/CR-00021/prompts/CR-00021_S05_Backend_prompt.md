# CR-00021_S05_Backend_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Step**: S05
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Testcontainer fixtures only. No `docker compose up/down/stop/kill/rm`. Read-only introspection fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design (AC5 is the key driver for the worktree-path threading; queue-not-frozen semantics from "Failure semantics")
- `ai-dev/active/CR-00021/reports/CR-00021_S03_Backend_report.md` — S03 confirms `run_pre_merge_rebase` exists with stable signature
- `orch/daemon/migration_rebase.py` — new module from S03 (caller here)
- `orch/daemon/migration_pipeline.py` — to modify `run_pre_merge_dry_run`
- `orch/db/safe_migrate.py` — to modify `dry_run`, `_build_alembic_config`, `_write_migration_log`
- `orch/daemon/merge_queue.py` — to modify `_merge_item`
- `orch/db/models.py` — `BatchItemStatus.migration_rebase_failed` already exists (S01)

## Output Files

- `orch/db/safe_migrate.py` (modified) — threaded `script_location` + `old_revision` kwargs
- `orch/daemon/migration_pipeline.py` (modified) — `run_pre_merge_dry_run` gains `worktree_path` parameter
- `orch/daemon/merge_queue.py` (modified) — inserts rebase phase, threads worktree_path to dry-run, handles new failure state
- `ai-dev/active/CR-00021/reports/CR-00021_S05_Backend_report.md` — step report

## Context

Wire the new `run_pre_merge_rebase` (from S03) into the merge-queue critical section and make the existing Phase 1 dry-run worktree-aware so it exercises the batch's migrations (fixes the pre-existing bug where dry-run tests the daemon's main-repo migrations directory).

All four modifications preserve backward compatibility: the new kwargs on `safe_migrate.dry_run` and `migration_pipeline.run_pre_merge_dry_run` default to the pre-CR behaviour when not supplied (operator CLI call sites stay working).

## Requirements

### 1. `orch/db/safe_migrate.py` — threading `script_location` + `old_revision`

Modify three call sites:

**a) `_build_alembic_config`** — accept optional override:

```python
def _build_alembic_config(db_url: str, script_location: str | None = None) -> AlembicConfig:
    cfg = AlembicConfig()
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", script_location or MIGRATIONS_SCRIPT_LOCATION)
    return cfg
```

**b) `dry_run`** — pass-through:

```python
def dry_run(
    tempdb_url: str,
    batch_id: int | None = None,
    script_location: str | None = None,
) -> DryRunResult:
    ...
    cfg = _build_alembic_config(tempdb_url, script_location=script_location)
    ...
```

Do NOT modify `apply` or `rollback` signatures — those are Phase 2 / Phase 3 and correctly use the main-repo location (main already holds the batch's squash-merged migrations at that point).

**c) `_write_migration_log`** — accept optional `old_revision`:

```python
def _write_migration_log(
    revision: str,
    direction: Literal["upgrade", "downgrade"],
    phase: Literal["dry_run", "apply", "rollback", "rebase"],  # NOTE: add "rebase" to the Literal
    batch_id: int | None,
    success: bool,
    stdout_tail: str,
    stderr_tail: str,
    error_message: str | None,
    old_revision: str | None = None,
) -> None:
    ...
    entry = PendingMigrationLog(
        revision=revision,
        direction=direction,
        phase=phase,
        batch_id=batch_id,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        success=success,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
        error_message=error_message,
        old_revision=old_revision,
    )
    ...
```

Existing callers passing `phase='dry_run'` / `'apply'` / `'rollback'` stay working without passing `old_revision` (NULL default).

Update `list_pending_revisions` to also accept `script_location` if convenient — but the design does not require it (list_pending_revisions is called from `apply` / `rollback`, where main-repo is correct). Leave it alone unless needed for backward compat.

### 2. `orch/daemon/migration_pipeline.py` — worktree-aware dry-run

Change `run_pre_merge_dry_run` to accept an optional worktree path and pass it to `safe_dry_run`:

```python
def run_pre_merge_dry_run(
    batch_id: int,
    worktree_path: str | None = None,
) -> PipelineResult:
    """Phase 1: Spin testcontainer, apply pending revisions, run integration tests.

    When worktree_path is provided, alembic uses that worktree's migrations
    directory — so the batch's new migrations are actually exercised.
    When not provided, falls back to the daemon's main-repo migrations location
    (backward-compat for operator entry points; do NOT use this path in the
    merge queue — merge_queue.py always passes worktree_path).
    """
    ...
    script_location = (
        f"{worktree_path}/orch/db/migrations" if worktree_path else None
    )
    result = safe_dry_run(tempdb_url, batch_id=batch_id, script_location=script_location)
    ...
```

No other changes to this module. `run_post_merge_apply` and `run_rollback` stay as-is.

### 3. `orch/daemon/merge_queue.py` — insert rebase phase + wire worktree_path

In `_merge_item`, the current order is:

1. set `status=merging`
2. emit `merge_started` event
3. (if batch_id is int) run_pre_merge_dry_run
4. worktree_commit.sh subprocess
5. (if merge succeeded AND batch_id is int) run_post_merge_apply

**Change to:**

1. set `status=merging`
2. emit `merge_started` event
3. **NEW** (if batch_id is int): `rebase_result = run_pre_merge_rebase(batch_item.batch_id, worktree_path, project_config.working_dir)`. On failure:
   - `batch_item.status = BatchItemStatus.migration_rebase_failed`
   - `batch_item.notes = f"Pre-merge rebase failed: {rebase_result.error_message}"`
   - `db.commit()`
   - Emit `DaemonEvent(event_type="migration_pipeline", entity_type="work_item", entity_id=item_id, message=..., event_metadata={"phase": "rebase", "success": False, "batch_id": ..., "worktree_base_sha": rebase_result.worktree_base_sha, "current_main_sha": rebase_result.current_main_sha, "effective_ref": rebase_result.effective_ref, "fetch_succeeded": rebase_result.fetch_succeeded})`
   - `logger.warning(...)` with item + batch + error
   - `return` (do NOT freeze the queue)
4. (if batch_id is int) `run_pre_merge_dry_run(batch_item.batch_id, worktree_path=worktree_path)` — **pass worktree_path**. Existing failure path (`status=migration_invalid`) unchanged.
5. worktree_commit.sh subprocess
6. (if merge succeeded AND batch_id is int) run_post_merge_apply — unchanged.

Import `run_pre_merge_rebase` at module top. Guard the whole rebase block with the existing `isinstance(batch_item.batch_id, int)` pattern so non-numeric batch ids (legacy) are skipped.

### 4. Signatures to preserve (backward compat — DO NOT CHANGE)

- `safe_migrate.dry_run(tempdb_url)` — existing operator CLI callers.
- `safe_migrate.apply(live_db_url, batch_id=None)` — Phase 2 (main-repo migrations is correct).
- `safe_migrate.rollback(live_db_url, steps=1, batch_id=None)` — Phase 3.
- `migration_pipeline.run_post_merge_apply(batch_id)` and `run_rollback(batch_id)` — unchanged.

### 5. Imports in `merge_queue.py`

At module top:

```python
from orch.daemon.migration_rebase import run_pre_merge_rebase
```

Grouped alphabetically with the existing `from orch.daemon.migration_pipeline import (...)` block.

## Project Conventions

- Use keyword arguments for the new optional parameters — `run_pre_merge_dry_run(batch_item.batch_id, worktree_path=worktree_path)`.
- Failure path emits the DaemonEvent first, then `logger.warning` — match existing pattern in `_merge_item`.
- `batch_item.notes` string is truncated to the DB column limit (Text, no limit) but should be a single short line for operator readability.
- Do NOT introduce new daemon-event types beyond `migration_rebase` (emitted inside the rebase module) and the existing `migration_pipeline` phase-failure event (reused for rebase failures).

## TDD Requirement

Write / extend tests alongside the wiring:

1. Unit test in `tests/unit/daemon/test_migration_pipeline.py`:
   - `test_run_pre_merge_dry_run_threads_worktree_path` — monkeypatch `safe_dry_run`, call `run_pre_merge_dry_run(1, worktree_path="/wt")`, assert `script_location="/wt/orch/db/migrations"` passed through.
   - `test_run_pre_merge_dry_run_backward_compat` — call without `worktree_path`, assert `script_location=None` passed.

2. Unit test in `tests/unit/daemon/test_safe_migrate.py` (add or extend):
   - `test_build_alembic_config_override_respected` — with explicit `script_location`, config uses it; without, falls back to module constant.
   - `test_write_migration_log_old_revision_persisted` — call with `old_revision="rev1"`, phase `"rebase"`; assert row written with `old_revision=rev1` and `phase='rebase'`.

3. Unit test in `tests/unit/daemon/test_merge_queue.py` (add or extend):
   - `test_rebase_failure_sets_migration_rebase_failed_and_returns` — stub `run_pre_merge_rebase` → `RebaseResult(success=False, error_message="boom")`; call `_merge_item`; assert `batch_item.status == migration_rebase_failed`, `batch_item.notes` contains `"boom"`, worktree_commit.sh NOT invoked, queue NOT frozen.
   - `test_rebase_success_continues_to_dry_run_with_worktree_path` — stub `run_pre_merge_rebase` → success, stub `run_pre_merge_dry_run` to assert `worktree_path=` arg matches the batch item's worktree path.

Full integration coverage is S07; S05 just needs enough local tests to trust the wiring.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — must pass
2. `make lint` / `make format` / `make typecheck` — must pass
3. Report accurately

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "CR-00021",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/safe_migrate.py",
    "orch/daemon/migration_pipeline.py",
    "orch/daemon/merge_queue.py",
    "tests/unit/daemon/test_migration_pipeline.py",
    "tests/unit/daemon/test_safe_migrate.py",
    "tests/unit/daemon/test_merge_queue.py"
  ],
  "tests_passed": true,
  "test_summary": "unit X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
