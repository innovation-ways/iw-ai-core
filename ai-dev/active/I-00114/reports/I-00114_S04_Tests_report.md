# I-00114 S04 Tests Report

## What was done
- Extended `tests/unit/test_pi_narration_guard.py` into a full helper-level suite:
  - narration/toolCall classification variants
  - missing/malformed/no-assistant handling
  - latest-session selection behavior
  - reprompt-message truncation and `None` handling
- Added `tests/integration/_stub_pi.py` deterministic stub runtime used by guard integration tests.
- Added full integration suite in `tests/integration/test_pi_narration_guard.py` driving `executor/pi_narration_guard.py` via real subprocesses and real DB writes through `iw` CLI:
  - narration-exit reproduction (5 events, attempt metadata, snippet assertion, 1 step_run)
  - clean completed-step path (no reprompt, no narration events)
  - non-zero pi exit path (no reprompt, exit code preserved)
  - reprompt cap boundary (no 6th reprompt loop)
  - opencode/claude command-builder regression guard (no wrapper)

## Files changed
- `tests/unit/test_pi_narration_guard.py`
- `tests/integration/test_pi_narration_guard.py`
- `tests/integration/_stub_pi.py`

## Preflight quality gates
- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Test verification
- `uv run pytest tests/unit/test_pi_narration_guard.py tests/integration/test_pi_narration_guard.py -v` ✅
- Result: **15 passed, 0 failed**

## TDD RED evidence anchor
- Design-time RED anchor: I-00114 Root Cause Analysis quotes F-00089 S05 pi sessions `2026-05-25T15-08-10-...jsonl` and `2026-05-25T15-11-34-...jsonl` (both `[thinking,text]`, no `toolCall`, both consumed retry budget).
- This suite’s assertion `len(narration_events) == 5` in `test_narration_exit_emits_event_and_reprompts` would have observed `0` against pre-S02 HEAD because `executor/pi_narration_guard.py` did not exist.

## Notes
- Stub-pi pattern is deterministic (no network, no sleeps).
- Guard subprocess timeout is set to `10s` per invocation to keep tests bounded and fail clearly on hangs.
- I could not read the two `/home/sergiog/.pi/...jsonl` files listed in the prompt because this worktree session is restricted to paths inside the current working directory.
