# Browser Verification Prompt: F-00068-S13-BrowserVerification

**Work Item**: F-00068 — AI Chat Visual Improvements
**Step**: S13
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack. Do NOT start services yourself.

**Base URL**: `$IW_BROWSER_BASE_URL`
**Credentials**: `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step**: `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use `$IW_BROWSER_BASE_URL`.

---

## Prerequisites

```bash
playwright-cli kill-all
```

---

## Verifications

### V1: Chat panel loads with prose styles (AC3, AC4)

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code`.
2. Wait for the chat panel to appear (`#chat-panel`).
3. **Verify**: The page does not show a JS console error related to `iwProcessChatCallouts` being undefined.
4. **Verify**: `#chat-panel` is present in the DOM.
5. Take screenshot: `ai-dev/active/F-00068/evidences/post/F-00068_v1_chat_panel.png`.

### V2: Chat-message-body prose CSS is applied (AC3)

1. Remain on the code page.
2. Open browser devtools snapshot — check that CSS rules for `.chat-message-body h2` exist in the loaded stylesheets.
3. Alternatively: send a test message if the chat is functional, or inject a test div via devtools.
4. **Verify**: `.chat-message-body` has `font-size: 0.9rem` or similar (not browser default).
5. Take screenshot: `ai-dev/active/F-00068/evidences/post/F-00068_v2_prose_styles.png`.

### V3: Callout CSS classes are available (AC2, AC5)

1. Using playwright snapshot, inspect the loaded stylesheets.
2. **Verify**: `.chat-message-body .callout-warning` CSS rule is present (border-color `#F59E0B`).
3. **Verify**: `.chat-message-body .callout-note` CSS rule is present (border-color `#3B82F6`).
4. Take screenshot: `ai-dev/active/F-00068/evidences/post/F-00068_v3_callout_css.png`.

### V4: Chat sends a message and response renders (AC2 — functional)

1. Find the chat input on the code page.
2. Type a test message: "What is the purpose of the daemon?" and submit.
3. Wait for the assistant response to appear.
4. **Verify**: The response renders in a `.chat-message-body` div without JS errors.
5. **Verify**: If the response contains any `>` blockquotes, they render styled (not raw text).
6. Take screenshot: `ai-dev/active/F-00068/evidences/post/F-00068_v4_chat_response.png`.

*Note: AC1 (LLM uses callouts) cannot be verified mechanically — depends on LLM output. If the response contains a callout, verify it renders as a colored block.*

### V5: No Regressions

1. Verify the mermaid diagram rendering still works: navigate to code page, check that any existing architecture diagram renders (not broken by render.js changes).
2. Verify the code copy button still appears on code blocks in existing chat messages (if any exist in the E2E env).
3. Verify no console errors on: code page, docs page, queue page.
4. Take screenshot: `ai-dev/active/F-00068/evidences/post/F-00068_v5_no_regressions.png`.

---

## Pass Criteria

All V1–V5 must pass. Any failure requires calling `iw step-fail`.

`ENV_DATA_MISSING` applies if: no chat history exists and V4 cannot send a message (e.g., chat input is disabled or Ollama unavailable in E2E). In that case, prefix with `ENV_DATA_MISSING:`.

---

## Report

Write `ai-dev/active/F-00068/reports/F-00068_S13_BrowserVerification_Report.md` with pass/fail table, base URL, screenshots list, and no-regressions subsection.

```bash
# On pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00068/reports/F-00068_S13_BrowserVerification_Report.md

# On failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<specific reason>" \
  --report ai-dev/active/F-00068/reports/F-00068_S13_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "F-00068",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "Chat panel loads with prose styles", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "chat-message-body prose CSS applied", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Callout CSS classes available", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Chat response renders correctly", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
