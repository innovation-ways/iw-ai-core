# CR-00066 S03 — Backend Implementation Report

## Step Summary

**Work Item**: CR-00066 — Context Window Usage Progress Bar  
**Step**: S03  
**Agent**: backend-impl  
**Status**: ✅ Complete

---

## What Was Done

Extended `orch/daemon/step_monitor.py` to extract token counts from pi session JSONL files and update `context_tokens_peak` / `context_tokens_last` on each poll cycle.

### Changes to `orch/daemon/step_monitor.py`

1. **Added `import json`** — required for JSON parsing in the new helper.

2. **Added `_extract_latest_tokens(session_file: str) -> int | None`** (lines 554–588)
   - Opens the session `.jsonl` file
   - Iterates lines in **reverse order** (most recent first) using `reversed()`
   - Skips non-matching lines (malformed JSON, wrong type, wrong role, missing usage)
   - Returns `message.usage.get("totalTokens")` as `int` from the first qualifying assistant message
   - Returns `None` for: file not found, empty file, no qualifying entries
   - All exceptions are swallowed silently

3. **Added `_update_token_counts(run: StepRun) -> None`** (lines 592–614)
   - Guards: `cli_tool == "pi"` and `session_file is not None`
   - Calls `_extract_latest_tokens` (wrapped in try/except)
   - Updates `run.context_tokens_last` to the latest value (may drop post-compaction)
   - Updates `run.context_tokens_peak` only when `latest > run.context_tokens_peak` (never decreases)

4. **Poll loop integration** (line 226)
   - For every alive `pi` StepRun with a resolved `session_file`, `_update_token_counts(run)` is called after the session-file resolution block, before any state-changing handlers

### New test file: `tests/unit/test_step_monitor_token_poll.py`

11 unit tests covering:
- `test_extract_latest_tokens_from_valid_jsonl` — returns totalTokens from most recent assistant message
- `test_extract_latest_tokens_ignores_non_assistant_entries` — skips tool_call, tool_result, thinking, etc.
- `test_extract_latest_tokens_returns_none_for_missing_usage` — no usage key or empty usage
- `test_extract_latest_tokens_returns_none_for_empty_file` — empty file returns None silently
- `test_extract_latest_tokens_returns_none_for_missing_file` — non-existent path returns None silently
- `test_extract_latest_tokens_skips_malformed_json_lines` — corrupt lines are skipped, valid last assistant is found
- `test_extract_finds_last_assistant_even_when_file_has_trailing_newlines` — trailing `\n\n\n` doesn't confuse reverse iteration
- `test_peak_never_decreases` — peak stays at 150K after compaction drops last to 80K
- `test_peak_increments_on_higher_tokens` — peak grows from 50K → 80K → 95K, then stays at 95K when last drops to 60K
- `test_non_pi_runs_are_not_touched` — claude runs are completely skipped
- `test_null_session_file_is_handled` — pi run with `session_file=None` does not raise

---

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/step_monitor.py` | +2 helper functions, +token polling in `_check_step_health`, +`import json` |
| `tests/unit/test_step_monitor_token_poll.py` | New file — 11 unit tests |

---

## Quality Gates

| Check | Result |
|-------|--------|
| `make format` | ⚠️ Other worktrees' files need formatting (not CR-00066 changes) |
| `make lint` | ✅ Passes (all ruff checks fixed) |
| `make typecheck` (orch/) | ✅ Passes — `mypy orch/daemon/step_monitor.py` clean |
| `make test-unit` | ✅ 11/11 tests pass |

**Note**: The `make typecheck` command fails due to a pre-existing mypy error in `dashboard/routers/items.py:2193` (unrelated to this worktree's changes — confirmed by stashing and running against the parent commit). The `orch/` package itself is clean.

---

## Notes

- The `_FakeStepRun` duck-type used in tests matches the pattern established in `test_step_monitor_session_file.py` for consistency.
- The reverse-iteration approach (`reversed(fh.readlines())`) was chosen over seeking from EOF to handle small files gracefully and avoid encoding issues with seek offsets.
- The existing `monitor_running_steps` / `_check_step_health` `db.commit()` at the end of the poll cycle handles persisting the token count updates — no separate commit needed.