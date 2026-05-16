# I-00086 S14 Browser Verification Report

## Environment
- Base URL used: http://localhost:9946
- E2E user: (from `$IW_BROWSER_E2E_USER`)

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/I-00086_v0_preflight_sanity.png | Checked `/`, `/project/iw-ai-core/`, `/project/iw-ai-core/history`, `/project/iw-ai-core/queue`, `/project/iw-ai-core/item/I-99086`, `/project/iw-ai-core/item/I-99087` for dangling fragment refs and load-time console errors; none found. |
| V1 | Navigate to item with editable steps | pass | null | evidences/post/I-00086_v1_item_detail_initial.png | Item `I-99086` opened from Queue. Overview tab visible by default, steps table rendered, per-step selects visible on editable rows, and footer "Apply to remaining steps:" visible. |
| V2 | Per-step dropdown updates row + toast | pass | null | evidences/post/I-00086_v2_per_step_updated.png | Changed S01 select to `OpenCode + GPT-5.3 Codex`; toast text `Model updated` appeared; same-row Model cell changed to `GPT-5.3 Codex` without refresh. |
| V3 | Bulk Apply updates rows + count toast | pass | null | evidences/post/I-00086_v3_bulk_apply_updated.png | Footer apply set to `Claude Code / Sonnet 4.6`; toast `Model updated for 2 step(s)` appeared; editable rows S01/S02 Model cells updated to `Sonnet 4.6`; non-editable S03 unchanged. |
| V4 | Bulk Apply zero-eligible info toast | pass | null | evidences/post/I-00086_v4_bulk_zero_eligible.png | On `I-99087` (no editable rows), Apply showed `No editable steps to update`; no row changes observed. |
| V5 | No regressions in adjacent controls | pass | null | evidences/post/I-00086_v5_no_regressions.png | Failed-row Restart/Skip buttons still rendered on `I-99086`. No item with `run_count > 1` expander badge found in visited seed set; no MERGE row in `awaiting_approval` found. No console errors observed. |

## Console / Network Errors
None observed (`.playwright-cli/console-*.log` not produced during navigations/actions).

## No Regressions
- Step-table adjacent controls remain intact after runtime override actions.
- Failed-step action buttons (Restart/Skip) still render.
- No load-time or post-action browser-console errors observed across V1..V5 pages.

## Screenshots captured
- ai-dev/active/I-00086/evidences/post/I-00086_v0_preflight_sanity.png
- ai-dev/active/I-00086/evidences/post/I-00086_v1_item_detail_initial.png
- ai-dev/active/I-00086/evidences/post/I-00086_v2_per_step_updated.png
- ai-dev/active/I-00086/evidences/post/I-00086_v3_bulk_apply_updated.png
- ai-dev/active/I-00086/evidences/post/I-00086_v4_bulk_zero_eligible.png
- ai-dev/active/I-00086/evidences/post/I-00086_v5_no_regressions.png

## File references checked
- `dashboard/routers/runtime_overrides.py:286` (`Model updated` toast)
- `dashboard/routers/runtime_overrides.py:347` (`Model updated for {N} step(s)` toast)
- `dashboard/routers/runtime_overrides.py:351` (`No editable steps to update` toast)
- `dashboard/templates/fragments/item_steps_table.html:166` (bulk footer label)
- `dashboard/templates/fragments/item_steps_table.html:168` (`bulk-runtime-option` selector)
