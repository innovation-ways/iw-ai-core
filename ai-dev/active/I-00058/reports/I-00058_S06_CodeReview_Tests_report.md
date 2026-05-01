# I-00058 S06 — Code Review: Tests (S05)

## Summary

Reviewed the test file `tests/integration/test_i00058_doc_generation_public_id.py` produced by the Tests agent (S05). The tests are well-structured and semantically correct. All 10 tests pass.

## Pre-Review Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 508 files already formatted |

## Test Execution

```
10 passed, 1 warning in 12.82s
```

## Review Checklist

### 1. Reproduction Test Presence and Correctness ✅

- **`test_i00058_public_id_exactly_doc_00001_on_first_insert`**: Uses `db_session.flush()` to trigger `before_insert`. Asserts `job.public_id == "DOC-00001"` — exact value, not just non-null. Would fail on pre-fix code (`AttributeError: 'DocGenerationJob' has no attribute 'public_id'`).

- **`test_i00058_public_id_format_is_doc_nnnnn_not_uuid`**: Asserts both `DOC_PUBLIC_ID_PATTERN.match(job.public_id)` (format check) and `not _UUID_PATTERN.match(job.public_id)` (explicitly NOT a UUID). Semantically correct.

### 2. Sequential Increment Test ✅

- **`test_i00058_sequential_increment_two_jobs`**: Two jobs inserted in one transaction, asserted as `"DOC-00001"` and `"DOC-00002"` (exact values). Integration test against testcontainer DB, not mocked.

- **`test_i00058_sequential_increment_three_jobs`**: Three jobs, exact values DOC-00001/02/03.

### 3. Aggregator Tests ✅

- **`test_i00058_aggregator_list_jobs_returns_public_id_as_job_id`**: Asserts `row.job_id == "DOC-00001"` (not the UUID), plus `_UUID_PATTERN` negative check. ✅

- **`test_i00058_aggregator_get_job_returns_public_id`**: `get_job(..., job_id="DOC-00001")` finds the correct row. ✅

- **`test_i00058_aggregator_raw_includes_public_id`**: Asserts `raw["public_id"] == "DOC-00001"`. ✅

### 4. Semantic Correctness (I003 Lesson) ✅

No weak assertions found. Every check is:
- Exact value: `assert job.public_id == "DOC-00001"` / `assert row.job_id == "DOC-00001"`
- Regex format: `assert DOC_PUBLIC_ID_PATTERN.match(job.public_id)`
- Negative UUID check: `assert not _UUID_PATTERN.match(job.public_id)`

No instances of `assert public_id is not None` as the sole assertion.

### 5. Test Isolation ✅

- Uses `db_session` fixture from `tests/integration/conftest.py` which provides a transactional rollback after each test — no cross-test contamination.
- No explicit `id_sequences` cleanup needed; the transaction rollback handles it.
- Tests use testcontainers (not port 5433). ✅

### 6. Conventions ✅

- File location: `tests/integration/test_i00058_doc_generation_public_id.py` — follows naming convention.
- Uses `db_session: Session` typed fixture.
- Uses `tmp_path: Path` for aggregator tests that instantiate `JobsAggregator` (requires a repo directory path for project settings lookups).
- `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` are installed by the `db_engine` fixture in `tests/integration/conftest.py` (lines 111–118) — no per-test re-install needed.
- Imports are clean, no live DB connections.

### 7. Additional Tests — DocService Integration ✅

- **`test_i00058_doc_service_create_doc_job_returns_doc_nnnnn_public_id`**: End-to-end test via `DocService.create_doc_job()`. Asserts `public_id` is not None, matches `^DOC-\d{5}$`, and is NOT a UUID. Also verifies the UUID `id` PK column is still set.

- **`test_i00058_doc_service_create_doc_job_multiple_have_incrementing_ids`**: Two consecutive `create_doc_job` calls produce `"DOC-00001"` and `"DOC-00002"` (exact values).

### 8. Code Changes Reviewed (S03 backend)

- `orch/db/models.py`: `public_id` column added to `DocGenerationJob` with unique index. `before_insert` listener uses `INSERT ... ON CONFLICT` pattern (same as `CodeIndexJob`). Correctly skips when `public_id` is pre-set.
- `orch/jobs/aggregator.py`: `_fetch_doc_generation` adds `public_id` to `raw` and uses `job.public_id or job.id` for `job_id`. `_get_doc_generation` queries by `public_id` first, falls back to PK. Correct legacy fallback handling.

## Notes

- The legacy UUID fallback test (for `public_id=None` rows returning UUID as `job_id`) was intentionally removed per S05 report — `session.get(DocGenerationJob, job_id)` does a PK lookup that would find any row by UUID regardless of `project_id` match. The fallback is correctly implemented as `job.public_id or job.id` in the aggregator code, which returns the UUID when `public_id` is NULL. No test gap here.

## Findings

No critical or high issues found.

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00058",
  "step_reviewed": "S05",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "tests_passed": true,
  "test_summary": "10 passed, 0 failed",
  "notes": "Tests are semantically correct, isolated, and follow all conventions. Pre-review lint and format gates passed. All reproduction, sequential increment, aggregator, and DocService integration tests pass."
}
```