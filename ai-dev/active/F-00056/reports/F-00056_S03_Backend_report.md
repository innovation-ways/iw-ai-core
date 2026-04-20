# S03 Backend Report — F-00056 Work Item Execution Report

## What Was Done

### 1. Report Assembly & Rendering (`orch/daemon/execution_report.py`)

Created a new module with:

- **5 frozen dataclasses**: `StepRunSegment`, `FixCycleEntry`, `StepRow`, `RetryHotspot`, `ExecutionReportData`
- **`assemble_execution_report(session, project_id, work_item_id)`**: Queries WorkItem, WorkflowStep, StepRun, and FixCycle tables; computes Gantt percentages, hotspots, verdict, and total duration. Single transaction, no caching.
- **`render_execution_report_markdown(data)`**: Pure function producing a 4-section markdown document (Header+Verdict, Retry Hotspots, Step Timeline, Fix Cycle Details) with footer. Byte-identical for same data (no I/O, no randomness).
- **`resolve_report_path(session, project_id, work_item_id)`**: Mirrors `archive_work_item` path resolution pattern — checks active dir first, then archive dir. Raises `ExecutionReportResolutionError` if neither exists.
- **`write_execution_report(session, project_id, work_item_id)`**: Assemble → render → write to disk.

### 2. `iw item-report` CLI Command

Added `item-report` command to `orch/cli/item_commands.py` and registered it in `orch/cli/main.py`:

```
iw item-report <item_id> [--project <pid>] [--stdout]
```

- `--stdout`: prints markdown to stdout instead of writing to disk
- Exit 0 on success; exit 2 on path resolution failure; exit 1 on DB lookup failure

### 3. Daemon Auto-Trigger (`orch/daemon/batch_manager.py`)

Extended `_complete_item()` to call `_generate_execution_report()` after the commit but before archive. Best-effort: failures log a WARNING but do not block completion.

### 4. Fix Summary Ingestion (`orch/daemon/fix_cycle.py`)

Added `_parse_and_store_fix_summary()` function called from `_complete_fix_cycle()`. Reads the fix agent's log file from `fix_metadata`, parses JSON, and stores `fix_summary` (truncated to 20000 chars) on the FixCycle record. Gracefully handles missing/malformed JSON (never raises).

### 5. Fix Prompt Templates

Updated all three templates to require `fix_summary` in the result contract:
- `ai-dev/templates/CodeReview_FIX_Prompt_Template.md`
- `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md`
- `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md`

Each now includes `"fix_summary": "- bullet 1\n- bullet 2\n- bullet 3"` in the JSON block with a note about the 2000-char guidance.

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/execution_report.py` | New — assembly + rendering module |
| `orch/cli/item_commands.py` | Added `item-report` command + imports |
| `orch/cli/main.py` | Registered `item-report` command |
| `orch/daemon/batch_manager.py` | Extended `_complete_item()` to auto-trigger report |
| `orch/daemon/fix_cycle.py` | Added `_parse_and_store_fix_summary()` |
| `ai-dev/templates/CodeReview_FIX_Prompt_Template.md` | Added `fix_summary` to contract |
| `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md` | Added `fix_summary` to contract |
| `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md` | Added `fix_summary` to contract |
| `tests/unit/test_execution_report.py` | New — 14 unit tests for renderer |

## Test Results

- **`make test-unit`**: 1006 passed (includes 14 new tests)
- **`make test-integration`**: 580 passed, 5 failed, 7 skipped
  - The 5 failures are **pre-existing** in `test_code_qa_findusages.py` and `test_code_qa_routes.py` (QA engine, unrelated to this feature)
- **`uv run ruff check orch/ tests/`**: All checks passed
- **`uv run mypy orch/`**: Success — no issues found in 92 source files

## Notes

- The `FixCycle.fix_summary` column was already added in a prior migration (S01); my code only adds the ingestion logic.
- The 5 integration test failures are in the QA engine (`symbol_hint` routing) and were verified to exist before my changes via `git stash`.
- Integration tests for the new execution report CLI and auto-trigger will be added in S09 (per the design's File Manifest).
