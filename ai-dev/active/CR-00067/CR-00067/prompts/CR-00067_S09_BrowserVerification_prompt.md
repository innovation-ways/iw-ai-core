# Browser Verification Prompt: CR-00067-S09-BrowserVerification

**Work Item**: CR-00067 -- AI Assistant — Context Usage Percentage Indicator
**Step**: S09
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

- `ai-dev/active/CR-00067/CR-00067_CR_Design.md` -- the design document
- `orch/chat/context_usage.py`
- `dashboard/routers/chat.py`
- `dashboard/templates/chat_assistant/composer.html`
- `dashboard/static/chat_assistant/chat.css`
- `dashboard/static/chat_assistant/chat.js`

## Output Files

- `ai-dev/active/CR-00067/reports/CR-00067_S09_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00067/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the dashboard presents a login form, log in with the provided credentials
(snapshot first to get element refs). The dashboard may not require auth — if
the project home renders directly, proceed.

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read
   the current accessible element IDs. Do not guess selectors.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00067/evidences/post/` with
   descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB. The
AI Assistant panel auto-creates a default chat tab for a project on first open,
so no extra fixture is required to exercise the UI.

`context_pct` is now computed by the backend (`get_tab`) from the active
session's real token usage. It is **absent** for a brand-new empty tab with no
assistant messages — that is expected and is itself part of what V2 verifies
(the label stays hidden when there is no data). To observe a populated
percentage and the colour bands, you may need to send one or more messages in a
tab. If a live agent run cannot be triggered in the E2E stack, verify the
colour-band logic instead by inspecting the served `chat.css` / `chat.js`
(see V3) rather than marking it `n/a`.

## Verifications

### V0: Pre-flight page sanity

Open `$IW_BROWSER_BASE_URL`, navigate to a per-project page (project home).
Confirm HTTP 200, no unhandled-exception page, and no load-time console
errors. Screenshot: `evidences/post/V0_project_home.png`.

### V1: Context % element exists left of the Clear button

Open the AI Assistant panel (click the collapsed "AI Assistant" expand rail,
or press Ctrl+/). With a chat tab active, snapshot the composer footer and
confirm a `#chat-assistant-context-pct` element exists in the Send/Abort row
and is positioned **before** (to the left of) the `#chat-assistant-clear`
button. Screenshot: `evidences/post/V1_context_pct_position.png`.

### V2: Label is hidden when there is no context data

On a freshly created / empty chat tab where the API returns no numeric
`context_pct`, confirm the `#chat-assistant-context-pct` element is NOT
visible (it carries the `hidden` class) — no `0%` placeholder is shown.
Screenshot: `evidences/post/V2_hidden_no_data.png`.

### V3: Context % is populated and colour bands apply

If a populated percentage can be produced in the E2E stack (send a message in a
tab and let it stream), confirm the `#chat-assistant-context-pct` label shows a
numeric value and that `chat.js` applies `is-crit` at `>=90`, `is-warn` at
`>=70 && <90`, and neither below 70. If a live run cannot be produced, confirm
the CSS rules `.chat-assistant-context-pct`, `.is-warn`, and `.is-crit` exist in
the served `chat_assistant/chat.css`, and that the class names applied in
`chat.js` match those selectors exactly. Screenshot:
`evidences/post/V3_colour_bands.png`.

### V4: Percentage appears on tab activation (no message needed)

Switch between chat tabs (create a second tab if only one exists). Confirm
that when a tab becomes active, the context percentage state updates promptly
(immediately, not only after a message is sent) — for a tab with data the
value shows at once; for a tab without data the label is hidden at once.
Screenshot: `evidences/post/V4_tab_activation.png`.

### V5: No regressions

Confirm the composer's Clear, Abort, and Send buttons, plus the per-tab model
bar, still render and are laid out correctly in the Send/Abort row — the new
element did not displace or overlap them. Send a short message in a tab and
confirm the chat still streams a response normally. Check the browser console
for errors throughout. Screenshot: `evidences/post/V5_no_regressions.png`.

## Pass Criteria

- `pass` only if every V0–V5 passed (or a V is legitimately `n/a` per the
  rules above — note that V3 must NOT be `n/a`; fall back to source inspection).
- If the environment cannot be provisioned, call `iw step-fail` with a reason
  prefixed `ENV_DATA_MISSING:`.

## Report

After verification, write
`ai-dev/active/CR-00067/reports/CR-00067_S09_BrowserVerification_Report.md`
containing:

- A pass/fail table with one row per V0..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if root cause was investigated.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V5.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00067/reports/CR-00067_S09_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00067/reports/CR-00067_S09_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "qv-browser",
  "work_item": "CR-00067",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Context % element exists left of Clear", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Label hidden when no data", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Context % populated and colour bands apply", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Percentage appears on tab activation", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
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
