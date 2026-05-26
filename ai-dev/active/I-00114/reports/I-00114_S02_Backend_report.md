# I-00114 S02 Backend Report

## What was done
- Added `executor/pi_narration_guard.py` as a Python wrapper around `pi` with required helper decomposition:
  - `parse_args`, `run_pi`, `is_step_still_running`, `find_latest_pi_session`, `classify_last_assistant`, `build_reprompt_message`, `emit_narration_event`, `main`.
- Implemented narration-exit handling flow:
  - Run initial `pi` command.
  - If exit non-zero: return immediately.
  - If exit zero: query `uv run iw -j item-status <item_id>` and gate on step status.
  - If still `in_progress`: emit `step_narration_exit` event via `iw daemon-event`, reprompt via `pi --continue ...`, repeat up to cap.
- Implemented JSONL telemetry classifier (`NarrationVerdict`) and last assistant text extraction.
- Implemented session-dir transform for current worktree CWD as:
  - strip leading `/`
  - replace `/` with `-`
  - wrap as `--<slug>--`
- Added required TDD seed test `tests/unit/test_pi_narration_guard.py::test_classify_narration_shape_text_only_returns_NARRATION`.

## TDD (RED -> GREEN)
- RED evidence:
  - `tests/unit/test_pi_narration_guard.py::test_classify_narration_shape_text_only_returns_NARRATION`
  - `ModuleNotFoundError: No module named 'executor.pi_narration_guard'`
- GREEN:
  - Implemented module and classifier; test now passes.

## Files changed
- `executor/pi_narration_guard.py`
- `tests/unit/test_pi_narration_guard.py`

## Preflight quality gates
- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Test verification
- `uv run pytest tests/unit/test_pi_narration_guard.py -v` ✅
- Result: `1 passed, 0 failed`

## Notes / observations
- Reprompt execution preserves model/isolation flags by reusing original argv and replacing `-p/--print <prompt>` with `--continue <message>`.
- Guard logs use stderr with `[narration-guard]` prefix for daemon log searchability.
- If session JSONL is missing or parse fails, guard continues reprompt flow and records `PARSE_ERROR`/`last_assistant_text=null` telemetry.
