---
name: iw-batch-execute
version: "3.0.0"
description: >
  Create and approve a batch for parallel execution of multiple work items.
  Analyzes dependencies, generates execution plan with diagram, requires
  explicit user approval. Use when running multiple work items, batch
  processing, or user says "batch execute", "run all", "execute batch",
  "/iw-batch-execute".
allowed-tools: Read, Grep, Glob, Bash
argument-hint: "<item IDs or 'all'> [--max=N]"
---

# Batch Execute Work Items

Create a batch for parallel execution of work items with full dependency
analysis, execution plan, and visual diagram.

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

## Phase 2: Create Batch (generates plan + diagram)

Create the batch — this automatically generates the execution plan with
dependency analysis, draw.io diagram, and PNG visualization:

```bash
iw batch-create {ITEM_ID_1} {ITEM_ID_2} ... [--max-parallel N]
```

This outputs the batch ID (e.g., `BATCH-00001`) and shows execution groups.

## Phase 3: Show Execution Plan and Diagram

After batch creation, show the generated execution plan to the user.
The plan is stored in the database and visible at the batch detail page.

Get the full batch status:
```bash
iw batch-status {BATCH_ID}
```

Present to the user:

```markdown
### Batch Execution Plan: {BATCH_ID}

**Items**: {count} work items
**Groups**: {N} execution group(s)
**Max parallel**: {N}

| Group | Items | Depends On |
|-------|-------|-----------|
| 0 | I070, I071 | — |
| 1 | I072 | I070 |

**Dependency Analysis**:
- File overlap detection: {results}
- DB migration sequencing: {results}
- Circular dependency check: {results}

**Execution diagram**: View at dashboard →
http://localhost:9900/project/{PROJECT}/batch/{BATCH_ID}?tab=plan

---

**IMPORTANT: This batch requires your approval before execution begins.**
Approve? (The daemon will create worktrees and launch agents)
```

**STOP HERE and wait for the user to explicitly confirm.**
Do NOT proceed to Phase 4 until the user says yes/approve/go/proceed.

## Phase 4: Approve Batch

ONLY after user confirms, approve the batch for daemon pickup:

```bash
iw batch-approve {BATCH_ID}
```

## Phase 5: Report

Show the final batch status:

```bash
iw batch-status {BATCH_ID}
```

Report to the user:

```markdown
### Batch Approved

**Batch ID**: {BATCH_ID}
**Items**: {count} work items
**Status**: approved (daemon will pick up within 60 seconds)

**Monitor**:
- Dashboard: http://localhost:9900/project/{PROJECT}/batch/{BATCH_ID}
- CLI: `iw batch-status {BATCH_ID}`

**Controls**:
- Pause: `iw batch-pause {BATCH_ID}`
- Resume: `iw batch-resume {BATCH_ID}`
```

---

## Constraints

- **MUST** verify items are `approved` before creating batch
- **MUST** show the execution plan with dependency analysis
- **MUST** reference the diagram at the dashboard plan tab
- **MUST** wait for EXPLICIT user confirmation before approving the batch
- **NEVER** call `iw batch-approve` without user saying yes
- **NEVER** include items that are not in `approved` status
