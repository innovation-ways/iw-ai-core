# CR-00086 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds a new migration; the daemon applies it.

## Why

The Innovation Ways AI Core dashboard already presents test and quality results for every managed project. The platform itself is also a managed project, but its own test-health signals — mutation score, coverage trend, flaky-test count, and assertion-baseline size — currently live only as artefact files dropped by the test pipeline. The team opens each file by hand to see how the platform is trending. This change closes the loop: the dashboard becomes the single pane of glass for the platform's own quality story, dogfooding the same view it ships to other projects.

## What Changed (for the User)

- The Tests and Quality pages for the Innovation Ways AI Core project show a new "Test Health" panel under the existing gates summary.
- The panel has four metric cards: mutation score, coverage percentage, flaky-test count, and assertion-baseline size.
- Each card shows the latest captured value, the change versus the previous capture, and a small inline trend line drawn from the last thirty captures.
- A new background job, "test-health-capture", appears in the unified Jobs view each time a capture runs, so users can see when the metrics were last refreshed and whether the refresh succeeded.
- A new automated job runs on every successful push to the main branch and once per night, so the panel stays current without manual action.

## How It Behaves

When a user opens the Tests or Quality page for the platform project, the panel loads after the rest of the page renders. Each metric card looks up its latest captured value and the previous one to compute the change. The trend line is drawn from up to thirty most-recent captures for that metric. If a metric has never been captured, its card shows a neutral "no data yet" message rather than failing.

Captures run unattended. After each main-branch merge, the workflow reads the four artefacts produced by the standard test pipeline, records one snapshot per metric, and reports success to the Jobs view. A nightly run does the same, even on days with no commits, so trends include weekends.

Captures are safe to re-run: two captures within the same minute on identical inputs leave the database with a single row, so retries do not skew the trend.

If the source artefact for a metric is missing on a given run, that metric skips the capture; the others still record. The next successful run resumes where it left off.

## Out of Scope

- Alerting when a metric regresses — a likely follow-up, not in this change.
- Cross-project rollups (one combined panel spanning all managed projects) — scoped to a single project per page.
- Red/amber/green colour banding on metric thresholds — values are shown as-is; the trend line tells the story.
