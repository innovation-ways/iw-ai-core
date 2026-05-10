# CR-00042 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item does not add, modify, or remove any migrations.

## Why

Every dashboard page has a "?" button that opens a help popup explaining what the page does. Each popup ends with an "Open full docs" link intended to take the user to deeper reference material. All 22 of these links are currently broken — clicking them produces a blank error page. The links point to addresses that do not exist on the platform. Because the link text is scattered across 22 separate files, fixing one broken link at a time is impractical and the situation will drift again as documents are renamed.

## What Changed (for the User)

- Clicking "Open full docs" from any help popup now opens a styled, readable page showing the relevant architecture reference document.
- The rendered page includes a back button, proper headings, tables, and code blocks — it is not raw text.
- Links that previously pointed to a specific section of a document (for example, the Queue page links to the section about approving items) still scroll to the correct heading on arrival.

## How It Behaves

When a user clicks "?" on any dashboard page, the help popup appears as before. At the bottom of the popup, the "Open full docs" link now targets a new system route. Clicking it opens the relevant architecture reference in the same tab. The page renders the markdown source with proper formatting and inherits the dashboard's visual theme. Heading anchors work, so deep links scroll directly to the referenced section. If a user manually types an invalid document name into the URL, they receive a standard 404 page — no file content is exposed.

Operators and developers who want to update which document a given help popup links to now make a single edit in one configuration file, rather than searching across 22 template files.

## Out of Scope

- Editing the content of any architecture reference document.
- Adding search, versioning, or edit controls to the rendered doc view — it is read-only.
