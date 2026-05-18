# I-00092_S01_Frontend_report

## Work Item
I-00092 — Auto-merge filter chip never highlights the active filter

## Step
S01 — Frontend implementation

## What Was Done

Fixed the filter chip active-state comparison in `dashboard/templates/fragments/auto_merge_events_table.html` and added accessibility attributes to each chip link.

### Problem
The old template compared `type_filter == key` (e.g. `"merge_auto_resolved" == "resolved"`) which was permanently `False` for all chips, so no chip ever highlighted as active.

### Fix Applied
**File:** `dashboard/templates/fragments/auto_merge_events_table.html`

1. **Replaced the active-class branch** with correct logic:
   - `all` chip (`mapped is None`) is active when there is no `type` query param
   - Every other chip is active when `type_filter == mapped` (the actual `event_type` string from the URL)

2. **Added accessibility attributes** to each `<a>` chip:
   - `title="{{ mapped or 'all event types' }}"` — tooltip naming the underlying event_type
   - `aria-pressed="{{ 'true' if _is_active else 'false' }}"` — announces pressed state to screen readers

### Chips Fixed
| Chip label | `mapped` value | Active when `type` param equals |
|---|---|---|
| `all` | `None` | no `type` param present |
| `resolved` | `merge_auto_resolved` | `type=merge_auto_resolved` |
| `attempted` | `merge_auto_resolution_attempted` | `type=merge_auto_resolution_attempted` |
| `failed` | `merge_auto_resolution_failed` | `type=merge_auto_resolution_failed` |
| `skipped` | `merge_auto_resolution_skipped` | `type=merge_auto_resolution_skipped` |
| `health_probe` | `auto_merge_health_probe` | `type=auto_merge_health_probe` |
| `config_updated` | `auto_merge_config_updated` | `type=auto_merge_config_updated` |

## Files Changed
- `dashboard/templates/fragments/auto_merge_events_table.html`

## Test Results
```
tests/dashboard/test_auto_merge_routes.py -v
25 passed in 35.18s
```

All 25 tests passed. Coverage warning (20% < 50% required) is pre-existing and unrelated to this change.

## Pre-flight Checks
- **format**: `uv run ruff format --check .` → 750 files already formatted ✓
- **typecheck**: `uv run mypy orch/ dashboard/` → Success: no issues found ✓
- **lint**: `uv run ruff check .` + `scripts/check_templates.py` → All checks passed ✓

## TDD Note
Template-only edit; behavioural tests for active-chip highlighting live in S03.

## Blockers
None.