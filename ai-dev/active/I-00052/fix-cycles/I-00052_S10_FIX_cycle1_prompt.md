# I-00052 S10 QV Fix Cycle 1/5

Quality gate S10 for work item I-00052 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: make allure-integration timed out after 300s on test_per_worktree_isolation (exit 143)

**Command output**:
```
...(truncated)...
ration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_running_page_does_not_have_mermaid PASSED [ 86%]
tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_running_page_does_not_have_hljs PASSED [ 86%]
tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_project_dashboard_does_not_have_mermaid PASSED [ 86%]
tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_base_html_comment_about_lazy_loading PASSED [ 86%]
tests/integration/test_parallel_migrations.py::test_rebase_idempotent_when_main_not_advanced PASSED [ 87%]
tests/integration/test_parallel_migrations.py::test_rebase_multi_file_chain_only_root_rewritten PASSED [ 87%]
tests/integration/test_parallel_migrations.py::test_batch_rebase_emits_daemon_event PASSED [ 87%]
tests/integration/test_parallel_migrations.py::test_parallel_batches_rebase_rewrites_stale_down_revision PASSED [ 87%]
tests/integration/test_parallel_migrations.py::test_rebase_and_dry_run_succeed_for_stale_worktree PASSED [ 87%]
tests/integration/test_pending_migration_log_migration.py::test_table_exists_with_columns PASSED [ 87%]
tests/integration/test_pending_migration_log_migration.py::test_direction_check_constraint PASSED [ 87%]
tests/integration/test_pending_migration_log_migration.py::test_phase_check_constraint PASSED [ 87%]
tests/integration/test_pending_migration_log_migration.py::test_valid_enum_values_accepted PASSED [ 87%]
tests/integration/test_pending_migration_log_migration.py::test_indexes_exist PASSED [ 87%]
tests/integration/test_pending_migration_log_migration.py::test_batch_id_accepts_values PASSED [ 87%]
tests/integration/test_pending_migration_log_migration.py::test_downgrade_drops_table PASSED [ 88%]
tests/integration/test_pending_migration_log_migration.py::test_upgrade_recreates_table_empty PASSED [ 88%]
tests/integration/test_per_worktree_isolation.py::test_two_parallel_iw_ai_core_worktrees_do_not_interfere make: *** [Makefile:48: allure-integration] Error 143


<bash_metadata>
bash tool terminated command after exceeding timeout 300000 ms. If this command is expected to take longer and is not waiting for interactive input, retry with a larger timeout value in milliseconds.
</bash_metadata>
[0m
The command timed out after 300 seconds. The last test running was `test_per_worktree_isolation.py::test_two_parallel_iw_ai_core_worktrees_do_not_interfere`. Exit code was 143 (SIGTERM).
[0m$ [0mmkdir -p ai-dev/active/I-00052/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/I-00052/reports/I-00052_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00052 --step S10 --reason "make allure-integration timed out after 300s on test_per_worktree_isolation (exit 143)"
Failed I-00052 step S10: make allure-integration timed out after 300s on test_per_worktree_isolation (exit 143)
[0m
**FAIL** — `make allure-integration` timed out after 300s (exit 143) at 88% completion. Last test: `test_two_parallel_iw_ai_core_worktrees_do_not_interfere`.

```


## Gate Command

The quality gate that failed runs:
```bash
make allure-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
