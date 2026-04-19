# Browser Verification Prompt: F-00055-S18-BrowserVerification

**Work Item**: F-00055 — Work-item-aware code chat: functional behavior Q&A linked to work-item history
**Step**: S18
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:9900`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT run any of the following — they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make dashboard-start`, `make test-e2e`, `make e2e-up`, or any `docker compose` command — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` — the design document
- `dashboard/routers/code_qa.py`
- `orch/rag/qa.py`, `orch/rag/evidence.py`, `orch/rag/classifier.py`
- `dashboard/static/chat/stream.js`, `render.js`, `composer.js`
- `dashboard/templates/chat/parts/work_item_chip.html`, `work_item_feed.html`, `phase_strip.html`

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S18_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/F-00055/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/F-00055/evidences/post/` with descriptive filenames.

## Verification Steps

The feature requires an indexed project with design-doc content. Use the seeded test project provided by the E2E stack (the orchestrator seeds at least one project with ≥3 work items and their design docs).

### V1: /why slash command triggers work-item-aware pipeline (AC1, AC2, AC6)

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/{{seeded_project_id}}/code`. The `seeded_project_id` is whichever project the E2E stack has indexed; read it from the dashboard home if not known.
2. Focus the chat input; type `/why` then Enter to accept the slash chip, then type a behavior question such as `why does the daemon poll every 60 seconds?` and press Enter to submit.
3. **Verify (AC6)**: a phase-strip element appears above the assistant bubble BEFORE the first answer token arrives, showing at least one of `Looking up related code…`, `Finding related items…`, `Reading design documents…`, `Writing answer…`.
4. **Verify (AC1)**: once streaming begins, inline work-item citation chips (format like `F-NNNNN`, `CR-NNNNN`, or `I-NNNNN` with a type glyph) render within the answer prose.
5. **Verify (AC1)**: after `done`, a `History` section appears below the answer prose containing 1–5 rows, each showing `YYYY-MM-DD · item-id · title · summary`.
6. **Verify (AC2)**: phase events were emitted (inspect the strip's transition sequence).
7. **Screenshot**: `ai-dev/active/F-00055/evidences/post/F-00055_v1_why_slash_happy_path.png`.

### V2: Work-item citation chip links to item detail page (AC10)

1. From the state after V1, click one of the inline work-item citation chips in the answer.
2. **Verify**: a popover opens showing the item's title, a short summary, and an `Open item →` link.
3. Click the `Open item →` link.
4. **Verify**: navigation occurs to `{{IW_BROWSER_BASE_URL}}/project/{{seeded_project_id}}/item/{{work_item_id}}` and the item detail page renders with the matching ID in the heading.
5. **Screenshot**: `ai-dev/active/F-00055/evidences/post/F-00055_v2_chip_to_item_page.png`.

### V3: Feed row link navigates to item detail (AC10)

1. Navigate back to the code page (browser back, then wait for the panel to re-render).
2. Re-submit the same `/why` query; after `done`, click the item-ID link in the History feed's first row.
3. **Verify**: navigation to the same item detail page as V2.
4. **Screenshot**: `ai-dev/active/F-00055/evidences/post/F-00055_v3_feed_row_to_item_page.png`.

### V4: Tone-switch chip re-renders at the other register (AC5)

1. From the completed-answer state, locate the tone-switch chip below the answer (label is either `Show implementation details` or `Show functional summary`).
2. Click the chip.
3. **Verify**: the answer prose is replaced with a re-rendered version; the chip's label flips to the opposite register; phase strip shows a new retrieval cycle OR updates with a "re-rendering" indicator (behavior depends on S07 implementation choice — either is acceptable as long as the new prose clearly reads in the switched register).
4. **Screenshot**: `ai-dev/active/F-00055/evidences/post/F-00055_v4_tone_switch.png`.

### V5: Classifier auto-detection without slash chip (AC3)

1. Start a fresh chat turn (clear input, do NOT add a slash chip).
2. Type a behavior query such as `why does export only support CSV` (or any behavior query appropriate to the seeded project) and submit.
3. **Verify**: phase events fire AND work-item citation chips appear, confirming the classifier auto-routed to the work-item-aware pipeline.
4. **Screenshot**: `ai-dev/active/F-00055/evidences/post/F-00055_v5_classifier_auto_detect.png`.

### V6: Code-only query has no regressions (AC9)

1. Start a fresh chat turn (no slash chip).
2. Submit a structural query such as `show the function signature of parse_id` (use a real symbol name present in the seeded project; if none, use `CodeIndexJob` as a class reference).
3. **Verify**: NO phase strip appears; NO work-item citation chips in the answer; NO History section below; the answer streams as in the legacy code-only flow.
4. **Screenshot**: `ai-dev/active/F-00055/evidences/post/F-00055_v6_code_only_no_regression.png`.

### V7: /findusages with symbol anchors retrieval and shows items (AC7)

1. Start a fresh turn; type `/findusages` then Enter to accept the slash chip; add a symbol name known to the seeded project (e.g., `QAEngine`).
2. Submit.
3. **Verify**: phase events fire; the answer includes both code-context references to the symbol and work-item citation chips for items that introduced or modified the symbol's use sites.
4. **Screenshot**: `ai-dev/active/F-00055/evidences/post/F-00055_v7_findusages.png`.

### V8: No Regressions

1. Revisit the following flows and confirm unchanged behavior:
   - The `/explain` and `/diagram` slash commands still work on a module-scoped page.
   - The sources-panel `<details>` collapse/expand still renders for legacy symbol citations.
   - The chat panel collapse (Cmd+\) and mobile drawer still open/close correctly.
2. Verify no new console errors appeared on any page visited during V1..V7 (open the browser dev tools console from the snapshot).
3. **Screenshot**: `ai-dev/active/F-00055/evidences/post/F-00055_v8_no_regressions.png`.

## Pass Criteria

All V1..V8 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

## Report

After verification, write `ai-dev/active/F-00055/reports/F-00055_S18_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V8.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if you investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V8.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00055/reports/F-00055_S18_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00055/reports/F-00055_S18_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S18",
  "agent": "qv-browser",
  "work_item": "F-00055",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "/why slash command triggers work-item-aware pipeline", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Work-item citation chip links to item detail page", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Feed row link navigates to item detail", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Tone-switch chip re-renders at the other register", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Classifier auto-detection without slash chip", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Code-only query has no regressions", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "/findusages with symbol anchors retrieval and shows items", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V8", "name": "No regressions across adjacent flows", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
