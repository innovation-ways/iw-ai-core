# F-00039 S10 QvGate Report

## What was done

Ran the integration tests QV gate (S10) for the Section-Level Guide feature.

## Command

```
.venv/bin/python -m pytest tests/integration/ -x -q
```

## Results

**428 passed, 3 warnings** in 17.76s

All integration tests passed. Warnings are pre-existing and unrelated to F-00039 (SAWarning about transaction deassociation and conflicting persistent instances in unique constraint tests).

## Files Changed

No files changed — this was a verification step only.

## Issues or Observations

- The `--timeout` flag is not recognized by this project's pytest configuration; removed to run successfully.
- No failures or errors.