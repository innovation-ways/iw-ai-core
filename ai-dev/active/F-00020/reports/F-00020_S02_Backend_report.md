# F-00020 S02 Backend Report

## Summary

**Work Item**: F-00020 — Add Research Work Item Type to iw-ai-core
**Step**: S02
**Status**: Completed

## What Was Done

Extended the Python enums and CLI commands to support `research` as a first-class work item type, following the design document and S02 Backend prompt precisely.

### Changes Made

1. **`orch/db/models.py` — `WorkItemType` enum**
   - Added `Research = "Research"`

2. **`orch/db/models.py` — `DocType` enum**
   - Added `research = "research"`

3. **`orch/cli/utils.py` — `TYPE_TO_PREFIX`**
   - Added `"research": "R"`

4. **`orch/cli/utils.py` — `TYPE_TO_ID_PREFIX`**
   - Added `"research": "R-"`

5. **`orch/cli/id_commands.py` — `next-id` command**
   - Extended `click.Choice` from `["feature", "incident", "cr", "batch"]` to `["feature", "incident", "cr", "batch", "research"]`

6. **`orch/cli/item_commands.py` — `register` command**
   - Added `"research": WorkItemType.Research` to `_ITEM_TYPE_MAP`
   - Extended `click.Choice` from `["feature", "incident", "cr"]` to `["feature", "incident", "cr", "research"]`

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `WorkItemType.Research` and `DocType.research` |
| `orch/cli/utils.py` | Added `"research": "R"` and `"research": "R-"` to type maps |
| `orch/cli/id_commands.py` | Added `"research"` to `next-id` click.Choice |
| `orch/cli/item_commands.py` | Added `"research"` to `_ITEM_TYPE_MAP` and `register` click.Choice |

## Test Results

- **Smoke checks**: All passed (WorkItemType.Research, DocType.research, TYPE_TO_PREFIX, TYPE_TO_ID_PREFIX)
- **ruff check**: Passed (no issues)
- **mypy**: Success — no issues found in 4 source files
- **Unit suite**: 631 passed, 1 warning (pre-existing TestRunStatus warning)

## Notes

- `doc_commands.py` required no change — it already uses `[e.value for e in DocType]` dynamically, so adding `DocType.research` was sufficient
- All changes are additive with no modifications to existing behavior