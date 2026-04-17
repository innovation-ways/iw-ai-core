# Browser Verification Prompt: CR-00008-S18-BrowserVerification

**Work Item**: CR-00008 -- Code module chat: docked panel, streaming markdown, beautiful diagrams (MVP)
**Step**: S18
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `localhost:5173`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make daemon-start`, `make dashboard-start`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00008/CR-00008_CR_Design.md` -- the design document
- `dashboard/routers/code_qa.py`
- `dashboard/templates/project_code.html`
- `dashboard/templates/chat/panel.html`, `composer.html`, `message.html`, `parts/*.html`
- `dashboard/static/chat/*.js`
- `dashboard/static/chat.css`
- `dashboard/static/vendor/**`

## Output Files

- `ai-dev/active/CR-00008/reports/CR-00008_S18_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00008/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If login is required:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00008/evidences/post/` with descriptive filenames.

## Verification Steps

### V1: Docked right panel visible on the code module page

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code`.
2. Take a snapshot; locate the `<aside>` with id `chat-panel` — this element is the new docked panel replacing the bottom-pinned fragment.
3. **Verify:** the `<aside id="chat-panel">` is visible, has a left-edge drag handle (`id="chat-resize-handle"`), and the reading surface to its left is a separate scroll container.
4. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v1_docked_panel.png`.

### V2: Cmd+\ collapses/expands the panel

1. From V1's page, press `Control+Backslash` via `playwright-cli press ControlOrMeta+Backslash` (use the cross-platform shortcut).
2. **Verify:** the panel wrapper has `data-collapsed="true"` (check via snapshot) and renders as a narrow 48px rail with just an icon.
3. Press the shortcut again.
4. **Verify:** `data-collapsed="false"` and the full panel is restored.
5. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v2_collapse_toggle.png`.

### V3: Slash command menu

1. Click into the composer textarea (`#chat-input`).
2. Type `/ex`.
3. **Verify:** a `#chat-slash-menu` is visible and lists at least an `/explain` item; arrow-down highlights it; Enter inserts the command and produces a chip in `#chat-context-chips`.
4. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v3_slash_menu.png`.

### V4: Send a question; streaming renders without raw markdown flash

1. With the `/explain` chip in place, type `Summarize this module.` and press `Control+Enter`.
2. **Verify:** a user bubble appears; an assistant bubble begins streaming; at no visible moment during streaming does the DOM contain a literal `**` or half-open ` ``` ` — the rendered markdown arrives formatted.
3. Wait for the stream to complete.
4. **Verify:** the assistant message contains at least one rendered code block (from the RAG engine's common responses); the code block has a visible Copy button; the message header shows Copy / Regenerate / 👍 / 👎 buttons.
5. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v4_streaming_render.png`.

### V5: Citations and Sources panel

1. If V4 produced citations inline (look for `[1]` text or `.citation-chip` elements), click one.
2. **Verify:** a popover appears with the cited label and a link to the source; clicking the link navigates to the module view.
3. Go back; expand the `<details>` Sources panel at the end of the assistant message.
4. **Verify:** the panel lists the citations in order.
5. If V4 produced no citations (the engine may yield none depending on the question), mark V5 as N/A with an explicit note and capture a screenshot showing the empty-Sources case is silently hidden.
6. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v5_citations.png`.

### V6: Mermaid diagram upgrade (beautiful rendering)

1. In the composer, type `/diagram` and select it.
2. Type `Render a flowchart showing the main modules of the code base and their dependencies.` Press `Control+Enter`.
3. Wait for the stream to complete.
4. **Verify:** a Mermaid diagram is rendered inside a sandboxed iframe (the iframe has a `sandbox` attribute); the wrapping container has `data-iw-layout="elk"` indicating ELK layout was applied; the color palette matches the brand variables; there are no overlapping edges on a graph of 6+ nodes.
5. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v6_mermaid_elk.png`.

### V7: Mermaid failure chip + retry

1. If feasible, inject an invalid Mermaid response via a test hook OR pre-seed a conversation via a URL param / query if supported. If no such hook exists in the shipped code, this V is validated via the unit test suite (documented in the report); capture a screenshot showing the happy path rendered correctly (from V6) and explicitly note the fallback is unit-test covered.
2. If a hook is available: trigger an invalid Mermaid block; **Verify:** the "Diagram error" chip appears with a Retry button and a collapsible "Show source" revealing the raw DSL.
3. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v7_mermaid_error.png`.

### V8: Image paste chip + 501 stub

1. Focus the composer.
2. Use `playwright-cli evaluate` or a helper fixture to paste a tiny transparent PNG blob (data-URL) via `navigator.clipboard` or by dispatching a synthetic paste event.
3. **Verify:** a thumbnail chip appears above the composer in `#chat-image-chips` with a remove button.
4. Press `Control+Enter`.
5. **Verify:** a toast appears saying "Image attachments coming soon" (or equivalent) and the typed text + image chip remain.
6. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v8_image_chip_501.png`.

### V9: Scroll behavior — stick-to-bottom + release

1. In an assistant message still streaming (repeat V4 with a longer-answer question), scroll the `#chat-messages` container up while streaming.
2. **Verify:** the stream no longer auto-scrolls; `#chat-scroll-to-bottom` is visible.
3. Click it.
4. **Verify:** the view returns to the bottom and stickiness resumes.
5. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v9_scroll_release.png`.

### V10: Accessibility spot-check

1. With DevTools / accessibility tree via `playwright-cli snapshot`, verify on the code module page:
   - The chat panel has `role="region"` with a non-empty `aria-label`.
   - The message list has `role="log" aria-live="polite" aria-relevant="additions"`.
   - Every action button resolves to a real `<button>` with an accessible name.
2. **Verify:** keyboard focus ring is visible when tabbing through composer → Copy → Regenerate → Thumbs buttons.
3. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v10_a11y_focus.png`.

### V11: No regressions

1. Revisit the previous code-module functionality: file tree navigation, module detail view, the Generate Code Map dropdown button.
2. **Verify:** all still work; the drop-down still opens; navigation still works; no JS console errors appeared during V1..V10.
3. **Screenshot:** `ai-dev/active/CR-00008/evidences/post/CR-00008_v11_no_regressions.png`.

## Pass Criteria

All V1..V11 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

V5 and V7 are permitted to be marked N/A **only** when the prerequisite conditions cannot be triggered through the UI; in that case the report must cite the unit-test coverage for the same behavior.

## Report

After verification, write `ai-dev/active/CR-00008/reports/CR-00008_S18_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V11.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V11.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00008/reports/CR-00008_S18_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00008/reports/CR-00008_S18_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S18",
  "agent": "qv-browser",
  "work_item": "CR-00008",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "Docked right panel visible", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Cmd+\\ collapse toggle", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Slash command menu", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Streaming render without markdown flash", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Citations + Sources panel", "status": "pass|fail|na", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Mermaid ELK beautiful rendering", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "Mermaid failure chip + retry", "status": "pass|fail|na", "screenshot": "", "notes": ""},
    {"id": "V8", "name": "Image paste chip + 501 stub", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V9", "name": "Scroll stick-to-bottom release", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V10", "name": "Accessibility spot-check", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V11", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
