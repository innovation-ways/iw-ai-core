# I-00064 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item leaves migrations unchanged.)

## Why

A user opening any documentation-generation job from the per-project Jobs
view and clicking "View document" was sent to a 404 page instead of the
documentation. The link was being built with an internal database identifier
that the destination route does not understand, so what should have been a
one-click trip to the document body became a dead end. This was reported
during normal dashboard use and is being fixed because broken navigation
out of the Jobs view is a quality-of-life paper cut for anyone reviewing
documentation activity.

## What Changed (for the User)

- Clicking "View document" on a documentation job now opens the
  corresponding document detail page, with title, content, version
  history, and the regenerate action available — the same page reachable
  from the Documentation catalog.
- If the underlying document has been deleted (orphan job), the
  "View document" link is hidden as before — no broken link is shown.
- No other links, pages, or workflows change. The Documentation catalog,
  the Research view, and the code-map "View code map" link continue to
  behave exactly as they did.

## How It Behaves

When a documentation job runs to completion (or is queued, in progress,
or failed) it stays linked to the document it targets. From the Jobs
view, a viewer can drill into the job and use the inline link to jump
straight to the document — useful for confirming what the agent wrote,
checking the latest version, or kicking off a regenerate. If the
document has been removed since the job ran, the link simply does not
appear, and the rest of the job detail (status, errors, lint warnings,
trigger reason, duration) renders unchanged.

## Out of Scope

- The "View code map" link on code-mapping jobs (it points to the
  project Code page, which already works).
- Any change to the documentation detail page itself, the docs catalog,
  or the routes that serve them.
- Renaming or reshaping the unified Jobs view's column set.
