# I-00096 S03 Backend Report

## What Was Done

Fixed the auto-merge events view to filter out non-auto-merge events (like `step_launched`) by default, while introducing an opt-in parameter to show all events.

### Changes

**`orch/auto_merge_aggregator.py`**

1. Added `AUTO_MERGE_EVENT_PREFIXES` module-level constant near the top of the file:
   ```python
   AUTO_MERGE_EVENT_PREFIXES: tuple[str, ...] = ("auto_merge_", "merge_auto_")
   ```
   This is the explicit, auditable source of truth for auto-merge event prefixes.

2. Added `include_non_auto_merge: bool = False` keyword-only parameter to `list_recent_events`.

3. Applied the prefix filter when `event_type_filter is None` AND `include_non_auto_merge is False`:
   ```python
   elif not include_non_auto_merge:
       stmt = stmt.where(
           or_(
               *(DaemonEvent.event_type.like(p + "%") for p in AUTO_MERGE_EVENT_PREFIXES)
           )
       )
   ```
   Uses `or_(*list)` pattern per project conventions.

**`tests/unit/test_auto_merge_aggregator.py`**

Added three new unit tests:
- `test_list_recent_events_default_excludes_non_auto_merge` — verifies the default view hides `step_launched` and shows `auto_merge_health_probe`
- `test_list_recent_events_include_non_auto_merge_shows_everything` — verifies `include_non_auto_merge=True` disables the prefix filter
- `test_list_recent_events_event_type_filter_takes_precedence` — verifies explicit `event_type_filter` overrides prefix default

### TDD RED Evidence

Initial RED run (pre-implementation):
```
tests/unit/test_auto_merge_aggregator.py::test_list_recent_events_default_excludes_non_auto_merge FAILED
AssertionError: assert 'step_launched' not in {'auto_merge_health_probe', 'step_launched'}
```
The mock returned both `step_launched` and `auto_merge_health_probe` events, proving the old implementation had no prefix filtering.

### Behaviour

- Default call: `list_recent_events(db, project_id)` — only auto-merge events (`auto_merge_*`, `merge_auto_*`)
- With `include_non_auto_merge=True` — all events returned (for "Show all" toggle)
- With `event_type_filter="..."` — explicit type wins, prefix filter not applied

## Test Results

```
tests/unit/test_auto_merge_aggregator.py: 22 passed, 0 failed
```

All pre-flight checks pass:
- `make format` — 760 files already formatted
- `make typecheck` — no issues
- `make lint` — all checks passed

## Notes

- I-00095 sort/direction parameters were **not** added (I-00095 not landed at S03 time)
- `get_event_detail`, `get_status_snapshot` and other functions were **not** modified (out of scope)
- The unit tests use MagicMock correctly — mock `db.execute.return_value.all` reflects the SQL-level filtering effect, not a literal row-by-row Python filter