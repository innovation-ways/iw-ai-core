# I-00065 S15 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9936`
- **E2E user:** `dev@example.local`
- **Project exercised:** `iw-ai-core` (IW AI Core (E2E))
- **Page exercised:** `/project/iw-ai-core/code` (Code Understanding — Architecture view)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | "+ New" hidden when chat panel is collapsed | **pass** | `evidences/post/I-00065_v1_collapsed_no_new_button.png` | The rail shows only the chat bubble icon, "Chat" label, and expand chevron — no "+ New" button visible. Snapshot confirms `data-collapsed="true"` and `#chat-new-btn` is not in the accessibility tree. The fix in `panel.html:6` (`#chat-panel[data-collapsed="true"] #chat-new-btn { display: none; }`) is working correctly. |
| V2 | Exactly one greeting after 3 successive "+ New" clicks | **pass** | `evidences/post/I-00065_v2_single_greeting_after_3_clicks.png` | After clicking the "+ New" button three times, the accessibility snapshot shows exactly ONE `generic` child under `#chat-messages` containing "Ask about this module" / "Try: What does this component do?" / "Type / for commands". The fix in `panel.js:175-189` (lines 178-181: `var existingEmpty = document.getElementById('chat-empty-state'); if (existingEmpty) existingEmpty.remove();`) correctly prevents duplicate greeting blocks. |
| V3 | No regressions on adjacent flows | **pass** | `evidences/post/I-00065_v3a_message_sent.png` + `evidences/post/I-00065_v3_collapsed_regression_check.png` | (1) Re-collapse/re-expand cycle retains exactly one greeting block. (2) Composer flow: typed a message ("Hello test message"), clicked Send — user bubble appeared (ref=e202, role="You") followed by a deterministic stub assistant reply (ref=e205, role="Assistant"), confirming the round-trip works. (3) Clicked "+ New" after chat history present — bubbles cleared, exactly one greeting returned. (4) `/healthz/identity` returned HTTP 200 with `{"expected":null,"actual":"9ef99d58-b2c2-4b25-b0ec-7f547bc84a7a","mode":"bootstrap","match":false}` — correct bootstrap-mode response. (5) Console errors observed: only `favicon.ico` 404 — unrelated to chat panel functionality, not a regression. |

## Console / Network Errors
- `favicon.ico` 404 — pre-existing missing asset, unrelated to chat panel.
- No other errors observed during V1..V3 verification.

## No Regressions
All adjacent flows confirmed intact:
- Rail expand/collapse (V1 → V3 re-collapse): smooth transitions, no flash of hidden content.
- "+ New" click on an already-empty panel: still produces exactly one greeting.
- "+ New" click after chat history: user bubbles correctly removed, greeting correctly singular.
- Send message round-trip: user bubble appears, stub assistant reply echoes back.
- `/healthz/identity` health check: HTTP 200, JSON payload as expected.

## Screenshots Captured

| File | Description |
|------|-------------|
| `evidences/post/I-00065_v1_collapsed_no_new_button.png` | Collapsed rail — no "+ New" button visible |
| `evidences/post/I-00065_v2_expanded_with_new_button.png` | Expanded panel with "+ New" button and greeting |
| `evidences/post/I-00065_v2_single_greeting_after_3_clicks.png` | State after 3 "+ New" clicks — exactly one greeting |
| `evidences/post/I-00065_v3_collapsed_regression_check.png` | Re-collapsed panel check |
| `evidences/post/I-00065_v3a_message_sent.png` | User bubble after Send click + stub assistant reply |

## Root Cause (N/A — no failure)
Both bugs were confirmed **fixed**:
1. **Bug 1 (CSS)**: `dashboard/templates/chat/panel.html:6` added `#chat-new-btn` to the `[data-collapsed="true"]` hide selector, so the "+ New" button is now `display: none` when the panel is collapsed.
2. **Bug 2 (JS)**: `dashboard/static/chat/panel.js:178-181` in `showEmptyState()` now removes any pre-existing `#chat-empty-state` element before inserting a fresh one, preventing duplicate greeting blocks.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "I-00065",
  "overall_status": "pass",
  "base_url_used": "http://localhost:9936",
  "verifications": [
    {"id": "V1", "name": "+ New hidden in collapsed rail", "status": "pass", "screenshot": "evidences/post/I-00065_v1_collapsed_no_new_button.png", "notes": "Fix in panel.html:6 confirmed — button not in accessibility tree when collapsed"},
    {"id": "V2", "name": "Exactly one greeting after 3 + New clicks", "status": "pass", "screenshot": "evidences/post/I-00065_v2_single_greeting_after_3_clicks.png", "notes": "Fix in panel.js:178-181 confirmed — no duplicate greeting after 3 clicks"},
    {"id": "V3", "name": "No regressions on adjacent flows", "status": "pass", "screenshot": "evidences/post/I-00065_v3a_message_sent.png", "notes": "Composer round-trip works; collapse/expand retains singular empty state; /healthz/identity returns 200"}
  ],
  "console_errors_observed": ["favicon.ico 404 (pre-existing, unrelated to chat panel)"],
  "screenshots": [
    "evidences/post/I-00065_v1_collapsed_no_new_button.png",
    "evidences/post/I-00065_v2_expanded_with_new_button.png",
    "evidences/post/I-00065_v2_single_greeting_after_3_clicks.png",
    "evidences/post/I-00065_v3_collapsed_regression_check.png",
    "evidences/post/I-00065_v3a_message_sent.png"
  ],
  "notes": "All three verifications pass. Both bugs confirmed fixed. No regressions observed."
}
```