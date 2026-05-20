# Browser Verification Prompt: CR-00063-S07-BrowserVerification

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Step**: S07
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var.

## Input Files

- `ai-dev/active/CR-00063/CR-00063_CR_Design.md` — Design document
- `dashboard/static/chat_assistant/chat.js` — Modified file
- `tests/dashboard/test_chat_history_restore.py` — New test file

## Output Files

- `ai-dev/active/CR-00063/reports/CR-00063_S07_BrowserVerification_Report.md`
- `ai-dev/active/CR-00063/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB. To verify history restoration, a chat tab with an existing runtime session and message history is needed. If no such tab exists in the seed data, add a fixture file `ai-dev/active/CR-00063/e2e_fixtures/001_chat_history_seed.py` that creates a ChatTab row with an `opencode_session_id` pointing to a pre-existing session — OR navigate the AI Assistant to send one message before testing the reload behavior.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> This verification is automatically prepended by the qv-browser agent. Work item authors do NOT need to write V0.

### V1: Chat history visible after page reload (AC1 + AC4)

1. Navigate to a project page at `$IW_BROWSER_BASE_URL` and open the AI Assistant panel.
2. If the active tab is empty (no history), send one message (e.g., type "Hello, who are you?" and submit) — this establishes a session with history.
3. Wait for the assistant response to complete (streaming ends).
4. Close the current browser session and open a new one: `playwright-cli kill-all`, then `playwright-cli open "$IW_BROWSER_BASE_URL"`.
5. Navigate back to the same project page and open the AI Assistant panel.
6. **Verify**: The previous message(s) are visible in the chat window without sending a new message. At minimum the user message bubble should be visible.
7. **Screenshot**: `ai-dev/active/CR-00063/evidences/post/CR-00063_v1_history_after_reload.png`.

### V2: Error state shown when history cannot be loaded (AC2)

1. On the same project page, open the AI Assistant panel.
2. Inspect the chat panel DOM to confirm that when a tab is active with a session, the history is either rendered OR an error banner is shown — but the panel is NOT silently empty without any feedback.
3. This V is partially observational: if V1 passed (history rendered), AC2 is exercised by the implementation even if not directly triggered in the browser. Note the result.
4. **Screenshot**: `ai-dev/active/CR-00063/evidences/post/CR-00063_v2_panel_state.png`.

### V3: Correct tab selected on fresh page load (AC3)

1. If multiple chat tabs are visible in the tab strip, note which one has the most recent activity.
2. Close and reopen the browser session (simulate sessionStorage clear as in V1).
3. Navigate back to the project page.
4. **Verify**: The AI Assistant panel activates the most recently used tab (visible by the tab strip highlighting and chat history content matching the most recently active tab, not necessarily the first in the list).
5. **Screenshot**: `ai-dev/active/CR-00063/evidences/post/CR-00063_v3_correct_tab_selected.png`.

### V4: No Regressions

1. Verify the composer input is still functional: type a message and confirm the Send button is enabled.
2. Verify existing chat tabs can still be switched by clicking tab buttons.
3. Verify no console errors appeared during V1–V3.
4. **Screenshot**: `ai-dev/active/CR-00063/evidences/post/CR-00063_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure requires `iw step-fail`. Classify per the CODE_DEFECT / ENV_DATA_MISSING / SPEC_MISMATCH framework.

## Report

After verification, write the report at `ai-dev/active/CR-00063/reports/CR-00063_S07_BrowserVerification_Report.md` then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00063/reports/CR-00063_S07_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00063/reports/CR-00063_S07_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "qv-browser",
  "work_item": "CR-00063",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Chat history visible after page reload", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Error state shown when history cannot be loaded", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Correct tab selected on fresh page load", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "No Regressions", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
