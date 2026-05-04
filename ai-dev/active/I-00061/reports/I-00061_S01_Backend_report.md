# I-00061 S01 Backend Report

## What Was Done

Implemented the auto-skip phantom QV gates feature end-to-end:

1. **Created `orch/qv_gate_validator.py`** — pure validators + DB-mutating orchestrator:
   - `_makefile_target(command)` — parses `make [flags] <target>` patterns, consuming flag arguments
   - `_makefile_has_target(repo_root, target)` — reads `Makefile` and checks for `^<target>:` regex
   - `_cd_directory(command)` — extracts dir from `cd <dir> && ...` pattern
   - `_bare_executable(command)` — classifies non-make/cd commands, skips shell-operator tokens
   - `GateVerdict` dataclass (frozen) with `runnable: bool` and `reason: str | None`
   - `classify_qv_gate(repo_root, gate, command) -> GateVerdict` — full pattern matching
   - `validate_qv_gate(...) -> bool` — convenience wrapper
   - `auto_skip_phantom_qv_gates(session, project_id, work_item_id, *, trigger) -> list[tuple[str, str, str]]` — orchestrator

2. **Wired `approve` in `orch/cli/item_commands.py`**:
   - Post `session.flush()`, calls `auto_skip_phantom_qv_gates(trigger="approve")`
   - JSON output: adds `auto_skipped_steps` array
   - Plain output: one line per skipped step

3. **Wired `batch_approve` in `orch/cli/batch_commands.py`**:
   - After batch transition + daemon event, iterates all `BatchItem` rows and calls `auto_skip_phantom_qv_gates(trigger="batch_approve")` for each
   - Aggregates results, surfaces in same JSON/plain style

## Design Decisions

- **Bare executable pattern**: Decided NOT to call `shutil.which()` on bare executables. The daemon's environment may have tools not in the test host's `PATH` (npx wrappers, worktree-local binaries). Conservative default: assume runnable → worst case is false negative (pre-fix behavior), not a false positive.
- **`gate` parameter in `classify_qv_gate`**: Currently unused (ARG001). The gate name is for audit purposes; the command is the source of truth. Marked `# noqa: ARG001` to suppress the lint warning without ignoring globally. Could be used in future for per-gate skip opt-outs.
- **`_makefile_target` flag handling**: Handles short flags (-C, -f, -j), long flags (--flag, --flag=value), and multi-char short flags (-abc) to robustly find the actual target token.
- **`_bare_executable` shell-operator guard**: If any token in the shlex-split command is a shell operator (`|`, `;`, `&`, `>`, `<`), returns `None` — prevents misclassifying complex commands like `shell_cmd | grep foo`.

## Files Changed

| File | Change |
|------|--------|
| `orch/qv_gate_validator.py` | **NEW** — pure validators + orchestrator |
| `orch/cli/item_commands.py` | Modified `approve` — added hook call and output enhancement |
| `orch/cli/batch_commands.py` | Modified `batch_approve` — added hook per batch item and output enhancement |

## Test Results

- **Pattern checks**: All pass (`_makefile_target`, `_makefile_has_target`, `_cd_directory`, `_bare_executable`, `classify_qv_gate`, `validate_qv_gate`)
- **`make type-check`**: Success — no issues in 217 source files
- **`make lint`** (ruff on changed files): All checks passed
- **`make test-unit`**: 2484 passed, 2 failed — pre-existing failures in `test_safe_migrate.py` (unrelated to this change; verified by git stash comparison)

## Pre-flight Results

| Check | Result |
|-------|--------|
| `make format` | Fixed — `batch_commands.py` was reformatted |
| `make type-check` | `ok` |
| `make lint` | `ok` |

## Notes

- The phantom-gate output appears after "Approved X" in plain mode, indented by 2 spaces to visually nest under the approval confirmation
- The `auto_skip_phantom_qv_gates` return type is `list[tuple[str, str, str]]` (step_id, gate, reason) — reason is always non-None when returned since we only return skipped items
- `trigger="batch_approve"` is passed from the batch hook so audit trail distinguishes the two entry points
