# Browser Verification Prompt: CR-00069-S07-BrowserVerification

**Work Item**: CR-00069 -- AI Assistant — Remove Clear Button Confirmation Dialog
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

- `ai-dev/active/CR-00069/CR-00069_CR_Design.md` -- the design document
- `dashboard/static/chat_assistant/chat.js`
- `tests/dashboard/test_chat_clear_button.py`

## Output Files

- `ai-dev/active/CR-00069/reports/CR-00069_S07_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00069/evidences/post/` -- screenshots taken during verification

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
3. Screenshots go under `ai-dev/active/CR-00069/evidences/post/` with
   descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB. The
AI Assistant panel auto-creates a default chat tab for a project on first open.
To exercise the Clear button you need a tab **with history** — send a message
in a tab first so the Clear button becomes enabled.

## Verifications

### V0: Pre-flight page sanity

Open `$IW_BROWSER_BASE_URL`, navigate to a per-project page (project home).
Confirm HTTP 200, no unhandled-exception page, and no load-time console
errors. Screenshot: `evidences/post/V0_project_home.png`.

### V1: Clear button is disabled on an empty chat

Open the AI Assistant panel (click the collapsed "AI Assistant" expand rail,
or press Ctrl+/). On a fresh / empty chat tab, confirm the Clear button
(`#chat-assistant-clear`) is `disabled`. Screenshot:
`evidences/post/V1_clear_disabled_empty.png`.

### V2: Clear clears immediately with no confirmation popup

In a chat tab, send a short message and wait for a response so the tab has
history and the Clear button becomes enabled. Click the Clear button. Confirm:
- **No** `window.confirm` / native confirmation dialog appears (the chat is
  cleared without any popup or dialog to accept). If `playwright-cli` exposes a
  dialog handler, confirm no dialog event fired; otherwise confirm the messages
  area emptied immediately after the single click with no intervening prompt.
- The conversation messages are removed.
Screenshot: `evidences/post/V2_clear_no_popup.png`.

### V3: "Chat cleared." feedback is shown

After the V2 clear, confirm a "Chat cleared." system message is shown in the
conversation area, and the Clear button has returned to the `disabled` state.
Screenshot: `evidences/post/V3_chat_cleared_message.png`.

### V4: No regressions

Confirm: after clearing, a new message can be sent in the same tab and it
streams a response normally; tab switching, the skills tray toggle, and the
composer (Abort / Send) still work. Check the browser console for errors
throughout — there must be none. Screenshot:
`evidences/post/V4_no_regressions.png`.

## Pass Criteria

- `pass` only if every V0–V4 passed.
- If the environment cannot be provisioned, call `iw step-fail` with a reason
  prefixed `ENV_DATA_MISSING:`.

## Report

After verification, write
`ai-dev/active/CR-00069/reports/CR-00069_S07_BrowserVerification_Report.md`
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
  --report ai-dev/active/CR-00069/reports/CR-00069_S07_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00069/reports/CR-00069_S07_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "qv-browser",
  "work_item": "CR-00069",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Clear disabled on empty chat", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Clear clears immediately, no popup", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Chat cleared feedback shown", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
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
