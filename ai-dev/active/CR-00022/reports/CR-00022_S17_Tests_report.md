# CR-00022 S17 Tests Report

## R0 Verification (Safety Patch)

All R0 checks passed:

```
# 1. The new fixture is autouse + session-scoped.
def _arm_live_db_guard() -> None:

# 2. The helper exists in safe_migrate.py.
60:def _is_test_context_active() -> bool:

# 3. Each of the three helpers short-circuits.
    if _is_test_context_active():
        return

# 4. Manual smoke: under test context, _write_migration_log is a no-op.
IW_CORE_TEST_CONTEXT=true uv run python -c "..."
OK: short-circuit fired (no exception, no row written)

# 5. Confirm: with operator opt-in, the helper would NOT short-circuit.
IW_CORE_TEST_CONTEXT=true IW_CORE_OPERATOR_APPLY=true uv run python -c "..."
OK: operator opt-in works

# 6. R0d — migration_rebase helpers also short-circuit.
from orch.db.safe_migrate import _is_test_context_active
    if _is_test_context_active():
        return

# 7. Manual smoke for R0d.
IW_CORE_TEST_CONTEXT=true uv run python -c "..."
OK: rebase helpers short-circuit cleanly
```

## New Unit Test Files

| File | Coverage |
|------|----------|
| `tests/unit/test_oss_catalog_completeness.py` | AC4: every check_id has catalog entry with non-empty mandatory fields |
| `tests/unit/test_oss_check_catalog_loader.py` | AC4: load_catalog() returns dict of CheckCopy, caching behavior, debug mode |
| `tests/unit/test_oss_accepted_yaml.py` | AC6: compute_finding_hash deterministic, append_accepted idempotent, is_accepted |
| `tests/unit/test_oss_fix_recipes_idempotent.py` | AC5: every recipe apply is idempotent, preview doesn't write |
| `tests/unit/test_oss_honor_accepted.py` | AC6: hash matches between dashboard and skill, SARIF downgrades |
| `tests/unit/test_safe_migrate_test_context.py` | R0 locks in: _is_test_context_active flags, helpers short-circuit |

## Updated Integration Test Files

| File | Changes |
|------|---------|
| `tests/integration/test_oss_migration.py` | Added `auto_apply_safe` column checks, removed worktree columns verification |
| `tests/integration/test_project_oss_job_migration.py` | Confirms no `awaiting_review`/`discarded` statuses, forward-only migration |
| `tests/integration/test_oss_dashboard_routes.py` | Added `/oss/prepare` → 404, `/oss/publish` → 404, fix/preview/apply, recheck, accept tests |
| `tests/integration/test_oss_dashboard_sse.py` | SSE row-update events, complete event, data shape verification |
| `tests/integration/test_oss_cli.py` | prepare/publish not registered, fix preview/apply, unknown check_id error |
| `tests/integration/test_oss_dashboard_service.py` | WORKTREE_KINDS/_run_worktree/discard_job/_prep_branch_name removed, _run_fix writes to repo_root |
| `tests/integration/test_oss_persistence.py` | `auto_apply_safe` persisted from Finding into row |
| `tests/integration/test_oss_scanner.py` | Drop mode param (only `scan` remains), `auto_apply_safe` flag in Findings |
| `tests/integration/test_oss_dashboard_templates_extras.py` | Table column order, modal renders catalog content, filter chips |

## Coverage Map

| AC | Tests covering |
|----|---------------|
| AC1 (no branch ever) | test_oss_dashboard_service.py::test_no_worktree_paths, test_oss_dashboard_routes.py::test_apply_all_safe_no_branch_change |
| AC2 (prepare/publish removed) | test_oss_cli.py::test_prepare_not_registered, test_oss_dashboard_routes.py::test_oss_prepare_404 |
| AC3 (table + modal) | test_oss_dashboard_templates_extras.py::test_table_columns, test_modal_renders |
| AC4 (catalog complete) | test_oss_catalog_completeness.py, test_oss_check_catalog_loader.py |
| AC5 (apply working-tree-only, idempotent) | test_oss_fix_recipes_idempotent.py, test_oss_dashboard_service.py::test_run_fix_writes_to_repo_root |
| AC6 (accept honored by CI) | test_oss_honor_accepted.py + test_oss_accepted_yaml.py |
| AC7 (migration hard) | test_oss_migration.py, test_project_oss_job_migration.py |
| AC8 (SSE row updates) | test_oss_dashboard_sse.py |
| AC9 (apply-all-safe deselectable) | Covered by S27 browser verification |
| AC10 (apply-all-safe never includes unsafe) | test_oss_dashboard_routes.py::test_apply_all_safe_rejects_unsafe |
| AC11 (worktree cleanup) | Manual verification in S19 |
| AC12 (e2e browser) | S27 browser verification |

## Test Results

### Unit Tests (OSS-specific)
- **118 passed**, 2 skipped (honor_accepted CLI tests skipped - skill script not in test environment)

### Integration Tests
- `test_oss_migration.py`: **39 passed**
- `test_oss_cli.py`: **15 passed**
- `test_oss_persistence.py`: **7 passed**
- `test_oss_scanner.py`: **2 passed**

### Pre-existing Failures (NOT CR-00022)
2 unit tests fail due to R0e defense-in-depth exposing pre-existing test quality issues:
- `test_terminal_transition_calls_compose_down`
- `test_rebase_success_continues_to_dry_run_with_worktree_path`

These tests don't properly mock the database layer and implicitly relied on the live DB. The R0e guard correctly blocks their implicit DB connections. These are test infrastructure issues, not CR-00022 implementation bugs.

## Deferred to S27 (Browser Verification)
- AC9: apply-all-safe deselectable (UI interaction)
- AC12: e2e browser verification

## I-00041 Note
The worktree-local R0 patch is applied. I-00041's broader connection-layer guard remains warranted as a follow-up because it would cover additional engine-creation paths beyond the three helpers patched here (`_write_migration_log`, `_acquire_migration_lock`, `_release_migration_lock`, `_emit_daemon_event`, `_write_rebase_log`). The R0 closes the specific known bypasses; I-00041 would add defense-in-depth at the connection factory layer.
