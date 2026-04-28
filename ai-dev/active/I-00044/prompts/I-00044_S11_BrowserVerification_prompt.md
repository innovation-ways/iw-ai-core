# Browser Verification Prompt: I-00044-S11-BrowserVerification

**Work Item**: I-00044 — Code View Chat Panel — Ugly Collapse State and Viewport Drift
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. Do NOT start, stop, or rebuild any services.

**Base URL:** `$IW_BROWSER_BASE_URL`
**Work item / step identifiers:** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use `$IW_BROWSER_BASE_URL`.
Use `playwright-cli` exclusively — not `agent-browser`, not `chromium.launch()`.

## Input Files

- `ai-dev/active/I-00044/I-00044_Issue_Design.md` — design document with AC and bug descriptions
- `dashboard/templates/project_code.html` — modified (Bug 2 fix: `lg:grid-rows-[1fr]`)
- `dashboard/templates/chat/panel.html` — modified (Bug 1 fix: slide-out toggle tab)
- `dashboard/static/chat/panel.js` — modified (`applyCollapsedState()` update)
- `dashboard/static/chat.css` — modified (toggle tab styles)

## Output Files

- `ai-dev/active/I-00044/reports/I-00044_S11_BrowserVerification_Report.md`
- `ai-dev/active/I-00044/evidences/post/` — screenshots from all V1–V4 verifications

## Prerequisites

Start every run with:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

No login is required for the code view — it does not have auth gates in the E2E stack.

Rules:
1. Always `playwright-cli snapshot` before `fill` / `click` to get current element refs.
2. Wait for content to settle before snapshotting.
3. Screenshots go under `ai-dev/active/I-00044/evidences/post/` with descriptive names.

---

## Verification Steps

### V1: Bug 1 fixed — collapsed chat has recognisable toggle tab

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code` and wait for the page to load (architecture map renders, chat panel appears on the right).
2. Take a baseline screenshot of the expanded state.
3. `playwright-cli snapshot` — locate the new collapse toggle button (should be `#chat-toggle-tab` or labelled "Collapse chat panel").
4. Click the collapse toggle.
5. **Verify**: The collapsed state shows a visually recognisable element — a chat icon and/or a "Chat" label — NOT just a bare `<` or `>` chevron in an otherwise empty strip. Take a screenshot.
6. **Verify**: The toggle button is visible (not hidden) in the collapsed state — it must appear in the accessibility snapshot.
7. **Verify**: The `aria-label` on the toggle mentions "expand" or "Expand chat panel".
8. **Screenshot**: `ai-dev/active/I-00044/evidences/post/I-00044_v1_collapsed_toggle_tab.png`

PASS if: collapsed strip shows recognisable affordance (chat icon + label visible in screenshot).
FAIL if: collapsed strip shows only a bare chevron with no chat identity.

### V2: Bug 1 — can expand the chat again

1. (Continuing from V1 — chat is collapsed.)
2. `playwright-cli snapshot` — locate the expand toggle (aria-label should contain "Expand").
3. Click the toggle.
4. **Verify**: The chat panel expands — `#chat-messages` is visible, the composer input is accessible, and the panel header shows "Chat — Architecture".
5. **Verify**: The panel width is restored to ~400 px (not 48 px).
6. **Screenshot**: `ai-dev/active/I-00044/evidences/post/I-00044_v2_expanded_after_collapse.png`

PASS if: full chat panel is visible and functional after re-expanding.

### V3: Bug 2 fixed — chat stays in viewport when long module loads

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code` (fresh page, chat expanded).
2. Wait for the component list to load below the architecture map.
3. `playwright-cli snapshot` — locate the "Orchestration Daemon" module link.
4. Click the Orchestration Daemon link.
5. Wait for the module detail to load (long content).
6. `playwright-cli screenshot` — take a screenshot of the current viewport.
7. **Verify**: The chat panel (including the composer input area) is VISIBLE in the screenshot on the right side of the viewport. The chat panel must NOT be scrolled above or below the visible area.
8. **Verify**: The left content column shows the Orchestration Daemon module content (breadcrumb "Architecture > orch/daemon/" visible).
9. **Verify**: In the accessibility snapshot, the chat composer input is present and accessible (not hidden, not `aria-hidden`).
10. **Screenshot**: `ai-dev/active/I-00044/evidences/post/I-00044_v3_chat_visible_long_module.png`

PASS if: chat panel is visible in the same viewport as the module content — user does NOT need to scroll to reach the chat.
FAIL if: chat panel is not visible (scrolled above fold) or chat-related elements are inaccessible.

### V4: No Regressions

1. Verify the chat Q&A still works: type a short question (e.g. "What is this module?") into the chat composer and press Enter (or click Send).
2. **Verify**: A streaming response appears in the chat messages area (or a "thinking" indicator), confirming the Q&A pipeline is intact.
3. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code` again and click a DIFFERENT module (e.g. the first listed component).
4. **Verify**: The module detail loads, the chat panel context label updates to the new module name, and the chat panel is still visible in the viewport.
5. **Verify**: No new console errors appeared during V1–V4.
6. **Screenshot**: `ai-dev/active/I-00044/evidences/post/I-00044_v4_no_regressions.png`

---

## Pass Criteria

All V1–V4 must pass. Any failure requires `iw step-fail`.

If a verification fails because the E2E DB lacks the required project/code-index data (the code view shows "No architecture map — run Generate Code Map first"), prefix the failure reason with `ENV_DATA_MISSING:`.

## Report

Write `ai-dev/active/I-00044/reports/I-00044_S11_BrowserVerification_Report.md` with:
- Pass/fail table for V1–V4
- The exact `$IW_BROWSER_BASE_URL` used
- List of screenshots captured
- Any console errors observed
- "No regressions observed" subsection

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00044/reports/I-00044_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short reason>" \
  --report ai-dev/active/I-00044/reports/I-00044_S11_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00044",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "collapsed_toggle_tab_visible", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "expand_after_collapse", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "chat_visible_long_module", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "no_regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
