# CR-00078 — S10: Integration & E2E Tests Report

**Step:** S10 (tests implementation)
**Work item:** CR-00078
**Date:** 2026-05-23

---

## Scope

Extending and creating test files for **per-batch overlap ignore & force-start tests**.

**In scope:**
- `tests/unit/test_batch_overlap_ignore.py` — new file; model instantiation, repr, field access (no DB)
- `tests/unit/test_daemon_overlap_filter.py` — existing; TDD for `filter_blocked_by_ignores` pure helper
- `tests/integration/test_batch_overlap_ignore.py` — existing; DB-backed model tests (testcontainer)
- `tests/integration/test_batch_overlap_ignore_flow.py` — existing; full CR-00078 flow (AC3/AC4/AC5)
- `tests/dashboard/test_batch_overlap_ignore_endpoints.py` — existing; API endpoint tests (AC1–AC6)

**Out of scope:** any production code changes.

---

## Test File Inventory

| File | Layer | Tests | Status |
|------|-------|-------|--------|
| `tests/unit/test_batch_overlap_ignore.py` | unit | 7 model/POJO tests | ✅ GREEN |
| `tests/unit/test_daemon_overlap_filter.py` | unit | 7 filter helper tests | ✅ GREEN |
| `tests/integration/test_batch_overlap_ignore.py` | integration | 5 DB-backed model tests | ✅ GREEN |
| `tests/integration/test_batch_overlap_ignore_flow.py` | integration | 3 flow tests (AC3/AC4/AC5) | ✅ GREEN |
| `tests/dashboard/test_batch_overlap_ignore_endpoints.py` | dashboard | 6 API/event tests (AC1–AC6) | ✅ GREEN |
| **Total** | | **28 tests** | ✅ **All pass** |

---

## Test Coverage Mapping

### Unit layer

**`test_batch_overlap_ignore.py`** — 7 tests:
- `TestBatchOverlapIgnoreInstantiation` (6 tests): instantiation, field round-trip, nullable reason, empty-string ignored_by, all PK fields, all fields, __tablename__
- `TestBatchOverlapIgnoreRepr` (2 tests): repr includes class name, repr returns a string

**`test_daemon_overlap_filter.py`** — 7 tests:
- `TestFilterBlockedByIgnoresEmpty` (1): empty ignore set returns input unchanged
- `TestFilterBlockedByIgnoresFull` (1): all globs ignored → empty list
- `TestFilterBlockedByIgnoresPartial` (1): partial ignore drops only matching globs
- `TestFilterBlockedByIgnoresTupleDropped` (1): tuple removed when all its globs are ignored
- `TestFilterBlockedByIgnoresStringEquality` (2): exact string equality, no fnmatch

### Integration layer

**`test_batch_overlap_ignore.py`** — 5 tests:
- `TestBatchOverlapIgnoreModel.test_insert_and_read`: insert + full field round-trip via real PostgreSQL (includes server_default on ignored_at)
- `test_composite_pk_uniqueness`: duplicate composite PK raises `IntegrityError` (not bare Exception)
- `test_default_ignored_at`: omitted field → DB applies server_default, timestamp is ≤5 s old
- `test_reason_optional`: reason=None accepted
- `test_ignored_by_not_null`: empty string for ignored_by accepted

**`test_batch_overlap_ignore_flow.py`** — 3 tests:
- `TestAllIgnoredReleasesItem.test_all_ignored_releases_item`: pre-populate all BatchOverlapIgnore rows; verify `batch_overlap_allowed_by_ignore` event emitted (AC3)
- `TestPartialIgnoreKeepsHold.test_partial_ignore_keeps_hold`: ignore 1 of 3 globs; verify 2 remain blocked and no release event emitted (AC4)
- `TestPerBatchIsolation.test_per_batch_isolation`: seed BATCH-A + BATCH-B; pre-populate ignores only for BATCH-A; assert BATCH-B is still held (AC5)

### Dashboard layer

**`test_batch_overlap_ignore_endpoints.py`** — 6 tests:
- `TestIgnoreSingleEndpoint.test_post_ignore_inserts_row_and_emits_event`: POST /ignore → 1 BatchOverlapIgnore row + 1 `batch_overlap_ignored_by_operator` event with correct metadata (AC1)
- `test_post_ignore_idempotent`: POST twice → 1 row + 2 events (audit preserved) (AC2)
- `TestIgnoreAllEndpoint.test_post_ignore_all_inserts_n_rows`: 5 item_held_for_scope events → POST /ignore-all → 5 rows + 1 `batch_overlap_ignore_all_by_operator` event with count=5 (AC3)
- `test_post_ignore_all_idempotent`: pre-populate 3 of 5 ignores → POST /ignore-all → final count = 5 (no duplicates)
- `TestOverlapModalFiltersIgnored.test_get_modal_filters_ignored_files`: pre-ignore 2 of 5 globs → GET modal → those 2 absent from HTML, 3 non-ignored present
- `TestTimelineRendering.test_timeline_renders_new_event_types`: seed 3 new event types → GET batch logs → exact human-readable lines from CR-00078 §5 appear (AC6)

---

## Quality Checks

| Check | Command | Result |
|-------|---------|--------|
| All 28 tests | `uv run pytest tests/unit/test_daemon_overlap_filter.py … tests/dashboard/test_batch_overlap_ignore_endpoints.py -v --no-cov` | ✅ 28 passed |
| ruff lint | `uv run ruff check tests/…/test_batch_overlap_ignore*.py tests/…/test_daemon_overlap_filter.py` | ✅ All checks passed |
| ruff fix | auto-fixed 1 import-order issue in test_batch_overlap_ignore.py | ✅ |
| mypy | `uv run mypy tests/…/test_batch_overlap_ignore*.py tests/…/test_daemon_overlap_filter.py` | ✅ No issues found |

---

## Notes

- The 1 SAWarning in `test_composite_pk_uniqueness` (`New instance … conflicts with persistent instance`) is an expected SQLAlchemy warning from the test intentionally raising an `IntegrityError` via a duplicate composite PK — not a test failure.
- Unit model tests (`test_batch_overlap_ignore.py` unit layer) test the model as a plain Python object: `BatchOverlapIgnore(…)` instantiated directly, fields accessed, no DB session needed. This is intentional: if the model needs no DB interaction for a given test, the test stays in the unit layer.
- The `_seed_batch_and_items` helper in the integration model tests flushes the Batch + WorkItems before creating BatchItem, ensuring FK constraints are satisfied before BatchOverlapIgnore is inserted.
- All tests in the 28-test suite are fully isolated (independent seeds); random ordering (`pytest-randomly`) is safe.