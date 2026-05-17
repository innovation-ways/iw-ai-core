# CR-00059 — Functional Design

## ⛔ Docker is off-limits

Standard policy. The new tooling re-uses the same testcontainer fixtures the regular test suite already uses; no new Docker invocations.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds, modifies, and removes no migrations.

## Why

Today the test suite measures whether code is exercised (coverage) and whether assertions exist at all (the assertion scanner), but it does not measure whether those assertions would actually catch a real bug. A test that asserts `result is not None` would pass even if the production code returned the wrong value. Mutation testing is the only direct way to answer "would our tests fail if the code regressed?" The daemon is the riskiest part of the platform — it is the component that merges work to the main branch — so it is the natural place to learn how expensive this measurement is on our codebase, and what the surviving-mutant queue looks like.

## What Changed (for the User)

Developers and reviewers gain four new on-demand commands for mutation testing of the daemon module: a single-module quick check, a bulk audit across the whole daemon, a results viewer, and a single-mutant inspector. The testing strategy document is rewritten to explain that mutation testing is now installed, what was measured during this change, and where the practice is heading next. The testing enhancement plan is updated with the measurement summary and a new follow-up item for widening scope and turning the measurement into a blocking pull-request gate. None of the existing commands, pull-request gates, or dashboards change behaviour. There is no new dashboard surface; the spike's measurements live in the strategy doc and the changelog.

## How It Behaves

A developer running the single-module command on a daemon source file sees the system temporarily mutate that file's code one change at a time, re-run the matching daemon tests, and report for each mutation whether a test failed (killed — good) or all tests still passed (survived — no test caught that bug). Results are cached for re-display, and any surviving mutation can be inspected to see the exact line and change that went undetected. A bulk audit command runs the same analysis across every daemon source file in sequence — the slow on-demand mode, intended for nightly or weekly runs rather than per-pull-request. During this change, the bulk audit is run once against the daemon; the resulting numbers (mutations generated, killed, time taken, which survived) are recorded as the spike's measurement table. None of this runs automatically as part of the merge gate yet — that flip is deliberately deferred so the threshold can be picked from real data rather than guessed up front.

## Out of Scope

Widening the analysis beyond the daemon to other parts of the platform, and flipping mutation testing into a blocking pull-request gate, are explicitly deferred to a follow-up so the threshold is informed by the measured cost rather than chosen up front. Strengthening individual surviving-mutant test cases is also follow-up work — the surviving list is captured here as the seed of that backlog, not as a fix list for this change.
