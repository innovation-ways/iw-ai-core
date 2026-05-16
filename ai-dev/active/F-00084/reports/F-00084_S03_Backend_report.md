# F-00084 S03 Backend Report

## Summary

Implemented daemon-side logic for LLM-assisted merge conflict resolution (Phase 0 plumbing + Phase 1 dry-run). TDD approach: RED unit tests written and confirmed failing (ImportError), then GREEN implementation, then lint/typecheck fixes.

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/auto_merge.py` | New module — full implementation (1150 lines) |
| `orch/daemon/merge_queue.py` | Added marker parsing + routing to `auto_merge` after conflict detection |
| `executor/step_executor_lib.sh` | Added `auto_merge_resolve` case + `_run_agent_oneshot` helper |
| `tests/unit/test_auto_merge_config.py` | 7 unit tests for AutoMergeConfig.load() |
| `tests/unit/test_auto_merge_classifier.py` | 7 unit tests for classify_conflicts() |
| `tests/unit/test_auto_merge_prompt.py` | 5 unit tests for build_resolution_prompt() |
| `tests/unit/test_auto_merge_marker.py` | 8 unit tests for parse_auto_resolve_marker/parse_auto_skip_marker |

## TDD Evidence

**RED phase**: Before implementation, running `uv run pytest tests/unit/test_auto_merge_*.py -v` produced:
```
ImportError: cannot import name 'AutoMergeConfig' from 'orch.daemon.auto_merge'
```
(module did not yet exist — all 27 tests failed at collection)

**GREEN phase**: After implementing `orch/daemon/auto_merge.py`, all 27 tests passed.

## Test Results

```
27 passed in 0.10s
```

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — 719 files already formatted |
| `make typecheck` | ok — 0 issues in 250 source files |
| `make lint` | ok — all checks passed |
| Targeted unit tests | 27 passed, 0 failed |

## Implementation Notes

- **Phase 0** path: `attempt_resolution()` short-circuits immediately, emits `EVENT_AUTO_RESOLUTION_SKIPPED` with `reason="phase_0"`, zero subprocess invocations. Phase 1 always returns `success=False` — operator UX unchanged.
- **`AutoMergeConfig.load()`** handles TOML `null` values (not valid TOML) by pre-stripping those lines, since `executor/auto_merge.toml` uses `runtime_option_id = null` idiom.
- **`classify_conflicts()`** implements the R-00076 §5.2 decision tree deterministically: refuse-list → binary → file_too_large → hunk_too_large → too_many_files → not_allowlisted → eligible.
- **`merge_queue.py` integration**: new code is entirely wrapped in `try/except` so any exception in the auto-merge path cannot prevent the existing `merge_conflict` event or `merge_failed` state transition.
- **`step_executor_lib.sh`**: added `_run_agent_oneshot` helper (reads stdin, calls `claude --print` or `opencode run`, no DB writes, no step-done call) and wired it to the `auto_merge_resolve` case.
- **Event ordering** preserved: `merge_auto_resolution_attempted` → per-file LLM → `merge_auto_resolved | merge_auto_resolution_failed | merge_auto_resolution_skipped` → existing `merge_conflict`.
- All four event type strings are plain TEXT values — no migration needed.
- `prompt_hash` and `output_hash` (sha256) stored in every event's metadata for audit without storing the full prompt.
