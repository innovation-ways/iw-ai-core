# I-00079 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.) This work touches no Docker state.

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.) This work adds no migrations and changes no database schema.

## Why

When a dashboard list is empty — for example a project's Queue with no work items — the dashboard shows a friendly panel with a button that is meant to open the relevant documentation ("How to design an item →", "How execution works →", "About batches →", and similar on a few other pages). A user reported that clicking that button on the empty Queue page leads to a "Not Found" error page instead of the documentation. The goal is to make every one of those buttons open the correct documentation page.

## What Changed (for the User)

- Clicking the call-to-action button in any empty-state panel now opens the matching documentation page instead of a "Not Found" error.
- This fixes six buttons across the product: the "How to design an item" button on an empty Queue (it appears twice — once for the approved list, once for the drafts list), the "How execution works" button on an empty History page, the "About batches" button on an empty Batches page, the "Daemon overview" button on the empty All Active Work page, and the "Doc catalogue" / "Open the catalogue" buttons on the empty Docs and Research library pages.
- The button now lands on the same documentation page that the page's contextual help popover already links to, so the two ways of reaching that documentation stay consistent.

## How It Behaves

When a list view has nothing to show, the empty-state panel renders as before — a heading, a short explanation, and a primary button. The only difference is where the button points: it now uses the dashboard's documentation viewer address, so the documentation renders normally. For the Queue button the link also jumps straight to the "iw approve" section of the CLI reference, matching the existing help popover. No other behaviour changes — the panels look the same, appear under the same conditions, and the documentation content itself is unchanged. A regression test now follows each of these buttons and fails if any of them ever points at a page that does not exist, so this class of broken link cannot return unnoticed.

## Out of Scope

- No visual redesign of the empty-state panels and no change to when they appear.
- No change to the documentation content, the documentation viewer, or the contextual help popovers themselves.
