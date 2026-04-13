# F-00020: Add Research Work Item Type to iw-ai-core

**Type**: Feature
**Phase**: IW AI Core — Research System Foundation
**Priority**: High
**Created**: 2026-04-13
**Status**: Draft
**Repository**: `iw-ai-core` (``)

---

## Description

Adds `Research` as a first-class work item type to iw-ai-core. This involves adding
`WorkItemType.Research` and `DocType.research` to the Python enums and PostgreSQL database
types, extending the `iw` CLI (`next-id`, `register`, `doc-update`) to accept `research`
as a valid type, and providing two Alembic `ALTER TYPE` migrations — one per PostgreSQL enum.
This is the foundational layer that the `iw-research` skill and the dashboard research panel
(F-00021) both depend on.

## Architecture References

| Document | Section | Relevance |
|----------|---------|-----------|
| `orch/db/models.py:48` | `WorkItemType` enum | Add `Research = "Research"` |
| `orch/db/models.py:150` | `DocType` enum | Add `research = "research"` |
| `orch/cli/utils.py` | `TYPE_TO_PREFIX`, `TYPE_TO_ID_PREFIX` | Add `"research": "R"` and `"research": "R-"` |
| `orch/cli/id_commands.py:90` | `next-id` click.Choice | Add `"research"` |
| `orch/cli/item_commands.py:100` | `register` command | Add `research → WorkItemType.Research` |
| `orch/db/migrations/versions/` | Migration head: `add_doc_types_functional` | Two new ALTER TYPE migrations chain from this head |

## Scope

### In Scope

- `WorkItemType.Research = "Research"` added to the Python enum
- `DocType.research = "research"` added to the Python enum
- `TYPE_TO_PREFIX["research"] = "R"` and `TYPE_TO_ID_PREFIX["research"] = "R-"` in `utils.py`
- `iw next-id --type research` produces IDs in `R-NNNNN` format
- `iw register <ID> <title> --type research` stores items with `WorkItemType.Research`
- `iw doc-update <ID> --doc-type research` stores docs with `DocType.research`
- Alembic migration: `ALTER TYPE work_item_type ADD VALUE IF NOT EXISTS 'Research'`
- Alembic migration: `ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'research'`
- Integration tests covering all new CLI paths

### Out of Scope

- Dashboard research panel (F-00021)
- `iw-research` skill implementation
- `iw-research-quick` skill implementation
- Backfilling existing `docs/research/` markdown files into the database
- Any frontend changes

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Database | Two Alembic migrations for `work_item_type` and `doc_type` enums | — |
| S02 | Backend | Enum models + CLI extensions (`utils.py`, `id_commands.py`, `item_commands.py`) | after S01 |
| S03 | CodeReview_Backend | Review S02 output | — |
| S04 | Tests | Integration tests for all new CLI paths | after S03 |
| S05 | CodeReview_Final | Global review of all work | — |
| S06 | QV: lint | `ruff check orch/ tests/` | — |
| S07 | QV: format | `ruff format --check orch/ tests/` | — |
| S08 | QV: typecheck | `mypy` on changed files | — |
| S09 | QV: unit-tests | `pytest tests/unit/` | — |
| S10 | QV: integration-tests | `pytest tests/integration/` | — |

### Database Changes

- **New tables**: None
- **Modified types**: `work_item_type` PostgreSQL enum (add `'Research'`), `doc_type` PostgreSQL enum (add `'research'`)
- **New indexes**: None
- **Migration notes**: PostgreSQL `ALTER TYPE … ADD VALUE` requires no table lock and is safe on live databases. Downgrade is a no-op (PostgreSQL does not support removing enum values).

### API Changes

- None

### Frontend Changes

- None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00020_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Orchestrator step definitions |
| `prompts/F-00020_S01_Database_prompt.md` | Prompt | Two Alembic migrations |
| `prompts/F-00020_S02_Backend_prompt.md` | Prompt | Enum + CLI extensions |
| `prompts/F-00020_S03_CodeReview_Backend_prompt.md` | Prompt | Review S02 |
| `prompts/F-00020_S04_Tests_prompt.md` | Prompt | Integration tests |
| `prompts/F-00020_S05_CodeReview_Final_prompt.md` | Prompt | Global review |
| `reports/F-00020_S01_Database_report.md` | Report | Created during execution |
| `reports/F-00020_S02_Backend_report.md` | Report | Created during execution |
| `reports/F-00020_S03_CodeReview_Backend_report.md` | Report | Created during execution |
| `reports/F-00020_S04_Tests_report.md` | Report | Created during execution |
| `reports/F-00020_S05_CodeReview_Final_report.md` | Report | Created during execution |

## Acceptance Criteria

### AC1: next-id research type

```
Given the iw-ai-core database has been migrated to include 'Research' in work_item_type
When I run `iw next-id --type research`
Then I receive a formatted ID in the form R-NNNNN (e.g. R-00001)
And subsequent calls increment the number atomically
```

### AC2: register research item

```
Given a valid research ID (e.g. R-00001)
When I run `iw register R-00001 "My Research Title" --type research`
Then a WorkItem row is stored in the database with type = WorkItemType.Research
And the item is retrievable via `iw item-status R-00001`
```

### AC3: doc-update with research doc type

```
Given a research item R-00001 is registered
When I run `iw doc-update R-00001 --doc-type research --title "My Research" --content-file report.md`
Then a ProjectDoc row is stored with doc_type = DocType.research
And the content is versioned (ProjectDocVersion created)
```

### AC4: ID prefix validation

```
Given a research ID R-00001 and a feature ID F-00001
When I run `iw register F-00001 "wrong" --type research`
Then the CLI exits with a non-zero exit code
And an error message indicates the ID prefix mismatch
```

### AC5: Atomic concurrency

```
Given two concurrent processes both call `iw next-id --type research`
When both calls complete
Then the two returned IDs are different and sequential (no duplicates, no gaps)
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| First-ever research ID | No prior R-prefix rows in id_sequences | `R-00001` allocated correctly |
| Concurrent allocation | 10 parallel `iw next-id --type research` calls | 10 unique sequential IDs |
| ID prefix mismatch | `iw register R-00001 ... --type feature` | CLI error, non-zero exit |
| Unknown type passed | `iw next-id --type unknown` | Click validation error before DB access |
| Doc-update without prior register | `iw doc-update R-00001 ...` with no work_items row | Error or upsert per existing doc-update behavior |
| JSON output flag | `iw --json next-id --type research` | JSON response includes `"prefix": "R"` |

## Invariants

1. The `work_item_type` and `doc_type` PostgreSQL enums include `'Research'`/`'research'` after migration
2. `TYPE_TO_PREFIX["research"] == "R"` and `TYPE_TO_ID_PREFIX["research"] == "R-"` are consistent with all ID validation logic
3. `iw next-id --type research` never returns a duplicate ID under concurrent execution
4. `_ITEM_TYPE_MAP["research"] == WorkItemType.Research` in `item_commands.py`
5. All existing types (`feature`, `incident`, `cr`, `batch`) continue to work identically after this change

## Dependencies

- **Depends on**: Nothing
- **Blocks**: F-00021 (dashboard research panel), `iw-research` skill, `iw-research-quick` skill

## TDD Approach

All tests are integration tests in `tests/integration/test_cli_core.py` (iw-ai-core):

- **test_next_id_research_type**: `iw next-id --type research` → ID starts with `R-`
- **test_next_id_all_types_includes_research**: Update existing `test_next_id_all_types` to include `"research": "R-"`
- **test_register_research_type**: `iw register R-00001 "title" --type research` → stored with `WorkItemType.Research`
- **test_doc_update_research_doc_type**: `iw doc-update` with `--doc-type research` → stored with `DocType.research`
- **test_next_id_research_json_output**: JSON flag → response includes `"prefix": "R"`
- **test_next_id_research_id_prefix_validation**: Registering an R- ID as feature type → error

## Notes

**Single-repository work**: This feature touches `iw-ai-core` only. The design doc, prompts, and reports all live in `ai-dev/active/F-00020/`.

**Migration naming convention**: Follow the existing pattern — descriptive name-based revision IDs (e.g., `add_research_work_item_type`), not UUIDs. The current head is `add_doc_types_functional`.

**No batch type in register**: The `iw register` command currently only supports `feature|incident|cr` (not `batch`). Research follows the same pattern — it gets added to `register` but not to `next-id`'s batch path.
