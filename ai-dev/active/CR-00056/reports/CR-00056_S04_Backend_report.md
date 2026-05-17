# CR-00056 S04 — Backend Report

**Work Item**: CR-00056 — Surface step prompts in dashboard (Prompt column + modal viewer)
**Step**: S04 (backend-impl)
**Agent**: backend-impl

## What was done

Wired the daemon's step-launch sites to snapshot prompt content into the new `StepRun.prompt_text` and `StepRun.fix_prompt_text` columns added by S01.

### AC2: Initial run prompt snapshot (`orch/daemon/batch_manager.py`)

At line ~1497, just before the `StepRun(...)` constructor call, the `prompt` variable holds the in-memory prompt string (set only on the implementation path, not the QV-gate direct-command path). The code:

1. Prefetches `prompt_file: Path | None = None` before the `if/else` that decides QV-gate vs implementation path.
2. After `subprocess.Popen` spawns the agent, snapshots `prompt_text_val` using the in-memory `prompt` variable (preferred — no extra IO) or the `prompt_file` on disk as fallback.
3. Passes `prompt_text=prompt_text_val` into `StepRun(...)`.

For QV-gate steps (which have `command` set and no `prompt_file`), `prompt_text_val` remains `None` — the column stays NULL and the UI shows `—`.

### AC3: Fix-cycle retry prompt snapshot (`orch/daemon/fix_cycle.py`)

At line ~2335, in `_launch_fix_agent`, the fix-prompt string is already in memory as `prompt_text` (read from the fix-prompt file at lines 2277–2280). The code:

1. Sets `fix_prompt_text_val = prompt_text` for the `StepRun(...)` constructor.
2. Reads the base prompt from `step.prompt_file` on disk (via `step.prompt_file` path), storing as `base_prompt_text_val`. If the file is missing or unreadable, logs a warning and sets the column to `None` — non-fatal, step launch continues.
3. Passes `prompt_text=base_prompt_text_val, fix_prompt_text=fix_prompt_text_val` into `StepRun(...)`.

## Design decisions

### Which of the 3 StepRun sites get `prompt_text=`?

Empirically determined from code analysis:

| Location | Step type | Gets `prompt_text=`? |
|----------|-----------|---------------------|
| Line ~1238 (browser env setup failure) | browser_verification | No — this is an error path, no `prompt` variable in scope |
| Line ~1311 (fixture apply failure) | browser_verification | No — same reasoning |
| Line ~1497 (successful launch) | implementation, code_review | **Yes** — `prompt_file` is set, `prompt` is in scope |

The QV-gate path (line ~1373, `if step.step_type == StepType.quality_validation and step.command`) does **not** set `prompt_file` or `prompt`, so `prompt_text_val` stays `None` — correct behavior.

### Base prompt source for fix-cycle retries

Per AC3: "StepRun.prompt_text remains the base prompt for that step." Chose to read `step.prompt_file` from disk (the simplest approach, available as `step.prompt_file` on the `WorkflowStep` row) rather than querying the first StepRun for the step. If the file is absent, the column is NULL and the UI shows `—` rather than failing the step launch.

## Files changed

| File | Change |
|------|--------|
| `orch/daemon/batch_manager.py` | Added `prompt_file: Path | None = None` pre-declaration; added `prompt_text_val` capture block; passed `prompt_text=prompt_text_val` to `StepRun(...)` |
| `orch/daemon/fix_cycle.py` | In `_launch_fix_agent`, added `fix_prompt_text_val` and `base_prompt_text_val` capture; passed both to `StepRun(...)`; fixed `project_id` → `project_config.id` in logger call |
| `tests/integration/test_daemon_prompt_snapshot.py` | New file with 3 integration tests: `test_initial_run_snapshots_prompt_text`, `test_fix_cycle_snapshots_fix_prompt_text_and_base_prompt_text`, `test_fix_cycle_missing_base_prompt_file_sets_null_not_error` |

## Test results

```
tests/integration/test_daemon_prompt_snapshot.py::test_initial_run_snapshots_prompt_text PASSED
tests/integration/test_daemon_prompt_snapshot.py::test_fix_cycle_snapshots_fix_prompt_text_and_base_prompt_text PASSED
tests/integration/test_daemon_prompt_snapshot.py::test_fix_cycle_missing_base_prompt_file_sets_null_not_error PASSED
=============== 3 passed in 5.64s ================

tests/unit/ -k "daemon or batch_manager or fix_cycle"
=============== 353 passed, 2664 deselected, 1 warning in 2.76s ================
```

## Preflight

| Check | Result |
|-------|--------|
| `make format` | OK — all files formatted |
| `make typecheck` | OK — no errors in 251 source files |
| `make lint` | OK — all checks passed |

## TDD RED evidence

```
tests/integration/test_daemon_prompt_snapshot.py::test_initial_run_snapshots_prompt_text
AssertionError: Expected prompt_text to be captured. Got: None
assert None == 'This is the EXPECTED prompt content for step S04.'
```

## Notes

- IO errors (missing prompt files, encoding errors) are swallowed with a `logger.warning` — step launch is **never** broken by prompt-snapshot failures. The column stays `None` and the UI renders `—`.
- The `append-only` invariant is preserved: both columns are set **only** in the `StepRun(...)` constructor call at row creation — no `UPDATE` statements.
- The `prompt_file: Path | None = None` pre-declaration before the QV-gate `if/else` avoids `UnboundLocalError` on the QV-gate path (where neither `prompt` nor `prompt_file` is assigned). Python's scoping requires all names used in a function to be declared before use, even within a conditional block that can't be reached on the QV path.
- Fix-cycle base prompt is read from `step.prompt_file` (a relative path in the worktree) via `Path(worktree_path) / "ai-dev" / "active" / item_id / step.prompt_file`. This is the same path resolution used by `_build_claude_prompt`, ensuring consistency.
