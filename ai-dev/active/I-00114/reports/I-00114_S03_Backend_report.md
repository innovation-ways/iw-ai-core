# I-00114 S03 Backend Report

## What was done
- Wired pi launches through the narration guard in both daemon command builders:
  - `orch/daemon/batch_manager.py::_build_initial_command` (pi branch)
  - `orch/daemon/fix_cycle.py::_build_fix_inner_command` (pi branch)
- Added shared constant in `batch_manager.py` and reused it from `fix_cycle.py`:
  - `_PI_NARRATION_GUARD_SCRIPT = "executor/pi_narration_guard.py"`
- Kept guard path worktree-relative (no absolute host paths).
- Threaded `item_id`/`step_id` into launch sites:
  - `_build_initial_command(..., item_id=step.work_item_id, step_id=step.step_id, ...)`
  - `_build_fix_inner_command(..., item_id=item_id, step_id=step_id)`
- Guard argv shape now includes:
  - `python executor/pi_narration_guard.py --item-id ... --step-id ... --max-reprompts 5 -- pi -p "$(cat ...)" --model ...`

## Files changed
- `orch/daemon/batch_manager.py`
- `orch/daemon/fix_cycle.py`
- `tests/unit/test_daemon_command_builders.py`

## TDD
- RED:
  - `tests/unit/test_daemon_command_builders.py::test_pi_branch_invokes_narration_guard`
  - Failure: `AssertionError: assert cmd.startswith("python ")` (command was bare `pi -p ...`)
- GREEN:
  - After wiring guard, all tests in the new test file pass.

## Regression pin (AC4)
- Added:
  - `test_opencode_branch_unchanged`
  - `test_claude_branch_unchanged`
- Confirmed those branches remain unchanged in both builders; guard wrapping is pi-only.

## Verification
- `uv run pytest tests/unit/test_daemon_command_builders.py -v` → **3 passed, 0 failed**
- `make format` → ok
- `make typecheck` → ok
- `make lint` → ok

## Notes
- Chose the **single shared constant** approach (defined once in `batch_manager.py`, imported in `fix_cycle.py`) to keep both builders in lock-step without introducing a new shared module.
