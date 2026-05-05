# Browser Verification Prompt: I-00065-S15-BrowserVerification

**Work Item**: I-00065 -- Code-view chat panel — "+ New" visible when collapsed and duplicates greeting
**Step**: S15
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
infrastructure containers are outside your scope. The IW orchestrator has
already started the per-worktree e2e stack — do NOT attempt to start, stop,
or rebuild it. `docker compose -p "$COMPOSE_PROJECT_NAME" exec app ...` is
the ONLY allowed compose verb (used to re-run the seed if you add a fixture).

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does not involve migrations. Do not run any state-changing
alembic command. Read-only `alembic history / current / show` is allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no `localhost:3100`). Always use the env var.

Do NOT run any of the following:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/build` command — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00065/I-00065_Issue_Design.md` -- the design document
- `dashboard/templates/chat/panel.html`
- `dashboard/static/chat/panel.js`

## Output Files

- `ai-dev/active/I-00065/reports/I-00065_S15_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00065/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs (e10, e12, ...)
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00065/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump`. It reflects current production state.

This incident verifies frontend behaviour of the Code chat panel; it requires:

- At least one project that already has a built Code index (so the Code tab renders fully and the chat panel mounts).

If no such project exists in the seeded data, that's an `ENV_DATA_MISSING` situation — add a fixture that seeds a minimal indexed project under `ai-dev/active/I-00065/e2e_fixtures/001_indexed_project_for_chat_panel.py` and re-run the seed inside the `app` container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell.** The host's `.env` resolves to the production orchestration DB on port 5433.

## Verification Steps

### V1: "+ New" button is hidden when chat panel is collapsed

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. Click into any project that has the Code tab populated, then navigate to `Code` (the route is `/project/{id}/code`).
3. Wait for the chat panel on the right to render. The panel's default state is collapsed (`data-collapsed="true"` on `#chat-panel`); confirm via snapshot that the rail icon and rotated "Chat" label are present.
4. **Verify:** the snapshot for `#chat-new-btn` (the button labelled "New") shows it as **not visible** to the accessibility tree, AND a screenshot does not show the "+ New" text inside the rail.
5. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00065/evidences/post/I-00065_v1_collapsed_no_new_button.png`.

### V2: Clicking "+ New" produces exactly one "Ask about this module" greeting

1. While still on the Code page, click the rail (or press `Cmd+\`) to expand the chat panel — this triggers `togglePanelWithReplay` in `panel.js`.
2. Snapshot to confirm the expanded panel header now shows BOTH the title ("Chat — …") AND the "+ New" button.
3. Click the "+ New" button THREE times in succession (with a brief `playwright-cli snapshot` between each to ensure the click registers).
4. **Verify:** after the third click, the page contains EXACTLY ONE element with the text "Ask about this module" and the message list `#chat-messages` contains EXACTLY ONE child div with `id="chat-empty-state"`. (You can confirm via snapshot — accessible-name lookup on "Ask about this module" should return a single ref. If there are zero or more than one, the bug is not fixed.)
5. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00065/evidences/post/I-00065_v2_single_greeting_after_3_clicks.png`.

### V3: No Regressions

1. Re-collapse the chat panel via the rail/Cmd+\, then re-expand. Confirm the empty state is still present and singular.
2. Type a quick message into the composer (`#chat-input`) and click Send — confirm the user bubble appears (this exercises the composer flow that S01 did not touch). Assistant streaming may or may not complete depending on RAG availability in the e2e env; the user-side echo is sufficient.
3. Click "+ New" once more — confirm the user bubble disappears and exactly one greeting block returns.
4. Visit `$IW_BROWSER_BASE_URL/healthz/identity` and confirm a 200 response (sanity check the dashboard is still serving normally).
5. Verify no new console errors appeared on any page visited during V1..V2 (capture `playwright-cli` console output if your build of the CLI exposes it; otherwise note "no console-error capture available in this CLI build").
6. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00065/evidences/post/I-00065_v3_no_regressions.png`.

## Pass Criteria

V1, V2, V3 must all pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the chat panel renders but the bug is still present (V1 still shows the "+ New" button in the rail, V2 still shows multiple greetings). Use a normal `--reason`.
- **ENV_DATA_MISSING** — the e2e DB has no project with a built Code index, so the Code page can't be exercised. Prefix the reason:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 needs a project with a built Code index — add ai-dev/active/I-00065/e2e_fixtures/001_indexed_project_for_chat_panel.py" \
    --report ai-dev/active/I-00065/reports/I-00065_S15_BrowserVerification_Report.md
  ```

## Report

After verification, write `ai-dev/active/I-00065/reports/I-00065_S15_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V3.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if you investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V3.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00065/reports/I-00065_S15_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00065/reports/I-00065_S15_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "I-00065",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "+ New hidden in collapsed rail", "status": "pass|fail", "screenshot": "evidences/post/I-00065_v1_collapsed_no_new_button.png", "notes": ""},
    {"id": "V2", "name": "Exactly one greeting after 3 + New clicks", "status": "pass|fail", "screenshot": "evidences/post/I-00065_v2_single_greeting_after_3_clicks.png", "notes": ""},
    {"id": "V3", "name": "No regressions on adjacent flows", "status": "pass|fail", "screenshot": "evidences/post/I-00065_v3_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
