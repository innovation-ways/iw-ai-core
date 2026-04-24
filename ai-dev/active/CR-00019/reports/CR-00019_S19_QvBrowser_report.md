# S19 Report: QvBrowser (Browser Verification) for CR-00019

## What was done

S19 is the QvBrowser step for CR-00019. Two browser verification fix cycles ran and both failed at the E2E environment setup stage (dashboard container crash).

**Root cause identified (from fix cycle 2):** The E2E dashboard container crashed because `verify_instance_identity()` in `dashboard/app.py` lifespan threw `InstanceMismatchError`. The E2E stack creates a fresh PostgreSQL DB with no `iw_core_instance` row, but the worktree's `.env` has `IW_CORE_EXPECTED_INSTANCE_ID` pinned to the production fingerprint (`518ac56a-36f7-4c43-8f53-cfbb8a6baa3e`). The expected/actual mismatch caused the app startup to fail.

**Fix applied:** Set `IW_CORE_EXPECTED_INSTANCE_ID: ""` (empty string) in the `e2e-dashboard` service in `docker-compose.e2e.yml` (line 66). An empty string causes `get_expected_instance_id()` to return `None`, putting the app in bootstrap mode which is allowed to proceed with a missing instance row.

## Files changed

| File | Change |
|------|--------|
| `docker-compose.e2e.yml` | Added `IW_CORE_EXPECTED_INSTANCE_ID: ""` to e2e-dashboard service environment (line 66) |

## Issues/Observations

1. **This is an E2E infrastructure issue, not a CR-00019 code defect.** CR-00019 is a backend-only change (adds `awaiting_review`/`discarded` lifecycle states to OSS Prepare workflow) - S15 QvGate confirmed no browser verification was needed.

2. The fix was already applied by the fix cycle 2 agent. The orchestrator should automatically rebuild the E2E stack and re-run browser verification.

3. No CR-00019 implementation files were modified - the fix is purely in the E2E infrastructure configuration.

4. The dashboard now runs in bootstrap mode in the E2E stack, which is the correct behavior for a fresh E2E database.

## Escalation Note

This is the final browser fix cycle (2/2). The root cause was identified and the fix was applied to `docker-compose.e2e.yml`. If the orchestrator re-runs and the verification still fails, the issue is likely:
- The E2E environment is timing out during subsequent runs
- Port allocation conflicts on the E2E stack ports
- The fresh E2E DB needs migrations to be run

The human reviewer should monitor the next automatic re-run by the orchestrator.

## Verdict

**fix_applied** — Root cause identified (`IW_CORE_EXPECTED_INSTANCE_ID` mismatch) and fix applied to `docker-compose.e2e.yml`. Awaiting orchestrator re-run of browser verification.