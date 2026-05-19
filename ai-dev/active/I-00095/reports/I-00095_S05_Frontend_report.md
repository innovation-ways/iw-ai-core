## I-00095 S05 Frontend Report

### What was done

- Updated `dashboard/templates/fragments/auto_merge_events_table.html` table header to support sortable controls for:
  - `timestamp` (`created_at`)
  - `event_type`
  - `entity_id`
  - `verdict`
- Added active-sort UX behavior per requirement:
  - Active column detection via `sort`
  - `next_dir` toggle (`desc` default for inactive columns)
  - Chevron indicator (`↑`/`↓`) for active column only
  - `aria-sort` on active sortable header for accessibility
- Kept filter chips and show-all toggle section intact (I-00092-owned section untouched).
- Preserved filter/show-all interop in sort URLs by carrying `type` and `all` when present.
- Updated pagination (`Prev`/`Next`) URLs to preserve sort state with `&sort={{ sort }}&dir={{ direction }}`.
- Appended sortable button styles in `dashboard/static/styles.css`.

### Files changed

- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/static/styles.css`

### Pre-flight quality gates

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

### Test results

- Command requested by prompt:
  - `uv run pytest tests/dashboard/test_auto_merge_routes.py -v`
  - Result: all 51 tests passed, but process exited non-zero due repository-level coverage fail-under gate (20% < 50%).
- Targeted verification run (coverage disabled):
  - `uv run pytest tests/dashboard/test_auto_merge_routes.py -v --no-cov`
  - Result: **51 passed, 0 failed**.

### Issues / observations

- No functional blockers for this frontend scope.
- The only non-zero test exit was global coverage enforcement unrelated to this targeted template/CSS change.
