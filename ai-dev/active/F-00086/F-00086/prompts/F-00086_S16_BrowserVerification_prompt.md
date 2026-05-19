# Browser Verification Prompt: F-00086-S16-BrowserVerification

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Step**: S16
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
infrastructure containers are outside your scope.

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

`docker compose exec app` is allowed and required when re-running the seed
after writing a fixture file.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against any DB from your step.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or routes. The port is allocated per-worktree.

Do NOT run any of the following — they will break the isolated stack:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — use `playwright-cli` exclusively
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — the design document
- `ai-dev/active/F-00086/evidences/pre/F-00086-before-single-session-chat.png` — pre-state evidence
- All files modified by S03/S06/S07/S08 (recorded in their respective `_report.md` files)

## Output Files

- `ai-dev/active/F-00086/reports/F-00086_S16_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/F-00086/evidences/post/` — screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in if the stack requires authentication:

```bash
playwright-cli snapshot
# If a login form is present, fill it:
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read current refs. Do not reuse refs from a previous page.
2. Wait for transitions before snapshotting again.
3. Screenshots go under `ai-dev/active/F-00086/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's Postgres is seeded from production via `pg_dump`. The iw-ai-core project itself is registered there. The runtime is OpenCode managed by the dashboard lifespan; the chat panel will reach a real (test) OpenCode runtime started inside the stack.

If a verification needs data not present in the seed (e.g., a prior OpenCode session for the bootstrap check), add an idempotent fixture under `ai-dev/active/F-00086/e2e_fixtures/001_<name>.py` and re-run the seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠ Never run `uv run python scripts/e2e_seed.py` from the host shell — `.env` resolves to production.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

Automatically prepended by qv-browser. Checks every distinct page route for dangling `hx-target`/`aria-controls`/`href="#X"`/`for="X"` references and load-time console errors.

### V1: Tab strip renders and "+" opens create-tab modal

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/`.
2. Click the "Expand AI Assistant panel" button to expand the chat panel.
3. **Verify:**
   - A tab strip is visible at the top of the chat panel.
   - A "+" button is visible at the right end of the strip.
   - Either: (a) the strip shows a "Default" tab seeded by bootstrap (the iw-ai-core project has prior OpenCode sessions in production data), OR (b) the empty-state message "No chats yet — click + to create one" appears.
4. Click the "+" button.
5. **Verify:** A modal opens containing fields: Project (locked to iw-ai-core), Runtime (dropdown with one option "OpenCode"), Model (dropdown populated from /api/chat/config), Title (text input).
6. **Screenshot:** `ai-dev/active/F-00086/evidences/post/F-00086_v1_create_tab_modal.png`.

### V2: Create two tabs with different models and verify per-tab independence

1. From the create-tab modal, set Title="Tab A", select the first model in the dropdown, click Create.
2. **Verify:** A new "Tab A" tab appears in the strip and becomes active. The composer is visible below.
3. Click "+" again. Set Title="Tab B", select a DIFFERENT model from the dropdown, click Create.
4. **Verify:** "Tab B" tab appears and becomes active. The per-tab model badge above the composer shows the second model's name.
5. Click "Tab A" in the strip.
6. **Verify:** The composer's per-tab model badge updates to show the first model's name (the badge is per-tab, not global).
7. Send a short prompt ("hello") in Tab A.
8. **Verify:** Streaming tokens appear in Tab A's message area within 10 seconds; no tokens appear in Tab B.
9. Click Tab B; send a different prompt ("hi").
10. **Verify:** Streaming tokens appear in Tab B; Tab A's last assistant message is unchanged.
11. **Screenshot:** `ai-dev/active/F-00086/evidences/post/F-00086_v2_two_tabs_independent.png`.

### V3: Tab persistence across page reload

1. With Tab A and Tab B both present from V2, refresh the browser (`playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/"` to reload).
2. Re-expand the AI Assistant panel.
3. **Verify:** Both "Tab A" and "Tab B" tabs are present in the strip.
4. Click each tab and verify the message history is restored (the prompts and assistant responses from V2 are visible).
5. **Screenshot:** `ai-dev/active/F-00086/evidences/post/F-00086_v3_tabs_persist_after_reload.png`.

### V4: Close a tab and reopen from recent-closed menu

1. Right-click "Tab A" → click "Close" in the context menu. (If no right-click menu exists in the UI, click an explicit × button on the tab.)
2. **Verify:** "Tab A" disappears from the main strip.
3. Click the "Recent closed" button at the right of the tab strip.
4. **Verify:** A dropdown opens listing "Tab A" with its model and a relative close-time.
5. Click "Tab A" in the dropdown.
6. **Verify:** "Tab A" reappears in the main strip with its full message history intact.
7. **Screenshot:** `ai-dev/active/F-00086/evidences/post/F-00086_v4_reopen_from_recent_closed.png`.

### V5: Per-tab abort

1. With Tab A active, send a longer prompt (e.g., "Write a haiku about software engineering and then explain each line in detail").
2. While Tab A is streaming, click "Tab B" to switch.
3. Send a quick prompt in Tab B ("hi").
4. Click "Tab A".
5. Click Tab A's "Abort" button.
6. **Verify:** Tab A's stream stops; Tab A's message area shows the partial response with an aborted indicator.
7. Switch to Tab B.
8. **Verify:** Tab B's response is intact (was not aborted by Tab A's abort action).
9. **Screenshot:** `ai-dev/active/F-00086/evidences/post/F-00086_v5_per_tab_abort.png`.

### V6: Runtime dropdown stub — only OpenCode

1. Click "+" to open the create-tab modal.
2. Click the "Runtime" dropdown.
3. **Verify:** Exactly one option is listed: "OpenCode". No "Pi" option appears.
4. Close the modal without submitting.
5. **Screenshot:** `ai-dev/active/F-00086/evidences/post/F-00086_v6_runtime_dropdown_opencode_only.png`.

### V7: No Regressions

1. Re-visit adjacent dashboard flows that share UI surface with the AI Assistant panel:
   - The dashboard home (`/project/iw-ai-core/`) renders without 5xx and without console errors.
   - The Queue page (`/project/iw-ai-core/queue` or the link from the dashboard sidebar) renders.
   - The Code page (`/project/iw-ai-core/code`) renders.
2. Verify the toggle-AI-Assistant-panel button (Ctrl+/) still works.
3. **Verify:** No new console errors appeared during V1..V6.
4. **Screenshot:** `ai-dev/active/F-00086/evidences/post/F-00086_v7_no_regressions.png`.

## Pass Criteria

All V1..V7 must pass. Any failure requires `iw step-fail` with a classified reason (CODE_DEFECT / ENV_DATA_MISSING / SPEC_MISMATCH per the qv-browser template).

## Report

After verification, write `ai-dev/active/F-00086/reports/F-00086_S16_BrowserVerification_Report.md` containing:

- Pass/fail table with one row per V1..V7.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with file:line references if root-caused.
- List of captured screenshots (relative paths under `evidences/post/`).
- A "No regressions observed" subsection covering V7.

Then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00086/reports/F-00086_S16_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason with classification prefix if applicable>" \
  --report ai-dev/active/F-00086/reports/F-00086_S16_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "F-00086",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Tab strip renders; + opens modal", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Two tabs independent with different models", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Tab persistence across reload", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Close and reopen from recent-closed", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Per-tab abort", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Runtime dropdown OpenCode-only", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V7", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
