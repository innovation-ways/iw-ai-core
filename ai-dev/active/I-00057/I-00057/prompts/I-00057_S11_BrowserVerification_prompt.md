# Browser Verification Prompt: I-00057-S11-BrowserVerification

**Work Item**: I-00057 -- Chat panel collapse toggle is intrusive and panel starts open
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Testcontainers via pytest fixtures allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials:** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers:** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Do NOT run `make dev`, `docker compose`, `playwright install`, `agent-browser`, or any `chromium.launch()` snippet. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00057/I-00057_Issue_Design.md`
- `dashboard/templates/chat/panel.html`
- `dashboard/static/chat/panel.js`

## Output Files

- `ai-dev/active/I-00057/reports/I-00057_S11_BrowserVerification_Report.md`
- `ai-dev/active/I-00057/evidences/post/` — screenshots

## Prerequisites

Every QvBrowser run MUST start with:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Always `playwright-cli snapshot` before `fill`/`click`. Screenshots: `playwright-cli screenshot` (no path arg), then `cp .playwright-cli/page-*.png ai-dev/active/I-00057/evidences/post/<name>.png`.

This incident does NOT need new e2e_fixtures — the chat panel renders on the Code page for any project; pick one that already has a code-map run on the seed DB (e.g. `iw-ai-core`).

## Verification Steps

### V1: Initial state — panel collapsed, no floating tab

1. Open a clean session (clear localStorage to simulate a first-time visitor):
   ```bash
   playwright-cli evaluate "localStorage.removeItem('iw_chat_collapsed'); localStorage.removeItem('iw_chat_width')"
   ```
2. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code`. Reload to apply the cleared storage.
3. **Verify** the initial state:
   ```bash
   playwright-cli evaluate "(()=>{
     const panel = document.querySelector('#chat-panel');
     const oldTab = document.querySelector('#chat-toggle-tab');
     const expandRail = document.querySelector('#chat-expand-rail');
     const widthVar = getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim();
     return {
       collapsed: panel?.dataset.collapsed,
       oldTabPresent: !!oldTab,
       expandRailPresent: !!expandRail,
       widthVar
     };
   })()"
   ```
   Expect: `collapsed === 'true'`, `oldTabPresent === false`, `expandRailPresent === true`, `widthVar === '48px'`.
4. **Screenshot:** `ai-dev/active/I-00057/evidences/post/I-00057_v1_initial_collapsed.png`.

### V2: Expand → state persists across reload

1. Snapshot, then click the expand rail (`#chat-expand-rail`).
2. **Verify** panel is now expanded:
   ```bash
   playwright-cli evaluate "(()=>{
     return {
       collapsed: document.querySelector('#chat-panel')?.dataset.collapsed,
       widthVar: getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim(),
       stored: localStorage.getItem('iw_chat_collapsed')
     };
   })()"
   ```
   Expect: `collapsed === 'false'`, `widthVar !== '48px'`, `stored === 'false'`.
3. **Screenshot:** `ai-dev/active/I-00057/evidences/post/I-00057_v2_expanded.png`.
4. Reload the page. Re-evaluate the same expression.
5. **Verify** the panel is STILL expanded after reload:
   - Expect: `collapsed === 'false'`, `stored === 'false'`.
6. **Screenshot:** `ai-dev/active/I-00057/evidences/post/I-00057_v2b_expanded_after_reload.png`.

### V3: Collapse → state persists across reload

1. Snapshot, then click the collapse button (`#chat-collapse-btn`) inside the panel header.
2. **Verify** panel is collapsed and stored:
   ```bash
   playwright-cli evaluate "({
     collapsed: document.querySelector('#chat-panel')?.dataset.collapsed,
     widthVar: getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim(),
     stored: localStorage.getItem('iw_chat_collapsed')
   })"
   ```
   Expect: `collapsed === 'true'`, `widthVar === '48px'`, `stored === 'true'`.
3. Reload. Re-evaluate.
4. **Verify** STILL collapsed.
5. **Screenshot:** `ai-dev/active/I-00057/evidences/post/I-00057_v3_collapsed_after_reload.png`.

### V4: Persistence is global (different project, same state)

1. Set localStorage to expanded:
   ```bash
   playwright-cli evaluate "localStorage.setItem('iw_chat_collapsed', 'false')"
   ```
2. Navigate to a DIFFERENT project's Code page if available (e.g. `$IW_BROWSER_BASE_URL/project/<other-project>/code`). If only one project is registered in the seed DB, navigate to a different page that includes the chat panel — the persistence is per-domain, so any same-origin page with the chat panel works.
3. **Verify** the panel is expanded on the new page:
   ```bash
   playwright-cli evaluate "document.querySelector('#chat-panel')?.dataset.collapsed"
   ```
   Expect: `'false'`.
4. **Screenshot:** `ai-dev/active/I-00057/evidences/post/I-00057_v4_global_persistence.png`.

### V5: No regressions — keyboard shortcut, mobile drawer, width

1. With panel expanded on desktop, press Cmd+\\ (or Ctrl+\\):
   ```bash
   playwright-cli evaluate "document.dispatchEvent(new KeyboardEvent('keydown', {key:'\\\\', metaKey:true, bubbles:true}))"
   ```
2. **Verify** the panel toggled to collapsed AND the new state was persisted (`localStorage.getItem('iw_chat_collapsed') === 'true'`).
3. **Verify** width persistence still works — set `iw_chat_width` to `420`, reload, expand, check `--chat-width` is `420px`.
4. **Verify** there are no console errors during V1..V4.
5. **Screenshot:** `ai-dev/active/I-00057/evidences/post/I-00057_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure requires `iw step-fail`.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — Panel renders open by default; floating tab still present; click does nothing; reload loses state → fix-cycle agent patches code.
- **ENV_DATA_MISSING** — Page returned 200 but no project to navigate to → seed a project via `e2e_fixtures/`. Prefix the reason with `ENV_DATA_MISSING:`.

## Report

Write `ai-dev/active/I-00057/reports/I-00057_S11_BrowserVerification_Report.md`:

- Pass/fail table for V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- JSON output from each `evaluate` call.
- Screenshot list.
- "No regressions observed" subsection covering keyboard shortcut, mobile drawer, width persistence.

Then call **one** of:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00057/reports/I-00057_S11_BrowserVerification_Report.md

uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00057/reports/I-00057_S11_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00057",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "initial collapsed; no floating tab", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "expand persists across reload", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "collapse persists across reload", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "persistence is global", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "no regressions (keyboard, drawer, width)", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
