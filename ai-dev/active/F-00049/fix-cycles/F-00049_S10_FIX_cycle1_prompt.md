# F-00049 S10 QV Fix Cycle 1/5

Quality gate S10 for work item F-00049 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Type check failed: 3 errors in dashboard/dependencies.py (lines 38, 44, 49)

**Command output**:
```
[93m[1m! [0m agent "QvGate" not found. Falling back to default agent
[0m
> build · MiniMax-M2.7
[0m
[0m$ [0muv run iw step-start F-00049 --step S10
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Started F-00049 step S10 (already in progress)
[0m
[0m$ [0muv run mypy orch/ dashboard/
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
dashboard/dependencies.py:38: error: Incompatible return value type (got "async_sessionmaker[AsyncSession]", expected "AsyncSession")  [return-value]
dashboard/dependencies.py:44: error: The return type of an async generator function should be "AsyncGenerator" or one of its supertypes  [misc]
dashboard/dependencies.py:49: error: "AsyncSession" not callable  [operator]
Found 3 errors in 1 file (checked 104 source files)
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00049/reports && cat > ai-dev/active/F-00049/reports/F-00049_S10_QvGate_report.md << 'EOF'
# F-00049 S10 QV Gate Report

## Gate: typecheck
**Command**: `uv run mypy orch/ dashboard/`
**Result**: FAIL

## Summary
Type checking revealed 3 errors in `dashboard/dependencies.py`.

## Errors Found
1. **Line 38**: Incompatible return value type (got "async_sessionmaker[AsyncSession]", expected "AsyncSession")
2. **Line 44**: The return type of an async generator function should be "AsyncGenerator" or one of its supertypes
3. **Line 49**: "AsyncSession" not callable

## Files Checked
- orch/ (checked 104 source files)
- dashboard/ (found errors in dashboard/dependencies.py)
EOF
[0m
[0m$ [0muv run iw step-fail F-00049 --step S10 --reason "Type check failed: 3 errors in dashboard/dependencies.py (lines 38, 44, 49)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00049 step S10: Type check failed: 3 errors in dashboard/dependencies.py (lines 38, 44, 49)
[0m
**FAIL**

Type check failed with 3 errors in `dashboard/dependencies.py`:
- Line 38: Incompatible return type (async_sessionmaker vs AsyncSession)
- Line 44: Missing AsyncGenerator return type annotation
- Line 49: AsyncSession not callable

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
