# F-00088 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by automated tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no database change and no migration.

## Why

The dashboard has many pages and interactive flows, but today there is no automated check that exercises them as a whole user journey in a real browser. The existing browser tests are ad-hoc, run against whatever happens to be in the local database, and cover isolated clicks rather than complete end-to-end flows. The result is that a broken project page, a non-rendering export button, or a silent JavaScript failure can ship unnoticed and is only discovered when a person actually uses that flow. This work adds a structured, seeded, journey-level safety net that runs on every pull request and every night.

## What Changed (for the User)

- Six complete user journeys are now automated: navigating the home page and a project's main tabs, creating and running a batch, asking a code question and seeing the answer stream, exporting a document, filtering the jobs list, and exercising the dashboard's interactive page fragments. Each is checked on every pull request.
- Every journey also confirms that no accessibility violations exist on the pages it visits and that the browser reports no errors. Teams get earlier, clearer signals when a page breaks.
- Two of the most critical journeys (navigation and queue-to-merge) form a smoke set that blocks pull requests. The remaining four run nightly without blocking merges, so the team can review results before making them strict.
- No visible change to the dashboard itself — the new journeys are purely a safety net running behind the scenes.

## How It Behaves

- When a pull request is opened, the two smoke journeys run in GitHub Actions against an isolated copy of the dashboard. If either journey fails, the pull request is blocked. The smoke journeys use seeded test data and are designed to be fast and deterministic.
- Every night, all six journeys run against a fresh isolated stack. Results are informational during an initial settling-in period. If a journey fails it reports the exact page and action that broke, so the team knows where to look.
- If a journey discovers that a dashboard page already has a bug on the current code, that journey is marked as a known failure with a tracking ticket — the new safety net does not force unrelated bug fixes. From that point on, the check fails only for new breakages.
- The journeys never touch the live production database. They run against a dedicated isolated database that the automation system brings up and tears down for each verification.

## Out of Scope

- Fixing any dashboard bug the journeys find — those are tracked separately as their own tickets.
- Removing or changing the existing browser smoke tests already in the project — they remain alongside the new layer.
- Making the nightly full-journey run a hard blocking gate — that is a deliberate later step once the journeys have proven stable.
