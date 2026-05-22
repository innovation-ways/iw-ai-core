# I-00103 S01 Backend Report

## Summary

Fixed the `merge_auto_resolution_failed` event to include per-file error strings. Before the fix, the event metadata only listed which file paths errored (`error_files`), dropping the human-readable reason (`LLMCallResult.error`). The fix adds a `per_file_errors` list to the failed-event metadata payload, derived directly from the `llm_calls` accumulator built during `attempt_resolution`.

## What Was Done

Added a `per_file_errors` derivation block immediately before the `if abstained_files or error_files:` branch in `attempt_resolution` (line ~963 in the modified file). The block:

- Iterates `llm_calls` and filters to only entries where `error is not None`.
- Maps each to a dict with `file_path`, `error` (truncated at 500 chars), `cli_tool`, `model`.
- Adds `per_file_errors` as a new key in the `EVENT_AUTO_RESOLUTION_FAILED` metadata dict.

This preserves all existing fields (`abstained_files`, `error_files`, `proposed_files`, `total_input_tokens`, `total_output_tokens`, `runtime_option_id`, `phase`) exactly as before. The change is purely additive.

## Files Changed

- `orch/daemon/auto_merge.py` — lines ~963-988: added `per_file_errors` list comprehension and new dict key in the failed-event payload.

## Design Decisions

- **Truncation at 500 chars**: matches the existing cap at `auto_merge.py:784` (`result.stderr[:500]`). The in-memory `LLMCallResult.error` is NOT modified; only the persisted copy is capped, preserving full log fidelity.
- **No new truncation pass**: worst-case payload is `5 × (500 + path + 80) ≈ 3.5 KB`, comfortably under the 256 KB `max_event_metadata_bytes` default. A one-line size-budget comment documents this analysis for future readers.
- **List order preserved**: `per_file_errors[i].file_path` matches the iteration order of `llm_calls`, which is identical to the order `error_files` is populated — ensuring consistency between the flat `error_files` list and the structured `per_file_errors` view.
- **Schema**: `{file_path: str, error: str, cli_tool: str, model: str}` per entry — forward-compatible with per-file runtime fallback (Phase 2).

## Preflight Results

| Gate | Result |
|------|--------|
| `make format` | ok — no drift |
| `make typecheck` | ok — 0 errors in 274 source files |
| `make lint` | ok — All checks passed |

## Test Verification

```
uv run pytest tests/integration/test_auto_merge_phase1.py -v
```

**19 passed, 0 failed** in 23.79 s. Coverage warning (4.65% total) is pre-existing and unrelated to this change. The existing `test_ac4_operator_ux_unchanged_on_llm_error` integration test exercises the `merge_auto_resolution_failed` emission path without regression.

**TDD note**: dedicated reproduction/regression tests (`tests/integration/test_auto_merge_failed_event_metadata.py`, `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py`) are owned by S05 (tests-impl) per the design doc's File Manifest. TDD red evidence: `n/a — reproduction + regression tests delegated to S05 tests-impl per design doc TDD Approach`.

## Blockers

None.
