# I-00074 S13 Browser Verification Report

## V0: Doc Detail Page Pre-flight
- **Status**: PASS
- **Evidence**: ai-dev/active/I-00074/evidences/post/I-00074-S13-doc-page.png
- **Notes**: Doc detail page (architecture-map) reachable via UI navigation (Projects → IW AI Core (E2E) → Docs → Architecture Map). HTTP 200. No load-time console errors (only a favicon 404, irrelevant). Page rendered correctly with heading, content, Download PDF button, and tab navigation.

## V1: PDF Download Route
- **Status**: PASS
- **Observed**: HTTP 503; body contains `{"error":"PDF generation unavailable","detail":"Chromium binary not found — check _PLAYWRIGHT_CHROME path"}`
- **Branch**: graceful-degradation-503 (Chromium absent in E2E container — expected per design doc)
- **Evidence**: ai-dev/active/I-00074/evidences/post/I-00074-S13-pdf-download.png
- **Notes**: Clicking "Download PDF" on the doc detail page produced the designed graceful-degradation JSON 503 response (not a 500 traceback, not a WeasyPrint error, not a blank/hung page). This is the correct, documented behavior for the E2E container which lacks the Playwright-managed Chromium binary. The design doc explicitly states this 503 is expected in this stack and is verified on the host via S11–S12 qv-gates.

## V2: No Regressions
- **Status**: PASS
- **Evidence**: ai-dev/active/I-00074/evidences/post/I-00074-S13-no-regressions.png
- **Notes**: Doc detail page still renders correctly after PDF interaction. Page shows heading "IW AI Core — Architecture Map", component list with code refs, section headings, and tab navigation (Markdown selected). No blank page, no 500, no error banners.

## Overall: PASS

All three verifications passed:
- V0: Doc detail page loads cleanly via UI navigation (HTTP 200, no load-time console exception).
- V1: PDF route degrades gracefully (HTTP 503 JSON) without server crash — the expected, designed behavior in this E2E container.
- V2: No regressions on doc detail page after PDF interaction.

Screenshots captured:
- ai-dev/active/I-00074/evidences/post/I-00074-S13-doc-page.png
- ai-dev/active/I-00074/evidences/post/I-00074-S13-pdf-download.png
- ai-dev/active/I-00074/evidences/post/I-00074-S13-no-regressions.png