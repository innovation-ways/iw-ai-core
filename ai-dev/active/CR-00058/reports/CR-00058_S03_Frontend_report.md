# CR-00058 S03 Frontend Report

## What Was Done

Implemented the dashboard-facing portion of CR-00058 (Configurable per-project scope-overlap gate with block/allow policy), specifically **AC6: Dashboard surfaces both held-reason and allowed-by-policy pills**.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/batches.py` | Replaced `held_reason: str \| None` field on `BatchItemRow` with `scope_status: ScopeStatus \| None`. Replaced `_get_held_reasons()` with `_get_scope_statuses()` that queries both event types in a single combined SQL query. Added `ScopeStatus` dataclass with `status`, `message`, `matched_globs`, `matched_allow_patterns`, `blocking_item_ids` fields and `pill_text` / `pill_tooltip` properties. Preserved backwards-compatible `_get_held_reasons()` wrapper for existing call sites. |
| `dashboard/templates/fragments/batch_items_rows.html` | Extended conditional rendering: `scope_status.status == "held"` renders the existing warning-tone held pill; `scope_status.status == "policy_allowed"` renders a new info-tone (blue) pill with SVG checkmark icon, truncated pattern list, and full tooltip via `title` attribute. |
| `tests/dashboard/test_batches_router.py` | New test file with 12 tests covering the full CR-00058 contract: policy_allowed record shape, held record shape, held precedence when both events exist, old event outside window, multiple items each get correct status, combined query single round-trip via SQLAlchemy event listener, `_batch_item_rows` integration, and HTTP smoke tests for both pill types. |
| `tests/dashboard/test_batch_held_indicator.py` | Updated to use `_get_scope_statuses` and the new `scope_status` field on `BatchItemRow` instead of `held_reason` string field. All 8 tests pass. |

## Key Design Decisions

1. **Combined query** (`event_type IN ("item_held_for_scope", "item_overlap_allowed_by_policy")`) — both event types fetched in a single SQL round-trip. SQLAlchemy event listener test confirms exactly 1 SELECT query.

2. **Held precedence**: events are scanned in reverse chronological order; when a `held` event is encountered for an item that already has a `policy_allowed` status, it replaces it. This ensures that if both event types exist within the window, only the held badge is shown.

3. **`ScopeStatus` dataclass** replaces the previous `held_reason: str | None` field. The `pill_text` property generates the short label (e.g., `"policy allowed (tests/**, docs/**)"`) and `pill_tooltip` generates the full title attribute string listing all patterns and blocking items.

4. **Backwards compatibility**: the HTTP routes continue to use `_get_held_reasons()` (which internally calls `_get_scope_statuses` and filters to held-only records), so no changes to page templates or route handlers were needed beyond updating the context key name from `held_reason` to `scope_status`.

5. **No new CSS needed**: the template uses `text-primary` (existing Tailwind utility) for the info-tone policy_allowed pill. The warning-tone held pill uses `text-warning` (existing).

## Test Results

**New tests (CR-00058)**: 12 passed in `tests/dashboard/test_batches_router.py`
**Regression tests**: 8 passed in `tests/dashboard/test_batch_held_indicator.py`
**Total**: 20 tests passed, 0 failed

## Preflight Results

- `make format`: ok (1 file reformatted — `batch_items_rows.html`)
- `make typecheck`: ok (mypy — no issues found in 3 source files)
- `make lint`: ok (ruff — no issues; `scripts/check_templates.py` passed)

## TDD RED Evidence

`tests/dashboard/test_batches_router.py::TestGetScopeStatuses::test_policy_allowed_event_returns_policy_allowed_status — AssertionError: 'none' != 'policy_allowed'` — the new test initially failed because `_get_scope_statuses` didn't exist yet; after implementing the function all 12 tests passed green.

## Blockers

None.