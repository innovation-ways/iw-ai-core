# F-00062 S17 QV Fix Cycle 1/5

Quality gate S17 for work item F-00062 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 12 mypy type errors found in orch/rag/classifier.py, orch/daemon/worktree_compose.py, dashboard/routers/worktrees.py, orch/daemon/batch_manager.py

**New Failures**:
  [typecheck] dashboard/routers/worktrees.py::arg-type
  [typecheck] dashboard/routers/worktrees.py::assignment
  [typecheck] dashboard/routers/worktrees.py::return-value
  [typecheck] dashboard/routers/worktrees.py::union-attr
  [typecheck] orch/daemon/batch_manager.py::arg-type
  [typecheck] orch/daemon/batch_manager.py::assignment
  [typecheck] orch/daemon/worktree_compose.py::assignment
**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start F-00062 --step S17
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started F-00062 step S17 (already in progress)
  $ make typecheck
  uv run mypy orch/ dashboard/
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Found 12 errors in 4 files (checked 160 source files)
  make: *** [Makefile:30: typecheck] Error 1
  **FAIL** - 12 mypy errors found.
  Let me create the report:
  $ mkdir -p ai-dev/active/F-00062/reports
  (no output)
  ← Write ai-dev/active/F-00062/reports/F-00062_S17_QvGate_report.md
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
