---
description: Gracefully stop (pause) a running batch execution.
---

# Stop Batch

Gracefully stop a running batch execution.

## Usage

Provide the batch ID to stop.

## Workflow

1. **Pause the batch**:
   ```bash
   iw batch-pause {BATCH_ID}
   ```

2. **Verify** the batch status changed:
   ```bash
   iw batch-status {BATCH_ID}
   ```

3. **Report** to the user:
   - Confirm batch is paused
   - Show which items completed before pause
   - Show which items were interrupted
   - Note that `iw batch-resume {BATCH_ID}` can restart execution
