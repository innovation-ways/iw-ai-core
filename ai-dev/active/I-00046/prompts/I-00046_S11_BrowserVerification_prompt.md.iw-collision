# Browser Verification Prompt: I-00046-S11-BrowserVerification

**Work Item**: I-00046 — Code view chat panel — toggle button clipped and viewport drift on module select
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this fix.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's
source code. Do NOT start, stop, or rebuild any services.

**Base URL**: `$IW_BROWSER_BASE_URL`
**Credentials**: `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Identifiers**: `$IW_ITEM_ID` / `$IW_STEP_ID`

Use `playwright-cli` exclusively. Never hardcode `localhost:9900` or any port.

## Input Files

- `ai-dev/active/I-00046/I-00046_Issue_Design.md` — design document
- `dashboard/templates/project_code.html` — fixed by S01
- `dashboard/templates/chat/panel.html` — fixed by S01

## Output Files

- `ai-dev/active/I-00046/reports/I-00046_S11_BrowserVerification_Report.md`
- `ai-dev/active/I-00046/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

The E2E dashboard does not require authentication (no login gate on the local stack).
Navigate directly to the Code page.

## E2E DB Seed Data

The E2E stack starts with the baseline seed from `scripts/e2e_seed.py`. It includes a
project row and an architecture map (level-1 doc). Module-level detail (level-2 docs) may
or may not be seeded. If the code components section shows no modules (empty state), the
toggle-button verification (V1) and drift test (V2) can still be performed using the
architecture-level view without selecting a module. Note this in the report.

## Verification Steps

### V1: Toggle button is visible and clickable (Bug a fix)

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code` (or the seeded project's code URL).
2. Take a snapshot (`playwright-cli snapshot`) and confirm the `#chat-toggle-tab` button
   is present in the accessibility tree — it should appear in the `complementary` region
   for "Code module chat" on the left edge of the chat panel.
3. Attempt to click the button — call `playwright-cli click <ref>` using the ref from the
   snapshot. Expect the click to succeed within 5 seconds (no timeout error).
4. Take a screenshot and verify the chat panel has visually collapsed (chat header,
   messages, and composer are hidden; only the narrow 48px tab remains).
5. **Verify**: Click again to re-expand — panel returns to full width.
6. **Screenshot**: save as `ai-dev/active/I-00046/evidences/post/I-00046_v1_toggle_button_works.png`

### V2: Page height stays bounded when a module is selected (Bug c fix)

1. From the Code page (chat panel expanded), click any module link in the architecture
   components list (e.g. "Orchestration Daemon", "Dashboard" etc.).
   - If no module links are visible (empty seed), skip to V2b.
2. After the module detail loads, take a screenshot.
3. **Verify**: The chat panel is still visible on the right side of the viewport —
   it has NOT disappeared or been pushed off-screen.
4. **Verify**: The page does not have a vertical scrollbar beyond the viewport (the
   layout stays within `100vh`). Check by calling `playwright-cli snapshot` — the chat
   panel's `region "Code module chat"` should still appear in the snapshot.
5. **Screenshot**: save as `ai-dev/active/I-00046/evidences/post/I-00046_v2_module_chat_visible.png`

**V2b (fallback if no modules)**: If no module links are seeded, scroll the architecture
content and verify the chat panel remains anchored. Screenshot as
`ai-dev/active/I-00046/evidences/post/I-00046_v2_fallback_chat_anchored.png`.
Note `ENV_DATA_MISSING: no module-level docs seeded` in the report (but do NOT fail the
step for this reason if V1 passed — module seeding is separate from the fix).

### V3: No regressions — architecture view and chat composition

1. With the chat panel expanded, type a short question in the chat composer
   (`#chat-input`) and verify the Send button is present and active (do NOT submit —
   just verify the composer renders correctly).
2. Navigate to another project's Code page (if seeded) or back to the home page and
   return to `/project/iw-ai-core/code` — verify the page loads cleanly with no console
   errors.
3. **Verify**: No JavaScript console errors appeared during V1–V3. Use `playwright-cli snapshot`
   to confirm the page is in a healthy state.
4. **Screenshot**: save as `ai-dev/active/I-00046/evidences/post/I-00046_v3_no_regressions.png`

## Pass Criteria

All of V1, V2 (or V2b), and V3 must pass. A Playwright timeout on the toggle-button click
(as seen in pre-fix testing) is a **CODE DEFECT** — fail the step with the reason.

## Report

Write `ai-dev/active/I-00046/reports/I-00046_S11_BrowserVerification_Report.md` with:
- Pass/fail table for V1, V2/V2b, V3
- The concrete `$IW_BROWSER_BASE_URL` used
- Screenshots list
- No regressions subsection

Then call:
```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00046/reports/I-00046_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short specific reason>" \
  --report ai-dev/active/I-00046/reports/I-00046_S11_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00046",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "Toggle button visible and clickable", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Page height bounded on module select", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
