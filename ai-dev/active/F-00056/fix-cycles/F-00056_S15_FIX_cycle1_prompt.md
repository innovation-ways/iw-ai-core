# F-00056 S15 QV Fix Cycle 1/5

Quality gate S15 for work item F-00056 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: mypy typecheck failed: 4 errors in dashboard/routers/code_qa.py (lines 130, 133, 176, 192)

**Command output**:
```
[93m[1m! [0m agent "qv-gate" not found. Falling back to default agent
[0m
> build · MiniMax-M2.7
[0m
[0m$ [0muv run iw step-start F-00056 --step S15
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Started F-00056 step S15 (already in progress)
[0m
[0m$ [0muv run mypy orch/ dashboard/
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
dashboard/routers/code_qa.py:130: error: Argument 1 to "put" of "Queue" has incompatible type "dict[str, object]"; expected "str | None"  [arg-type]
dashboard/routers/code_qa.py:133: error: Argument 1 to "put" of "Queue" has incompatible type "dict[str, str]"; expected "str | None"  [arg-type]
dashboard/routers/code_qa.py:176: error: Argument 11 to "submit" of "Executor" has incompatible type "Queue[str | None] | Queue[dict[str, object]]"; expected "Queue[str | None]"  [arg-type]
dashboard/routers/code_qa.py:192: error: "object" has no attribute "encode"  [attr-defined]
Found 4 errors in 1 file (checked 120 source files)
[0m
**FAIL**

4 type errors found in `dashboard/routers/code_qa.py`:
- Lines 130, 133: `Queue.put` type incompatibility
- Line 176: `Executor.submit` type incompatibility  
- Line 192: `"object"` has no attribute `encode`
[0m$ [0muv run iw step-fail F-00056 --step S15 --reason "mypy typecheck failed: 4 errors in dashboard/routers/code_qa.py (lines 130, 133, 176, 192)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00056 step S15: mypy typecheck failed: 4 errors in dashboard/routers/code_qa.py (lines 130, 133, 176, 192)
[0m
**FAIL** - Typecheck gate failed with 4 mypy errors in `dashboard/routers/code_qa.py`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
