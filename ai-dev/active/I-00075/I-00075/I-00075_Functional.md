# I-00075 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This work does not touch any docker container, volume, or network state.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work leaves migrations unchanged — no new revision is generated.

## Why

When CR-00039 reshaped the step pipeline strip into a row of labelled pills, it added a new amber pill that signals "this step had to be retried" — the small `↺` marker following a step that ran fix cycles. The browser verification could not actually look at one of these amber pills because the test database had no items that had ever been retried, so the verification had to be marked "not applicable" and the new visual state shipped without an end-to-end visual check. This work plugs that gap so future browser verifications of retry-related UI can actually see what they are checking.

## What Changed (for the User)

- A reviewer running the dashboard against the test environment can now open at least one example item whose pipeline shows the amber retry markers, exactly as a real retried item would appear in production.
- Anyone authoring a future change that touches retry rendering (or any UI keyed off "this step has been retried N times") has a small, copy-able example that demonstrates how to seed the example data their own browser verification needs.
- Nothing changes for end users on the live dashboard. The visible behaviour of any real production item is identical to before this work.

## How It Behaves

When the orchestrator stands up the test environment for an I-00075 browser verification, it loads a small set of example rows shaped like a finished work item that had to be retried twice on the same step. The dashboard then renders that example exactly the way it would render any real retried item: the retried step appears in the strip with two amber retry markers attached to it, each marker tooltip naming the cycle ("fix cycle 1", "fix cycle 2"). The browser verification compares what is on screen with what the design says should appear and records the screenshot as evidence. Items that were never retried — every other item visible in the test environment — render with no amber markers at all; the example does not change their appearance.

The example is local to this work item and is not visible in any other test run or in production. Each time the test environment is rebuilt the example is recreated cleanly; running the load step a second time on the same database is a no-op.

## Out of Scope

- Updating the design templates (Feature, Change Request, Issue) to add a dedicated "Browser-verification example data" section that systematically reminds future authors to seed historical data when their verification needs it. That broader change is a separate Change Request.
- Backfilling any retry data into the live production database. The example is strictly a test fixture.
