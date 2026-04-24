# I-00037 S06 Code Review Report

## What was reviewed

S05 (Tests) implementation for `compute_batch_step_progress` parity between dashboard views.

## Files changed

- `tests/dashboard/conftest.py` — re-exports `db_session` from integration conftest
- `tests/dashboard/test_batches_progress_parity.py` — 16-test module (4 classes)

## Review Checklist Results

### 1. Reproduction test — PASS (CRITICAL)

`test_dashboard_home_and_batches_view_agree_on_progress` (line 133-191):
- Scenario: 1 item, 10 steps (3 completed, 7 pending), 1 `executing` batch item
- Pre-fix bug: `_active_batches()` used item-level formula → `progress_pct = 0` (0 completed items)
- Test asserts `dash.progress_pct == 30` AND `full.progress_pct == 30` AND parity
- Would fail against pre-fix code; correctly passes with fix

### 2. Semantic correctness — PASS (HIGH)

All `progress_pct` assertions pin specific integers. No shape-only assertions (`>= 0`, `<= 100`, `isinstance`). HTTP smoke tests assert `"30%"` substring, which is semantically correct for the 3/10 seeded scenario.

### 3. Regression matrix coverage — PASS (HIGH)

All 11 scenarios covered:
- `empty batch_ids → {}`
- `3/10 → 30`
- `all done → 100`
- `0 steps → 0` (no crash)
- `skipped counts → 40` (2 completed + 2 skipped)
- `failed does NOT count → 30` (3 completed + 2 failed)
- `needs_fix does NOT count → 30`
- `in_progress does NOT count → 30`
- `multi-batch bulk → {A:10, B:50, C:0, D:100}`
- `missing batch_id → 0` (no KeyError)
- `project_id scoping` — same work_item_id in two projects returns 30/80 respectively

### 4. Parity test — PASS

`test_active_batches_and_all_batches_match_on_partial` explicitly calls both routers on same seeded state and asserts `dash.progress_pct == full.progress_pct`.

### 5. Items-count preservation — PASS

`test_active_batches_total_items_is_item_count_not_step_count` asserts `total_items == 1` when 1 item and 10 steps exist, confirming items column stays item-level.

### 6. Test isolation — PASS

- Uses testcontainer-backed `db_session` from integration conftest
- No live DB hits (port 5433)
- No DB mocking
- FTS DDL runs via integration conftest after `create_all()`
- All tests deterministic

### 7. HTTP smoke tests — PASS

Both `test_project_dashboard_html_contains_30_percent` and `test_batches_list_html_contains_30_percent` assert "30%" substring in rendered HTML.

## Test Results

```
tests/dashboard/test_batches_progress_parity.py: 16 passed
make test-unit: 1395 passed, 19 warnings
make lint: ruff error in executor/scope_gate.py:75 (pre-existing, not S05)
make typecheck: Success — no issues in 150 source files
```

## Verdict

**pass**

No CRITICAL or HIGH findings. All assertions are semantically correct with pinned values. Regression matrix fully covered. Parity lock present. Test isolation proper.
