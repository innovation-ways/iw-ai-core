# I-00121 S11 QV Fix Cycle 1/7

Quality gate S11 for work item I-00121 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/test_runner.py
  tests/unit/test_test_runner_allure_env.py
  tests/integration/test_test_runner_report_persistence.py

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/I-00121/**
  ai-dev/archive/I-00121/**
  ai-dev/work/I-00121/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00121/ai-dev/active/I-00121/I-00121_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
y::test_table_exists_with_columns
ERROR tests/integration/test_pending_migration_log_migration.py::test_batch_id_accepts_values
ERROR tests/integration/test_pending_migration_log_migration.py::test_direction_check_constraint
ERROR tests/integration/test_i00105_max_output_tokens_migration.py::TestI00105MaxOutputTokensMigration::test_migration_backfills_pi_minimax_m2_7
ERROR tests/integration/test_i00105_max_output_tokens_migration.py::TestI00105MaxOutputTokensMigration::test_orm_max_output_tokens_read_write
ERROR tests/integration/test_i00105_max_output_tokens_migration.py::TestI00105MaxOutputTokensMigration::test_orm_create_new_runtime_with_max_output_tokens
ERROR tests/integration/test_i00105_max_output_tokens_migration.py::TestI00105MaxOutputTokensMigration::test_migration_adds_max_output_tokens_column
ERROR tests/integration/test_i00105_max_output_tokens_migration.py::TestI00105MaxOutputTokensMigration::test_other_runtimes_remain_null
ERROR tests/integration/test_i00105_max_output_tokens_migration.py::TestI00105MaxOutputTokensMigration::test_migration_downgrade_removes_column
ERROR tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row
ERROR tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_rejects_make_oss_mode
ERROR tests/integration/test_oss_cli.py::TestOssEnable::test_oss_enable_writes_config_and_flips_flag
ERROR tests/integration/test_oss_cli.py::TestOssEnable::test_oss_enable_overwrites_with_force
ERROR tests/integration/test_oss_cli.py::TestOssEnable::test_oss_enable_refuses_without_force_if_config_differs
ERROR tests/integration/test_oss_cli.py::TestOssEnable::test_oss_enable_exits_2_when_project_not_found
ERROR tests/integration/test_oss_cli.py::TestOssEnable::test_oss_enable_exits_2_on_non_git_repo
ERROR tests/integration/test_oss_cli.py::TestOssEnable::test_oss_enable_idempotent_when_config_unchanged
ERROR tests/integration/test_oss_cli.py::TestOssDisable::test_oss_disable_clears_flag
ERROR tests/integration/test_oss_cli.py::TestOssScan::test_oss_scan_exits_2_when_project_not_found
ERROR tests/integration/test_oss_cli.py::TestOssScan::test_oss_scan_refuses_when_disabled
ERROR tests/integration/test_oss_cli.py::TestOssStatus::test_oss_status_exits_2_when_project_not_found
ERROR tests/integration/test_oss_cli.py::TestOssStatus::test_oss_status_json_shape
ERROR tests/integration/test_iw_core_instance_migration.py::test_check_constraint_prevents_second_row
ERROR tests/integration/test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip
ERROR tests/integration/test_iw_core_instance_migration.py::test_table_created_and_seeded
ERROR tests/integration/test_daemon_alembic_guard.py::TestDaemonStartupGuard::test_daemon_exits_nonzero_when_db_behind_head_via_mock
= 6 failed, 3309 passed, 28 skipped, 2 deselected, 5 xfailed, 2 xpassed, 160 warnings, 48 errors in 1229.72s (0:20:29) =
make: *** [Makefile:129: test-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.

## Post-Edit Gate (MANDATORY before exit)

After your final edit, run these two commands and fix any NEW violation
your edits introduced:

```bash
make format-check
make lint
```

If either command reports a violation in a file you touched this cycle,
resolve it before exiting — `uv run ruff format <file>` for format-check
failures, targeted edit for lint failures. Re-run both commands to confirm
green. The next review run WILL fail on these gates and burn another fix
cycle, so closing them now is strictly cheaper.

(Diagnosed 2026-05-25: in CR-00082 S04, cycle N reformatted
`playwright_wrapper.py` while cycle N+1 introduced a new line-length
violation in the same file; the loop never converged because no fix
agent self-checked these gates. This gate exists to break that loop.)



**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
