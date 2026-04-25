# CR-00021_S06_CodeReview_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Step Being Reviewed**: S05 (backend-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Testcontainer fixtures only. Read-only docker introspection fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design (AC4, AC5; "Failure semantics"; "Breaking Changes" — no breaking changes allowed)
- `ai-dev/active/CR-00021/reports/CR-00021_S05_Backend_report.md` — S05 implementation report
- `orch/db/safe_migrate.py`, `orch/daemon/migration_pipeline.py`, `orch/daemon/merge_queue.py` — the three modified files
- All modified / new test files in `tests/unit/daemon/`
- `orch/daemon/migration_rebase.py` — stable contract from S03 (read to confirm `RebaseResult` fields used correctly)

## Output Files

- `ai-dev/active/CR-00021/reports/CR-00021_S06_CodeReview_report.md` — review report

## Context

Review S05's wiring: the new rebase phase threaded into `_merge_item`, `worktree_path` threaded to `run_pre_merge_dry_run`, `script_location` threaded to `safe_migrate.dry_run`, and `old_revision` added to `_write_migration_log`. Backward compatibility at operator entry points must hold.

## Review Checklist

### 1. Backward compatibility

- `safe_migrate.dry_run(tempdb_url)` (no kwargs) still works — `script_location` defaults to `None` and falls through to module constant?
- `safe_migrate.apply(live_db_url, batch_id=None)` unchanged — no `script_location` parameter added?
- `safe_migrate.rollback(...)` unchanged?
- `run_pre_merge_dry_run(batch_id)` (no `worktree_path`) still works — falls back to main-repo location?
- `run_post_merge_apply(batch_id)` / `run_rollback(batch_id)` unchanged?
- `_write_migration_log` existing call sites (phase='dry_run'/'apply'/'rollback') still work without passing `old_revision` (default `None`)?
- Any other operator CLI call sites (`orch/cli/db_commands.py`, `orch/cli/lock_commands.py`) audited — grep for `safe_migrate.` and `run_pre_merge_dry_run` to confirm?

### 2. `_merge_item` phase ordering

- New phase runs AFTER `status=merging` and AFTER the `merge_started` event, BEFORE Phase 1 dry-run?
- Guard `isinstance(batch_item.batch_id, int)` applied consistently — rebase phase skipped for legacy non-numeric batch ids (same treatment as existing phases)?
- Worktree path extracted from `batch_item.worktree_info["path"]` with the same pattern as existing code? (No duplication of path-resolution logic.)
- On rebase failure: `batch_item.status=migration_rebase_failed`, notes populated, DaemonEvent emitted, `db.commit()`, `return`. Nothing else runs.
- **Worktree is NOT cleaned up** on rebase failure (the operator may want to inspect the branch state).

### 3. Queue-not-frozen invariant

- Rebase failure path does NOT call `set_merge_queue_frozen(...)` or any equivalent?
- Phase 1 failure path (existing) unchanged — still does NOT freeze?
- Only Phase 2 rollback failure freezes (existing behaviour, unchanged)?

### 4. DaemonEvent emission on rebase failure

- `event_type="migration_pipeline"` (reused from existing failure events) not a new type — matches design?
- `event_metadata` includes `phase="rebase"`, `success=False`, `batch_id`, `worktree_base_sha`, `current_main_sha`, `effective_ref`, `fetch_succeeded`?
- `message` is human-readable (starts with "Phase" or similar)?
- Uses `event_metadata=` kwarg (SQLAlchemy reserves `metadata` — CLAUDE.md gotcha)?

### 5. `run_pre_merge_dry_run` threading

- `script_location = f"{worktree_path}/orch/db/migrations"` when `worktree_path` is truthy?
- `script_location = None` when `worktree_path is None` (backward-compat)?
- No accidental prefix stripping or path normalisation — raw join with `/` is correct on Linux/WSL?
- Docstring updated to describe when to pass `worktree_path` vs not?

### 6. `_build_alembic_config` signature

- `script_location: str | None = None` keyword parameter?
- Body: `cfg.set_main_option("script_location", script_location or MIGRATIONS_SCRIPT_LOCATION)`?
- Module constant `MIGRATIONS_SCRIPT_LOCATION` still computed from `__file__` (unchanged)?

### 7. `_write_migration_log` signature

- `phase: Literal["dry_run", "apply", "rollback", "rebase"]` — the `"rebase"` literal added?
- `old_revision: str | None = None` at the end of the parameter list?
- `PendingMigrationLog(old_revision=old_revision, ...)` in the instantiation?

### 8. Tests added/updated

- `test_run_pre_merge_dry_run_threads_worktree_path` — asserts exact kwarg value?
- `test_run_pre_merge_dry_run_backward_compat` — asserts `script_location=None`?
- `test_build_alembic_config_override_respected` — with explicit path, config uses it?
- `test_write_migration_log_old_revision_persisted` — writes row, reads back, asserts `old_revision` value and `phase='rebase'`?
- `test_rebase_failure_sets_migration_rebase_failed_and_returns` — status + notes + NO queue freeze + worktree_commit NOT called?
- `test_rebase_success_continues_to_dry_run_with_worktree_path` — stubs confirm the worktree_path flows through?

### 9. Conventions

- No new daemon-event types (reuse `migration_pipeline` + the module's own `migration_rebase`)?
- Use `keyword=` form for new optional parameters at call sites (readability)?
- Imports grouped alphabetically at top of `merge_queue.py`?

### 10. Integration correctness

- `run_pre_merge_rebase(batch_item.batch_id, worktree_path, project_config.working_dir)` — argument order matches S03's signature `(batch_id, worktree_path, repo_root)`?
- `worktree_path` extracted and guarded against empty — same pattern as existing `if not worktree_path:` check?

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — must pass
2. `make lint` / `make format` / `make typecheck` — must pass
3. Report accurately

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Backward compat broken (operator CLI stops working), queue-not-frozen invariant broken, dry-run doesn't see worktree migrations |
| **HIGH** | Wrong argument order at rebase call site, DaemonEvent metadata missing phase='rebase' key, worktree_commit.sh still runs after rebase failure |
| **MEDIUM (fixable)** | Tests weak (don't assert exact kwarg value), docstring missing, convention drift |
| **MEDIUM (suggestion)** | Better way to express guard, helper extraction |
| **LOW** | Formatting / typing |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00021",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "backward_compat|phase_order|queue_freeze|event_metadata|signature|testing|conventions|integration",
      "file": "orch/daemon/merge_queue.py",
      "line": 42,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "unit X passed, 0 failed",
  "notes": ""
}
```
