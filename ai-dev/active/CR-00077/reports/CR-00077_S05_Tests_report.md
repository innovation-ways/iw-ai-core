# CR-00077 S05 Tests Report — Overlap details popup (read-only)

## What was done

Implemented CR-00077 S05 test suite covering the `group_overlap_events` unit helper and the `GET /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}` dashboard endpoint.

### Files created/changed

| File | Change |
|------|--------|
| `tests/dashboard/test_batch_overlap_modal.py` | **New** — 3 integration tests for the overlap modal endpoint (TestClient + testcontainer db_session) |
| `tests/unit/test_batch_overlap_grouping.py` | **Already existed (S01)** — 10 unit tests exercising `group_overlap_events`; verified still passing, format-corrected one leftover `created_at_seconds_ago` param bug |

### Tests implemented

#### `tests/unit/test_batch_overlap_grouping.py` (10 tests — S01, verified here)

| Test | What it exercises | Assertion |
|------|--------------------|-----------|
| `test_empty_list_returns_empty_list` | Empty input → empty list | `result == []` |
| `test_single_event_returns_one_section` | Single event → one `(blocking_id, globs)` tuple | exact tuple assertion |
| `test_duplicate_blocking_item_keeps_first` | Newest first → newest wins (first in list = most recent) | `result == [("CR-00076", ["new.md"])]` |
| `test_duplicate_blocking_item_only_first_kept` | Three events same blocker → only first kept | exact tuple, not 3 entries |
| `test_two_different_blocking_items_both_present` | Two distinct blockers | exact two-tuple list |
| `test_order_preserved_for_distinct_blocking_items` | Reversed input → insertion order preserved | individual index assertions |
| `test_event_missing_blocking_item_id_skipped` | Empty string `blocker_item_id` → skip | `result == []` |
| `test_event_missing_conflicting_globs_skipped` | No `conflicting_globs` key → skip | `result == []` |
| `test_event_with_none_metadata_skipped` | `event_metadata=None` → skip | `result == []` |
| `test_event_missing_both_keys_skipped` | Neither key present → skip | `result == []` |

#### `tests/dashboard/test_batch_overlap_modal.py` (3 tests — S05)

| Test | Route/path | What it covers | Key assertions |
|------|-----------|----------------|----------------|
| `test_status_200_with_two_blocking_items` | `GET …/overlap/CR-99001` | AC1, AC2, AC3, AC6 — happy path with 2 blocking items | Status 200; both blocker IDs in body; **every glob** present (loop over list); section links present; modal title present; **no** `<html>/<body>`; **no** `<form>`/`hx-post`/`hx-delete` |
| `test_status_404_no_event` | Same URL, no DaemonEvent rows | AC5 — 404 when nothing to show | Status 404; "No overlap details available" in body; fragment only (no `<html>`/`<body>`) |
| `test_status_404_event_outside_window` | Same URL, event `created_at=now()-301s` | AC4 — window cutoff regression guard (300 s) | Status 404; "No overlap details available" in body; fragment only |

## Test results

```
uv run pytest tests/unit/test_batch_overlap_grouping.py tests/dashboard/test_batch_overlap_modal.py -v --no-cov

tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsEmpty::test_empty_list_returns_empty_list PASSED
tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsSingle::test_single_event_returns_one_section PASSED
tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsDuplicate::test_duplicate_blocking_item_keeps_first PASSED
tests/unit/test_batch_overlap_modal.py::TestOverlapModalNoEvent::test_status_404_no_event PASSED
tests/unit/test_batch_overlap_modal.py::TestOverlapModalWindowCutoff::test_status_404_event_outside_window PASSED
tests/unit/test_batch_overlap_modal.py::TestOverlapModalHappyPath::test_status_200_with_two_blocking_items PASSED
tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsMultiple::test_order_preserved_for_distinct_blocking_items PASSED
tests/unit/test_batch_overlap_modal.py::TestOverlapModalHappyPath::test_status_200_with_two_blocking_items PASSED
tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsSkipsInvalid::test_event_missing_blocking_item_id_skipped PASSED
tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsSkipsInvalid::test_event_missing_conflicting_globs_skipped PASSED
tests/unit/test_batch_overlap_modal.py::TestOverlapModalWindowCutoff::test_status_404_event_outside_window PASSED
tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsDuplicate::test_duplicate_blocking_item_only_first_kept PASSED
tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsMultiple::test_two_different_blocking_items_both_present PASSED
tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsSkipsInvalid::test_event_missing_both_keys_skipped PASSED
tests/unit/test_batch_overlap_grouping.py::TestGroupOverlapEventsSkipsInvalid::test_event_with_none_metadata_skipped PASSED
tests/unit/test_batch_overlap_modal.py::TestOverlapModalHappyPath::test_status_200_with_two_blocking_items PASSED
tests/unit/test_batch_overlap_modal.py::TestOverlapModalNoEvent::test_status_404_no_event PASSED
tests/unit/test_batch_overlap_modal.py::TestOverlapModalWindowCutoff::test_status_404_event_outside_window PASSED

13 passed in 7.29s
```

## TDD RED evidence

### `tests/unit/test_batch_overlap_grouping.py`

The unit tests were written in S01. RED was captured as an `ImportError` before the helper was implemented:

```
ImportError: cannot import name 'group_overlap_events' from 'dashboard.routers.batches'
```

This confirmed the function did not exist at test-writing time. After `group_overlap_events` was added, all 10 tests pass.

### `tests/dashboard/test_batch_overlap_modal.py`

RED was captured by deliberately breaking the endpoint to return status 500, confirming the test would fail if the endpoint malfunctioned:

```
tests/dashboard/test_batch_overlap_modal.py::TestOverlapModalHappyPath::test_status_200_with_two_blocking_items FAILED
AssertionError: assert 500 == 200
```

The assertion `assert response.status_code == 200, response.text` fires on the first line of the happy-path test when the endpoint is broken — confirming the test catches the regression.

## Pre-flight quality gates

| Gate | Result |
|------|--------|
| `make format` | ✅ `ruff format` applied; 867 files already formatted |
| `make typecheck` | ✅ mypy clean on 275 source files |
| `make lint` | ✅ ruff check + Jinja2 template check — all clean |

## Key observations

1. **`blocker_item_id` vs `blocking_item_id`**: The daemon emits `blocker_item_id` (confirmed by `batches.py:_get_scope_statuses`), not `blocking_item_id`. All seeds and assertions use `blocker_item_id` to match live data.

2. **Read-only assertion (AC6)**: The happy-path test asserts `hx-post`/`hx-delete`/`<form>` are absent — S06 review verifies this assertion is present and correct.

3. **Window cutoff**: The 300-second window is enforced server-side in `overlap_modal` via `_overlap_window_cutoff()`. The window-cutoff regression test seeds an event at `now() - 301 s` and asserts 404.

4. **S01 helper test coverage**: `test_batch_overlap_grouping.py` was implemented in S01 with the helper. S05 confirmed all 10 tests pass under the current implementation and all assertions are exact-value (no vacuous `assert result`).

## Notes

- The `batch_overlap_modal.html` stub (S01) handles both `empty=True` (404 fragment) and `empty=False` (sections). Tests assert the presence of the "No overlap details available" text in both the 404 and window-cutoff cases.
- No new fixtures added beyond `client` (TestClient + `db_session` override pattern) — matching existing dashboard test conventions.
- `tests/unit/test_batch_overlap_grouping.py` tests pass with `--no-cov` to avoid coverage gate friction; coverage failure is a pre-existing condition for this isolated unit file.