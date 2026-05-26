# CR-00088 S02 — Backend Implementation: `deferred_files` Threading Through Event Metadata

## Summary

Threaded the `deferred_files` tuple (populated by `classify_conflicts` in S01) through all three daemon event emission paths so operators can see the allowlist partition in the dashboard auto-merge views and raw `daemon_events` rows.

## What Was Done

### 1. `attempt_resolution()` — new `deferred_files` kwarg (auto_merge.py:883–888)

Added `deferred_files: list[str] | None = None` as a keyword-only parameter with `None` as the default (backward compatible with any existing callers that don't pass it). The LLM is still invoked only for `eligible_files`; `deferred_files` only affects event metadata.

Updated the `EVENT_AUTO_RESOLUTION_SKIPPED` phase-0 short-circuit metadata dict to also include `"deferred_files": list(deferred_files or [])` alongside `"eligible_files"`. The test `test_cr88_deferred_files_skipped_event` found this gap and it was patched in the same edit pass.

### 2. `EVENT_AUTO_RESOLUTION_ATTEMPTED` metadata (auto_merge.py:924–932)

Metadata dict now includes:

```python
"allowlisted_files": eligible_files,       # alias — dashboard reads this
"deferred_files": list(deferred_files or []),
```

`conflict_files` is preserved for backward compatibility with existing dashboard views.

### 3. `EVENT_AUTO_RESOLUTION_FAILED` metadata (auto_merge.py:976–991)

When LLM abstains or errors for one or more eligible files, the failed event now carries `"deferred_files": list(deferred_files or [])` so operators see the full picture even when the LLM didn't complete all allowlisted files.

### 4. `EVENT_AUTO_RESOLVED` metadata (auto_merge.py:1057)

Success-path metadata dict includes `"deferred_files": list(deferred_files or [])`. The human-readable event message was updated to mention the deferred count when non-zero (e.g., `"...; 1 file(s) deferred (non-allowlisted) for operator"`).

### 5. `merge_queue.py` — pass-through to `attempt_resolution` (line ~556)

The `attempt_resolution(...)` call now passes `deferred_files=list(_classification.deferred_files)` immediately after `eligible_files=...`.

### 6. `merge_queue.py` — `emit_skipped_event` dict (line ~517)

Added `"deferred_files": list(_classification.deferred_files)` to the details dict so the skipped event (fired when no LLM is invoked at all, e.g., phase=0) also carries the deferred list.

### 7. Docstrings

`attempt_resolution()` docstring now documents the `deferred_files` parameter and its sole effect on event metadata.

## TDD RED Evidence

Before the parameter was added, tests would fail with:

```
TypeError: attempt_resolution() got an unexpected keyword argument 'deferred_files'
```

After adding the parameter but before the metadata dictionary updates, tests would fail with:

```
KeyError: 'allowlisted_files'
```

```
KeyError: 'deferred_files'
```

## Tests Added / Modified

| Test | Description |
|------|-------------|
| `test_cr88_deferred_files_attempted_event` | REQ-1: `allowlisted_files` + `deferred_files` in `EVENT_AUTO_RESOLUTION_ATTEMPTED` |
| `test_cr88_deferred_files_resolved_event` | REQ-2: `deferred_files` in `EVENT_AUTO_RESOLVED` |
| `test_cr88_deferred_files_failed_event` | REQ-3: `deferred_files` in `EVENT_AUTO_RESOLUTION_FAILED` when LLM abstains |
| `test_cr88_deferred_files_default_empty` | REQ-4 (backward compat): `deferred_files=[]` when not passed |
| `test_cr88_deferred_files_skipped_event` | REQ-4 (skipped path): `deferred_files` in `EVENT_AUTO_RESOLUTION_SKIPPED` |

All 5 new tests: **PASS** (24/24 total in `test_auto_merge_phase1.py`).

## Files Changed

- `orch/daemon/auto_merge.py` — `attempt_resolution()` signature + all 3 event metadata dicts
- `orch/daemon/merge_queue.py` — pass-through argument + `emit_skipped_event` dict
- `tests/integration/test_auto_merge_phase1.py` — 5 new integration tests

## Quality Gates

```
make lint        ✓ All checks passed
make typecheck   ✓ Success: no issues found in 276 source files
pytest           ✓ 24 passed, 1 warning (shared fixture reimport warning, pre-existing)
```

## Notes

- The phase-0 path in `attempt_resolution()` emits `EVENT_AUTO_RESOLUTION_SKIPPED` directly (no `emit_skipped_event` helper needed), so it also got the `deferred_files` key added in the same edit.
- No new event types added; no worktree mutation; phase stays at 1.
- The `allowlisted_files` alias in the attempted event metadata is read by the dashboard to render the partition without depending on `conflict_files` being an array.