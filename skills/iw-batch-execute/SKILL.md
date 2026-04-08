---
name: iw-batch-execute
version: "2.0.0"
description: >
  Create and approve a batch for parallel execution of multiple work items.
  Analyzes dependencies, builds execution groups, creates batch in platform.
  Use when running multiple work items, batch processing, or user says
  "batch execute", "run all", "execute batch", "/iw-batch-execute".
allowed-tools: Read, Grep, Glob, Bash
argument-hint: "<item IDs or 'all'> [--max=N]"
---

# Batch Execute Work Items

Create a batch for parallel execution of work items.

**Input**: $ARGUMENTS

## Parse Input

Parse the arguments to determine:

1. **Work items**: Either a space-separated list of IDs (e.g., `I070 I071 I072`) or the keyword `all`
2. **Max parallel**: If `--max=N` is present, use N. Otherwise use project default (4).

Examples:
- `/iw-batch-execute I070 I071 I072` → items=[I070, I071, I072]
- `/iw-batch-execute all --max=4` → all approved items, max=4

## Phase 1: Discover Work Items

**If specific IDs provided**: Verify each item is registered and approved:
```bash
iw item-status {ID} --json
```

Include only items with status `approved`.

**If `all`**: Get all approved items from the platform:
```bash
iw projects list --json
```
Then check each item. Include only `approved` items.

## Phase 2: Dependency Analysis

For each item, check its `depends_on` field from `iw item-status {ID} --json`.

Build execution groups where items with no dependencies (or all dependencies met) are in Group 1, and so on.

Show the dependency graph:
```
Group 1 (parallel): I070, I071
Group 2 (after Group 1): I072
```

## Phase 3: Present Plan for Confirmation

Show the execution plan to the user:

```markdown
### Batch Execution Plan

**Items**: {list}
**Groups**: {N} execution group(s)
**Max parallel**: {N}

| Group | Items | Depends On |
|-------|-------|-----------|
| 1 | I070, I071 | — |
| 2 | I072 | I070 |

Proceed? (The daemon will create worktrees and launch agents)
```

Wait for user confirmation before creating the batch.

## Phase 4: Create and Approve Batch

After user confirms, create the batch:

```bash
iw batch-create {ITEM_ID_1} {ITEM_ID_2} ...
```

This outputs the batch ID (e.g., `BATCH-001`). Then approve it for daemon pickup:

```bash
iw batch-approve {BATCH_ID}
```

## Phase 5: Report

Show the batch status:

```bash
iw batch-status {BATCH_ID}
```

Report to the user:

```markdown
### Batch Created and Approved

**Batch ID**: {BATCH_ID}
**Items**: {count} work items
**Status**: approved (daemon will pick up within 60 seconds)

**Monitor**:
- Dashboard: http://localhost:9900 → Running Tasks
- CLI: `iw batch-status {BATCH_ID}`

**Stop batch if needed**:
- `iw batch-pause {BATCH_ID}` — pause (in-progress steps finish, no new launches)
- `iw batch-resume {BATCH_ID}` — resume a paused batch
```

---

## Constraints

- **MUST** verify items are `approved` before creating batch
- **MUST** show dependency analysis and execution groups
- **MUST** wait for user confirmation before creating the batch
- **NEVER** include items that are not in `approved` status
