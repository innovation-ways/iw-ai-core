# CR-00078_S10_Tests_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S10
**Agent**: tests-impl

---

## ⛔ Docker is off-limits
(Testcontainers in pytest fixtures are exempt.)

## ⛔ Migrations: agents generate, daemon applies
No migration files in this step.

## Input Files

- `ai-dev/active/CR-00078/CR-00078_CR_Design.md` (every AC + TDD Approach)
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`
- `tests/conftest.py` for `db_session` testcontainer fixture
- All prior step reports for context

## Output Files

- `tests/unit/test_daemon_overlap_filter.py` — extend the single RED case S04 added to cover the full matrix
- `tests/unit/test_batch_overlap_ignore.py` — new
- `tests/integration/test_batch_overlap_ignore_flow.py` — new
- `tests/dashboard/test_batch_overlap_ignore_endpoints.py` — new
- Possibly `tests/dashboard/test_batch_overlap_modal.py` — extend the CR-00077 happy-path test with one assertion that ignored files are filtered out (additive change; do NOT delete existing tests)
- `ai-dev/active/CR-00078/reports/CR-00078_S10_Tests_report.md`

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed —
but the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "ignored_pairs" in event.event_metadata` (shape only)
- GOOD: `assert event.event_metadata["count"] == 5` (semantic — exact expected value)
- GOOD: `assert event.event_type == "batch_overlap_allowed_by_ignore"` (exact string, not a substring or truthiness)

For this work item the "shape" traps are: asserting a `BatchOverlapIgnore` row merely *exists*
instead of asserting its exact composite-PK values; asserting *some* `DaemonEvent` was emitted
instead of the exact `event_type` string and `event_metadata` payload; asserting the daemon
filter returned *a* list instead of the exact surviving `(blocking_item_id, [globs])` tuples in
original order. A test that still passes against an under-filtered, mis-scoped, or
non-idempotent implementation is worthless — assert the concrete values.

## Requirements

### 1. `tests/unit/test_daemon_overlap_filter.py` — extend with full matrix

Existing case from S04: `test_empty_ignores_returns_input`. Add:

- `test_full_ignore_returns_empty` — all globs of all blocking items are ignored → result is `[]`.
- `test_partial_ignore_drops_only_matching_globs` — input has 3 globs against one blocking item; ignore 1; result has the same blocking_id with 2 globs (in original order).
- `test_tuple_dropped_when_globs_empty` — input has 1 glob against blocking item A and 2 against B; ignore the only A-glob → result has only B with its 2 globs (the A-tuple is dropped, not retained empty).
- `test_string_equality_not_fnmatch` — ignore `"dir/x.py"` does NOT match `"dir/*.py"` in the input. The filter is string-equal only.

All assertions must compare exact tuples / lists — no `assert result` or `assert len(...)`.

### 2. `tests/unit/test_batch_overlap_ignore.py`

Model-level tests against an in-memory SQLite via the test `db_session` fixture (or testcontainer if SQLite incompatibility on `DateTime(timezone=True)`):

- `test_insert_and_read` — insert one row, read it back, assert every field round-trips.
- `test_composite_pk_uniqueness` — two inserts with identical PK columns raise `IntegrityError`. Use `pytest.raises(IntegrityError)` (exact class, not bare `Exception`).
- `test_default_ignored_at` — insert with `ignored_at=None` (omitted) → DB populates with `now()`. Assert the resulting timestamp is within the last few seconds.

### 3. `tests/integration/test_batch_overlap_ignore_flow.py`

Use the `db_session` testcontainer fixture from `tests/conftest.py`. Seed in each test: a `Project`, two `WorkItem`s (held + blocking), a `Batch`, a `BatchItem` for the held item, plus `DaemonEvent` rows.

Test cases — assertions are exact:

- `test_no_ignores_held_path` — no ignore rows; invoke the daemon's overlap-resolve path (either via `BatchManager._launch_pending_items` directly OR by calling the pure helper + simulating the surrounding emission); assert exactly one `item_held_for_scope` event row exists for the held item AND zero `batch_overlap_allowed_by_ignore` rows.
- `test_all_ignored_releases_item` (AC3) — pre-populate `BatchOverlapIgnore` with every `(blocking_item_id, file_pattern)` pair from the seeded events; invoke the resolve path; assert one `batch_overlap_allowed_by_ignore` event exists with `event_metadata["candidate_item_id"] == held_item_id`. Then assert the held item's `BatchItem.status` transitioned (or that the launch helper was called — choose whichever is testable without spinning up a real worktree).
- `test_partial_ignore_keeps_hold` (AC4) — ignore only 1 of 3 file globs; assert the held item is still held; assert no `batch_overlap_allowed_by_ignore` event.
- `test_per_batch_isolation` (AC5) — seed TWO batches BATCH-A and BATCH-B, both with the same held item id and the same conflicts; pre-populate ignore rows only for BATCH-A; invoke the resolve path for BATCH-B; assert BATCH-B's held item is still held (the BATCH-A ignore rows have no effect).

### 4. `tests/dashboard/test_batch_overlap_ignore_endpoints.py`

Use TestClient + `db_session` testcontainer.

- `test_post_ignore_inserts_row_and_emits_event` (AC1) — POST `/ignore` with body fields; assert response status 200; assert exactly 1 `BatchOverlapIgnore` row exists with the expected PK; assert exactly 1 `DaemonEvent` with `event_type == "batch_overlap_ignored_by_operator"` whose `event_metadata["file_pattern"]` matches.
- `test_post_ignore_idempotent` (AC2) — POST the same `/ignore` twice; assert exactly 1 row in `BatchOverlapIgnore` (no duplicates); assert exactly 2 `DaemonEvent` rows with the ignored event type (audit preserved on the second call).
- `test_post_ignore_all_inserts_n_rows` (AC3) — seed 5 `item_held_for_scope` events with distinct `(blocking_id, file)` pairs; POST `/ignore-all`; assert exactly 5 `BatchOverlapIgnore` rows exist; assert exactly 1 `DaemonEvent` with `event_type == "batch_overlap_ignore_all_by_operator"` and `event_metadata["count"] == 5`.
- `test_post_ignore_all_idempotent` — pre-populate 3 of 5 pairs; POST `/ignore-all`; assert final row count is 5 (2 new + 3 pre-existing, no duplicates).
- `test_get_modal_filters_ignored_files` — seed events + pre-ignore 2 of the file globs; GET the modal endpoint; assert the response body does NOT contain those 2 globs but DOES contain the remaining ones.
- `test_timeline_renders_new_event_types` (AC6) — seed exactly one `DaemonEvent` of each of the 3 new event types (`batch_overlap_ignored_by_operator`, `batch_overlap_ignore_all_by_operator`, `batch_overlap_allowed_by_ignore`) with realistic `event_metadata`; GET the batch Timeline tab (`?tab=timeline`); assert the exact human-readable line from CR-00078 §5 appears in the response for each. This is the only automated coverage of the Timeline render branches — assert exact line substrings (e.g. `"Operator ignored all 5 remaining overlaps for CR-00072"`), not just status 200.

For the event-emission assertions in the other tests, query `DaemonEvent` directly via the test session — do NOT rely on Timeline rendering. (`test_timeline_renders_new_event_types` is the deliberate exception: it specifically exercises the render path.)

### 5. TDD RED evidence

Capture `tdd_red_evidence` for at least one test per module (4 evidences total). This step runs
*after* the implementation steps (S01–S09), so the authoritative pre-implementation RED was
already captured upstream — **cite it**: the helper's `ImportError` RED from the S04 report, and
the model / endpoint RED from the S01 and S06 reports. For a brand-new test whose target already
exists, run the test once as written; if it passes, record the upstream RED reference plus a note
that the assertion is GREEN against the shipped implementation.

**Do NOT** `git checkout`, `git stash`, edit, or otherwise revert/break already-shipped source
files to manufacture a RED. Runtime source mutation causes thrash and is not a valid RED — the
genuine RED for this work item was the upstream steps' pre-implementation failures.

### 6. Targeted runs only

```bash
uv run pytest tests/unit/test_daemon_overlap_filter.py tests/unit/test_batch_overlap_ignore.py -v
uv run pytest tests/integration/test_batch_overlap_ignore_flow.py -v
uv run pytest tests/dashboard/test_batch_overlap_ignore_endpoints.py -v
```

Do NOT run `make test-unit` or `make test-integration`.

## Project Conventions

- Testcontainer fixture from `tests/conftest.py`. NEVER port 5433.
- For event-emission assertions, query `DaemonEvent` rows directly with a SQLAlchemy `select` — exact `event_type` string match.
- For idempotency assertions, count `BatchOverlapIgnore` rows with the composite PK filter.

## Subagent Result Contract

```json
{
  "step": "S10",
  "agent": "tests-impl",
  "work_item": "CR-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_daemon_overlap_filter.py",
    "tests/unit/test_batch_overlap_ignore.py",
    "tests/integration/test_batch_overlap_ignore_flow.py",
    "tests/dashboard/test_batch_overlap_ignore_endpoints.py",
    "tests/dashboard/test_batch_overlap_modal.py (additive only)"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "<X> passed across 4 test files",
  "tdd_red_evidence": "tests/integration/test_batch_overlap_ignore_flow.py::test_all_ignored_releases_item — AssertionError: no DaemonEvent with event_type='batch_overlap_allowed_by_ignore' (captured RED before S04 daemon hook landed)",
  "blockers": [],
  "notes": ""
}
```
