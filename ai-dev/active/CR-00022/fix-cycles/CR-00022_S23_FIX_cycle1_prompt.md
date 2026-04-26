# CR-00022 S23 QV Fix Cycle 1/5

Quality gate S23 for work item CR-00022 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 23 files would be reformatted by ruff format. Run 'uv run ruff format .' to fix.

**Command output**:
```
[93m[1m! [0m agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
[0m
> build · MiniMax-M2.7
[0m
[0m$ [0muv run iw step-start CR-00022 --step S23
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Started CR-00022 step S23 (already in progress)
[0m
[0m$ [0muv run ruff format --check .
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Would reformat: dashboard/routers/oss.py
Would reformat: dashboard/routers/oss_models.py
Would reformat: dashboard/services/oss_accepted.py
Would reformat: dashboard/services/oss_service.py
Would reformat: orch/cli/oss_commands.py
Would reformat: orch/db/migrations/versions/c062b6bf5eb3_cr_00022_oss_redesign_drop_prepare_.py
Would reformat: orch/db/safe_migrate.py
Would reformat: orch/oss/fix_recipes/ci_cd.py
Would reformat: orch/oss/fix_recipes/community.py
Would reformat: orch/oss/fix_recipes/contributor.py
Would reformat: orch/oss/fix_recipes/governance.py
Would reformat: orch/oss/fix_recipes/hygiene.py
Would reformat: orch/oss/fix_recipes/internal_refs.py
Would reformat: orch/oss/fix_recipes/license_check.py
Would reformat: orch/oss/fix_recipes/release.py
Would reformat: orch/oss/fix_recipes/secrets.py
Would reformat: tests/integration/test_oss_dashboard_service.py
Would reformat: tests/unit/test_oss_accepted_yaml.py
Would reformat: tests/unit/test_oss_catalog_completeness.py
Would reformat: tests/unit/test_oss_check_catalog_loader.py
Would reformat: tests/unit/test_oss_fix_recipes_idempotent.py
Would reformat: tests/unit/test_oss_honor_accepted.py
Would reformat: tests/unit/test_safe_migrate_test_context.py
23 files would be reformatted, 375 files already formatted
[0m
[0m$ [0mmkdir -p ai-dev/active/CR-00022/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00022/reports/CR-00022_S23_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00022 --step S23 --reason "23 files would be reformatted by ruff format. Run 'uv run ruff format .' to fix."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00022 step S23: 23 files would be reformatted by ruff format. Run 'uv run ruff format .' to fix.
[0m
**FAIL** — 23 files would be reformatted by ruff format.

Report written to `ai-dev/active/CR-00022/reports/CR-00022_S23_QvGate_report.md`.

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
