# Browser Verification Prompt: F-00083-S18-BrowserVerification

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S18
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only introspection (`docker ps`, `docker inspect`, `docker logs`); `./ai-core.sh` and `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head`, `alembic upgrade <rev>`, `alembic downgrade <anything>`, or `alembic stamp <anything>` against the live orchestration DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use `$IW_BROWSER_BASE_URL`. Do NOT hardcode application route paths — navigate via the UI where possible.

Before asserting on the *content* of any page, first confirm the page itself **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors).

Do NOT run any of the following:
- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — the design document
- Files modified by S01–S04 (subset; the prompt does not need to enumerate them — use the design as the contract):
  - `orch/chat/*`
  - `dashboard/routers/chat.py`
  - `dashboard/app.py`
  - `dashboard/templates/base.html`
  - `dashboard/templates/chat_assistant/*`
  - `dashboard/static/chat_assistant/*`
  - `.opencode/config.json`
  - 7 per-page templates that register context

## Output Files

- `ai-dev/active/F-00083/reports/F-00083_S18_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/F-00083/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the dashboard has an authentication wall, then log in with the provided credentials (use `playwright-cli snapshot` first to get accessible element refs). If the worktree e2e stack runs without auth, skip the login flow and note it in the report.

## Pre-flight: OpenCode runtime availability

This feature depends on `opencode serve` being available in the worktree e2e stack. Before running any V(n) check, verify the runtime is healthy:

```bash
playwright-cli open "${IW_BROWSER_BASE_URL}/api/chat/config"
```

- If the response is JSON with a `models` array: PASS — proceed with V1..V(n).
- If the response is `503 {"error": "OpenCode runtime unavailable"}`: the OpenCode binary is not available in this worktree's e2e stack. Mark this run as `spec_mismatch` (NOT `code_defect`), report the gap, recommend that the worktree-compose configuration include the OpenCode binary, and exit. Do NOT proceed with the V(n) checks (they will all fail for the same reason and provide no signal).

## Verifications

### V1 — Ctrl+/ toggles the panel (AC1)

1. Navigate to the dashboard root (`$IW_BROWSER_BASE_URL/`).
2. Verify HTTP 200 and no console errors.
3. Take a screenshot: `evidences/post/F-00083-v1-before-toggle.png`. Confirm the Dashboard AI Assistant panel is **collapsed** (40 px rail, or hidden).
4. Press Ctrl+/ via `playwright-cli` (use `playwright-cli press_keys "Control+/"` or the equivalent — check the CLI's keypress syntax).
5. Take a screenshot: `evidences/post/F-00083-v1-after-toggle.png`. Confirm the panel is expanded (360 px wide, header visible, composer visible).
6. Press Ctrl+/ again. Confirm the panel collapses.
7. Navigate to a different page (e.g., Projects → click any project). Confirm the panel state persists (cookie). Verify with another screenshot.

### V2 — Prompt → stream → approval → abort (AC2)

1. With the panel expanded, click into the composer (`#chat-assistant-input`).
2. Type a prompt that will trigger a `bash` tool (which is gated by `permission.bash = ask`). Example: `run ls in dashboard/routers`.
3. Click Send.
4. Observe the streaming response — text deltas should appear in real time. Take a screenshot mid-stream.
5. When the agent attempts `bash`, the approval modal must render. Take a screenshot. The modal must show the bash command + Allow + Deny + (optional) Remember.
6. Click Deny once — the tool is blocked, the agent reports.
7. Send another prompt that triggers another `bash` (e.g., re-run). When the modal appears, click Allow. Confirm the tool runs and the result streams back.
8. Send a longer prompt that takes >10 s. Mid-stream, click Abort. Confirm streaming stops within ~2 s and the transcript shows an aborted-run indicator.

### V3 — Per-tab independent sessions (AC3)

1. Open two browser tabs at the dashboard root.
2. In tab A, prompt "count to 5 slowly with one bash echo per number." In tab B, prompt "list the dashboard routers."
3. Observe both panels stream independently. Take a screenshot of each tab.
4. Verify the transcripts do NOT interleave. Confirm via `playwright-cli snapshot` that each panel has its own `#chat-assistant-` DOM tree.

### V4 — Model selector (AC4)

1. Open the model selector dropdown in tab A.
2. Confirm it lists multiple models (the exact list depends on `.opencode/config.json` providers).
3. Select a different model and submit a follow-up prompt. The new prompt should use the new model — verify in the agent's first turn output (usually the model name is in metadata) OR via the network panel showing the `model` field in the POST body.

### V5 — Skills + commands tray + `/` autocomplete (AC5)

1. Click the "?" tray. Verify it shows two sections: Skills (e.g., `iw-research`, `iw-new-feature`) and Commands.
2. Each entry shows name + description.
3. Close the tray. In the composer, type `/`. Verify an autocomplete list appears. Type `re`. Verify it filters to entries containing `re`.

### V6 — Tab-refresh reconnect with Last-Event-ID (AC6)

1. In tab A, start a prompt that takes >15 s.
2. Mid-stream, press F5 to reload the tab.
3. After reload, confirm the panel re-opens (cookie state) and the active session's transcript is restored.
4. Verify in browser DevTools Network panel that the new EventSource connection sends a `Last-Event-ID` header (or via `playwright-cli evaluate "..." ` to inspect).
5. Verify the agent loop continued running upstream — the transcript should not appear "frozen."

### V7 — Research view deep-link (AC7)

1. Navigate to the Research library page.
2. Locate the "Create new research" button.
3. Click it. Confirm the chat panel opens (if collapsed) and the composer is pre-populated with `/iw-research ` (with trailing space) and focus is in the composer.

### V8 — "Currently viewing X" chip (AC8)

1. Navigate to any item-detail page (e.g., click an item from the Queue).
2. Open the chat panel.
3. Verify a chip "Currently viewing: <item_id> (<item_title>)" is rendered above the composer.
4. Click the X on the chip. Verify the chip disappears.
5. Send a prompt without re-opening; verify the chip does NOT come back this session.
6. Navigate to a batch-detail page. Open the chat panel. Verify the chip now shows the batch (the previous dismissal was per-session).

### V9 — Context % indicator (AC9)

1. Start a long-running prompt.
2. Observe the context % indicator near the model selector. Verify it updates at least once during the stream.
3. When the agent reports done (`session.idle`), verify the polling stops within ~5 s (no more network requests to `/api/chat/sessions/{sid}` after that).

### V10 — Regression guard: existing Code Q&A chat unchanged (AC10) — CRITICAL

1. Navigate to any project's Code view (Code tab in the project nav).
2. Confirm the existing **right-side** chat panel is still present (DOM id `#chat-panel`, not `#chat-assistant-panel`).
3. Press Cmd+\ (or Ctrl+\ on non-Mac) — verify it toggles the existing right-side chat.
4. Take a snapshot. Confirm the panel layout, fonts, and behaviour match the pre-FR baseline.
5. Verify Ctrl+/ in this view still toggles the Dashboard AI Assistant (left side), NOT the Code chat. The two must be independent.
6. **Any deviation here is a CRITICAL code_defect.**

### V(n) — No Regressions

1. Browse to the dashboard's main pages: Projects, Queue, History, Batches, Tests, Quality, Jobs, Worktrees, Docs, Research.
2. For each page: confirm 200, no unhandled-exception page, no JS/HTMX console errors at load.
3. Confirm the existing SSE stream from `/api/stream/events` (the system-wide live updates) still works — open the page, watch for `running-update` / `toast` events in DevTools.
4. Confirm dark-mode toggle still works (regression guard for `base.html` edits).

## Pass Criteria

Every V(n) must PASS. Any FAIL is the verification's deliverable — write a clear, reproducible failure report with screenshots and the exact reproduction steps. V10's failure (regression in existing Code chat) is automatic-block of the merge.

## Report

Write `ai-dev/active/F-00083/reports/F-00083_S18_BrowserVerification_Report.md` with:
- Pre-flight result (OpenCode runtime healthy or spec_mismatch).
- V1..V10..V(n) results: each PASS / FAIL with evidence path.
- Console errors observed (if any).
- Network errors observed (if any).
- Performance notes (e.g., stream latency, panel toggle smoothness).

## Result Contract

```json
{
  "step": "S18",
  "agent": "qv-browser",
  "work_item": "F-00083",
  "result": "pass|fail|spec_mismatch",
  "verifications": {
    "V1": "pass|fail",
    "V2": "pass|fail",
    "V3": "pass|fail",
    "V4": "pass|fail",
    "V5": "pass|fail",
    "V6": "pass|fail",
    "V7": "pass|fail",
    "V8": "pass|fail",
    "V9": "pass|fail",
    "V10": "pass|fail",
    "V_no_regressions": "pass|fail"
  },
  "evidence_paths": [
    "ai-dev/active/F-00083/evidences/post/F-00083-v1-before-toggle.png",
    "..."
  ],
  "console_errors": [],
  "network_errors": [],
  "notes": "OpenCode runtime: healthy|unavailable. Regression-guard (V10): PASS|FAIL."
}
```
