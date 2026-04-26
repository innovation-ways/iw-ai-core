# CR-00022 S24 QV Fix Cycle 1/5

Quality gate S24 for work item CR-00022 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: mypy found 8 type errors in orch/oss/fix_recipes/ files (missing dict type arguments)

**New Failures**:
  [typecheck] orch/oss/fix_recipes/ci_cd.py::type-arg
  [typecheck] orch/oss/fix_recipes/community.py::type-arg
  [typecheck] orch/oss/fix_recipes/governance.py::type-arg
  [typecheck] orch/oss/fix_recipes/license_check.py::type-arg
  [typecheck] orch/oss/fix_recipes/secrets.py::type-arg
**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start CR-00022 --step S24
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started CR-00022 step S24 (already in progress)
  $ make typecheck
  uv run mypy orch/ dashboard/
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Found 8 errors in 5 files (checked 175 source files)
  make: *** [Makefile:30: typecheck] Error 1
  $ mkdir -p ai-dev/active/CR-00022/reports
  (no output)
  ← Write ai-dev/active/CR-00022/reports/CR-00022_S24_QvGate_report.md
  Wrote file successfully.


## Gate Command

The quality gate that failed runs:
```bash
make typecheck
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
