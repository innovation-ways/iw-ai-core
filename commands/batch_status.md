---
description: Show the current status of a batch execution including progress of each item.
---

# Batch Status

Show the status of a batch execution.

## Usage

Provide the batch ID to check.

## Workflow

1. **Get batch status**:
   ```bash
   iw batch-status {BATCH_ID}
   ```

2. **Present results** showing:
   - Overall batch status (pending, running, completed, failed)
   - Per-item status and current step
   - Any failures or blockers
   - Completion percentage
