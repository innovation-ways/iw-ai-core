# I-00074 — Functional Design

**Type**: Functional Design
**Work Item**: I-00074
**Status**: Approved

---

## Why

When a user exports a documentation page as a PDF, any Mermaid architecture or flow
diagrams in that page appear with empty boxes — all node labels are invisible. Only the
shapes and arrows are present; the text identifying each node is gone. This affects any
document that contains diagrams and makes the exported PDF unusable for sharing or
archiving.

The underlying cause is that the PDF renderer being used (WeasyPrint) does not support a
specific SVG feature that Mermaid relies on to draw text inside diagram nodes. WeasyPrint
silently discards everything inside that feature, leaving blank shapes behind.

## What Changed (for the User)

Before this fix, downloading a PDF from any documentation page with diagrams would
produce a PDF where the diagram nodes were empty boxes with no labels.

After this fix, the PDF download produces a fully rendered diagram with all node labels,
arrows, and connection text visible — matching what the user sees on the HTML page.

The PDF export button and workflow remain unchanged. The user does not need to do
anything differently; the improvement is transparent.

## How It Behaves

When a user clicks the PDF download button on a documentation page, the system now uses
the same browser engine that renders the live page to generate the PDF. This ensures
that all text, diagrams, and formatting that appear on the page are faithfully reproduced
in the downloaded file.

If the PDF generation encounters a problem (for example, in a restricted environment
where the browser engine is unavailable), the user receives a clear error message instead
of a corrupted or empty PDF.

Cached PDFs generated in the past from the old renderer will be regenerated the next time
the user requests a download for a document whose content has been updated.

## Out of Scope

Dark-mode label visibility in the browser (white text on light diagram boxes) was fixed
separately. This fix addresses only the PDF export path.

Documentation pages generated as PDFs by automated background jobs already use a
different rendering path that is unaffected by this change.
