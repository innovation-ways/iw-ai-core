# I-00074_S13_BrowserVerification_prompt

**Work Item**: I-00074 — PDF Export Missing Diagram Labels
**Step**: S13
**Agent**: qv-browser

---

## Environment

```
Base URL:    $IW_BROWSER_BASE_URL
E2E User:    $IW_BROWSER_E2E_USER
E2E Password: $IW_BROWSER_E2E_PASSWORD
Item ID:     $IW_ITEM_ID
Step ID:     $IW_STEP_ID
```

Do NOT hardcode URLs, ports, or credentials. Use the env vars above.

## Prerequisites

1. Run `playwright-cli kill-all` before starting any browser session.
2. The isolated worktree stack is already running — do NOT run `make dev`,
   `docker compose up`, or any install command.
3. Screenshots save to `.playwright-cli/page-<ts>.png` — copy them to target paths
   using `cp .playwright-cli/page-*.png <destination>`.

## Input Files

- `ai-dev/active/I-00074/I-00074_Issue_Design.md` — acceptance criteria

## Output Files

- `ai-dev/active/I-00074/evidences/post/I-00074-S13-pdf-download.png` — screenshot of doc page after PDF download (or error state)
- `ai-dev/active/I-00074/evidences/post/I-00074-S13-no-regressions.png` — screenshot confirming docs list renders correctly
- `ai-dev/work/I-00074/reports/I-00074_S13_browser_verification_report.md` — pass/fail report

---

## V1: PDF Download Does Not Return a Server Error

**Goal**: Verify the PDF download endpoint returns a successful response (not 501/503/500).

1. Kill all browser sessions:
   ```bash
   playwright-cli kill-all
   ```

2. Open the dashboard and navigate to the docs catalog:
   ```bash
   playwright-cli open "$IW_BROWSER_BASE_URL"
   # Navigate to a project that has documents with Mermaid diagrams
   # Look for iw-ai-core or any project with architecture diagrams
   playwright-cli snapshot
   ```

3. Find a document that contains Mermaid diagram code blocks and click into it.
   Take a snapshot to confirm you're on a doc detail page:
   ```bash
   playwright-cli snapshot
   playwright-cli screenshot
   cp .playwright-cli/page-*.png ai-dev/active/I-00074/evidences/post/I-00074-S13-doc-page.png
   ```

4. Click the **Download PDF** button (or look for a PDF link):
   ```bash
   playwright-cli snapshot
   # Find the PDF download link/button reference
   playwright-cli click <ref>
   playwright-cli screenshot
   cp .playwright-cli/page-*.png ai-dev/active/I-00074/evidences/post/I-00074-S13-pdf-download.png
   ```

**Pass criteria**: No error page (not "WeasyPrint not installed", not "500 Internal Server Error",
not "503 unavailable"). The browser either downloads a PDF or shows a PDF inline viewer.

**Note**: You cannot visually inspect the PDF content for labels inside Playwright (PDF is
binary). The functional test (S11/S12 qv-gate) verifies the Chromium path is taken. This
step verifies the route does not error out in the live stack.

---

## V2: No Regressions on Doc Detail Page

**Goal**: Verify the documentation detail page still renders correctly (HTML view, not PDF).

1. Navigate back to the doc detail page (HTML view):
   ```bash
   playwright-cli snapshot
   ```

2. Confirm:
   - The page renders (not blank, not 404)
   - Mermaid diagrams are visible in the HTML view (SVG shapes present)
   - No console error banners in the page content

3. Screenshot the result:
   ```bash
   playwright-cli screenshot
   cp .playwright-cli/page-*.png ai-dev/active/I-00074/evidences/post/I-00074-S13-no-regressions.png
   ```

**Pass criteria**: Doc detail page renders correctly; HTML Mermaid diagrams visible; no error
banners on screen.

---

## Pass Criteria Summary

| Check | Pass Condition |
|-------|----------------|
| V1: PDF download | Returns PDF (no error page / no 501/503/500) |
| V2: No regressions | Doc detail page renders; Mermaid HTML diagrams visible |

## Result Contract

Write the result to `ai-dev/work/I-00074/reports/I-00074_S13_browser_verification_report.md`:

```markdown
# I-00074 S13 Browser Verification Report

## V1: PDF Download
- Status: PASS / FAIL
- Evidence: ai-dev/active/I-00074/evidences/post/I-00074-S13-pdf-download.png
- Notes: <observed behavior>

## V2: No Regressions
- Status: PASS / FAIL
- Evidence: ai-dev/active/I-00074/evidences/post/I-00074-S13-no-regressions.png
- Notes: <observed behavior>

## Overall: PASS / FAIL
```
