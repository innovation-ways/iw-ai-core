# I-00036 S03 Tests Report

## What was done

S03 (Tests) validates the S01 backend fix to the batch progress bar (step-level vs item-level progress). The fix changes `_all_batches()` in `dashboard/routers/batches.py` to compute `progress_pct` from `WorkflowStep` done/skipped counts rather than `BatchItem` completed/merged counts.

## Files reviewed

| File | Change |
|------|--------|
| `dashboard/routers/batches.py` | S01 fix — step-counting logic in `_all_batches()` (lines 195–246) |
| `dashboard/routers/project_dashboard.py` | Reviewed independently — has its own `_active_batches()` with item-level progress (pre-existing issue) |

## Test results

- `ruff check dashboard/routers/batches.py dashboard/routers/project_dashboard.py` — **All checks passed**
- `mypy dashboard/routers/batches.py dashboard/routers/project_dashboard.py` — **No issues found**
- `tests/unit/test_batch_archiver.py + test_batch_planner.py` — **27 passed**
- `tests/integration/test_batch_archive.py + test_batch_manager.py + test_cli_batches.py` — **37 passed**
- `tests/dashboard/` (non-browser, non-conflicting) — **109 passed, 1 skipped, 1 xfailed**

Dashboard test failures (7 failures, pre-existing, unrelated to batch progress):
- `test_chat_security.py::TestChatTemplatesNoMarkedReferences` — missing vendor assets (dompurify, highlightjs)
- `test_code_qa_sse_wire.py` (5 failures) — FakeEngine/FailingEngine use `answer_stream` not `answer_stream_v2`; SSE test infrastructure issue

## Issues or observations

**MEDIUM (non-blocking):** `project_dashboard.py` has its own `_active_batches()` function (lines 87–147) that still computes `progress_pct` from item-level counts, not step-level. This is pre-existing and not introduced by S01. The batch list page (`/project/{id}/batches`) shows step-level progress correctly, while the project dashboard home (`/project/{id}/`) shows item-level progress (jumps 0→100). Not in scope for S01/S03 fix cycle.

**No blocking issues found.** The S01 implementation is correct and passes all quality checks.