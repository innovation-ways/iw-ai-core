# CR-00017 S16 QV Fix Cycle 1/5

Quality gate S16 for work item CR-00017 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 4 mypy errors in orch/db/safe_migrate.py and orch/daemon/merge_queue.py

**Command output**:
```
[93m[1m! [0m agent "qv-gate" not found. Falling back to default agent
[0m
> build · MiniMax-M2.7
[0m
[0m$ [0muv run iw step-start CR-00017 --step S16
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Started CR-00017 step S16 (already in progress)
[0m
[0m$ [0muv run mypy orch/ dashboard/
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
orch/db/safe_migrate.py:338: error: "Script" has no attribute "description"  [attr-defined]
orch/db/safe_migrate.py:339: error: Argument "down_revision" to "Revision" has incompatible type "str | list[str] | tuple[str, ...] | None"; expected "str | None"  [arg-type]
orch/daemon/merge_queue.py:189: error: Argument 1 to "run_post_merge_apply" has incompatible type "str"; expected "int"  [arg-type]
orch/daemon/merge_queue.py:196: error: Argument 1 to "run_rollback" has incompatible type "str"; expected "int"  [arg-type]
Found 4 errors in 2 files (checked 138 source files)
[0m
**FAIL** — 4 type errors found:

- `orch/db/safe_migrate.py:338-339` — `Script.description` attribute missing, wrong type for `down_revision`
- `orch/daemon/merge_queue.py:189,196` — wrong argument type (str vs int) to `run_post_merge_apply` and `run_rollback`
[0m$ [0mmkdir -p ai-dev/active/CR-00017/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00017/reports/CR-00017_S16_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00017 --step S16 --reason "4 mypy errors in orch/db/safe_migrate.py and orch/daemon/merge_queue.py"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00017 step S16: 4 mypy errors in orch/db/safe_migrate.py and orch/daemon/merge_queue.py
[0m
**FAIL** — 4 mypy errors:

| File | Line | Error |
|------|------|-------|
| `orch/db/safe_migrate.py` | 338 | `"Script"` has no attribute `description` |
| `orch/db/safe_migrate.py` | 339 | `down_revision` type `str \| list[str] \| ... \| None` expected `str \| None` |
| `orch/daemon/merge_queue.py` | 189 | `run_post_merge_apply` arg 1: `str` expected `int` |
| `orch/daemon/merge_queue.py` | 196 | `run_rollback` arg 1: `str` expected `int` |

Reported via `iw step-fail`. Fix required before proceeding.

```


## Gate Command

The quality gate that failed runs:
```bash
uv run mypy orch/ dashboard/
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
