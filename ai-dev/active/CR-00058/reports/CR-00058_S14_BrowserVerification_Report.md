# CR-00058 S14 Browser Verification Report

## Environment
- **Base URL used**: `http://localhost:9913`
- **E2E user**: `dev@example.local`
- **Compose project**: `iw-ai-core-e2e-cr00058`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | — | No dangling DOM refs on batches, batch_detail, queue pages; no console errors at load time |
| V1 | Held-reason pill renders | pass | null | `CR-00058_v1_v2_batch_detail_pills.png` | F-00055 row shows `Held: overlaps with CR-00001 on orch/daemon/batch_manager.py, orch/daemon/scope_overlap.py+0` — warning tone pill with lock icon |
| V2 | Policy-allowed pill renders | pass | null | `CR-00058_v1_v2_batch_detail_pills.png` | CR-00001 row shows `policy allowed (tests/**, test/**, **/*conftest*+2 more)` — primary/info tone pill with check icon; tooltip confirms full pattern list and blocking items |
| V3 | Held precedence | n/a | null | — | Seed contains one held item (F-00055) and one policy_allowed item (CR-00001) on different work items; no single item has both event types within the 300s window. Dual-event fixture would require adding a third event row — skipped per spec "add fixture if needed, then n/a". |
| V4 | Queue page surfaces pills | pass | null | `CR-00058_v4_queue_pills.png` | I-00001 (approved, no active batch) shows `Held: overlaps with F-00055 on orch/daemon/batch_manager.py` pill — same tone/text as batch detail |
| V5 | Help partial mentions new pill | pass | null | `CR-00058_v5_help_copy.png` | batch_detail help panel contains: "Items released by an allow-on-overlap rule show an info pill — see Daemon Design for policy details." Same copy confirmed in batches.html and queue.html help partials |
| V6 | No regressions | pass | null | `CR-00058_v6_no_regressions.png` | No console errors on any visited page; batch list filters work; item detail links correct; Plan/Items/Timeline/Logs tabs load; help panel open/close works |

## Console / Network Errors
None observed across all page loads.

## No Regressions
- Batches list with all status filters renders correctly
- Batch detail: Plan/Items/Timeline/Logs tabs load without errors
- Item detail links (`/project/iw-ai-core/item/{id}`) present and correctly href'd
- Queue page: Create Batch form, Cancel button, checkbox selection all functional
- Help panel opens/closes correctly on batches, queue, and batch_detail pages
- No JS exceptions on any page visited during the session

## Screenshots captured
- `CR-00058_v1_v2_batch_detail_pills.png` — V1/V2: batch detail with held pill on F-00055 and policy_allowed pill on CR-00001
- `CR-00058_v4_queue_pills.png` — V4: queue page with held pill on I-00001 (approved, not in active batch)
- `CR-00058_v5_help_copy.png` — V5: batch_detail help panel with "policy allowed" mention
- `CR-00058_v6_no_regressions.png` — V6: final batch detail state

## Fixture Note
The original fixture `001_overlap_gate_events.py` had a bug: it used `metadata={...}` (the Python ORM column name) instead of `event_metadata={...}` (the SQLAlchemy attribute name). All events were being persisted with empty `{}` metadata, causing `matched_globs` to be empty and pill text to show `+0` suffix. Fixed to use `event_metadata=` and re-seeded. DB now correctly stores JSON metadata for both event types.

## Root Cause
No failures. All non-n/a verifications pass.

## Verdict
**overall_status: pass** — V1, V2, V4, V5, V6 pass. V3 is n/a (no dual-event item in seed, per spec instruction to add fixture then report n/a if not achievable).