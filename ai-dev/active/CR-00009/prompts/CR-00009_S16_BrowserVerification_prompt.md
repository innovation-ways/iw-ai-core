# Browser Verification Prompt: CR-00009-S16-BrowserVerification

**Work Item**: CR-00009 — Chat panel context awareness
**Step**: S16
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no `localhost:3100`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment.

Do NOT run any of the following — they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make dashboard-start`, `make daemon-start`, `make test-e2e`, `make e2e-up`, or any `docker compose` command — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md` — the design document
- `dashboard/templates/chat/panel.html`
- `dashboard/templates/project_code.html`
- `dashboard/templates/fragments/code_module_detail.html`
- `dashboard/static/chat/panel.js`
- `dashboard/static/chat/composer.js`
- `dashboard/routers/code_qa.py`
- `orch/rag/qa.py`

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S16_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/CR-00009/evidences/post/` — screenshots

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials if the dashboard exposes an auth screen:

```bash
playwright-cli snapshot
# If a login form appears:
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

(This platform's dashboard may not require auth in the isolated stack — if no login form appears, proceed directly.)

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions (htmx swaps) to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00009/evidences/post/` with descriptive filenames.

## Verification Steps

### V1: Chat header shows "Chat — Architecture" on first paint (AC1)

1. Navigate to `{{IW_BROWSER_BASE_URL}}/projects/iw-ai-core/code` (or whichever project is seeded in the isolated stack — if `iw-ai-core` is not present, pick any project that has an indexed architecture doc and substitute its ID consistently in V2/V3/V4).
2. Wait for the page to fully render. Do not click any module yet.
3. **Verify:** the `#chat-context-label` element is visible in the chat panel header and its text is exactly `Chat — Architecture`. Use `playwright-cli snapshot` and confirm the role=heading node with that text exists.
4. **Verify:** the browser console has no errors.
5. **Screenshot:** `ai-dev/active/CR-00009/evidences/post/CR-00009_v1_architecture_header.png`.

### V2: Chat header updates to module path + name on module navigation (AC2)

1. From the architecture view, click a module entry in the sidebar — pick one whose name is visibly not a synthetic "test" entry (prefer "Orchestration Daemon" if present; otherwise the first real module). Record the path and name you picked (read from the sidebar link text).
2. Wait for the htmx swap into `#code-detail-panel` to complete (module navigation targets `#code-detail-panel`, NOT `#code-content-root` — the inline script at the end of `code_module_detail.html` mirrors attrs onto `#code-content-root` after the swap lands).
3. **Verify:** `#chat-context-label` text now equals `Chat — <path> (<name>)` where `<path>` and `<name>` match the module you clicked. The separator is a space, em-dash, space. The name is wrapped in parentheses.
4. **Verify:** the composer shows the `module:<path>` chip. **Important — this chip was a pre-existing dead read path before CR-00009; this V2 also verifies that the Option-A propagation fixed it.** If the chip does not appear, the `iw:code-context-changed` event wiring in `composer.js` is missing — FAIL.
5. **Verify:** `document.getElementById('code-content-root').dataset.modulePath` equals the module path string (inspect via `playwright-cli evaluate` if available, otherwise rely on V5 / the chip rendering as proof).
6. **Verify:** the browser console has no errors.
7. **Screenshot:** `ai-dev/active/CR-00009/evidences/post/CR-00009_v2_module_header.png`.

### V3: Chat reply references the module (AC3 + AC6)

1. From the module view selected in V2, focus the chat input (`#chat-input`) and type a question that names the module: `how does this module work?`.
2. Click the send button (`#chat-send`).
3. Wait for the streaming response to complete (up to 60 seconds — Ollama-backed, local inference). If streaming stalls past 60s in the isolated stack, record as a partial pass with a note that Ollama was slow — the contract you're verifying is the *text* of the reply, not streaming latency.
4. **Verify:** the assistant message in `#chat-messages` references the module either by its path substring (e.g., `orch/daemon`) or its human-readable name substring. A generic refusal like "no information provided" is a FAIL.
5. **Verify:** no SSE error markers (`__ERROR__`) surfaced.
6. **Screenshot:** `ai-dev/active/CR-00009/evidences/post/CR-00009_v3_module_reply.png`.

### V4: Header reverts to "Chat — Architecture" when navigating back to architecture view (AC1 on navigation)

1. From the module view, click whatever control returns to the architecture view (sidebar root, breadcrumb "Architecture" link, or the components-list re-render trigger).
2. Wait for the swap (target will be `#code-components-section` OR `#code-detail-panel` with architecture content) to complete.
3. **Verify:** `#chat-context-label` text is exactly `Chat — Architecture` again. A stale `Chat — <previous-module>` is a FAIL (this is the bug guard for stale `data-module-name`).
4. **Verify:** the composer's `module:<path>` chip has disappeared. A stale chip is a FAIL (bug guard for stale `data-module-path`).
5. **Screenshot:** `ai-dev/active/CR-00009/evidences/post/CR-00009_v4_back_to_architecture.png`.

### V5: POST body includes module_path AND module_name on send (AC7 positive path)

1. Open DevTools Network panel via `playwright-cli` (if supported in the harness) or inspect via `fetch` interception — if DevTools inspection is not available in the CLI, skip this V5 and cover it via V2/V3 indirectly. Record the choice in your report.
2. If inspection is possible: trigger a chat send from a module view and capture the outgoing POST body to `/api/projects/.../code/qa`. **Verify both:**
   - `"module_path": "<expected-path>"` — this also validates the Option-A propagation fixed the pre-existing dead read path (before CR-00009, `module_path` was always empty in the request body even on module views).
   - `"module_name": "<expected-name>"`.
3. **Screenshot:** `ai-dev/active/CR-00009/evidences/post/CR-00009_v5_post_body.png` (if applicable).

### V(n): No Regressions

1. Revisit the chat panel features delivered by CR-00008: slash menu (type `/` in the input, verify the `/explain`, `/findusages`, `/diagram` menu appears), collapse/expand (Cmd+\\ on desktop), mobile drawer open/close (if you can resize the viewport via `playwright-cli`).
2. Verify the composer `module:<path>` chip still appears on module navigation.
3. Verify markdown rendering in the assistant bubble still works (V3's reply should render as markdown if it contains any).
4. Verify no new console errors appeared on any page visited during V1..V5.
5. **Screenshot:** `ai-dev/active/CR-00009/evidences/post/CR-00009_v6_no_regressions.png`.

## Pass Criteria

All V1..V(n) must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a specific reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

V5 is the only V marked optional — if DevTools interception is not available in the harness, skip it and note the reason. Do NOT fail the step on V5 alone.

## Report

After verification, write `ai-dev/active/CR-00009/reports/CR-00009_S16_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V(n).
- The exact `$IW_BROWSER_BASE_URL` used (copy from env).
- Any issues found, with `file:line` references if the agent investigated root cause.
- The module path + name you selected for V2/V3/V4 (so reviewers know which module was exercised).
- A list of screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V(n).

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00009/reports/CR-00009_S16_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00009/reports/CR-00009_S16_BrowserVerification_Report.md
```

Always include `--report` on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "CR-00009",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "Architecture header on first paint", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Module header updates on navigation", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Chat reply references module", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Header reverts on architecture navigation", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "POST body includes module_path and module_name", "status": "pass|fail|skip", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions (CR-00008 surface)", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed (V5 may be `skip`).
- `base_url_used`: The concrete URL the agent actually hit.
- `console_errors_observed`: Any console errors seen during any V(n). A non-empty list on a passing run should be flagged in the report.
