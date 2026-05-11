# I-00080 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.) This work touches no Docker state.

## ⛔ Migrations: agents generate, daemon applies

This work adds no migrations and changes no database schema.

## Why

A user generated the "Architecture Diagram" document, then found that opening it from the Docs page took about half a minute to load, the diagram's text labels were white-on-white and unreadable in dark mode, and the HTML and PDF tabs showed nothing. A previous incident was supposed to have fixed dark-mode diagrams, but it only fixed the Code page — the Docs page uses a different, slower rendering path that was never covered. The same problem affects every document on the Docs page that contains a diagram, not just the architecture one. This work makes diagram-bearing documents on the Docs page load quickly and display correctly in both light and dark mode.

## What Changed (for the User)

- Opening a document that contains a diagram on the Docs page is now fast — the diagram is drawn in the browser instead of being re-generated on the server on every visit.
- Diagrams now follow the dashboard theme: in dark mode the diagram and its labels are legible, with no more white-on-white text.
- The HTML and PDF tabs no longer sit blank: the first time you open them the rendered output is saved and reused on later visits, and they update automatically when the document is regenerated to a new version.
- If the system can't produce a PDF (the PDF engine isn't available on that server), the PDF tab now shows a short "PDF unavailable" message instead of an empty panel or an error.
- Diagram documents that were stored as raw diagram text now render as an actual diagram, instead of appearing as a jumble of lines, headings, and code-like text.
- Research documents that contain a diagram now render the diagram too, for consistency with the rest of the dashboard.

## How It Behaves

When you open a document on the Docs page, any diagrams in it are drawn by the browser using the same theme-aware renderer the Code page already uses — so it appears almost immediately and matches whether you're in light or dark mode. The HTML and PDF views are produced once and cached against the document's version; opening them again serves the saved copy, and regenerating the document (which bumps its version) automatically produces a fresh render on the next view. Downloading the PDF works as before. When the server can't generate a PDF at all, you get a clear message rather than a blank screen. A diagram document that holds plain diagram text — the kind produced by the code-mapping tool — is recognised as a diagram and rendered as one.

## Out of Scope

- The one-time wait the first time you open the HTML tab of a never-before-rendered document (it has to build a self-contained HTML file once); it is cached after that.
- The document-generation jobs themselves and the editorial/templating pipeline — unchanged.
- The unrelated "database schema is behind" banner currently shown on the development dashboard.
