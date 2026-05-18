# CR-00058 S14 Browser Verification — Summary

## What was done
- Verified that the batch detail page renders both `item_held_for_scope` and `item_overlap_allowed_by_policy` DaemonEvents as correctly styled pills
- Verified that the queue page surfaces the same held pill for approved items not in active batches
- Verified that the help panels (batches, queue, batch_detail) mention the new policy-allowed pill
- Confirmed no console errors or regressions on any visited page
- Fixed a fixture bug (wrong attribute name `metadata` → `event_metadata`) that caused empty metadata in events

## Files changed
- `ai-dev/active/CR-00058/e2e_fixtures/001_overlap_gate_events.py` — Fixed `metadata=` → `event_metadata=` when creating DaemonEvent rows; re-seeded DB

## Test results
| Verification | Result |
|---|---|
| V0 Pre-flight sanity | PASS |
| V1 Held pill renders (F-00055) | PASS |
| V2 Policy-allowed pill renders (CR-00001) | PASS |
| V3 Held precedence (both events) | n/a — no item has both event types within window |
| V4 Queue page pills | PASS |
| V5 Help copy mentions policy pill | PASS |
| V6 No regressions | PASS |

## Issues / Observations
- V3 requires a work item that has BOTH `item_held_for_scope` AND `item_overlap_allowed_by_policy` events within the same 300s window — not achievable with current seed without adding a third event row. Per spec: report n/a.
- The fixture bug (`metadata=` vs `event_metadata=`) was caught because the pill text showed `+0` instead of actual glob counts, indicating empty metadata.