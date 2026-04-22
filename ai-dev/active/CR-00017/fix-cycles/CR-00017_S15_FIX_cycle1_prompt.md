# CR-00017 S15 QV Fix Cycle 1/5

Quality gate S15 for work item CR-00017 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 11 files would be reformatted: orch/cli/merge_queue_commands.py, orch/cli/migrations_commands.py, orch/daemon/migration_pipeline.py, orch/db/safe_migrate.py, tests/integration/test_agent_constraints_coverage.py, tests/integration/test_pending_migration_log_migration.py, tests/unit/test_merge_queue.py, tests/unit/test_merge_queue_cli.py, tests/unit/test_migrations_cli.py, tests/unit/test_safe_migrate.py, tests/unit/test_safe_migrate_guards.py

**Command output**:
```
...(truncated)...
t found. Falling back to default agent
[0m
> build · MiniMax-M2.7
[0m
[0m$ [0muv run ruff format --check .
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Would reformat: orch/cli/merge_queue_commands.py
Would reformat: orch/cli/migrations_commands.py
Would reformat: orch/daemon/migration_pipeline.py
Would reformat: orch/db/safe_migrate.py
Would reformat: tests/integration/test_agent_constraints_coverage.py
Would reformat: tests/integration/test_pending_migration_log_migration.py
Would reformat: tests/unit/test_merge_queue.py
Would reformat: tests/unit/test_merge_queue_cli.py
Would reformat: tests/unit/test_migrations_cli.py
Would reformat: tests/unit/test_safe_migrate.py
Would reformat: tests/unit/test_safe_migrate_guards.py
11 files would be reformatted, 278 files already formatted
[0m
[0m$ [0muv run iw step-start CR-00017 --step S15
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Started CR-00017 step S15 (already in progress)
[0m
[0m$ [0muv run iw step-fail CR-00017 --step S15 --reason "11 files would be reformatted: orch/cli/merge_queue_commands.py, orch/cli/migrations_commands.py, orch/daemon/migration_pipeline.py, orch/db/safe_migrate.py, tests/integration/test_agent_constraints_coverage.py, tests/integration/test_pending_migration_log_migration.py, tests/unit/test_merge_queue.py, tests/unit/test_merge_queue_cli.py, tests/unit/test_migrations_cli.py, tests/unit/test_safe_migrate.py, tests/unit/test_safe_migrate_guards.py"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00017 step S15: 11 files would be reformatted: orch/cli/merge_queue_commands.py, orch/cli/migrations_commands.py, orch/daemon/migration_pipeline.py, orch/db/safe_migrate.py, tests/integration/test_agent_constraints_coverage.py, tests/integration/test_pending_migration_log_migration.py, tests/unit/test_merge_queue.py, tests/unit/test_merge_queue_cli.py, tests/unit/test_migrations_cli.py, tests/unit/test_safe_migrate.py, tests/unit/test_safe_migrate_guards.py
[0m
**FAIL** - 11 files would be reformatted by ruff format.

Files needing formatting:
- orch/cli/merge_queue_commands.py
- orch/cli/migrations_commands.py
- orch/daemon/migration_pipeline.py
- orch/db/safe_migrate.py
- tests/integration/test_agent_constraints_coverage.py
- tests/integration/test_pending_migration_log_migration.py
- tests/unit/test_merge_queue.py
- tests/unit/test_merge_queue_cli.py
- tests/unit/test_migrations_cli.py
- tests/unit/test_safe_migrate.py
- tests/unit/test_safe_migrate_guards.py

Step failed via `iw step-fail`.

```


## Gate Command

The quality gate that failed runs:
```bash
uv run ruff format --check .
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
