# I-00068 S02 Code Review — Backend (S01 Review)

## Summary

Reviewed S01 (`backend-impl`) changes to `orch/archive/batch_archiver.py`. The fix adds `entity_type="batch"` to all batch-scoped `DaemonEvent` emissions, correctly addressing **Defect 1** from the design doc.

## Files Changed

Only `orch/archive/batch_archiver.py` was modified (1 file, +10 lines / -1 line).

## Review Findings

### ✅ Architecture Compliance

| Check | Result |
|-------|--------|
| Fix contained to `orch/archive/batch_archiver.py` | ✅ No leakage to other emitters |
| New parameter has sensible default (`None`) | ✅ Line 355: `entity_type: str | None = None` |
| No UPDATE/DELETE on `daemon_events` | ✅ Append-only — only `db.add(event)` |

### ✅ Correctness

All 3 `_emit(...)` call sites pass `entity_type="batch"` as a **keyword argument** (not positional):

| Line | Event | How passed |
|------|-------|------------|
| 72 | `batch_archive_failed` (fatal error path in `archive_batch`) | `entity_type="batch"` kwarg |
| 172 | `batch_archive_failed` (error path in `_run_archive`) | `entity_type="batch"` kwarg |
| 189 | `batch_archived` (success path in `_run_archive`) | `entity_type="batch"` kwarg |

`DaemonEvent(...)` constructor at line 358-365 receives `entity_type=entity_type` — propagation is correct.

### ✅ Type Hints

- Function signature (line 355): `entity_type: str | None = None` ✅
- Passed as keyword argument at all call sites ✅
- mypy reports no issues ✅

### ✅ No Unintended Changes

- `orch/daemon/batch_manager.py`: Not modified ✅
- `orch/cli/batch_commands.py`: Not modified ✅
- `event_metadata=metadata or {}` preserved at line 363 ✅
- No new imports added ✅

### ✅ Project Conventions

- `event_metadata` Python name used (not `metadata`) ✅
- `daemon_events` append-only contract respected ✅
- Follows `orch/CLAUDE.md` rules ✅

### ✅ Security / Safety

- `entity_type="batch"` is a literal string — no untrusted input interpolation ✅
- SQLAlchemy ORM constructor handles parameterization ✅

### ✅ Test Coverage (I-00068-specific tests)

| Test | Status |
|------|--------|
| `test_batch_archived_event_has_entity_type_batch` | PASSED |
| `test_batch_archive_failed_event_has_entity_type_batch` | PASSED |
| `test_emit_entity_type_default_is_none` | PASSED |

| Suite | Result |
|-------|--------|
| `tests/integration/test_batch_archive.py` | 9 passed |
| `tests/integration/test_batch_manager.py` | 10 passed |
| `tests/integration/test_i00068_batch_link_routing.py` | 3 passed |

## Pre-Review Gate

| Check | Result | Note |
|-------|--------|------|
| `make lint` | 2 errors | Pre-existing in `ai-dev/active/I-00067/...` — not in S01 scope |
| `make format` | 2 files | Pre-existing in `ai-dev/active/I-00067/...` — not in S01 scope |
| `uv run ruff check orch/archive/batch_archiver.py` | PASSED | Changed file is clean |
| `uv run ruff format --check orch/archive/batch_archiver.py` | PASSED | Changed file is clean |
| `uv run mypy orch/archive/batch_archiver.py` | PASSED | No issues |

**The lint/format failures are pre-existing in I-00067's e2e fixtures (missing trailing newlines), completely unrelated to I-00068 S01 changes.**

## Notes

- S01 correctly implemented only Defect 1 (backend fix). Defect 2 (template fallback hardening) is S03's scope.
- The 3 new tests in `test_i00068_batch_link_routing.py` test the `_emit` boundary directly — they are falsifiable on `main` and would fail without the S01 fix.
- Coverage failure on `make test-integration` is expected for a single-file integration test run (17% vs required 46% — this is a full-suite threshold, not a per-file gate).