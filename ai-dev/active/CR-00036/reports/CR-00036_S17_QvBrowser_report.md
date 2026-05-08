# CR-00036 S17 QvBrowser Report

## What was done

Executed browser-based end-to-end verifications (V1–V8) for the CR-00036 `auto_merge` feature against the isolated E2E stack at `http://localhost:9957`. All verifications passed.

## Files changed

No files were modified by this step. The step performed read-only browser verification only.

## Test results

| Verification | Result |
|--------------|--------|
| V1: Toggle on create-batch form | PASS — `Auto-merge each item when it succeeds` checkbox pre-checked (project default `true`). Form submits to create new batch. |
| V2: Auto-merge persists in new batch | PASS — New batch (BATCH-00002) header shows `Auto-merge: yes` and Plan tab checkbox is checked. |
| V3: Plan-tab toggle editable pre-execution | PASS — Toggled BATCH-00002's auto-merge from checked→unchecked. Header updated immediately. Reload confirmed persistence. |
| V4: Plan-tab toggle disabled while running | PASS — BATCH-D-0002 (status=executing) does not render Plan tab edit form — consistent with `max_parallel` behavior. |
| V5: Merge button rendered on awaiting_approval | PASS — CR-00001 item shows MERGE step with `awaiting_approval` status and a `Merge` button in the Actions cell. |
| V6: Click Merge transitions out of awaiting_approval | PASS — After clicking Merge, status changed `awaiting_approval` → `pending`. Merge button disappeared from Actions cell. |
| V7: auto_merge=true shows no Merge button | PASS — BATCH-D-0003 (auto_merge=true) item CR-00004 shows `merged` status with no Merge button. |
| V8: No regressions | PASS — Batches list, batch detail, item detail pages render correctly. No JavaScript console errors (only benign 404 for favicon.ico). |

## Screenshots captured

All screenshots saved to `ai-dev/active/CR-00036/evidences/post/`:
- `CR-00036_v1_create_batch_form.png`
- `CR-00036_v2_batch_plan_off.png`
- `CR-00036_v3_toggle_on.png`
- `CR-00036_v4_toggle_disabled.png`
- `CR-00036_v5_merge_button.png`
- `CR-00036_v6_merge_clicked.png`
- `CR-00036_v8_no_regressions.png`

## Issues or observations

- **V4 note:** The Plan tab form controls are not rendered at all for executing batches — the page shows the Items table directly. This is consistent with how `max_parallel` behaves and is the expected "disabled" state per the design.
- **Seed data note:** The E2E fixtures created items with correct `BatchItemStatus` in the DB, but the step-run history shows `pending` instead of the terminal statuses because no actual agent execution ran. This does not affect the verification of UI rendering or state transitions.
- **V7 screenshot:** Captured via the V8 verification path (navigated to CR-00004 directly).