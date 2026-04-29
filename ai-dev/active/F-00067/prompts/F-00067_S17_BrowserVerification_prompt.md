# Browser Verification Prompt: F-00067-S17-BrowserVerification

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step**: S17
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. Do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL**: `$IW_BROWSER_BASE_URL`
**Credentials**: `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step**: `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use `$IW_BROWSER_BASE_URL`.

---

## Prerequisites

Before starting verifications, run:
```bash
playwright-cli kill-all
```

Use `playwright-cli` exclusively for all browser interactions.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — AC1–AC6

## Verifications

### V1: Diagram semantic colors (AC1)

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code`.
2. Wait for the architecture diagram to render (look for `#code-arch-diagram`).
3. **Verify**: The rendered diagram contains colored nodes — at least one node with a fill color other than white/default (check for colored `rect` or `div` elements in the Mermaid output).
4. Take screenshot: `ai-dev/active/F-00067/evidences/post/F-00067_v1_diagram_colors.png`.

### V2: "Why" paragraph above architecture diagram (AC2)

1. Remain on `$IW_BROWSER_BASE_URL/project/iw-ai-core/code`.
2. **Verify**: A `<p>` element with class `text-muted-foreground italic` (or similar) appears immediately before the `#code-arch-diagram` diagram container. The text should be a sentence about what the diagram shows.
3. Take screenshot: `ai-dev/active/F-00067/evidences/post/F-00067_v2_why_paragraph.png`.

### V3: Callout rendering in docs (AC3)

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/docs`.
2. Click on the "Documentation Index" or any doc that contains a `[!NOTE]` or `[!WARNING]` callout (check the code-index doc or any module doc generated after this feature was deployed).
3. **Verify**: At least one element with class `callout callout-note` or `callout callout-warning` is present in the page HTML.
4. **Verify**: The callout has a colored left border and a header with an emoji icon.
5. Take screenshot: `ai-dev/active/F-00067/evidences/post/F-00067_v3_callout_render.png`.

### V4: In-page TOC for long documents (AC4)

1. Navigate to a long document in the docs section (e.g., the code-map architecture doc or any module doc with multiple sections).
2. **Verify**: A `<nav class="doc-toc">` element is present in the page DOM.
3. **Verify**: The TOC contains links (`<a href="#...">`) pointing to section headings.
4. Take screenshot: `ai-dev/active/F-00067/evidences/post/F-00067_v4_toc.png`.

### V5: Index page exists (AC5)

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/docs/code-index` (or find the "Documentation Index" link in the docs library).
2. **Verify**: The page loads with HTTP 200 (no 404).
3. **Verify**: The page content contains `## Architecture` and `## Module Documentation` sections.
4. Take screenshot: `ai-dev/active/F-00067/evidences/post/F-00067_v5_index_page.png`.

### V6: Typographic hierarchy (AC6)

1. Open any document in the docs section.
2. **Verify**: H1 heading has a visible bottom border.
3. **Verify**: H2 heading has a bottom border and is visually distinct from H1 (smaller and lighter weight).
4. **Verify**: H3 heading has a muted/gray color, clearly different from H2.
5. Take screenshot: `ai-dev/active/F-00067/evidences/post/F-00067_v6_typography.png`.

### V7: No Regressions

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/docs` and verify the docs library loads.
2. Open the PDF download link on any doc. A **501 Not Implemented** response is **acceptable and expected** in E2E (WeasyPrint is not installed in the E2E environment). Only a **500 Internal Server Error** is a regression. Do NOT fail V7 for a 501.
3. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code` and verify the code map page loads without JS errors.
4. Open the "Regenerate" button on a module diagram and verify no console errors.
5. **Verify**: No new console errors appeared on any page visited during V1–V6.
6. Take screenshot: `ai-dev/active/F-00067/evidences/post/F-00067_v7_no_regressions.png`.

---

## Pass Criteria

All V1–V7 must pass. Any failure requires calling `iw step-fail` with a reason.

ENV_DATA_MISSING applies if: diagram has no color because no code map has been run in the E2E environment, or no docs with `[!NOTE]` callouts exist in the E2E DB yet. In that case, prefix the reason with `ENV_DATA_MISSING:`.

---

## Report

Write `ai-dev/active/F-00067/reports/F-00067_S17_BrowserVerification_Report.md` with:
- Pass/fail table for V1–V7
- The exact `$IW_BROWSER_BASE_URL` used
- Screenshots list
- No regressions subsection

Then call:
```bash
# On pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00067/reports/F-00067_S17_BrowserVerification_Report.md

# On failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<specific reason>" \
  --report ai-dev/active/F-00067/reports/F-00067_S17_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "qv-browser",
  "work_item": "F-00067",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "Diagram semantic colors", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Why paragraph above diagram", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Callout rendering in docs", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "In-page TOC", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Index page exists", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Typographic hierarchy", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
