# CR-00065 S03 — Backend Implementation

## What was done

Implemented two backend pieces for the Live Agent Session Log Viewer:

### Part 1 — `orch/daemon/step_monitor.py`

Added pi session file resolution:

- **`_resolve_pi_session_file(run: StepRun) -> str | None`**: Resolves the session `.jsonl` file path for a running `pi` StepRun. The session directory slug is derived by stripping the leading `/` from `worktree_path` and wrapping with `--` on both sides (`/home/user/CR-00065` → `--home-user-CR-00065--`). Scans `~/.pi/agent/sessions/{slug}/` for `.jsonl` files whose mtime >= `run.started_at`, returning the most recently modified one. All FS errors are swallowed and return `None`.

- **`_maybe_resolve_pi_session_file(db, run, now)`**: Called every poll cycle for any alive `pi` run whose `session_file` is still `NULL`. On success, writes the path to `run.session_file`; the caller commits the DB transaction. Wraps `_resolve_pi_session_file` in a broad `try/except` so any failure is non-fatal.

- Integrated into `_check_step_health`: after confirming the PID is alive, if `run.session_file is None`, calls `_maybe_resolve_pi_session_file`.

### Part 2 — `orch/daemon/session_reader.py`

New module exposing `read_session_content(run, max_chars=50_000)`:

- **pi runs**: Parses `session_file` JSONL. Each line is a JSON object. `type=="message"` with `role=="assistant"`: emits `assistant` (text, ≤2000 chars), `thinking` (truncated to 200 chars + `…`, collapsible), or `tool_call` (name + args summary, ≤200 chars) segments. `role=="toolResult"`: emits `tool_result` (first 500 chars, collapsible). `role=="user"`: skipped. `type=="compaction"`: emits `compaction` segment. `stopReason=="error"`: emits `error` segment. Malformed lines are logged at DEBUG and skipped.

- **claude/opencode runs**: Falls back to `log_content` DB field → `log_file` on disk (last `max_chars` bytes) → error segment.

- **unknown cli_tool**: Returns `[]`.

## Files changed

| File | Change |
|------|--------|
| `orch/daemon/step_monitor.py` | Added `_resolve_pi_session_file`, `_maybe_resolve_pi_session_file`, and integration in `_check_step_health` |
| `orch/daemon/session_reader.py` | New module with `read_session_content` |
| `tests/unit/test_session_reader.py` | 14 unit tests (RED→GREEN) |
| `tests/unit/test_step_monitor_session_file.py` | 8 unit tests for session file resolution |

## Test results

- **22 unit tests pass** (14 session_reader + 8 step_monitor_session_file)
- Format: clean
- Lint: clean
- Typecheck: clean (`mypy 1.20.0`, no issues)

## Notes

- Correct pi slug derivation: strip leading `/`, replace remaining `/` with `-`, wrap with `--`. e.g. `/home/user/CR-00065` → `--home-user-CR-00065--`. This was verified against actual session directories in `~/.pi/agent/sessions/`.
- The `started_at` mtime filter uses `>=` (not `>`) so files created at the same second as step start are still included.
- `_maybe_resolve_pi_session_file` has a no-op DB parameter kept for future use (e.g. logging events).