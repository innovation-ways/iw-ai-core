# CR-00072 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by automated tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no database change and no migration.

## Why

Every page of the dashboard is served by a route. Today nothing checks that those routes still work as a whole — a route is only tested if someone wrote a test for that one page. The result is that a broken page, a typo in a shared template, or an unhandled error can ship unnoticed and is only discovered when a person opens the affected page in a browser. This work closes that gap by adding an automated check that visits every route and fails the build the moment any of them returns a server error.

## What Changed (for the User)

- A new automated check now sweeps every dashboard route on every change and fails the build if any route returns a server error. Broken pages are caught before a human ever sees them.
- A second, deeper check runs every night. It automatically generates many unusual requests against the data-style endpoints (jobs, runtime overrides, keep-alive) and reports any that crash the server.
- Operators and reviewers get earlier, clearer signals: a regression is named by the exact route that broke, instead of surfacing as a vague "the page is down" report later.
- No visible change to the dashboard itself — this is purely a safety net. Nothing about how pages look or behave changes.

## How It Behaves

- On every work item and every pull request, the route sweep loads the dashboard against a fresh isolated test database seeded with representative sample data, then requests each route in turn. A normal response — including an expected "not found" or "not allowed" — passes. A server error fails the build and names the route.
- Routes that need an identifier in their address (for example, a specific project or work item) are given real identifiers from the seeded sample data so they can be exercised properly.
- A small number of routes that stream data continuously are deliberately skipped, because a plain visit to them would never finish; those are documented and covered by other existing tests.
- If a route is already broken on the current code when this work lands, it is recorded on a short, explicit "known issue" list with a tracking ticket, and the sweep still passes. From then on, the check fails only for *new* breakages. This keeps the safety net honest without forcing unrelated bug fixes into this change.
- The nightly deep check runs on a schedule, not on ordinary changes. During an initial settling-in period it reports problems without blocking anything, so the team can review and triage what it finds before it is ever made strict.

## Out of Scope

- Fixing any route that is found to be already broken — those are tracked separately as their own tickets.
- Making the nightly deep check a hard, build-blocking gate — that is a deliberate later step once the check has proven stable.
