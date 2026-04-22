# CR-00017 S14 QV Fix Cycle 1/5

Quality gate S14 for work item CR-00017 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Lint failed: 6 ruff errors (ARG001, N818, SIM117)

**Command output**:
```
...(truncated)...
117 Use a single `with` statement with multiple contexts instead of nested `with` statements
   --> tests/unit/test_merge_queue.py:256:13
    |
254 |           with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
255 |               mock_run.return_value = MagicMock(returncode=0, stdout=long_output, stderr="")
256 | /             with patch("orch.daemon.merge_queue._cleanup_worktree"):
257 | |                 with patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry:
    | |________________________________________________________________________________________^
258 |                       with patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply:
259 |                           mock_dry.return_value = MagicMock(
    |
help: Combine `with` statements

SIM117 Use a single `with` statement with multiple contexts instead of nested `with` statements
   --> tests/unit/test_safe_migrate_guards.py:153:9
    |
151 |           from orch.db.safe_migrate import apply
152 |
153 | /         with patch("orch.db.safe_migrate._assert_not_agent_context"):
154 | |             with patch("orch.db.safe_migrate._acquire_migration_lock"):
    | |_______________________________________________________________________^
155 |                   with patch(
156 |                       "orch.db.safe_migrate._run_alembic_upgrade",
    |
help: Combine `with` statements

SIM117 Use a single `with` statement with multiple contexts instead of nested `with` statements
   --> tests/unit/test_safe_migrate_guards.py:172:9
    |
170 |           from orch.db.safe_migrate import rollback
171 |
172 | /         with patch("orch.db.safe_migrate._assert_not_agent_context"):
173 | |             with patch("orch.db.safe_migrate._acquire_migration_lock"):
    | |_______________________________________________________________________^
174 |                   with patch(
175 |                       "orch.db.safe_migrate._run_alembic_downgrade",
    |
help: Combine `with` statements

Found 6 errors.
make: *** [Makefile:17: lint] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/CR-00017/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00017/reports/CR-00017_S14_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00017 --step S14 --reason "Lint failed: 6 ruff errors (ARG001, N818, SIM117)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00017 step S14: Lint failed: 6 ruff errors (ARG001, N818, SIM117)
[0m
**FAIL** — `make lint` failed with 6 ruff errors:

- `ARG001`: unused arg `archive_dir` in `orch/cli/item_commands.py:593`
- `N818`: exception `AgentContextForbidden` should end in `Error` in `orch/db/safe_migrate.py:64`
- `SIM117` (x4): nested `with` statements in test files

Report written to `ai-dev/active/CR-00017/reports/CR-00017_S14_QvGate_report.md`.

```


## Gate Command

The quality gate that failed runs:
```bash
make lint
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
