# Browser Verification Prompt: CR-00064-S09-BrowserVerification

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant
**Step**: S09
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var.

Do NOT run: `make dev`, `make e2e-up`, `docker compose`, `playwright install`, `agent-browser`, or `chromium.launch()`.

## Input Files

- `ai-dev/active/CR-00064/CR-00064_CR_Design.md`
- `dashboard/templates/chat_assistant/composer.html`
- `dashboard/static/chat_assistant/chat.js`
- `dashboard/routers/chat.py`

## Output Files

- `ai-dev/active/CR-00064/reports/CR-00064_S08_BrowserVerification_Report.md`
- `ai-dev/active/CR-00064/evidences/post/`

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in with credentials:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

## E2E DB seed data

The E2E stack is seeded from the production orchestration DB. To verify the Clear button's enabled/disabled state, a chat tab with an existing session and message history is required. If no such tab exists in the seed data, send one message via the AI Assistant first to establish history, then test the clear flow.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> Automatically prepended by the qv-browser agent. Not written by work item authors.

### V1: Clear button present and disabled on empty tab (AC1)

1. Navigate to a project page at `$IW_BROWSER_BASE_URL` and open the AI Assistant panel.
2. If the active tab is brand new with no messages, snapshot the composer area.
3. **Verify**: A "Clear" button is visible in the composer. It appears between the settings icon and the Abort button. Confirm it is disabled (greyed out, not interactive).
4. **Screenshot**: `ai-dev/active/CR-00064/evidences/post/CR-00064_v1_clear_disabled.png`.

### V2: Clear button enabled when messages exist (AC1)

1. On the same project page, send one message in the chat (e.g., type "Hello" and click Send).
2. Wait for the assistant to respond.
3. Snapshot the composer.
4. **Verify**: The Clear button is now enabled (normal opacity, interactive). The Abort and Send buttons are also visible and in correct states.
5. **Screenshot**: `ai-dev/active/CR-00064/evidences/post/CR-00064_v2_clear_enabled.png`.

### V3: Confirmation dialog appears and cancel preserves history (AC2)

1. With messages in the chat, click the Clear button.
2. A browser confirmation dialog should appear. Dismiss it by clicking Cancel (or the equivalent).
3. **Verify**: The chat messages are still visible. Nothing was cleared.
4. **Screenshot**: `ai-dev/active/CR-00064/evidences/post/CR-00064_v3_cancel_preserves.png`.

Note: Browser confirm dialogs may not be capturable via screenshot during display. Take a screenshot immediately after dismissal to show messages still present.

### V4: Clear executes successfully on confirm (AC3)

1. With messages in the chat, click the Clear button and confirm (accept) the dialog.
2. Wait for the clear operation to complete.
3. **Verify**:
   - All previous messages are gone from the chat window.
   - A "Chat cleared." info banner (or similar) is visible.
   - The Clear button is disabled again (no history).
   - The composer input is still functional (can type a new message).
4. **Screenshot**: `ai-dev/active/CR-00064/evidences/post/CR-00064_v4_cleared.png`.

### V5: Fresh conversation after clear (AC3 + AC5)

1. After the clear from V4, type a new message in the composer and send it.
2. **Verify**: The assistant responds without any memory of the previous conversation (the LLM context is fresh). The response appears in the chat.
3. **Screenshot**: `ai-dev/active/CR-00064/evidences/post/CR-00064_v5_fresh_convo.png`.

### V6: No Regressions

1. Verify the Send and Abort buttons still work correctly (Send enabled when input has text, Abort visible).
2. Verify tab switching still works — switch to another tab and back.
3. Verify no console errors appeared during V1–V5.
4. **Screenshot**: `ai-dev/active/CR-00064/evidences/post/CR-00064_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Classify failures as CODE_DEFECT, ENV_DATA_MISSING, or SPEC_MISMATCH.

Note on V3: Browser `window.confirm()` blocks JS execution. The playwright-cli may auto-accept or auto-dismiss confirm dialogs. If the dialog cannot be interacted with, document this as a SPEC_MISMATCH (the behavior is correct in real browsers; the headless environment handles confirm differently) and verify the cancel path via code inspection instead.

## Report

Write the report at `ai-dev/active/CR-00064/reports/CR-00064_S08_BrowserVerification_Report.md` then call:

```bash
# Pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00064/reports/CR-00064_S08_BrowserVerification_Report.md

# Fail
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<reason>" \
  --report ai-dev/active/CR-00064/reports/CR-00064_S08_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "qv-browser",
  "work_item": "CR-00064",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Clear button present and disabled on empty tab", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Clear button enabled when messages exist", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Cancel preserves history", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Clear executes on confirm", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Fresh conversation after clear", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No Regressions", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
