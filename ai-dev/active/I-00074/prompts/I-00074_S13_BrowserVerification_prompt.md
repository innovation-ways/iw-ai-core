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

- `ai-dev/active/I-00074/evidences/post/I-00074-S13-doc-page.png` — screenshot of the doc detail page (pre-flight)
- `ai-dev/active/I-00074/evidences/post/I-00074-S13-pdf-download.png` — screenshot of the doc page after clicking PDF (or the graceful-degradation state)
- `ai-dev/active/I-00074/evidences/post/I-00074-S13-no-regressions.png` — screenshot confirming the doc detail page renders correctly
- `ai-dev/work/I-00074/reports/I-00074_S13_browser_verification_report.md` — pass/fail report

---

## ⚠️ Read this before judging V1

This item replaced WeasyPrint with a headless-Chromium PDF renderer
(`dashboard/utils/markdown.py::render_pdf_chromium`). That renderer needs the
Playwright-managed Chromium binary, which is installed **on the host** but is
**not present inside the isolated E2E / per-worktree container** — `Dockerfile.e2e`
still ships only WeasyPrint's native deps and was never given a browser (a
follow-up CR tracks adding Chromium to the E2E image and making the binary path
configurable). So inside this stack the PDF route is *expected* to take its
graceful-degradation branch and return **HTTP 503** with the JSON body
`{"error":"PDF generation unavailable","detail":"Chromium binary not found ..."}`.

That 503 is **the correct, designed behavior here** — NOT a code defect, NOT an
`ENV_DATA_MISSING` blocker. The design doc's "Browser Evidence" section already
records that the rendered-PDF-with-labels assertion is verified on the host /
via the S11–S12 qv-gates, not in this browser step. **Do not** classify this 503
as `ENV_DATA_MISSING` or `CODE_DEFECT`; do not request a fix cycle for it.

A *real* V1 failure is: a `500 Internal Server Error` / a Python traceback page,
a `weasyprint`-related error string anywhere in the response, a blank/hung page,
or any unhandled exception — i.e. the route crashing instead of degrading.

---

## V0: Doc Detail Page Loads Cleanly (pre-flight)

1. `playwright-cli kill-all`
2. `playwright-cli open "$IW_BROWSER_BASE_URL"` — confirm HTTP 200, no load-time console exception.
3. Navigate (via the UI — click links, don't hardcode paths) to a project with
   architecture documents that contain Mermaid diagrams, then into one such doc.
4. Confirm the doc detail page is HTTP 200 with no load-time console exception, then:
   ```bash
   playwright-cli snapshot
   playwright-cli screenshot
   cp .playwright-cli/page-*.png ai-dev/active/I-00074/evidences/post/I-00074-S13-doc-page.png
   ```

**Pass criteria**: Doc detail page reachable via UI navigation; HTTP 200; no
load-time console error/exception.

---

## V1: PDF Download Route Degrades Gracefully (no server crash)

**Goal**: Verify the PDF endpoint either returns a PDF or returns the clean
503 graceful-degradation JSON — never a 500 / traceback / WeasyPrint error.

1. From the doc detail page, find and click the **Download PDF** link/button:
   ```bash
   playwright-cli snapshot
   playwright-cli click <ref-for-Download-PDF>
   ```
2. Inspect the result of the `/pdf` request — use the console log and, if useful,
   `curl -s -o /dev/null -w "%{http_code}" "<base>/project/<proj>/docs/<slug>/pdf"`
   and `curl -s "<base>/.../pdf" | head -c 300` to see the status code and body.
3. Screenshot the resulting state:
   ```bash
   playwright-cli screenshot
   cp .playwright-cli/page-*.png ai-dev/active/I-00074/evidences/post/I-00074-S13-pdf-download.png
   ```

**Pass criteria** — V1 PASSES if **either**:
- the route returns **HTTP 200** and the body starts with the `%PDF` magic bytes
  (Chromium is available — the full happy path), **or**
- the route returns **HTTP 503** with a JSON body containing
  `"PDF generation unavailable"` (Chromium absent in this container — the
  expected graceful-degradation path; see the box above).

**V1 FAILS** only if: HTTP 500 / a Python traceback / `werkzeug`/`weasyprint`
error text / a blank or hung page / any unhandled exception page.

> You cannot visually inspect PDF bytes inside Playwright (binary). The
> labels-rendered-in-PDF assertion is covered by the design doc + S11/S12; this
> step only proves the route doesn't crash in the live stack.

---

## V2: No Regressions on Doc Detail Page

**Goal**: Verify the documentation detail page still renders correctly (HTML view, not PDF).

1. Navigate back to the doc detail page (HTML view) and `playwright-cli snapshot`.
2. Confirm:
   - The page renders (not blank, not 404, not 500)
   - Mermaid diagrams are visible in the HTML view (SVG shapes present) *or* the
     diagram source falls back to a code block — either is acceptable; an error
     banner is not
   - No console error banners in the page content
3. Screenshot:
   ```bash
   playwright-cli screenshot
   cp .playwright-cli/page-*.png ai-dev/active/I-00074/evidences/post/I-00074-S13-no-regressions.png
   ```

**Pass criteria**: Doc detail page renders correctly; no error banners; no 500.

---

## Pass Criteria Summary

| Check | Pass Condition |
|-------|----------------|
| V0: Doc page pre-flight | Doc detail page reachable via UI; HTTP 200; no load-time console exception |
| V1: PDF route | HTTP 200 + `%PDF` body **OR** HTTP 503 + `"PDF generation unavailable"` JSON. FAIL only on 500 / traceback / WeasyPrint error / blank / hang |
| V2: No regressions | Doc detail page renders; no error banners; no 500 |

Overall PASS requires V0, V1, V2 all PASS. If V1's 503-graceful-degradation
branch is taken, that is still a PASS — record it as such and do **not** mark
the step `ENV_DATA_MISSING` or request a fix cycle.

## Result Contract

Write the result to `ai-dev/work/I-00074/reports/I-00074_S13_browser_verification_report.md`:

```markdown
# I-00074 S13 Browser Verification Report

## V0: Doc Detail Page Pre-flight
- Status: PASS / FAIL
- Evidence: ai-dev/active/I-00074/evidences/post/I-00074-S13-doc-page.png
- Notes: <observed behavior>

## V1: PDF Download Route
- Status: PASS / FAIL
- Observed: HTTP <code>; body starts with <…>
- Branch: happy-path-PDF / graceful-degradation-503
- Evidence: ai-dev/active/I-00074/evidences/post/I-00074-S13-pdf-download.png
- Notes: <observed behavior>

## V2: No Regressions
- Status: PASS / FAIL
- Evidence: ai-dev/active/I-00074/evidences/post/I-00074-S13-no-regressions.png
- Notes: <observed behavior>

## Overall: PASS / FAIL
```
