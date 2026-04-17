# CR-00006 S07 — Tests Implementation Report

## Summary

Implemented test coverage for CR-00006 (Code View UX: Jobs View, Streaming Q&A, Markdown Rendering).

## Files Created

| File | Tests | Status |
|------|-------|--------|
| `tests/unit/test_code_qa_streaming.py` | 2 async unit tests | 1 pass, 1 fail* |
| `tests/unit/test_jobs_aggregator.py` | 11 unit tests | All pass |
| `tests/integration/test_jobs_api.py` | 7 integration tests | 2 pass, 5 fail** |
| `tests/unit/test_qa_markdown_sanitize.py` | 6 template-grep tests | All pass |

## Test Details

### `test_code_qa_streaming.py`
- **`test_sse_generator_streams_tokens_live`** — Proves `_sse_generator` yields SSE frames as tokens are produced (timing assertion: last token ≥0.3s after first with 5×100ms tokens). **FAILS with current implementation** (0ms gap — buffering bug correctly detected).
- **`test_sse_generator_handles_connection_error`** — Proves `ConnectionRefusedError` yields `{"event":"error","message":"Local AI unavailable"}` frame. PASSES.

### `test_jobs_aggregator.py`
All 11 tests pass against the testcontainer:
- Empty state returns `JobListResult(rows=[], total=0, page=1, page_size=25)`
- Four-source union returns 4 rows with distinct `job_type` values
- `types=[JobType.code_mapping]` narrows to 1 row
- `statuses=["completed"]` correctly excludes failed rows
- Date range filter works correctly
- Pagination: 30 rows → page=1,size=10 returns 10 rows,total=30; page=4 returns []
- Sort `desc`/`asc` produces inverse orderings
- `get_job` returns correct row for each type; `None` for bad id
- `BatchStatus.executing` normalises to `"running"`
- `DocStatus.published` (research doc) normalises to `"completed"`

### `test_qa_markdown_sanitize.py`
All 6 template-grep tests pass:
- DOMPurify CDN loaded with pinned version in `base.html`
- `code_qa_panel.html` calls `DOMPurify.sanitize` and `marked.parse`
- No `responseSpan.textContent +=` stale path
- `noopener noreferrer` hook present
- User bubble uses `textContent`, not `innerHTML`
- `qaRenderMarkdown` returns sanitized HTML

### `test_jobs_api.py`
- `test_code_mapping_job_detail_bogus_id_returns_404` — PASSES
- `test_jobs_bogus_project_returns_404` — PASSES
- Other 5 tests return 404 because `dashboard/routers/jobs_ui.py` (S03 scope) is not yet present in the worktree. Tests define the API contract; they will pass once S03 is implemented.

## Notes

- **`test_sse_generator_streams_tokens_live` failure is expected**: The current `code_qa.py` still has the buffering bug (`_run_qa_in_thread` collects all tokens via `asyncio.run(collect_tokens())` before the outer generator yields). The test correctly detects this (0ms between first and last token vs. expected ≥300ms). S01 was supposed to fix this.
- **`test_jobs_api.py` 404s are expected**: The `jobs_ui` router (S03) doesn't exist in this worktree yet. Tests are correctly written against the CR design contract.
- All tests use testcontainers (never live DB port 5433) per `tests/CLAUDE.md` rules.
- All ruff checks pass on all 4 new files.

## Ruff / Quality

```bash
uv run ruff check tests/unit/test_code_qa_streaming.py \
    tests/unit/test_jobs_aggregator.py \
    tests/unit/test_qa_markdown_sanitize.py \
    tests/integration/test_jobs_api.py   # All clean
```
