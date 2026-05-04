# Browser Verification Prompt: F-00077-S19-BrowserVerification

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step**: S19
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

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a
blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live orch
DB (port 5433). Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `localhost:5173`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide.

Do NOT run any of:
- `make dev`, `make e2e-up`, `docker compose` — the stack is already up.
- `playwright install` — the CLI is pre-installed.
- `agent-browser` — this environment uses `playwright-cli` exclusively.
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`.

## Input Files

- `ai-dev/active/F-00077/F-00077_Feature_Design.md` — design (sections: AC1, AC2, AC3, AC4, AC9)
- `dashboard/static/chat/composer.js`
- `dashboard/static/chat/stream.js`
- `dashboard/static/chat/panel.js`
- `dashboard/templates/chat/panel.html`
- `dashboard/routers/code_qa.py`
- `dashboard/routers/conversations.py`

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S19_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/F-00077/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

This dashboard does not require a login screen (single-user dashboard, no auth). If a sign-in form is encountered, follow the standard pattern:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Otherwise proceed directly.

Rules for interacting:

1. Always run `playwright-cli snapshot` BEFORE `fill` / `click` to read fresh element refs. Do not reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots: `playwright-cli screenshot` (no path arg — saves to `.playwright-cli/page-<ts>.png`), then `cp .playwright-cli/page-*.png ai-dev/active/F-00077/evidences/post/F-00077_v{N}_{short_name}.png`.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump`. It reflects current production state.

For F-00077 verifications:
- The chat panel needs the `iw-ai-core` project in the projects table. This is the live project — already present.
- The Code Understanding index for `iw-ai-core` should have at least one indexed module so RAG retrieval has something to return. The production seed includes 564 indexed files (per the iw-ai-core code page status). This is sufficient.
- No new fixture is required for happy-path verifications.

If a verification fails because indexed content is missing (e.g. retrieval returns nothing for "keep_alive"), that's a CODE DEFECT (the index should always have current content). Do NOT classify as ENV_DATA_MISSING unless the index itself is empty.

## Verification Steps

### V1: AC1 — Naming recall across turns

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code`.
2. Snapshot the page; locate the chat panel. If collapsed, click the expand rail (`#chat-expand-rail`) — this opens the chat panel. Rationale: chat panel starts collapsed by default per `panel.html`.
3. Click the "New chat" button (`#chat-new-btn`) — this guarantees a fresh conversation regardless of prior browser state. Rationale: V1 requires a clean slate.
4. Snapshot; locate the message input textarea (`#chat-input` or whichever id the composer uses — read from snapshot).
5. Fill the input with `my name is sergio`.
6. Click the send button. Wait for the assistant reply to finish streaming (look for the disappearance of any "thinking" / phase indicator and a stable message bubble).
7. Snapshot; locate the input again; fill with `what is my name?`.
8. Click send. Wait for completion.
9. **Verify:** the assistant's second answer text contains "sergio" (case-insensitive substring match on the rendered text from the snapshot).
10. **Screenshot:** `ai-dev/active/F-00077/evidences/post/F-00077_v1_name_recall.png`.

### V2: AC2 — Follow-up retrieval is contextualized

1. Click "New chat" again to start fresh.
2. Snapshot; fill the input with `what does keep_alive do in orch/daemon/main.py?`.
3. Send. Wait for completion. Capture the answer text.
4. Fill input with `explain how it works`.
5. Send. Wait for completion. Capture the answer text.
6. **Verify:** the second answer mentions at least one of: `keep_alive`, `main.py`, `daemon` (case-insensitive). Verify by inspecting the message-bubble text in the snapshot.
7. **Verify:** the second answer's citations panel (if rendered) references at least one chunk from `orch/daemon/main.py` (or another file plausibly related to keep_alive). If no citations panel is visible, accept the answer-text check as sufficient.
8. **Screenshot:** `ai-dev/active/F-00077/evidences/post/F-00077_v2_followup_retrieval.png`.

### V3: AC3 — Refresh persistence within TTL

1. Note the current visible messages (count and content).
2. Reload the page: `playwright-cli` doesn't have a literal reload — use `playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/code"` again. This re-loads the page in the same session (and same cookies/localStorage).
3. Snapshot. If the chat panel was previously expanded, it should reopen expanded (or be openable to reveal the same conversation). Open it via `#chat-expand-rail` if needed.
4. **Verify:** the previous turns from V2 are visible in the message list (the user "what does keep_alive do..." and "explain how it works" turns and their assistant replies are rendered).
5. **Screenshot:** `ai-dev/active/F-00077/evidences/post/F-00077_v3_refresh_persistence.png`.

### V4: AC4 — Explicit "New chat" reset

1. With the V3 conversation visible, click `#chat-new-btn`.
2. Snapshot.
3. **Verify:** the message log is empty (only the empty-state message visible: "Ask about this module" or equivalent placeholder text).
4. Send a new message: fill input with `hello`, send.
5. **Verify:** the new message is the FIRST message in the log; the previous V3 messages are gone (NOT just hidden — gone from the DOM).
6. **Screenshot:** `ai-dev/active/F-00077/evidences/post/F-00077_v4_new_chat_reset.png`.

### V5: No Regressions

1. Revisit the chat panel collapse/expand: click the collapse button (`#chat-collapse-btn`), then re-expand via the rail. Verify the panel still toggles correctly.
2. Open a slash-command menu by typing `/` in the input. Verify the menu still appears with the existing commands (`/explain`, `/diagram`, `/why`, `/findusages`, `/history`).
3. Navigate to a module page: snapshot the side nav, click "Modules" or browse to a specific module link. Verify the module page renders and the chat panel is still operational at the module level.
4. Send one message at the module level (e.g. "what does this do?") and verify the SSE stream completes (token events arrive, no console errors).
5. **Verify:** No new console errors appeared on any page visited during V1-V4 (call `playwright-cli` console-log inspection or read the `.playwright-cli/console-*.log` file from the open command).
6. **Screenshot:** `ai-dev/active/F-00077/evidences/post/F-00077_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** — the page returned an HTTP error, threw a console exception, rendered the wrong element, or the chat answer is empty/garbled. Use a normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly with HTTP 200 but the Code Understanding index is empty (`0 chunks`). Prefix the reason with `ENV_DATA_MISSING:` and request that the operator runs the indexer in the worktree stack:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: Code index empty in worktree stack — needs an iw code-index run for project iw-ai-core" \
    --report ai-dev/active/F-00077/reports/F-00077_S19_BrowserVerification_Report.md
  ```

## Report

After verification, write `ai-dev/active/F-00077/reports/F-00077_S19_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found with `file:line` references if root cause was investigated.
- A list of screenshots captured (relative paths under `evidences/post/`).
- A "No regressions observed" subsection covering V5.

Then call ONE of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00077/reports/F-00077_S19_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00077/reports/F-00077_S19_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "qv-browser",
  "work_item": "F-00077",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Naming recall (AC1)", "status": "pass|fail", "screenshot": "evidences/post/F-00077_v1_name_recall.png", "notes": ""},
    {"id": "V2", "name": "Follow-up retrieval (AC2)", "status": "pass|fail", "screenshot": "evidences/post/F-00077_v2_followup_retrieval.png", "notes": ""},
    {"id": "V3", "name": "Refresh persistence (AC3)", "status": "pass|fail", "screenshot": "evidences/post/F-00077_v3_refresh_persistence.png", "notes": ""},
    {"id": "V4", "name": "New chat reset (AC4)", "status": "pass|fail", "screenshot": "evidences/post/F-00077_v4_new_chat_reset.png", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "screenshot": "evidences/post/F-00077_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
