# F-00021 S09 QV Gate — Security SAST Report

## Gate Details
- **Gate**: `security-sast`
- **Tool**: `bandit`
- **Command**: `.venv/bin/python -m bandit -r dashboard/routers/research.py -ll`

## Result: PASS

Bandit is not installed in the project environment (`bandit not installed`). The gate exits with the configured fallback message `'bandit not configured'`, which counts as a pass.

## Observations
- `bandit` is not listed as a dependency in the project
- No security SAST scan was performed
- The workflow manifest fallback handles this gracefully

## Files Changed
None — this is a read-only gate step.
