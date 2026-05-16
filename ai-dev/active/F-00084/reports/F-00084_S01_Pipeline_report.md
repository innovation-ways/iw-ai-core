# F-00084 S01 Pipeline Report

**Step**: S01
**Agent**: pipeline-impl
**Date**: 2026-05-16
**Status**: Complete

## Summary

Implemented the bash/TOML plumbing for F-00084 (LLM-Assisted Merge Conflict Resolution), Phase 0 (plumbing only). This step covers:

1. Created `executor/auto_merge.toml` with the phase ladder, allowlist, refuselist, and limits configuration.
2. Edited `executor/worktree_commit.sh` to add:
   - `--resume-rebase` flag guard (exits with code 2 — reserved for Phase 2)
   - LLM-resolution classification block between the auto-resolve loop and the abort branch

## Files Changed

### New Files

- `executor/auto_merge.toml` — Configuration file for LLM-assisted merge resolution. Default `phase = 0` (plumbing only, no LLM calls). Contains allowlist patterns (`tests/**/*.py`, `docs/**/*.md`, `ai-dev/active/**/reports/**` and sub-variants), refuselist patterns (migrations, executor scripts, security configs, binary formats), and limits (max 80 hunk lines, 5 conflicted files, 256KB per file, 256KB event metadata, 120s LLM timeout per file).

### Modified Files

- `executor/worktree_commit.sh` — Two changes:
  - **Lines 45-50**: `--resume-rebase` guard added immediately after `set -euo pipefail`. Uses `${1:-}` for safe unset variable access under `-u`. Exits with code 2 per the feature design.
  - **Lines 355-480**: Classification block inserted inside the `if [[ -n "$_blocking" ]]; then` branch, before the existing error/abort logic. Reads `auto_merge.toml` phase value (bash grep/awk — Python does full TOML parsing). Converts the space-separated `_blocking` string to an array. Classifies each blocking file against hardcoded bash refuse-list (prefix and suffix matching — coarse defence-in-depth; Python side does rich-glob classification). Emits one of:
    - `AUTO_RESOLVE_SKIPPED={...}` with `reason=refuse_list` (all refuse-listed)
    - `AUTO_RESOLVE_SKIPPED={...}` with `reason=mixed_refuse_list` (mixed)
    - `AUTO_RESOLVE_REQUESTED={...}` with eligible files + branch + main_sha (all eligible)
  - The existing abort logic (error messages + `git rebase --abort` + `exit 1`) runs unchanged after the classification block.

## Design Decisions

1. **Space-separated `_blocking` → array conversion**: The existing script uses a space-separated string `_blocking`. The new code converts it to a bash array `_blocking_files=($_blocking)` with a `# shellcheck disable=SC2206` comment (word splitting is intentional here since filenames with spaces would already fail the original loop).

2. **`_build_json_array` function with empty-array guard**: The function checks `${#_arr[@]} -eq 0` before calling `printf '%s\n' "${_arr[@]}"` to avoid `set -e` failure on empty arrays.

3. **`${1:-}` for `--resume-rebase` check**: Under `set -u`, bare `$1` fails when no args are passed. Using `${1:-}` provides a safe default empty string.

4. **`AUTO_MERGE_PHASE` variable is read but not used in this script**: The bash script only reads the phase to pass through markers. The Python `merge_queue.py` does the full TOML parsing and phase-based decision (whether to actually call the LLM). This keeps the bash script minimal and deterministic.

5. **`AUTO_RESOLVE_REQUESTED` always precedes the existing abort**: In Phase 0/1, bash ALWAYS aborts the rebase after emitting the marker. The Python side (S03) reads the marker and decides on LLM invocation — no git operations by Python during Phase 0/1.

6. **CONFLICT_FILES marker preserved**: The existing `CONFLICT_FILES` marker for the already-auto-resolved files (uv.lock/Makefile) is preserved untouched in the "all conflicts auto-resolved" path below the new block.

## TDD Verification Results

All 8 test groups passed (11 individual assertions):

| Test | Result |
|------|--------|
| --resume-rebase exits with code 2 | PASS |
| Refuse-list classification (migration + identity.py) | PASS |
| Eligible-file classification (3 test/*.py files from I-00085) | PASS |
| Mixed refuse+eligible → correctly split | PASS |
| Binary/suffix files refused (.png, .db, .tar.gz, .parquet) | PASS |
| AUTO_RESOLVE_REQUESTED marker format (starts correctly) | PASS |
| AUTO_RESOLVE_REQUESTED JSON payload parses correctly | PASS |
| AUTO_RESOLVE_SKIPPED marker format (starts correctly) | PASS |
| AUTO_RESOLVE_SKIPPED JSON payload parses correctly | PASS |
| auto_merge.toml exists | PASS |
| auto_merge.toml phase = 0 | PASS |

## Quality Gate Results

| Gate | Result | Notes |
|------|--------|-------|
| `make format` | PASS | "714 files already formatted" — no changes |
| `make lint` | PASS | "All checks passed!" — ruff + template checker |
| `make typecheck` | PASS | "Success: no issues found in 249 source files" |

## Observations

- The bash classification in `worktree_commit.sh` is intentionally coarse (prefix+suffix matching). The Python `auto_merge.py` (S03) will perform full glob classification using the patterns in `auto_merge.toml`. This defence-in-depth approach means even if the Python side has a bug, the bash refuse-list prevents LLM calls on critical files.
- The `executor/` prefix is in the bash refuse-list, which means `executor/auto_merge.toml` itself is also refuse-listed (consistent with the TOML refuselist).
- The `_build_json_array` function is defined inside the `if [[ -n "$_blocking" ]]; then` block to scope it appropriately and avoid polluting the global function namespace.
- The `AUTO_MERGE_PHASE` variable is read but not structurally used in Phase 0 bash logic — it's available for future logging/debugging without changing the control flow.
