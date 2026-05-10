# CR-00044 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This work leaves migrations unchanged.)

## Why

A recent change made every dashboard page's "?" help popover end with an "Open full docs" link that opens a rendered reference document. It works, but the in-app document viewer can only open documents that sit directly in the project's docs folder, so five pages — Code, Item Detail, Projects, Research and Search — all fall back to the same generic Architecture document instead of something page-specific. The Code page is the most noticeable: its link used to be meant for the code-understanding documentation, and now it points at the generic overview. Separately, every page quietly logs one browser error because the site has no classic icon file at its root. This work makes the help links land on the right document and removes that stray error.

## What Changed (for the User)

- The in-app document viewer can now open documents kept in sub-folders of the docs area, plus a small, hand-picked set of module guide files.
- The "Open full docs" link on the Code page now opens the code-understanding guide; the links on the Item Detail, Research and Search pages now open the dashboard guide. The Projects page link keeps pointing at the architecture overview, which is the right document for it.
- Where a document has a stable section heading that matches a page, the help link jumps straight to that section.
- Visiting any dashboard page no longer produces a console error — the site now answers the browser's automatic request for its icon.
- The document viewer's page title now comes from the document's own top heading, so sub-folder documents get a readable title instead of a path-like string.

## How It Behaves

Clicking "Open full docs" in a help popover opens a normal dashboard page that renders the chosen reference document, scrolled to the relevant section when one is specified. Only documents on an explicit, server-side allow-list can be opened this way — anything not on the list, anything that tries to step outside the docs area, and anything that is not a Markdown document is refused with a "not found" response. Requests for the previously working top-level documents keep working exactly as before. The browser's automatic request for the root icon now returns the existing icon image instead of failing.

## Out of Scope

- Moving the page-to-document mapping into a separate configuration file, or changing what happens for a page that has no mapping at all (it still falls back to the architecture overview).
- Writing any new reference documentation or rewriting the help popover text.
