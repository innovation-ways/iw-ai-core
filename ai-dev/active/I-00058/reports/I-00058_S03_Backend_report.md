# I-00058_S03_Backend_report — Step S03: Backend Implementation

**Work Item**: I-00058 — DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers
**Step**: S03
**Agent**: backend-impl
**Date**: 2026-05-01

---

## Summary

Implemented the business-logic layer for I-00058. Added the `before_insert` SQLAlchemy event listener that auto-allocates `DOC-NNNNN` public_ids for `DocGenerationJob` records, and updated the jobs aggregator to surface `public_id` as the display identifier with UUID fallback for legacy rows.

---

## Changes Made

### 1. `orch/db/models.py` — Added `before_insert` event listener for `DocGenerationJob`

**Location**: After `DocGenerationJob` class definition (line ~1386), immediately before `DocTypeGuide`.

**Pattern**: Exact match to `_code_index_job_allocate_public_id` (lines 1542–1559), using `id_sequences['DOC']` instead of `id_sequences['CM']`.

```python
@event.listens_for(DocGenerationJob, "before_insert")
def _doc_generation_job_allocate_public_id(
    _mapper: Mapper[Any], connection: Connection, target: DocGenerationJob
) -> None:
    """Auto-allocate ``DOC-NNNNN`` public_id from id_sequences if not set."""
    if target.public_id is not None:
        return
    n = connection.execute(
        text(
            "INSERT INTO id_sequences (prefix, next_number) VALUES ('DOC', 2)"
            " ON CONFLICT (prefix) DO UPDATE"
            " SET next_number = id_sequences.next_number + 1"
            " RETURNING next_number - 1"
        )
    ).scalar()
    target.public_id = f"DOC-{int(n or 1):05d}"
```

Key design decisions:
- Uses `INSERT … ON CONFLICT … DO UPDATE RETURNING next_number - 1` for atomic increment
- Respects pre-set `public_id` (won't overwrite explicitly assigned values)
- Starts from `DOC-00001` (next_number=2, returning next_number-1=1)

### 2. `orch/jobs/aggregator.py` — Updated `_fetch_doc_generation`

**Location**: Lines ~378–401.

- Added `"public_id": job.public_id` to the `raw` dict alongside `"id": job.id`
- Changed `job_id=job.id` → `job_id=job.public_id or job.id` in `JobRow` construction

### 3. `orch/jobs/aggregator.py` — Updated `_get_doc_generation`

**Location**: Lines ~596–617.

- Changed lookup strategy: tries `scalar(select(DocGenerationJob).where(DocGenerationJob.public_id == job_id))` first (new rows), falls back to `session.get(DocGenerationJob, job_id)` for legacy UUID-based rows
- Changed `job_id=job.id` → `job_id=job.public_id or job.id` in `JobRow`
- Updated `raw` dict to include `"public_id": job.public_id`

### 4. `tests/integration/test_doc_generation_job_public_id.py` — New test file

Added 3 integration tests (TDD RED→GREEN cycle):

| Test | Purpose |
|------|---------|
| `test_i00058_doc_generation_job_gets_sequential_public_id` | Proves `public_id` is auto-allocated as `DOC-NNNNN` on insert |
| `test_i00058_doc_generation_job_public_id_increments` | Proves sequential inserts get strictly incrementing IDs |
| `test_i00058_doc_generation_job_public_id_not_overwritten` | Proves pre-set `public_id` is not overwritten by listener |

---

## Test Results

| Suite | Result |
|-------|--------|
| `test_doc_generation_job_public_id.py` (3 tests) | ✅ 3 passed |
| `test_doc_generation.py` (19 tests) | ✅ 19 passed |
| `test_jobs_aggregator.py` (11 tests) | ✅ 11 passed |
| `make test-unit` (2254 tests) | ✅ 2254 passed, 2 skipped, 5 xfailed |

---

## Quality Gates

| Gate | Status |
|------|--------|
| `make format` | ✅ Fixed 2 files (ruff format) |
| `make typecheck` | ✅ Success: no issues in 211 source files |
| `make lint` | ✅ Fixed unused import (pytest) |

---

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `_doc_generation_job_allocate_public_id` before_insert listener |
| `orch/jobs/aggregator.py` | Updated `_fetch_doc_generation` and `_get_doc_generation` to use `public_id` |
| `tests/integration/test_doc_generation_job_public_id.py` | New TDD test file (3 tests) |

---

## Observations

- The `public_id` column was already present on `DocGenerationJob` (added by S01), but the auto-allocation listener was missing — exactly the gap described in the design.
- The `id_sequences['DOC']` sequence starts at `DOC-00001` because `next_number` is initialized to `2` in the INSERT and we RETURN `next_number - 1`. This matches the `CM` pattern where the first code index job gets `CM-00001`.
- Legacy rows (UUID `id` with NULL `public_id`) are handled gracefully by the `job.public_id or job.id` fallback in both `_fetch_doc_generation` and `_get_doc_generation`.