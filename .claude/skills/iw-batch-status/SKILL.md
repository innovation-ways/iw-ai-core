---
name: iw-batch-status
version: "2.0.0"
description: >
  Show the current status of a batch execution. Uses iw CLI to query the platform.
  Use when checking batch progress, or user says "batch status", "check batch", "/iw-batch-status".
allowed-tools: Bash
argument-hint: "[BATCH-NNN]"
---

# Batch Status

Show the current status of batch **$ARGUMENTS**.

## If BATCH ID provided:

```bash
iw batch-status $ARGUMENTS
```

This shows:
- Batch status (planning / approved / executing / completed / paused / failed)
- Items in the batch and their individual statuses
- Currently running steps with live duration
- Any failed steps with error details

## If no BATCH ID:

List all recent batches for the current project:

```bash
iw batch-status
```

Or check the dashboard for a visual overview: http://localhost:9900
