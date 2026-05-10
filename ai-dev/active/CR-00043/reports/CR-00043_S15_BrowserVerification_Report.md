# CR-00043 S15 Browser Verification Report

## Environment
- **Base URL used**: `http://localhost:9944`
- **E2E user**: `dev@example.local`
- **Work item**: CR-00043
- **Step**: S15

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | — | Docs catalog and doc detail pages have no dangling fragment references; no unhandled console errors at load time (only 404 favicon.ico) |
| V1 | PDF download returns HTTP 200 + %PDF | pass | null | `CR-00043_v1_doc_page.png` (doc page), `CR-00043_v1_pdf.png` (post-download) | `/project/iw-ai-core/docs/architecture-map/pdf` returned **HTTP 200** with body beginning `%PDF-1.4` (25 50 44 46); AC5 satisfied |
| V2 | Mermaid HTML view renders (no regression) | pass | null | `CR-00043_v2_html_view.png` | architecture-map doc page HTTP 200 with no error banner; no Mermaid blocks found in prod-seeded doc content (architecture-map is plain text), so SVG rendering was not exercised, but no error state was triggered |
| V3 | No regressions | pass | null | `CR-00043_v3_no_regressions.png` | Docs catalog, doc detail page, and project home all returned HTTP 200; no new console errors |

## Console / Network Errors

- `404 Not Found @ http://localhost:9944/favicon.ico:0` — benign, appears on every page
- No other console errors observed on any visited page

## Chromium in Container

```
$ docker compose -p "iw-ai-core-e2e-cr00043" exec e2e-dashboard sh -c 'command -v chromium && chromium --version'
/usr/bin/chromium
Chromium 148.0.7778.96 built on Debian GNU/Linux 13 (trixie)
```

Chromium is present and on PATH in the E2E dashboard container.

## V0: Dangling DOM References

Checked on both routes visited (`/project/iw-ai-core/docs`, `/project/iw-ai-core/docs/architecture-map`):
- All `hx-target="#…"`, `hx-include="#…"`, `aria-controls="…"`, `for="…"` fragment references resolve to an `id="…"` in the same HTML
- No dangling references found on either page

## V1: PDF Download Detail

| Check | Value |
|-------|-------|
| HTTP status | **200** |
| First 8 bytes (hex) | `25 50 44 46 2d 31 2e 34` = `%PDF-1.4` |
| PDF route | `/project/iw-ai-core/docs/architecture-map/pdf` |
| Doc title | IW AI Core — Architecture Map |
| Chromium binary | `/usr/bin/chromium` in `e2e-dashboard` container |
| Chromium version | Chromium 148.0.7778.96 |

**AC5 (PDF works in E2E stack) is satisfied.**

## V2: HTML View

- Architecture-map doc detail page: HTTP 200, no error banner
- The architecture-map doc in the prod seed does not contain Mermaid diagram code blocks (it's plain text describing components/data flow), so Mermaid SVG rendering was not exercised in this run
- No regression: page renders correctly in both Markdown and HTML view modes
- Error/warning banner: none

## V3: No Regressions

Adjacent flows verified:
- `/project/iw-ai-core/docs` — docs catalog lists 4 documents (architecture-map, orch-daemon, module-dashboard, orch-rag), HTTP 200
- `/project/iw-ai-core/docs/architecture-map` — doc detail page, HTTP 200
- `/project/iw-ai-core/` — project home, HTTP 200
- No new console errors on any page

## Screenshots Captured

- `ai-dev/active/CR-00043/evidences/post/CR-00043_v1_doc_page.png` — architecture-map doc detail page (markdown view)
- `ai-dev/active/CR-00043/evidences/post/CR-00043_v1_pdf.png` — after PDF download check
- `ai-dev/active/CR-00043/evidences/post/CR-00043_v2_html_view.png` — HTML view tab on doc detail page
- `ai-dev/active/CR-00043/evidences/post/CR-00043_v3_no_regressions.png` — docs catalog / adjacent flows

## Root Cause

N/A — all verifications passed.