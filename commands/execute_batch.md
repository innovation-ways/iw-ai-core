---
description: Create and approve a batch for parallel execution of multiple work items.
---

# Execute Batch

Create a batch for parallel execution of multiple work items.

## Usage

Provide the work item IDs to include in the batch.

## Workflow

1. **Validate items** — check each item's status via `iw item-status`:
   ```bash
   iw item-status {ID}
   ```
   All items must be in an approved state.

2. **Create the batch**:
   ```bash
   iw batch-create --items {ID1} {ID2} {ID3} ...
   ```

3. **Approve the batch** to start execution:
   ```bash
   iw batch-approve {BATCH_ID}
   ```

4. **Report** the batch ID and status to the user.

The daemon will pick up the approved batch and execute items in parallel.
