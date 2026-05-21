# Browser Verification Prompt: CR-00068-S07-BrowserVerification

**Work Item**: CR-00068 -- AI Assistant — Remove Per-Tab Model Bar
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

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic migration commands against the live
orchestration DB. This work item adds no migrations.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var. Do NOT hardcode application
route paths — navigate via the UI where possible. Before asserting on the
content of any page, first confirm the page loaded successfully (HTTP 200, no
unhandled-exception page, no load-time console errors).

Do NOT run `make dev`, `make e2e-up`, any `docker compose` command,
`playwright install`, `agent-browser`, or any `chromium.launch()` snippet.
Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/CR-00068/CR-00068_CR_Design.md` -- the design document
- `dashboard/templates/chat_assistant/panel.html`
- `dashboard/static/chat_assistant/chat.js`

## Output Files

- `ai-dev/active/CR-00068/reports/CR-00068_S07_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00068/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the dashboard presents a login form, log in with the provided credentials
(snapshot first to get element refs). If the project home renders directly,
proceed.

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read
   the current accessible element IDs. Do not guess selectors.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00068/evidences/post/` with
   descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB. The
AI Assistant panel auto-creates a default chat tab for a project on first open,
so no extra fixture is required to exercise the UI.

## Verifications

### V0: Pre-flight page sanity

Open `$IW_BROWSER_BASE_URL`, navigate to a per-project page (project home).
Confirm HTTP 200, no unhandled-exception page, and no load-time console
errors. Screenshot: `evidences/post/V0_project_home.png`.

### V1: Model bar is gone

Open the AI Assistant panel (click the collapsed "AI Assistant" expand rail,
or press Ctrl+/). With a chat tab active, confirm there is **no** model bar
above the messages area: no `#chat-assistant-tab-model-bar`, no
`#chat-assistant-tab-model-badge` button, and no `#chat-assistant-tab-model-dropdown`
in the panel. Screenshot: `evidences/post/V1_no_model_bar.png`.

### V2: Model is still changeable via the settings panel

With a chat tab active, click the settings/hamburger button
(`#chat-assistant-settings-btn`) to open the settings panel. Confirm the panel
shows a Model `<select>` (`#chat-assistant-settings-model`). Change the model
to a different available value and click Save. Confirm the save succeeds (no
error message) and the tab's model updates. Screenshot:
`evidences/post/V2_settings_model_change.png`.

### V3: Tab-strip model badge is kept

Confirm the tab strip still renders a small model badge on each tab button
(the `.chat-assistant-tab-model-badge` element). After the V2 model change,
confirm the active tab's badge reflects the newly selected model. Screenshot:
`evidences/post/V3_tab_strip_badge.png`.

### V4: No regressions

Confirm: switching between tabs works (create a second tab if needed); the
skills tray toggle, the recent-closed-tabs history dropdown, and the composer
(Clear / Abort / Send) all still work; collapsing and re-expanding the whole
AI Assistant panel works. Send a short message in a tab and confirm the chat
still streams a response normally. Check the browser console for errors
throughout — there must be none referencing removed model-bar elements or
functions. Screenshot: `evidences/post/V4_no_regressions.png`.

## Pass Criteria

- `pass` only if every V0–V4 passed.
- If the environment cannot be provisioned, call `iw step-fail` with a reason
  prefixed `ENV_DATA_MISSING:`.

## Report

After verification, write
`ai-dev/active/CR-00068/reports/CR-00068_S07_BrowserVerification_Report.md`
containing:

- A pass/fail table with one row per V0..V4.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if root cause was investigated.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V4.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00068/reports/CR-00068_S07_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00068/reports/CR-00068_S07_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "qv-browser",
  "work_item": "CR-00068",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Model bar is gone", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Model changeable via settings panel", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Tab-strip model badge kept", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed or was legitimately `n/a`.
- `overall_failure_class`: most severe class observed; `null` when `pass`.
- `base_url_used`: the concrete URL actually hit.
- `console_errors_observed`: any console errors seen during any V(n).
