# Browser Verification Prompt: F-00066-S13-BrowserVerification

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step**: S13
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

Allowed exceptions: Testcontainers (pytest), read-only introspection (`docker ps`), `./ai-core.sh` / `make` targets.

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack from this worktree. Do NOT start, stop, or rebuild services.

**Base URL:** `$IW_BROWSER_BASE_URL`
**Credentials:** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Identifiers:** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Use `$IW_BROWSER_BASE_URL` exclusively.

## Input Files

- `ai-dev/active/F-00066/F-00066_Feature_Design.md`
- `dashboard/routers/code_qa.py`
- `dashboard/static/chat/stream.js`
- `dashboard/static/chat/render.js`

## Output Files

- `ai-dev/active/F-00066/reports/F-00066_S13_BrowserVerification_Report.md`
- `ai-dev/active/F-00066/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in:
```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:
1. Call `playwright-cli snapshot` before every `fill`/`click`.
2. Screenshots: `playwright-cli screenshot` (no path), then `cp .playwright-cli/page-*.png ai-dev/active/F-00066/evidences/post/F-00066_v<N>_<name>.png`.

## Binary availability pre-check

Before running verifications, check if `mmdc` is available:

```bash
which mmdc || echo "MMDC_ABSENT"
```

- If `mmdc` is present: run V1 (server-side Mermaid rendering) as normal.
- If `mmdc` is absent: V1 becomes a fallback verification (client-side rendering must still work). Note in the report: "mmdc not installed — server-side rendering disabled; verifying client-side fallback instead."

## E2E DB seed data

The baseline seed provides a project row. The QA chat requires a LanceDB index to be present for the project. If the index doesn't exist, the QA endpoint returns a 422/404 and V1–V3 will fail.

Check:
```bash
ls /path/to/lancedb/store  # check if index exists for the seeded project
```

If the LanceDB index is missing, call `iw step-fail` with `ENV_DATA_MISSING: LanceDB index absent for seeded project — run CodeIndexJob first`.

## Verification Steps

### V1: Mermaid diagram appears inline in QA chat response (AC1, AC2)

1. Navigate to `$IW_BROWSER_BASE_URL/projects/<project-slug>/code`.
2. Open the Code Q&A panel. Snapshot to find the question input.
3. Type a question that should trigger a diagram: `"Show me a flowchart of how the QA pipeline works"`. Submit.
4. Wait for the response to stream. Observe whether a diagram figure appears inline (a rendered SVG image inside a `<figure class="chat-diagram-figure">` element).
5. **If mmdc is available**: **Verify** a `<figure class="chat-diagram-figure">` element is visible in the response, containing an `<img>` with a `data:image/svg+xml;base64,...` src. The `<pre data-lang="mermaid">` must NOT be visible (it should be hidden with `display:none`).
6. **If mmdc is absent** (fallback): **Verify** the Mermaid block is rendered client-side as an SVG by `upgradeAllMermaidBlocks` — no raw DSL text visible, SVG present inside the block.
7. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00066/evidences/post/F-00066_v1_mermaid_inline.png`

### V2: "Download SVG" link present (AC2)

1. (Continue from V1, same response.)
2. **If mmdc is available**: In the `<figcaption>`, verify a "Download SVG" link is present. Snapshot to confirm the link text.
3. **If mmdc is absent**: Skip this verification (no server-rendered figure) — note in report.
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00066/evidences/post/F-00066_v2_download_link.png`

### V3: Client-side fallback when server rendering unavailable (AC3)

1. If mmdc IS available, simulate the fallback case by asking a question and checking that client-side Mermaid blocks that were NOT intercepted (e.g., ask a second question about code that the LLM answers with text only) don't break the UI.
2. Alternatively, if mmdc is absent, this is already the fallback case. Ask the Q&A: `"Draw a class diagram of the project structure"`. Verify the Mermaid block renders client-side.
3. **Verify**: No console errors; the response shows a rendered diagram (or no diagram if the LLM chose not to emit one — check response text).
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00066/evidences/post/F-00066_v3_fallback.png`

### V4: No Regressions

1. Ask a plain text question (no diagram) in the Q&A panel, e.g. `"What is the purpose of the daemon?"`. Verify the response streams correctly with no errors.
2. Navigate to the code modules list, click a module, verify the module detail still loads (no regressions from F-00065 changes).
3. Verify no new console errors appeared on any page during V1–V3.
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00066/evidences/post/F-00066_v4_no_regressions.png`

## Pass Criteria

All V1–V4 must pass. Failure in V1/V2 due to mmdc absence with client-side fallback working is classified as `ENV_DATA_MISSING` (binary not installed), not a code defect.

## Report

Write `ai-dev/active/F-00066/reports/F-00066_S13_BrowserVerification_Report.md` with:
- Pass/fail table for V1–V4
- `mmdc` availability status (present/absent)
- The exact `$IW_BROWSER_BASE_URL` used
- Screenshots list
- **No regressions observed** subsection

Then:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00066/reports/F-00066_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<reason>" \
  --report ai-dev/active/F-00066/reports/F-00066_S13_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "F-00066",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Mermaid diagram inline", "status": "pass|fail", "screenshot": "F-00066_v1_mermaid_inline.png", "notes": ""},
    {"id": "V2", "name": "Download SVG link", "status": "pass|fail", "screenshot": "F-00066_v2_download_link.png", "notes": ""},
    {"id": "V3", "name": "Client-side fallback", "status": "pass|fail", "screenshot": "F-00066_v3_fallback.png", "notes": ""},
    {"id": "V4", "name": "No regressions", "status": "pass|fail", "screenshot": "F-00066_v4_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/F-00066/evidences/post/F-00066_v1_mermaid_inline.png",
    "ai-dev/active/F-00066/evidences/post/F-00066_v2_download_link.png",
    "ai-dev/active/F-00066/evidences/post/F-00066_v3_fallback.png",
    "ai-dev/active/F-00066/evidences/post/F-00066_v4_no_regressions.png"
  ],
  "notes": ""
}
```
