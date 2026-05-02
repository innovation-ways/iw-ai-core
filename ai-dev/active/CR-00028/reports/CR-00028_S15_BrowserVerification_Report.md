# CR-00028 S15 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9919`
- **E2E user:** `dev@example.local`
- **Compose project:** `iw-ai-core-e2e-cr00028`
- **E2E DB:** `iw_e2e` on `e2e-db-1:5432`

## E2E Seed Fixture

Created `ai-dev/active/CR-00028/e2e_fixtures/001_merge_failed_batch.py` which seeds:
- WorkItem `CR-00028-S15` (in_progress, ChangeRequest)
- WorkItem `CR-00028-S15-2` (approved, ChangeRequest — cascade victim)
- Batch `BATCH-CR00028-S15` (executing, max_parallel=4)
- BatchItem I1 (CR-00028-S15): `merge_failed`, execution_group=0, with worktree_info
- BatchItem I2 (CR-00028-S15-2): `pending`, execution_group=1

Fixture is idempotent and was re-run via `scripts/e2e_seed.py` inside the `e2e-dashboard` container after V4 consumed the seeded state.

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | `merge_failed` badge distinct from `failed` | **pass** | `evidences/post/CR-00028_v1_merge_failed_badge.png` | Batch detail page shows `merge_failed` in amber/warning color (bg-warning token). The legacy `failed` badge in BATCH-CR29 would render red (bg-destructive). Both statuses visually distinguishable per design. |
| V2 | Retry Merge button + hx-get confirm-modal pattern | **pass** | `evidences/post/CR-00028_v2_retry_merge_button.png` | Item overview page shows "↻ Retry Merge" button on the MERGE row. Button's `hx-get="/project/iw-ai-core/api/confirm-item/restart-merge/CR-00028-S15"` opens a modal (hx-target="#confirm-dialog"), NOT a direct POST, NOT an hx-confirm attribute. Correct per design. |
| V3 | Abandon button uses confirm-modal pattern (no hx-confirm) | **pass** | `evidences/post/CR-00028_v3_abandon_modal.png` | "⚠ Abandon" button's `hx-get="/project/iw-ai-core/api/confirm-item/abandon-merge/CR-00028-S15"`. No `hx-confirm` attribute. Clicking opens modal with danger-styled "Abandon Merge" confirm button and explanatory text: "Marks this item as failed and cascade-fails all dependent items in later groups." Correct per design. |
| V4 | Retry Merge transitions item out of `merge_failed` | **pass** | `evidences/post/CR-00028_v4_retry_merge_clicked.png` | After clicking confirm on the Restart Merge modal: MERGE step status changed from `merge_failed` → `in_progress` (step pipeline shows ● running). No console errors during htmx swap. Expected behavior: daemon will pick up the item on next poll and re-merge. |
| V5 | Abandon triggers cascade (I1→failed, I2 cascade) | **pass** | `evidences/post/CR-00028_v5_abandon_cascade.png` | After re-seeding and clicking Abandon: MERGE step status → `failed` (red badge, error "[operator abandoned via abandon-merge]"). Batch detail page shows I1: `failed`. I2 remains `pending` in the batch list — the cascade to group=1 items is a daemon poll action (60s interval) and is verified by the integration test `test_abandon_merge_triggers_cascade.py`. V5.7 deferred to integration tests as documented in the step prompt. |
| V6 | No regressions | **pass** | `evidences/post/CR-00028_v6_no_regressions.png` | Batches list renders correctly with 3 rows: BATCH-CR00028-S15 (executing), BATCH-F00055 (completed), BATCH-CR29 (completed_with_errors). Legacy `completed_with_errors` batch shows correct status. No console errors observed on any visited page. |

## Console / Network Errors
None observed across all V1–V6 navigations.

## No Regressions Observed (V6)
- Batches list (`/project/iw-ai-core/batches`) renders all 3 batches with correct statuses
- Legacy `completed_with_errors` batch (BATCH-CR29) still shows correct badge
- No new console errors on any page visited during verification
- `failed` badge still renders in red (bg-destructive) for the abandoned item, visually distinct from `merge_failed` amber badge

## Screenshots Captured
- `ai-dev/active/CR-00028/evidences/post/CR-00028_v1_merge_failed_badge.png` — V1: batch detail with merge_failed badge
- `ai-dev/active/CR-00028/evidences/post/CR-00028_v2_retry_merge_button.png` — V2: item overview with Retry Merge + Abandon buttons
- `ai-dev/active/CR-00028/evidences/post/CR-00028_v2_retry_modal_open.png` — V2: restart-merge confirm modal open
- `ai-dev/active/CR-00028/evidences/post/CR-00028_v3_abandon_modal.png` — V3: abandon confirm modal open
- `ai-dev/active/CR-00028/evidences/post/CR-00028_v4_retry_merge_clicked.png` — V4: MERGE step transitioned to in_progress after retry
- `ai-dev/active/CR-00028/evidences/post/CR-00028_v5_abandon_cascade.png` — V5: MERGE step failed after abandon + batch detail showing cascade result
- `ai-dev/active/CR-00028/evidences/post/CR-00028_v6_no_regressions.png` — V6: batches list with no regressions

## Files Changed (by prior steps)
- `orch/db/models.py` (S01): Added `BatchItemStatus.merge_failed`
- `orch/db/migrations/versions/48218f84b69f_cr_00028_add_merge_failed...py` (S01): PostgreSQL enum addition
- `orch/daemon/merge_queue.py` (S03): Writes `merge_failed` for recoverable MergeError/TimeoutExpired
- `orch/daemon/batch_manager.py` (S03): Excludes `merge_failed` from `_BLOCKING_TERMINAL_STATUSES`
- `dashboard/routers/actions.py` (S03): restart-merge / abandon-merge endpoints
- `dashboard/templates/components/status_badge.html` (S05): `merge_failed` → `bg-warning` (amber, distinct from red `failed`)
- `dashboard/templates/fragments/item_overview.html` (S05): Both buttons shown for `merge_failed` MERGE row
- `ai-dev/active/CR-00028/e2e_fixtures/001_merge_failed_batch.py` (this step): Synthetic test data for V1–V5

## Root Cause (none — all pass)
N/A — all 6 verifications passed. No code defects found.

## Subagent Result

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "CR-00028",
  "overall_status": "pass",
  "base_url_used": "http://localhost:9919",
  "verifications": [
    {"id": "V1", "name": "merge_failed badge distinct from failed", "status": "pass", "screenshot": "evidences/post/CR-00028_v1_merge_failed_badge.png", "notes": "Amber/warning color distinct from red failed badge. BATCH-CR00028-S15 item row shows merge_failed correctly."},
    {"id": "V2", "name": "retry-merge button + hx-get confirm-modal pattern", "status": "pass", "screenshot": "evidences/post/CR-00028_v2_retry_merge_button.png", "notes": "hx-get=/project/iw-ai-core/api/confirm-item/restart-merge/CR-00028-S15 — opens modal, not direct POST"},
    {"id": "V3", "name": "abandon button uses confirm-modal pattern", "status": "pass", "screenshot": "evidences/post/CR-00028_v3_abandon_modal.png", "notes": "No hx-confirm attribute. hx-get=/project/iw-ai-core/api/confirm-item/abandon-merge/CR-00028-S15. Modal shows danger button + cascade explanation."},
    {"id": "V4", "name": "retry-merge transitions item out of merge_failed", "status": "pass", "screenshot": "evidences/post/CR-00028_v4_retry_merge_clicked.png", "notes": "MERGE step status changed merge_failed → in_progress after confirm. No console errors."},
    {"id": "V5", "name": "abandon triggers cascade (I1→failed, I2 cascade deferred to daemon poll)", "status": "pass", "screenshot": "evidences/post/CR-00028_v5_abandon_cascade.png", "notes": "MERGE step → failed with [operator abandoned via abandon-merge] error. I1 batch_item status = failed. I2 pending unchanged (daemon poll 60s). Cascade verified by integration test."},
    {"id": "V6", "name": "no regressions", "status": "pass", "screenshot": "evidences/post/CR-00028_v6_no_regressions.png", "notes": "Batches list renders correctly (3 rows). completed_with_errors batch still correct. No console errors."}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "evidences/post/CR-00028_v1_merge_failed_badge.png",
    "evidences/post/CR-00028_v2_retry_merge_button.png",
    "evidences/post/CR-00028_v2_retry_modal_open.png",
    "evidences/post/CR-00028_v3_abandon_modal.png",
    "evidences/post/CR-00028_v4_retry_merge_clicked.png",
    "evidences/post/CR-00028_v5_abandon_cascade.png",
    "evidences/post/CR-00028_v6_no_regressions.png"
  ],
  "notes": "All 6 verifications passed. Cascade V5.7 (I2 becoming failed after 60s poll) deferred to integration test test_abandon_merge_triggers_cascade.py per step prompt guidance."
}
```