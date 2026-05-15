# Browser Verification Prompt: CR-00054-S18-BrowserVerification

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S18
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. The IW orchestrator has **already** started the isolated E2E stack — do NOT attempt to start, stop, or rebuild any services. Read-only `docker ps` / `docker inspect` / `docker logs` are allowed.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch migrations.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from this worktree's source code, including the new OpenCode stub.

**Base URL:** `$IW_BROWSER_BASE_URL`
**E2E credentials:** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers:** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports, application route paths, or credentials. Use the env vars above.

Before asserting on the *content* of any page, first confirm the page itself **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors).

Do NOT run any of:
- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` / `npx playwright install`
- `agent-browser`
- Any `chromium.launch()` Python/Node snippet

## Input Files

- `ai-dev/active/CR-00054/CR-00054_CR_Design.md`
- `scripts/e2e_opencode_stub.py` (new in this CR)
- `Dockerfile.e2e` (modified by S02)
- `docker-compose.e2e.yml` (modified by S03)

## Output Files

- `ai-dev/active/CR-00054/reports/CR-00054_S18_BrowserVerification_Report.md`
- `ai-dev/active/CR-00054/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the dashboard has an auth wall, log in with the provided credentials. If the worktree e2e stack runs without auth, skip the login flow and note it in the report.

## Pre-flight: OpenCode stub reachability

This CR exists to make `/api/chat/config` return 200 inside the e2e stack. Verify the stub is doing its job:

```bash
playwright-cli open "${IW_BROWSER_BASE_URL}/api/chat/config"
```

- If the response is JSON with a `models` array containing at least one entry: PASS — proceed with V1..V(n).
- If the response is `503 {"error": "OpenCode runtime unavailable"}`: this is a CR-00054 **CODE_DEFECT** (the very thing this CR was supposed to fix). Capture the response and the e2e-dashboard container logs (`docker logs <container>` is read-only and allowed) and fail with `code_defect`.

## Verification Steps

### V1 — `/api/chat/config` returns a populated models array (AC1)

1. Navigate to `${IW_BROWSER_BASE_URL}/api/chat/config`.
2. **Verify:** HTTP 200, `Content-Type: application/json`, body parses as JSON, top-level keys include `models` and `default_model`, `models` is a non-empty list whose first entry has both `id` and `name` keys, `default_model` matches one of `models[*].id`.
3. **Screenshot:** `ai-dev/active/CR-00054/evidences/post/CR-00054_v1_config_endpoint.png`.

### V2 — Ctrl+/ opens the chat panel without console errors (AC2)

1. Navigate to `${IW_BROWSER_BASE_URL}/`.
2. Confirm HTTP 200 and no load-time JS/HTMX console errors.
3. Take a baseline screenshot (panel collapsed).
4. Press `Control+/` via `playwright-cli press_keys "Control+/"`.
5. **Verify:** the Dashboard AI Assistant panel is expanded (its left-sidebar container with `id="chat-assistant-panel"` or equivalent is visible; composer textarea is present). No console errors during the toggle.
6. **Screenshot:** `ai-dev/active/CR-00054/evidences/post/CR-00054_v2_panel_open.png`.

### V3 — Prompt → stream → permission.asked → approval modal (AC2)

1. With the panel open, click into the composer and type "list dashboard routers".
2. Click Send (or press Enter).
3. **Verify:** text deltas appear in the panel (streaming). After at most 5 s, an approval modal renders showing the synthetic `bash` request from the stub. Take a screenshot mid-flow.
4. Click Allow. **Verify:** the modal closes and one more `message.updated` from the stub appears, followed by a session-idle indicator.
5. **Screenshot:** `ai-dev/active/CR-00054/evidences/post/CR-00054_v3_permission_modal.png` and `ai-dev/active/CR-00054/evidences/post/CR-00054_v3_after_allow.png`.

### V4 — Deny path (AC2 secondary)

1. Send another prompt that will trigger another `permission.asked` from the stub.
2. When the modal appears, click Deny.
3. **Verify:** the modal closes, the panel shows an aborted-run indicator (the stub's `session.idle` with `permission_denied: true`).
4. **Screenshot:** `ai-dev/active/CR-00054/evidences/post/CR-00054_v4_deny.png`.

### V5 — Healthcheck integrity (AC3)

1. Read the e2e-dashboard container's health status via `docker inspect <container> --format '{{.State.Health.Status}}'`.
2. **Verify:** `healthy`. (If `unhealthy`, the new healthcheck is wedged — that's CR-00054 CODE_DEFECT.)
3. No screenshot — record the docker output in the report.

### V_no_regressions — Adjacent flows unchanged (AC3)

1. Navigate to each of: Projects, Queue, History, Batches, Tests, Quality, Jobs, Worktrees, Docs, Research. For each: confirm HTTP 200, no console errors at load.
2. Open the existing **right-side** Code Q&A chat on a project's Code page (DOM id `#chat-panel`, NOT `#chat-assistant-panel`) and press `Cmd+\` (or `Ctrl+\`). **Verify:** that panel still toggles independently of the left-sidebar Dashboard AI Assistant.
3. Confirm dark-mode toggle still works.
4. **Screenshot:** `ai-dev/active/CR-00054/evidences/post/CR-00054_vN_no_regressions.png`.

## Pass Criteria

Every V must PASS. Any FAIL is the verification's deliverable — write a clear, reproducible failure report. Distinguish CODE_DEFECT vs ENV_DATA_MISSING vs SPEC_MISMATCH per the standard template guidance.

## Report

Write `ai-dev/active/CR-00054/reports/CR-00054_S18_BrowserVerification_Report.md` with:
- Pre-flight result (stub reachable or not).
- V1..V_no_regressions: each PASS/FAIL with evidence path.
- Console / network errors observed.
- The exact `$IW_BROWSER_BASE_URL` used.

Then call:

```bash
# Pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00054/reports/CR-00054_S18_BrowserVerification_Report.md

# Fail
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<class>: <short specific reason>" \
  --report ai-dev/active/CR-00054/reports/CR-00054_S18_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S18",
  "agent": "qv-browser",
  "work_item": "CR-00054",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "/api/chat/config returns populated models", "status": "pass|fail", "failure_class": "...|null", "screenshot": "evidences/post/CR-00054_v1_config_endpoint.png", "notes": ""},
    {"id": "V2", "name": "Ctrl+/ opens chat panel", "status": "pass|fail", "failure_class": "...|null", "screenshot": "evidences/post/CR-00054_v2_panel_open.png", "notes": ""},
    {"id": "V3", "name": "Prompt → stream → permission.asked → allow", "status": "pass|fail", "failure_class": "...|null", "screenshot": "evidences/post/CR-00054_v3_permission_modal.png", "notes": ""},
    {"id": "V4", "name": "Deny path", "status": "pass|fail", "failure_class": "...|null", "screenshot": "evidences/post/CR-00054_v4_deny.png", "notes": ""},
    {"id": "V5", "name": "Healthcheck reports healthy", "status": "pass|fail", "failure_class": "...|null", "screenshot": "", "notes": ""},
    {"id": "V_no_regressions", "name": "Adjacent flows unchanged", "status": "pass|fail", "failure_class": "...|null", "screenshot": "evidences/post/CR-00054_vN_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
