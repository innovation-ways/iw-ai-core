# Browser Verification Prompt: F-00091-S19-BrowserVerification

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Step**: S19
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker compose / docker kill / docker rm / docker volume / docker prune commands. The isolated E2E stack is already up. Allowed: `docker compose exec app …` when re-running the seed after writing a fixture file; read-only `docker ps` / `docker logs` / `docker inspect`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB (5433). Read-only `alembic history` is allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Environment

The IW orchestrator has already started an isolated E2E stack built from THIS worktree's source. Do NOT start, stop, or rebuild any services.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Do NOT hardcode route paths beyond the ones called out below — navigate via the UI where possible.

Do NOT run any of:
- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/restart/build`
- `playwright install` / `npx playwright install`
- `agent-browser` — this environment uses `playwright-cli` exclusively
- Any `chromium.launch()` Python/Node snippet

## Input Files

- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — design doc
- `ai-dev/active/F-00091/evidences/pre/F-00091-before-01-home-no-project.png` — pre state on `/`
- `ai-dev/active/F-00091/evidences/pre/F-00091-before-02-project-iw-ai-core.png` — pre state on a project page
- `ai-dev/active/F-00091/evidences/pre/F-00091-before-03-system-status-tabs-empty.png` — pre state on `/system/status`
- `dashboard/templates/chat_assistant/panel.html`
- `dashboard/templates/chat_assistant/composer.html`
- `dashboard/static/chat_assistant/chat.js`
- `dashboard/static/chat_assistant/chat.css`
- `dashboard/routers/chat.py`

## Output Files

- `ai-dev/active/F-00091/reports/F-00091_S19_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/F-00091/evidences/post/` — verification screenshots

## Prerequisites

Every QvBrowser run MUST start with:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Snapshot first, then interact:

```bash
playwright-cli snapshot
```

Reads access keys with the env credentials if the project has auth. (This dashboard typically has none — confirm by inspecting the snapshot for a login form. If none, proceed straight to the verifications.)

Rules:

1. Always `playwright-cli snapshot` before `click` / `fill` to read accessible refs. Never reuse refs across navigations.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots: run `playwright-cli screenshot` (no path argument), then `cp .playwright-cli/page-*.png ai-dev/active/F-00091/evidences/post/F-00091_v{N}_<short>.png`.

## E2E DB seed data

The E2E DB is seeded from prod. It already contains multiple `Project` rows including `iw-ai-core` and `innoforge` (or similar). If you discover the seed lacks the second project needed for the project-switch verification, add an `e2e_fixtures/001_two_projects.py` file exporting `def seed(db: Session) -> None` that inserts two enabled projects, then re-run the seed inside the `app` container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

NEVER run the seed from the host shell.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify)

The agent visits every page route referenced in V1..V5, checks fragment refs / IDs / load-time console errors, and flags any dangling reference as a V0 FAIL. V1..V5 still run on V0 fail.

### V1: Project selector renders in the panel

1. Navigate to `$IW_BROWSER_BASE_URL/` (the root).
2. `playwright-cli snapshot` — locate the AI Assistant panel toggle.
3. Click the AI Assistant toggle (the chat icon in the top bar) to open the panel.
4. **Verify:** within the panel header, a `<select id="chat-assistant-project-select">` is visible AND has at least one populated `<option>` (not just "Loading…").
5. **Verify:** the dropdown's currently selected value matches the response from `GET /api/chat/projects` returned alphabetically (the first project, since URL is `/`).
6. **Screenshot:** `ai-dev/active/F-00091/evidences/post/F-00091_v1_selector_visible.png`.

### V2: Switching the dropdown changes the tab strip

1. With the panel still open from V1, `playwright-cli snapshot` again.
2. `playwright-cli select <select-ref> <second-project-id>` — pick a different project from the dropdown.
3. Wait for the tab strip to settle.
4. **Verify:** the tab strip now shows tabs scoped to the newly selected project. Tab titles or count should differ from V1.
5. **Verify:** the dropdown's selected value matches the newly chosen project.
6. **Screenshot:** `ai-dev/active/F-00091/evidences/post/F-00091_v2_after_dropdown_switch.png`.

### V3: URL navigation does NOT change the Assistant's project (AC1)

1. With the panel showing project B from V2, navigate to a sidebar link for project A: `playwright-cli snapshot` → click the project-A link in the sidebar.
2. Wait for the page to load (`playwright-cli snapshot` afterwards confirms the URL changed).
3. **Verify:** the URL is now project A's project page.
4. **Verify:** the AI Assistant dropdown STILL reads project B (NOT project A).
5. **Verify:** the tab strip STILL shows project B's tabs.
6. Navigate to `$IW_BROWSER_BASE_URL/system/status` next.
7. **Verify:** the AI Assistant dropdown STILL reads project B and the tab strip STILL shows project B's tabs (the system page does NOT clear them).
8. **Screenshot:** `ai-dev/active/F-00091/evidences/post/F-00091_v3_url_navigation_no_swap.png`.

### V4: Per-project active-tab restoration (AC2)

1. Switch the dropdown back to project A.
2. Snapshot, then click the second tab in the tab strip (NOT the first). Use the per-tab inline title text to disambiguate via snapshot refs.
3. **Verify:** the messages area swaps to that tab's content; the composer's title input (if expanded) reflects the new title.
4. Switch the dropdown to project B.
5. Switch back to project A.
6. **Verify:** the previously chosen tab is the active one (NOT `_tabs[0]`). Compare the tab title text against the title clicked in step 2.
7. **Verify:** the message area shows that tab's chat history (assuming the tab has existing messages from the seed; if not, the verification is "the active-tab indicator is on the same tab" — capture the screenshot regardless).
8. Now reload the page (`playwright-cli reload`).
9. **Verify:** the same tab is still active after reload.
10. **Screenshot:** `ai-dev/active/F-00091/evidences/post/F-00091_v4_tab_restored_after_reload.png`.

### V5: Context-usage progress bar (AC3 known + AC4 unknown)

1. With an active tab on project A, snapshot the panel.
2. **Verify (known branch — only IF the seed has a tab with a model that has a configured context window):** a `<div id="chat-assistant-context-pct">` is visible in the composer area, contains a child `.chat-assistant-context-pct__bar` and a child `.chat-assistant-context-pct__label`, and the label reads `<n>%` (not `—%`). The bar's fill width is non-zero. Hover over the element with `playwright-cli hover` and assert the `title` attribute contains "tokens".
3. **Verify (unknown branch):** if NO seed tab exposes a known model, or if you can switch to a tab whose model has no `context_window_tokens` row, the label MUST read `—%` and the element MUST still be visible (NOT `display:none`). The `title` attribute / tooltip must contain a phrase like "unknown" or "not configured".
4. If neither known nor unknown branch can be exercised from the seed, add an `e2e_fixtures/002_context_pct_branches.py` file that inserts two ChatTab rows (one Pi tab with a model that has `context_window_tokens` set, one Pi tab with a model where it's NULL), re-run the seed, and retry.
5. **Screenshot:** `ai-dev/active/F-00091/evidences/post/F-00091_v5_progress_bar.png`.

### V6: No regressions

1. Open the panel; verify the per-tab settings panel (cogwheel button → Title / Runtime / Model row) still opens and saves.
2. Verify the Clear button, Abort button, and Send button still appear in the composer.
3. Verify the skills tray (`?` button in the header) still opens and lists skills.
4. Verify the tabs strip "+ New Tab" button still creates a tab.
5. **Verify:** no JS errors logged to console on any page visited during V1..V5 (read `.playwright-cli/console-*.log` if present).
6. **Screenshot:** `ai-dev/active/F-00091/evidences/post/F-00091_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Classify any failure:

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Element rendered cleanly but data missing because seed lacks it | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + add fixture |
| Page rendered cleanly, element correctly absent per design, V step asks for it anyway | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` |
| Page rendered cleanly, design says element should be present, it isn't | CODE_DEFECT | normal `--reason` |

Do NOT write "blocked by V2 — n/a" chains. The agent is responsible for creating preconditions (fixtures, dashboard CLI calls, direct DB writes if design supplies SQL).

## Report

Write `ai-dev/active/F-00091/reports/F-00091_S19_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V6.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found with `file:line` references.
- A list of screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V6.

Then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00091/reports/F-00091_S19_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00091/reports/F-00091_S19_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "qv-browser",
  "work_item": "F-00091",
  "overall_status": "pass|fail",
  "v_results": [
    {"v": "V0", "status": "pass|fail", "summary": "..."},
    {"v": "V1", "status": "pass|fail", "summary": "..."},
    {"v": "V2", "status": "pass|fail", "summary": "..."},
    {"v": "V3", "status": "pass|fail", "summary": "..."},
    {"v": "V4", "status": "pass|fail", "summary": "..."},
    {"v": "V5", "status": "pass|fail", "summary": "..."},
    {"v": "V6", "status": "pass|fail", "summary": "..."}
  ],
  "evidence": [
    "ai-dev/active/F-00091/evidences/post/F-00091_v1_selector_visible.png",
    "ai-dev/active/F-00091/evidences/post/F-00091_v2_after_dropdown_switch.png",
    "ai-dev/active/F-00091/evidences/post/F-00091_v3_url_navigation_no_swap.png",
    "ai-dev/active/F-00091/evidences/post/F-00091_v4_tab_restored_after_reload.png",
    "ai-dev/active/F-00091/evidences/post/F-00091_v5_progress_bar.png",
    "ai-dev/active/F-00091/evidences/post/F-00091_v6_no_regressions.png"
  ],
  "notes": ""
}
```
