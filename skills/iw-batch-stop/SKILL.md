---
name: iw-batch-stop
version: "2.0.0"
description: >
  Gracefully pause a running batch execution. In-progress items finish but
  no new items launch. Use when stopping a batch, or user says "batch stop",
  "stop batch", "/iw-batch-stop".
allowed-tools: Bash
argument-hint: "BATCH-NNN"
---

# Batch Stop

Gracefully pause batch **$ARGUMENTS**.

## Steps

1. Verify the batch exists and show current status:
   ```bash
   iw batch-status $ARGUMENTS
   ```

2. Pause the batch (in-progress steps finish, no new ones start):
   ```bash
   iw batch-pause $ARGUMENTS
   ```

3. Report:
   - Items currently executing will finish
   - No new items will be launched
   - To resume later: `iw batch-resume $ARGUMENTS`
   - To kill immediately: use dashboard Kill actions on running steps

## If you need to resume:

```bash
iw batch-resume $ARGUMENTS
```

## If you need to kill a specific running step:

Use the dashboard at http://localhost:9900 → Running Tasks → Kill button.
