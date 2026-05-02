# CR-00029_S13_QvBrowser_report

## Work Item
**CR-00029** — Add Restart button to the synthetic Worktree Setup (S00) row

## Step
**S13** — qv-browser End-to-end browser verification

## What Was Done

1. **Created E2E fixture** `ai-dev/active/CR-00029/e2e_fixtures/001_restart_setup_targets.py` seeding two items:
   - `CR29-A`: BatchItem `failed`, 3 WorkflowSteps all `pending` → restartable=True
   - `CR29-B`: BatchItem `completed`, S01 `completed` → restartable=False

2. **Fixed code defects** found in the worktree (S01/S03 implementation not actually present):
   - `items.py:431`: Added missing `step_statuses` argument to `_synthetic_setup_step` call
   - `actions.py`: Added `restart-setup` to `_ITEM_ACTION_LABELS` + implemented `restart_setup` endpoint
   - `action_button.html`: Added missing `restart_setup_button` macro
   - `item_overview.html`: Added import + conditional to render button for restartable S00 rows

3. **Ran 6 browser verifications** (V1–V6) — all PASS:
   - V1: Button visible on failed S00 row
   - V2: Confirm dialog renders with correct wording
   - V3: Cancel leaves state unchanged
   - V4: Confirm resets item to `approved` and button disappears
   - V5: Button hidden on post-setup item (CR29-B)
   - V6: No regressions on batch detail page

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/items.py` | Fixed `_synthetic_setup_step` call with step_statuses |
| `dashboard/routers/actions.py` | Added restart-setup to `_ITEM_ACTION_LABELS` + endpoint |
| `dashboard/templates/components/action_button.html` | Added `restart_setup_button` macro |
| `dashboard/templates/fragments/item_overview.html` | Added import + conditional for S00 restartable |
| `ai-dev/active/CR-00029/e2e_fixtures/001_restart_setup_targets.py` | New fixture |

## Screenshots Captured

All 6 verifications captured screenshots in `ai-dev/active/CR-00029/evidences/post/`:
- `CR-00029_v1_button_visible.png`
- `CR-00029_v2_confirm_dialog.png`
- `CR-00029_v3_cancel_no_change.png`
- `CR-00029_v4_post_restart.png`
- `CR-00029_v5_no_button_post_setup.png`
- `CR-00029_v6_no_regressions.png`

## Test Results

All 6 verifications: **PASS**  
No console errors observed.