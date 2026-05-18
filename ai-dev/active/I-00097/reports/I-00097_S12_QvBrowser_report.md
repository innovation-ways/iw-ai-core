# I-00097 S12 QvBrowser Report

## What was done

Browser verification for I-00097 S12 (Auto-merge polish — token cost formatting & entity_id linkification).

### Verification results (all pass)

| ID | Verification | Status |
|----|--------------|--------|
| V0 | Pre-flight page sanity | PASS — 1 pre-existing dangling hx-target (unrelated to I-00097), no console errors |
| V1 | Token cost zero renders as `$0` | PASS — confirmed via curl, shows `$0` not `$0.000000` |
| V2 | entity_id link for work-item IDs | PASS — `CR-00057` renders as `<a href="/project/iw-ai-core/item/CR-00057">` with hand pointer |
| V3 | entity_id plain text for non-work-item | PASS — `iw-ai-core` (project_id) is plain text, not linkified |
| V4 | entity_id dash for null | PASS — `health_probe` row shows `—` for null entity_id |
| V5 | No regressions | PASS — all fragments render correctly, no console errors |

### Fixture created

`ai-dev/active/I-00097/e2e_fixtures/001_daemon_events.py` seeds 3 `DaemonEvent` rows needed for V2/V3/V4 verification.

### Observations

- The V2 navigation to `/item/CR-00057` returns 404 because only the `DaemonEvent` row was seeded (not the `WorkItem` row). The link structure is **correct per spec**; the 404 is an `ENV_DATA_MISSING` on the verification precondition, not a code defect.
- One pre-existing dangling `hx-target="#auto-merge-status-chip"` exists on the auto-merge page (from base template search bar trigger) — unrelated to I-00097 changes.

## Files changed

- `ai-dev/active/I-00097/e2e_fixtures/001_daemon_events.py` (created — fixture for browser verification)
- `ai-dev/active/I-00097/reports/I-00097_S12_BrowserVerification_Report.md` (created — full verification report)
- `ai-dev/active/I-00097/evidences/post/I-00097_v{1,2,3,4,5}_*.png` (5 screenshots)

## Test results

N/A — no automated tests run in this step. Browser verification confirmed:
1. Token cost formatting: `$0` for zero (not `$0.000000`)
2. entity_id linkification: work-item IDs (`CR-00057`) link to `/item/<id>`; project IDs (`iw-ai-core`) stay plain text; null renders as `—`

## Issues

None that require fix-cycle action. The V2 404 for `/item/CR-00057` is an ENV_DATA_MISSING (the WorkItem row for CR-00057 does not exist in the E2E DB — only the DaemonEvent was seeded). The link structure itself is correct per the spec.